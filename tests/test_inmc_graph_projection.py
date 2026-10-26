"""Invented identities test outcome-blind projection and paired graph boundaries."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "prepare_inmc_graphs", Path(__file__).resolve().parents[1] / "scripts/prepare_inmc_graphs.py")
projection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(projection)
HAS_NETWORKX = importlib.util.find_spec("networkx") is not None


def inventory():
    return {"panel_gene_ids": ["gene_a", "gene_b", "gene_c", "gene_d", "gene_gap"],
            "targets": [
                {"uniprot_id": "UniProtKB:P00001", "panel_gene_ids": ["gene_a", "gene_b"]},
                {"uniprot_id": "UniProtKB:P00002", "panel_gene_ids": ["gene_a"]},
                {"uniprot_id": "UniProtKB:P00003", "panel_gene_ids": ["gene_c"]},
                {"uniprot_id": "UniProtKB:P00004", "panel_gene_ids": ["gene_d"]}]}


def training():
    return [("gene_a", "gene_c"), ("gene_b", "gene_c"),
            ("gene_a", "gene_d"), ("gene_b", "gene_d"),
            ("gene_c", "gene_d"), ("gene_gap", "gene_d"),
            ("gene_gap", "gene_gap")]


def ontology():
    ids = ["GO:0005575", "GO:0032991", *(f"GO:900000{i}" for i in range(1, 7))]
    result = {"nodes": [{"id": uid, "lbl": "Invented term " + uid} for uid in ids],
              "edges": [{"sub": a, "pred": predicate, "obj": b} for a, predicate, b in [
                  ("GO:0032991", "is_a", "GO:0005575"),
                  ("GO:9000001", "is_a", "GO:0005575"),
                  ("GO:9000002", "is_a", "GO:9000001"),
                  ("GO:9000003", "is_a", "GO:0032991"),
                  ("GO:9000004", "is_a", "GO:0005575"),
                  ("GO:9000006", "part_of", "GO:0005575")]]}
    next(row for row in result["nodes"] if row["id"] == "GO:9000004")["meta"] = {"deprecated": True}
    return result


def observation(uid="P00001", term="GO:9000002", evidence="IDA", aspect="C"):
    return uid, {"goid": term, "evidence": evidence, "assigned_by": "INVENTED",
                 "type": aspect}, "invented.json#/records/0"


def goa_for(record, **updates):
    uid, raw, _ = record
    fields = ["UniProtKB", uid, "INVENTED", "located_in", raw["goid"],
              "PMID:00000000", raw["evidence"], "", "C", "Invented", "", "protein",
              "taxon:9606", "20000101", "INVENTED", "", "UniProtKB:" + uid]
    row = {"projection_key": list(projection.projection_key(uid, raw["goid"], raw["evidence"], "INVENTED")),
           "raw_fields": fields, "source_line": 1, "negated": False,
           "blocked_reference_present": False, "annotation_extension_present": False,
           "with_from_inventory_ids": [], "extension_inventory_ids": []}
    row.update(updates)
    return row


class ScaffoldProjectionTests(unittest.TestCase):
    def test_transitive_shared_product_component_masks_even_unobserved_pairs(self):
        # A--Q--C--R--D is a masking component, not one biological gene.
        source = {"panel_gene_ids": ["A", "B", "C", "D"], "targets": [
            {"uniprot_id": "UniProtKB:P", "panel_gene_ids": ["A"]},
            {"uniprot_id": "UniProtKB:Q", "panel_gene_ids": ["A", "C"]},
            {"uniprot_id": "UniProtKB:R", "panel_gene_ids": ["C", "D"]},
            {"uniprot_id": "UniProtKB:S", "panel_gene_ids": ["D"]},
            {"uniprot_id": "UniProtKB:T", "panel_gene_ids": ["B"]}]}
        scaffold = [(gene, gene) for gene in source["panel_gene_ids"]]
        result = projection.split_scaffold(scaffold, [{"original_genes": ["A", "B"]}], source)
        self.assertEqual(result["excluded_reserved_pairs"], [])
        self.assertEqual(result["development_pairs"], [])
        self.assertEqual({tuple(pair) for pair in result["product_masks"]},
                         {("P", "T"), ("Q", "T"), ("R", "T"), ("S", "T")})
        self.assertEqual({tuple(pair) for pair in result["masked_gene_pairs"]},
                         {("A", "B"), ("B", "C"), ("B", "D")})
        self.assertEqual(result["all_gene_ids"], ["A", "B", "C", "D"])
        self.assertEqual(result["train_pairs"], [[gene, gene] for gene in source["panel_gene_ids"]])

    def test_reserved_shared_product_equivalents_removed_without_merging_nodes(self):
        candidates = [{"original_genes": ["gene_c", "gene_a"]}]
        original = deepcopy((training(), candidates, inventory()))
        result = projection.split_scaffold(*original, fraction=0.2)
        excluded = {tuple(pair) for pair in result["excluded_reserved_pairs"]}
        self.assertEqual(excluded, {("gene_a", "gene_c"), ("gene_b", "gene_c")})
        self.assertTrue({("P00001", "P00003"), ("P00002", "P00003")} <=
                        {tuple(pair) for pair in result["product_masks"]})
        self.assertEqual(result["all_gene_ids"], sorted(inventory()["panel_gene_ids"]))
        self.assertEqual(result["gene_components_for_masking_only"]["gene_a"],
                         result["gene_components_for_masking_only"]["gene_b"])
        self.assertEqual(original, (training(), candidates, inventory()))

    def test_development_is_grouped_deterministic_and_not_repaired_for_coverage(self):
        first = projection.split_scaffold(training(), [], inventory(), fraction=0.999999)
        second = projection.split_scaffold(list(reversed(training())), [], inventory(), fraction=0.999999)
        self.assertEqual(first, second)
        self.assertEqual(first["train_pairs"], [["gene_gap", "gene_gap"]])
        self.assertEqual(set(first["panel_isolated_after_development"]),
                         {"gene_a", "gene_b", "gene_c", "gene_d"})
        self.assertEqual(first["training_degree"]["gene_a"], 0)
        dev = {tuple(pair) for pair in first["development_pairs"]}
        self.assertTrue({("gene_a", "gene_d"), ("gene_b", "gene_d")} <= dev)
        self.assertIn(["P00001", "P00004"], first["product_masks"])
        self.assertIn(["P00002", "P00004"], first["product_masks"])

    def test_duplicate_or_reverse_training_and_missing_panel_genes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate/reversed"):
            projection.split_scaffold(training() + [("gene_c", "gene_a")], [], inventory())
        with self.assertRaisesRegex(ValueError, "Every original panel gene"):
            projection.split_scaffold(training()[:-2], [], inventory())
        for fraction in [0, 1, -0.1, float("nan")]:
            with self.subTest(fraction=fraction), self.assertRaises(ValueError):
                projection.split_scaffold(training(), [], inventory(), fraction=fraction)

    def test_paired_graphs_share_union_vocabulary_and_exact_hierarchy_intervention(self):
        split = projection.split_scaffold(training(), [{"original_genes": ["gene_a", "gene_c"]}], inventory())
        qualified = {"annotations": [("UniProtKB:P00001", "pharos_cc_annotation", "GO:9000002")],
                     "hierarchy": [("GO:9000002", "go_is_a", "GO:9000001")],
                     "nodes": [{"id": uid, "type": "go_term"} for uid in ["GO:9000002", "GO:9000001"]]}
        result = projection.paired_arms(split, inventory(), qualified)
        self.assertEqual(set(result["arms"]["enriched"]) - set(result["arms"]["baseline"]),
                         set(qualified["hierarchy"]))
        self.assertEqual(result["arms"]["scaffold"], result["supervision"])
        ids = {row["id"] for row in result["entities"]}
        self.assertTrue({"gene_gap", "gene_a", "gene_b", "UniProtKB:P00002", "GO:9000001"} <= ids)
        self.assertEqual(len(result["product_links"]), 5)
        for triples in result["arms"].values():
            self.assertNotIn(("gene_a", "interacts", "gene_c"), triples)
            self.assertNotIn(("gene_c", "interacts", "gene_a"), triples)
            self.assertNotIn(("gene_b", "interacts", "gene_c"), triples)
            self.assertTrue(all(a in ids and b in ids for a, _, b in triples))


@unittest.skipUnless(HAS_NETWORKX, "optional graph preparation requires NetworkX")
class GOProjectionTests(unittest.TestCase):
    def qualify(self, records, goa_rows=(), masks=(), source=None):
        return projection.qualify_go(records, goa_rows, source or ontology(), masks)

    def test_positive_relation_is_never_inferred_from_unqualified_pharos_listing(self):
        source = observation()
        current = goa_for(source)
        before = deepcopy((source, current))
        result = self.qualify([source], [current])
        self.assertEqual(result["summary"]["retained_annotation_pairs"], 1)
        entry = result["records"][0]
        self.assertEqual(entry["polarity"], "unknown")
        self.assertFalse(entry["biological_validation"])
        self.assertFalse(entry["historical_row_identity_established"])
        self.assertEqual(result["annotations"], [("UniProtKB:P00001", "pharos_cc_annotation", "GO:9000002")])
        self.assertEqual(result["hierarchy"], [("GO:9000001", "go_is_a", "GO:0005575"),
                                               ("GO:9000002", "go_is_a", "GO:9000001")])
        self.assertEqual((source, current), before)

    def test_negation_and_other_compatible_current_records_trigger_shared_exclusion(self):
        source = observation()
        for reason, transform in [
            ("current_goa_possible_negation", lambda row: row.update(negated=True)),
            ("current_goa_blocked_reference", lambda row: row.update(blocked_reference_present=True)),
            ("current_goa_context_extension_unresolved", lambda row: row.update(annotation_extension_present=True)),
            ("current_goa_distinct_product_form", lambda row: row["raw_fields"].__setitem__(16, "UniProtKB:P00001-2")),
            ("current_goa_IDA_with_from_incompatible", lambda row: row["raw_fields"].__setitem__(7, "UniProtKB:P00004"))]:
            with self.subTest(reason=reason):
                row = goa_for(source); transform(row)
                result = self.qualify([source], [row])
                self.assertEqual(result["annotations"], [])
                self.assertEqual(result["summary"]["prequalification_pairs"], 1)
                self.assertIn(reason, result["records"][0]["reasons"])
                self.assertEqual(result["records"][0]["polarity"], "unknown")
                self.assertFalse(result["records"][0]["biological_validation"])

    def test_reverse_or_self_product_pair_exposure_is_excluded(self):
        source = observation(evidence="HDA")
        for partner in ["P00004", "P00001"]:
            row = goa_for(source, with_from_inventory_ids=["UniProtKB:" + partner],
                          extension_inventory_ids=["UniProtKB:" + partner])
            result = self.qualify([source], [row], masks=[(partner, "P00001")])
            reasons = result["records"][0]["reasons"]
            self.assertIn("current_goa_masked_pair_with_from", reasons)
            self.assertIn("current_goa_masked_pair_extension", reasons)
            self.assertFalse(result["annotations"])

    def test_complex_obsolete_unknown_and_outside_scope_rows_preserved_but_excluded(self):
        records = [observation(term=term) for term in ["GO:9000003", "GO:9000004", "GO:9000005", "GO:9000006", "GO:9999999"]]
        records += [observation(evidence="IPI"), observation(aspect="F")]
        result = self.qualify(records)
        self.assertEqual(len(result["records"]), len(records))
        self.assertFalse(result["annotations"])
        reasons = {reason for row in result["records"] for reason in row["reasons"]}
        self.assertTrue({"protein_complex_subtree", "obsolete_GO_term", "unknown_GO_term",
                         "not_in_cellular_component_is_a_branch", "outside_IDA_HDA_scope",
                         "outside_cellular_component_scope"} <= reasons)

    def test_matching_projection_key_is_required_before_using_current_goa_warning(self):
        source = observation()
        unrelated = goa_for(observation(uid="P00004"), negated=True)
        result = self.qualify([source], [unrelated])
        self.assertEqual(result["summary"]["retained_without_current_goa_match"], 1)
        self.assertEqual(result["summary"]["retained_annotation_pairs"], 1)

    def test_original_blocked_reference_and_obsolete_ancestor_cannot_enter_features(self):
        source = observation(); source[1]["reference"] = "PMID:36949045"
        result = self.qualify([source])
        self.assertIn("blocked_reference_in_pharos_row", result["records"][0]["reasons"])
        changed = ontology()
        next(row for row in changed["nodes"] if row["id"] == "GO:9000001")["meta"] = {"deprecated": True}
        with self.assertRaisesRegex(ValueError, "obsolete ancestor"):
            self.qualify([observation()], source=changed)

    def test_ontology_cycles_missing_endpoints_and_non_go_identifiers_fail(self):
        for kind in ["cycle", "missing", "non_go"]:
            changed = ontology()
            if kind == "cycle":
                changed["edges"].append({"sub": "GO:0005575", "pred": "is_a", "obj": "GO:9000001"})
            elif kind == "missing":
                changed["edges"].append({"sub": "GO:9000001", "pred": "is_a", "obj": "GO:9999999"})
            else:
                changed["nodes"].append({"id": "CHEBI:1234", "type": "CLASS"})
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.qualify([observation()], source=changed)

    def test_obo_property_nodes_are_not_mistaken_for_go_classes(self):
        changed = ontology()
        changed["nodes"].append({"id": "http://purl.obolibrary.org/obo/BFO_0000050",
                                 "type": "PROPERTY", "lbl": "part of"})
        result = self.qualify([observation()], source=changed)
        self.assertEqual(result["summary"]["retained_annotation_pairs"], 1)
        self.assertTrue(all(row["id"].startswith("GO:") for row in result["nodes"]))


if __name__ == "__main__":
    unittest.main()
