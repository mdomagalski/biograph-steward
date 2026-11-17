"""Invented-source controls for the one-family Reactome projection contract."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "reactome_projection", Path(__file__).resolve().parents[1] / "scripts/prepare_reactome_context_graphs.py")
projection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(projection)


def source(uid="P00001", stable="R-HSA-123", label="Invented pathway", pwid=123, **updates):
    row = {"pwid": pwid, "name": label, "type": "Reactome", "sourceID": stable,
           "url": "https://reactome.org/content/detail/" + stable}
    row.update(updates)
    return uid, row, "chunks/00000.json#/targets/0/pathways/0"


def inventory():
    return {"panel_gene_ids": ["gene_a", "gene_b", "gene_c", "gene_gap"],
            "targets": [{"uniprot_id": "UniProtKB:P00001", "panel_gene_ids": ["gene_a", "gene_b"]},
                        {"uniprot_id": "UniProtKB:P00002", "panel_gene_ids": ["gene_a"]},
                        {"uniprot_id": "UniProtKB:P00003", "panel_gene_ids": ["gene_c"]}]}


def candidates():
    return [{"id": str(index), "original_genes": pair, "self_pair": pair[0] == pair[1]}
            for index, pair in enumerate([["gene_a", "gene_b"], ["gene_a", "gene_c"],
                                           ["gene_c", "gene_gap"], ["gene_gap", "gene_gap"]])]


def entities():
    return [{"id": g, "type": "original_gene"} for g in inventory()["panel_gene_ids"]] + [
        {"id": r["uniprot_id"], "type": "reviewed_product_context"} for r in inventory()["targets"]] + [
        {"id": "GO:9000001", "type": "go_term"}]


def baseline():
    return sorted([("gene_a", "interacts", "gene_c"), ("gene_c", "interacts", "gene_a"),
                   ("gene_a", "reviewed_product_context", "UniProtKB:P00001"),
                   ("gene_b", "reviewed_product_context", "UniProtKB:P00001"),
                   ("UniProtKB:P00001", "pharos_cc_annotation", "GO:9000001")])


def relations():
    return [{"id": value} for value in [*projection.BASE_RELATIONS, "go_is_a"]]


class ReactomeQualificationTests(unittest.TestCase):
    def test_exact_listing_preserves_raw_row_hash_locator_and_uncertainty(self):
        record = source()
        before = deepcopy(record)
        result = projection.qualify_memberships([record], {"P00001"})
        self.assertEqual(result["memberships"], [("UniProtKB:P00001", projection.RELATION, "REACT:R-HSA-123")])
        row = result["ledger"][0]
        self.assertEqual(record, before)
        self.assertEqual(row["source_locator"], record[2])
        self.assertEqual(row["source_row"], record[1])
        self.assertEqual(row["source_row_sha256"], projection.digest(record[1]))
        self.assertFalse(row["qualifications"]["direct_binding_assertion"])
        self.assertFalse(row["qualifications"]["biological_validation"])
        self.assertEqual(row["qualifications"]["study_lineage"], "unverified")

    def test_invalid_nonhuman_and_missing_pathway_ids_are_explicitly_excluded(self):
        for stable in ["R-MMU-123", "R-HSA-123.1", "Reactome:123", "R-HSA-0", "", None]:
            with self.subTest(stable=stable):
                record = source(stable="R-HSA-123")
                record[1]["sourceID"] = stable
                result = projection.qualify_memberships([record], {"P00001"})
                self.assertEqual(result["memberships"], [])
                self.assertIn("invalid_or_nonhuman_Reactome_stable_id", result["ledger"][0]["reasons"])

    def test_duplicate_rows_keep_one_membership_and_every_source_disposition(self):
        record = source()
        duplicate = (record[0], deepcopy(record[1]), "chunks/00000.json#/targets/0/pathways/1")
        result = projection.qualify_memberships([record, duplicate], {"P00001"})
        self.assertEqual(result["counts"]["source_distinct_product_pathway_memberships"], 1)
        self.assertEqual(result["counts"]["duplicate_membership_rows"], 1)
        self.assertEqual(len(result["memberships"]), 1)
        self.assertEqual(len(result["ledger"]), 2)
        self.assertEqual(result["ledger"][1]["reasons"], ["duplicate_product_pathway_membership"])

    def test_conflicting_labels_exclude_all_affected_rows_without_guessing(self):
        result = projection.qualify_memberships([source(), source(uid="P00002", label="Conflicting label")],
                                               {"P00001", "P00002"})
        self.assertEqual(result["memberships"], [])
        self.assertEqual(result["counts"]["stable_id_label_conflicts"], 1)
        self.assertTrue(all("conflicting_stable_id_labels" in row["reasons"] for row in result["ledger"]))

    def test_conflicting_local_id_to_stable_ids_excludes_both(self):
        result = projection.qualify_memberships([source(), source(stable="R-HSA-456")], {"P00001"})
        self.assertEqual(result["memberships"], [])
        self.assertEqual(result["counts"]["Pharos_local_id_stable_id_conflicts"], 1)

    def test_unknown_product_and_other_provider_do_not_enter_graph(self):
        result = projection.qualify_memberships([source(uid="P99999"), source(type="KEGG")], {"P00001"})
        self.assertEqual(result["memberships"], [])
        self.assertIn("product_absent_from_frozen_reviewed_vocabulary", result["ledger"][0]["reasons"])
        self.assertEqual(result["ledger"][1]["reasons"], ["outside_selected_Reactome_source"])

    def test_unrecognized_qualifiers_or_blocked_reference_are_not_ignored(self):
        result = projection.qualify_memberships([source(qualifier="NOT"), source(reference="PMID:36949045")],
                                               {"P00001"})
        self.assertEqual(result["memberships"], [])
        self.assertIn("unexpected_source_field_semantics", result["ledger"][0]["reasons"])
        self.assertIn("blocked_reference_in_pathway_row", result["ledger"][1]["reasons"])


class ReactomePairTests(unittest.TestCase):
    def qualified(self):
        return projection.qualify_memberships([source()], {"P00001", "P00002", "P00003"})

    def test_common_ordered_union_and_exact_addition_with_isolated_nodes(self):
        result = projection.graph_pair(baseline(), entities(), relations(), self.qualified())
        self.assertEqual(result["arms"]["rgcn_baseline"], baseline())
        difference = set(result["arms"]["rgcn_reactome"]) - set(result["arms"]["rgcn_baseline"])
        self.assertEqual(difference, set(self.qualified()["memberships"]))
        self.assertEqual(result["relations"], relations() + [{"id": projection.RELATION}])
        ids = [r["id"] for r in result["entities"]]
        self.assertEqual(ids, sorted(ids))
        self.assertIn("gene_gap", ids)
        self.assertFalse(any(r[1] == "go_is_a" for r in result["arms"]["rgcn_reactome"]))
        self.assertFalse(any(r[0].startswith("UniProtKB:") and r[2].startswith("UniProtKB:")
                             for r in result["arms"]["rgcn_reactome"]))

    def test_direct_protein_pairs_or_hierarchy_in_either_arm_are_rejected(self):
        for addition in [("UniProtKB:P00001", "interacts", "UniProtKB:P00003"),
                         ("GO:9000001", "go_is_a", "GO:9000001")]:
            with self.subTest(addition=addition), self.assertRaises(ValueError):
                projection.graph_pair(baseline() + [addition], entities(), relations(), self.qualified())
        for addition in [("UniProtKB:P00001", projection.RELATION, "UniProtKB:P00003"),
                         ("gene_a", "interacts", "gene_c")]:
            qualified = self.qualified()
            qualified["memberships"].append(addition)
            with self.subTest(addition=addition), self.assertRaisesRegex(ValueError, "direct protein-pair"):
                projection.graph_pair(baseline(), entities(), relations(), qualified)

    def test_shared_product_mapping_preserves_gene_identity_and_zero_coverage(self):
        result = projection.candidate_coverage(candidates(), inventory(), self.qualified()["memberships"])
        self.assertEqual([r["coverage_only_score"] for r in result["rows"]], [2, 1, 0, 0])
        self.assertEqual(result["counts"]["all_candidates"], 4)
        self.assertEqual(result["counts"]["panel_genes_with_membership"], 2)
        self.assertEqual(result["rows"][0]["original_genes"], ["gene_a", "gene_b"])
        self.assertEqual(result["rows"][2]["pathways_by_gene"], {"gene_c": [], "gene_gap": []})
        self.assertFalse(result["outcome_values_loaded"])
        self.assertFalse(any("label" in row or "outcome" in row for row in result["rows"]))

    def test_zero_context_keeps_every_nomination_and_tied_zero_scores(self):
        result = projection.candidate_coverage(candidates(), inventory(), [])
        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(result["counts"]["all_candidates_by_endpoint_coverage"], {"0": 4})

    def test_relation_and_vocabulary_conflicts_fail_closed(self):
        with self.assertRaises(ValueError):
            projection.graph_pair(baseline(), entities() + [entities()[0]], relations(), self.qualified())
        with self.assertRaises(ValueError):
            projection.graph_pair(baseline(), entities(), list(reversed(relations())), self.qualified())
        with self.assertRaises(ValueError):
            projection.candidate_coverage(candidates(), inventory(), [("UniProtKB:P00001", "interacts", "P00002")])


class ReactomeSourceBindingTests(unittest.TestCase):
    def test_changed_hash_and_byte_count_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            path = root / "source.json"
            path.write_text('{"invented":true}')
            record = {"path": "source.json", "sha256": projection.sha(path), "bytes": path.stat().st_size}
            self.assertEqual(projection.bound_file(root, record), path)
            path.write_text('{"invented":false}')
            with self.assertRaisesRegex(ValueError, "Source binding changed"):
                projection.bound_file(root, record)
            record["sha256"] = projection.sha(path)
            with self.assertRaisesRegex(ValueError, "Source binding changed"):
                projection.bound_file(root, record)

    def test_symlink_traversal_and_unsafe_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            path = root / "source.json"
            path.write_text("{}")
            (root / "link.json").symlink_to(path)
            for name in ["../source.json", str(path), "link.json"]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    projection.ordinary(root, name)

    def test_selection_record_cannot_be_silently_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            selection = root / projection.SELECTION
            selection.parent.mkdir(parents=True)
            selection.write_text("{}")
            with patch.object(projection, "ROOT", root), self.assertRaisesRegex(ValueError, "intervention record changed"):
                projection.selection_bindings()

    def test_duplicate_json_keys_and_nonunique_triples_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "x.json").write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                projection.load_json(root / "x.json")
            (root / "x.tsv").write_text("subject\tpredicate\tobject\na\tr\tb\na\tr\tb\n")
            with self.assertRaisesRegex(ValueError, "unique and ordered"):
                projection.triples(root / "x.tsv")


if __name__ == "__main__":
    unittest.main()
