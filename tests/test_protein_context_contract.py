"""Independent source-contract examples; all proteins/results are invented.

These checks concern exact sequence applicability, source fidelity and explicit
source reuse. They supply no scientific truth labels and make no network calls.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.graph import build_graph
from biograph_steward.protein_context import (
    inspect_selection, load_publication, selection_contexts,
)
from test_normalization import fixture


from protein_context_fixtures import ContractPacket, SEQUENCE, IPR, native_go


class ProteinContextContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.graph = build_graph(fixture())
        self.edge = next(row for row in self.graph["edges"] if row["record_kind"] == "go_annotation")
        self.protein, self.selection = self.edge["subject"], self.edge["id"]

    def inspect(self, packet, **kwargs):
        return inspect_selection(self.root, self.graph, self.selection, self.protein,
                                 source_run="run", **kwargs)

    def test_exact_sequence_source_versions_fragments_and_sites_survive_without_mutation(self):
        packet = ContractPacket(self.root, self.protein, sequence="  " + SEQUENCE.lower()[:20] + "\n" + SEQUENCE[20:] + "  ")
        before_graph = deepcopy(self.graph)
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch("biograph_steward.client.PharosClient._http", side_effect=AssertionError("No retrieval")):
            result = self.inspect(packet)
        self.assertEqual(result["format"], "biograph-steward.protein-context-selection.v1")
        self.assertEqual(result["protein"], self.protein)
        self.assertEqual([row["native_match"] for row in result["matches"]], packet.matches)
        same_pf = [row for row in result["matches"] if row["signature"]["accession"] == "PF99999"]
        self.assertEqual(len(same_pf), 2)
        self.assertEqual({(row["source"], row["signature"]["signatureLibraryRelease"]["version"]) for row in same_pf},
                         {("Pfam", "39.0"), ("InterPro-N", "37.3")})
        self.assertEqual(same_pf[0]["locations"][0]["location-fragments"], packet.matches[0]["locations"][0]["location-fragments"])
        self.assertNotEqual(same_pf[0]["locations"][0]["location-fragments"], [{"start": 2, "end": 20}])
        self.assertIsNone(same_pf[0]["locations"][0]["sites"])
        self.assertNotIn("sites", same_pf[1]["locations"][0])
        self.assertEqual(result["matches"][2]["locations"][0]["sites"], packet.matches[2]["locations"][0]["sites"])
        self.assertEqual(result["identifier_overlap"]["shared_interpro_ids"], [IPR])
        self.assertEqual(len(result["identifier_overlap"]["shared_member_ids"]), 2)
        self.assertTrue(all(row["record_version_equivalence_established"] is False
                            for row in result["identifier_overlap"]["shared_member_ids"]))
        for displayed in result["matches"]:
            relative, pointer = displayed["source_pointer"].split("#", 1)
            value = json.loads((packet.folder / relative).read_text())
            for token in pointer.removeprefix("/").split("/"):
                value = value[int(token)] if isinstance(value, list) else value[token]
            value = json.loads(value)
            for token in displayed["decoded_text_pointer"].removeprefix("/").split("/"):
                value = value[int(token)] if isinstance(value, list) else value[token]
            self.assertEqual(value, displayed["native_match"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["source_graph_changed"])
        self.assertEqual((result["source_fetches"], result["model_calls"]), (0, 0))
        self.assertEqual(self.graph, before_graph)
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_unknown_hash_known_empty_and_unavailable_sequence_do_not_collapse(self):
        for name, kwargs in (("unknown", {"found": False}), ("empty", {"matches": []}),
                             ("unavailable", {"sequence": None})):
            with self.subTest(state=name):
                root = self.root / name
                root.mkdir()
                packet = ContractPacket(root, self.protein, **kwargs)
                source = load_publication(packet.folder, packet.pin)["proteins"][self.protein]
                if name == "unavailable":
                    self.assertEqual(source["manifest"]["status"], "sequence_unavailable")
                    self.assertIsNone(source["manifest"]["query_md5"])
                    self.assertIsNone(source["result"])
                else:
                    self.assertEqual(source["result"]["found"], name == "empty")
                    self.assertEqual(source["result"]["matches"], [])
                view = inspect_selection(root, self.graph, self.selection, self.protein, source_run="run")
                self.assertEqual(view["precomputed_found"], None if name == "unavailable" else name == "empty")
                self.assertEqual(view["sequence"]["status"], "sequence_unavailable" if name == "unavailable" else "sequence_available")
                self.assertEqual(view["matches"], [])

    def test_same_sequence_does_not_collapse_requested_protein_or_isoform_identity(self):
        from protein_context_fixtures import write_packet
        proteins = [self.protein, self.protein + "-2"]
        packet = write_packet(self.root / "same_sequence", proteins)
        source = load_publication(packet.folder, packet.pin)
        self.assertEqual(list(source["proteins"]), proteins)
        self.assertEqual(source["proteins"][proteins[0]]["manifest"]["query_md5"],
                         source["proteins"][proteins[1]]["manifest"]["query_md5"])
        with self.assertRaises(ValueError):
            inspect_selection(self.root, self.graph, self.selection, proteins[1], source_run="run")

    def test_alias_accession_equality_does_not_use_labels_or_establish_version_reuse(self):
        packet = ContractPacket(self.root, self.protein)
        def labels_are_not_identifiers(value):
            value["response"]["data"]["target"]["interpro"] = [
                {"source": "InterPro", "name": "IPR888888", "value": IPR}]
            value["response_sha256"] = digest(value["response"])
        packet.change_json("pharos/" + packet.accession + ".json", labels_are_not_identifiers)
        result = self.inspect(packet)
        self.assertEqual(result["identifier_overlap"]["shared_interpro_ids"], [])
        self.assertEqual(result["identifier_overlap"]["interpro_ids_not_in_captured_pharos_xrefs"], [IPR])
        self.assertFalse(result["identifier_overlap"]["independent_evidence"])

    def test_semantic_sequence_identity_cannot_be_changed_by_resigning_files(self):
        for field, invalid in (("query_md5", "0" * 32), ("sequence_sha256", "0" * 64),
                               ("sequence_length", len(SEQUENCE) - 1)):
            with self.subTest(field=field):
                root = self.root / field
                root.mkdir()
                packet = ContractPacket(root, self.protein)
                packet.manifest["proteins"][0][field] = invalid
                packet.seal()
                with self.assertRaises(ValueError):
                    load_publication(packet.folder, packet.pin)
        root = self.root / "protein"
        root.mkdir()
        packet = ContractPacket(root, self.protein)
        def change(value):
            value["response"]["data"]["target"]["uniprot"] = "P00001"
            value["response_sha256"] = digest(value["response"])
        packet.change_json("pharos/" + packet.accession + ".json", change)
        with self.assertRaises(ValueError):
            load_publication(packet.folder, packet.pin)

    def test_corrupt_native_body_and_mixed_source_release_are_rejected(self):
        packet = ContractPacket(self.root, self.protein)
        path = packet.folder / "interpro/matches_000.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            load_publication(packet.folder, packet.pin)
        packet.seal()
        packet.change_json("interpro/info_after.json", lambda value: value.update(release="112.0"))
        with self.assertRaises(ValueError):
            load_publication(packet.folder, packet.pin)

    def test_coordinates_must_apply_to_the_bound_sequence_even_after_resigning(self):
        for target in ("location", "fragment", "site"):
            with self.subTest(coordinate=target):
                root = self.root / target
                root.mkdir()
                packet = ContractPacket(root, self.protein)
                def corrupt(payload):
                    rows = payload["results"][0]["matches"]
                    position = (rows[0]["locations"][0] if target == "location" else
                        rows[0]["locations"][0]["location-fragments"][0] if target == "fragment" else
                        rows[2]["locations"][0]["sites"][0]["siteLocations"][0])
                    position["end"] = len(SEQUENCE) + 1
                packet.change_matches(corrupt)
                with self.assertRaises(ValueError):
                    load_publication(packet.folder, packet.pin)
    def test_native_go_groups_not_forms_and_source_row_context_are_not_rewritten(self):
        packet = ContractPacket(self.root, self.protein)
        native = native_go(self.protein, self.edge["object"], self.graph, self.selection)
        before = deepcopy(native)
        result = self.inspect(packet, native_go=native)
        records = result["goa_lineage"]["records"]
        self.assertEqual([row["native_record"] for row in records], native["records"])
        self.assertEqual(native, before)
        groups = records[0]["with_from_groups"]
        self.assertEqual(groups[0]["status"], "partial_group")
        self.assertEqual(groups[0]["additional_required_members"], ["UniProtKB:P00002"])
        self.assertEqual(groups[0]["members"], ["InterPro:" + IPR, "UniProtKB:P00002"])
        self.assertEqual(groups[1]["status"], "unmatched_group")
        self.assertEqual(groups[2]["status"], "complete_group")
        self.assertEqual(groups[2]["additional_required_members"], [])
        self.assertTrue(records[0]["interpro2go_reference_chain"])
        self.assertFalse(records[0]["positive_annotation_inferred"])
        self.assertTrue(records[1]["native_record"]["negated"])
        self.assertEqual(records[1]["native_record"]["gene_product_form_id"], self.protein + "-2")
        self.assertEqual(records[1]["native_record"]["taxon_ids"], ["taxon:9606", "taxon:10090"])
        self.assertFalse(result["goa_lineage"]["reference_independence_established"])
        self.assertFalse(result["goa_lineage"]["historical_record_identity_established"])
        self.assertTrue(all(group["record_identity_or_independence_established"] is False
                            for row in records for group in row["with_from_groups"]))
        changed = deepcopy(native)
        changed["records"][0]["with_from_or_groups_raw"] = [["InterPro:" + IPR]]
        with self.assertRaises(ValueError):
            self.inspect(packet, native_go=changed)
        different_query = native_go(self.protein, "GO:0000002", self.graph, self.selection)
        with self.assertRaises(ValueError):
            self.inspect(packet, native_go=different_query)

    def test_context_offer_remains_exact_to_selected_graph_protein(self):
        ContractPacket(self.root, self.protein)
        offer = selection_contexts(self.root, self.graph, self.selection)
        self.assertTrue(offer["eligible"])
        self.assertEqual([row["protein"] for row in offer["proteins"]], [self.protein])
        with self.assertRaises(ValueError):
            inspect_selection(self.root, self.graph, self.selection, "UniProtKB:P00001", source_run="run")

    def test_native_entry_retirement_and_editorial_flags_are_source_context_only(self):
        packet = ContractPacket(self.root, self.protein)
        current = {"metadata": {"accession": IPR, "is_llm": True,
            "is_reviewed_llm": False, "is_updated_llm": False, "go_terms": None}}
        retired = {"accession": "ipr888888", "source_database": "interpro", "type": "family",
            "name": "INVENTED", "deletion_date": "2022-08-25T00:00:00.000Z",
            "history": {"signatures": {"panther": {"PTHR99999:SF1": "INVENTED"}}}}
        packet.add_entries({IPR: (200, current), "IPR888888": (410, retired)})
        result = self.inspect(packet)
        self.assertEqual([row["native_record"] for row in result["entry_metadata"]], [current, retired])
        self.assertEqual([row["http_status"] for row in result["entry_metadata"]], [200, 410])
        self.assertTrue(all(row["automatic_remapping_performed"] is False and row["independent_evidence"] is False
                            for row in result["entry_metadata"]))
        self.assertEqual(result["identifier_overlap"]["pharos_interpro_ids"], ["IPR888888", IPR])
        self.assertEqual(result["identifier_overlap"]["shared_interpro_ids"], [IPR])
        self.assertNotIn("replacement", result["entry_metadata"][1])

    def test_entry_metadata_unknown_flags_stay_unknown_and_wrong_types_fail(self):
        packet = ContractPacket(self.root, self.protein)
        packet.add_entries({IPR: (200, {"metadata": {"accession": IPR}})})
        self.assertNotIn("is_llm", self.inspect(packet)["entry_metadata"][0]["native_record"]["metadata"])
        bad = {"metadata": {"accession": IPR, "is_llm": "false"}}
        packet.add_entries({IPR: (200, bad)})
        with self.assertRaisesRegex(ValueError, "flag"):
            load_publication(packet.folder, packet.pin)


if __name__ == "__main__":
    unittest.main()
