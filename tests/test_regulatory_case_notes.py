"""Synthetic source observations exercise note bindings, not causal truth.

Fixtures patch only their raw-row digest in the fixed lookup. Production pins
refer to the inspected complete official rows; no research run files are read.
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.inspection import _external_url
from biograph_steward.signor_source import COLUMNS
from biograph_steward import regulatory_case_notes as notes


def fixture(record_id="SIGNOR-277255", *, prefix="extension_sources/signor/"):
    pmid, ordinal, _, case = notes._ROW_PINS[record_id]
    a, b = ("P15056", "P15056") if case.startswith("BRAF") else ("P00533", "P01116")
    egfr_sites = {"SIGNOR-236467": "Tyr1172", "SIGNOR-236471": "Tyr1197", "SIGNOR-236475": "Tyr1016",
        "SIGNOR-236479": "Tyr1092", "SIGNOR-236483": "Tyr1110", "SIGNOR-236487": "Tyr869", "SIGNOR-251093": "Tyr1069"}
    residue = ("Ser614" if case == "BRAF_S614" else "Ser465" if case == "BRAF_P_LOOP" else
        egfr_sites[record_id] if case == "EGFR_COORDINATE_CONVENTION" else "")
    raw = {key: "" for key in COLUMNS}
    raw.update(ENTITYA="invented regulator", TYPEA="protein", IDA=a, DATABASEA="UNIPROT",
        ENTITYB="invented target", TYPEB="protein", IDB=b, DATABASEB="UNIPROT",
        EFFECT="down-regulates activity", MECHANISM="phosphorylation", RESIDUE=residue,
        SEQUENCE="invented", TAX_ID="9606", PMID=pmid, DIRECT="t", ANNOTATOR="invented fixture",
        SENTENCE="Invented source sentence for binding tests.", SIGNOR_ID=record_id)
    if case == "CRC_MCC_UV_CHECKPOINT":
        a, b = "P78527", "P23508"
        raw.update(IDA=a, IDB=b, ENTITYA="PRKDC", ENTITYB="MCC", EFFECT="up-regulates activity",
            RESIDUE="Ser120" if record_id == "SIGNOR-273531" else "Ser118", CELL_DATA="BTO:0001109")
    elif case == "CRC_PIK3CA_AKT_SCOPE":
        a, b = "P42336", "P31749" if record_id == "SIGNOR-235914" else "P31751"
        raw.update(IDA=a, IDB=b, ENTITYA="PIK3CA", ENTITYB="AKT1" if b == "P31749" else "AKT2",
            EFFECT="up-regulates activity", MECHANISM="", RESIDUE="", SEQUENCE="", DIRECT="f",
            CELL_DATA="BTO:0000586" if record_id == "SIGNOR-141814" else "",
            TISSUE_DATA="BTO:0000586" if record_id == "SIGNOR-235914" else "")
    elif case == "CRC_AXIN_APC_SCOPE":
        a, b = "O15169", "P25054"
        raw.update(IDA=a, IDB=b, ENTITYA="AXIN1", ENTITYB="APC", EFFECT="up-regulates activity",
            MECHANISM="binding", RESIDUE="", SEQUENCE="", CELL_DATA="BTO:0000038")
    observation = {"id": "invented-observation", "source_record_id": record_id, "source_row": raw,
        "source_kind": "signor", "source_release": notes.SOURCE_RELEASE,
        "source": {"kind": "signor", "release": notes.SOURCE_RELEASE, "url": notes.SOURCE_URL},
        "source_data_record_ordinal": ordinal, "products": ["UniProtKB:" + a, "UniProtKB:" + b],
        "publications": ["PMID:" + pmid], "source_reported_direct": raw["DIRECT"] == "t", "self_regulation": a == b,
        "source_locators": [{"locator": prefix + "source/Oct2026_release.txt#data-record=" + str(ordinal),
            "file_sha256": notes.SOURCE_SHA256, "role": "original_source_data_record"}]}
    observation.update({field: raw[column] for field, column in notes._PROJECTED_FIELDS.items()})
    return observation, (pmid, ordinal, digest(raw), case)


class RegulatoryCaseNotesTests(unittest.TestCase):
    def check_fixture(self, record_id="SIGNOR-277255", **kwargs):
        observation, pin = fixture(record_id, **kwargs)
        handle = patch.dict(notes._ROW_PINS, {record_id: pin})
        handle.start()
        self.addCleanup(handle.stop)
        return observation

    def test_fixed_scopes_contain_24_rows_14_flags_and_three_examples(self):
        self.assertEqual(len(notes._ROW_PINS), 24)
        self.assertEqual(len(notes._CASES), 14)
        self.assertEqual(set(pin[3] for pin in notes._ROW_PINS.values()), set(notes._CASES))
        self.assertEqual({case for case, item in notes._CASES.items() if item["useful_example"]},
            {"BRAF_S614", "EGFR_CTNNB1_Y142", "CRC_MCC_UV_CHECKPOINT"})
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", pin[2]) for pin in notes._ROW_PINS.values()))

    def test_exact_source_note_is_separate_and_preserves_input(self):
        observation = self.check_fixture()
        before = deepcopy(observation)
        result = notes.case_notes(observation)
        self.assertEqual(observation, before)
        self.assertEqual(result["status"], "examined_with_qualifications")
        self.assertEqual(result["source_binding"]["source_record_id"], "SIGNOR-277255")
        self.assertEqual(result["source_binding"]["raw_source_sha256"], notes.SOURCE_SHA256)
        self.assertFalse(result["human_reviewed"])
        self.assertFalse(result["novel_discovery"])
        self.assertFalse(result["biologically_validated"])
        self.assertEqual(result["audit_kind"], "agent_assisted_literature_check")
        self.assertNotIn("confidence", result)
        self.assertNotIn("prune", result)
        self.assertNotIn("accept", result)
        self.assertEqual(result["notes"][0]["status"], "qualified_example")

    def test_return_values_are_deep_copied_including_nested_sources(self):
        observation = self.check_fixture()
        first = notes.case_notes(observation)
        first["notes"][0]["conditions"].append("changed")
        first["notes"][0]["sources"][0]["url"] = "https://example.org/changed"
        first["notes"][0]["source_binding"]["pmid"] = "999"
        second = notes.case_notes(observation)
        self.assertNotIn("changed", second["notes"][0]["conditions"])
        self.assertNotEqual(second["notes"][0]["sources"][0]["url"], "https://example.org/changed")
        self.assertEqual(second["notes"][0]["source_binding"]["pmid"], "27345148")
        self.assertEqual(observation["source_row"]["PMID"], "27345148")

    def test_changed_source_version_hash_locator_or_identity_is_not_examined(self):
        observation = self.check_fixture()
        mutations = [
            lambda r: r.update(source_release="Nov2026"),
            lambda r: r["source"].update(release="Nov2026"),
            lambda r: r["source"].update(url="https://example.org/unbound"),
            lambda r: r.update(source_kind="other-source"),
            lambda r: r["source_locators"][0].update(file_sha256="0" * 64),
            lambda r: r["source_locators"][0].update(locator="unverified/source/Oct2026_release.txt#data-record=34773"),
            lambda r: r.update(source_data_record_ordinal=34774),
            lambda r: r.update(source_record_id="SIGNOR-999999"),
            lambda r: r["source_locators"].append(deepcopy(r["source_locators"][0])),
        ]
        for mutate in mutations:
            value = deepcopy(observation)
            mutate(value)
            with self.subTest(value=value):
                result = notes.case_notes(value)
                self.assertEqual(result["status"], "not_examined")
                self.assertEqual(result["notes"], [])

    def test_every_raw_field_change_and_projected_literal_change_blocks_notes(self):
        observation = self.check_fixture()
        for column in COLUMNS:
            changed = deepcopy(observation)
            changed["source_row"][column] += " changed"
            with self.subTest(raw_column=column):
                self.assertEqual(notes.case_notes(changed)["status"], "not_examined")
        for field in notes._PROJECTED_FIELDS:
            changed = deepcopy(observation)
            changed[field] += " changed"
            with self.subTest(projected_field=field):
                self.assertEqual(notes.case_notes(changed)["status"], "not_examined")
        for field, value in (("publications", ["PMID:999"]), ("products", list(reversed(observation["products"]))),
                             ("source_reported_direct", False), ("self_regulation", False)):
            changed = deepcopy(observation)
            changed[field] = value
            if changed == observation:  # Reversing a self pair is no mutation.
                changed[field] = ["UniProtKB:P00533", "UniProtKB:P01116"]
            with self.subTest(field=field):
                self.assertEqual(notes.case_notes(changed)["status"], "not_examined")

    def test_unexamined_rows_are_not_automatically_cleared(self):
        for value in (None, {}, {"source_record_id": []}, {"source_record_id": "SIGNOR-999999",
                "publication_metadata": [{"publication_types": ["Journal Article"]}]}):
            result = notes.case_notes(value)
            self.assertEqual(result["status"], "not_examined")
            self.assertEqual(result["notes"], [])
            self.assertFalse(result["human_reviewed"])
            self.assertFalse(result["biologically_validated"])
            self.assertIn("not a clearance", result["interpretation"])

    def test_raw_and_prefixed_original_locators_are_supported(self):
        observation = self.check_fixture(prefix="")
        self.assertEqual(notes.case_notes(observation)["status"], "examined_with_qualifications")
        observation["source_locators"][0]["locator"] = "extension_sources/signor/" + observation["source_locators"][0]["locator"]
        self.assertEqual(notes.case_notes(observation)["status"], "examined_with_qualifications")

    def test_braf_conditions_include_variant_mechanism_and_model_limits(self):
        observation = self.check_fixture("SIGNOR-277498")
        note = notes.case_notes(observation)["notes"][0]
        text = " ".join([note["summary"], *note["conditions"], *note["what_is_not_established"]])
        for expected in ("WT BRAF", "D594G:CRAF", "MEK", "HEK293", "colorectal", "independent"):
            self.assertIn(expected.casefold(), text.casefold())
        self.assertFalse(note["useful_example"])
        s614 = self.check_fixture("SIGNOR-277255")
        detail = notes.case_notes(s614)["notes"][0]
        self.assertIn("S614D", " ".join(detail["conditions"]))
        self.assertTrue(detail["useful_example"])

    def test_known_egfr_mapping_is_separate_from_site_support_and_notice(self):
        observation = self.check_fixture("SIGNOR-236475")
        note = notes.case_notes(observation)["notes"][0]
        self.assertEqual(note["documented_mapping"], "Y992 → Y1016")
        self.assertIn("not full experimental adjudication", note["site_support_scope"])
        self.assertTrue(any("28651473" in item["url"] for item in note["sources"]))
        other = self.check_fixture("SIGNOR-251093")
        other_note = notes.case_notes(other)["notes"][0]
        self.assertEqual(other_note["documented_mapping"], "Y1045 → Y1069")
        self.assertFalse(any("28651473" in item["url"] for item in other_note["sources"]))
        unconfirmed = self.check_fixture("SIGNOR-236467")
        unmatched = notes.case_notes(unconfirmed)["notes"][0]
        self.assertIsNone(unmatched["documented_mapping"])
        self.assertIn("no coordinate is inferred", unmatched["mapping_scope"])

    def test_review_role_requires_exact_inspected_record_not_missing_index_label(self):
        observation = self.check_fixture("SIGNOR-175204")
        observation["publication_metadata"] = [{"publication_types": ["Journal Article"]}]
        note = notes.case_notes(observation)["notes"][0]
        self.assertIn("explicitly describes itself as a review", note["summary"])
        self.assertEqual(note["status"], "secondary_literature")
        observation["source_record_id"] = "SIGNOR-999999"
        self.assertEqual(notes.case_notes(observation)["status"], "not_examined")

    def test_citation_context_flag_requires_review_not_a_false_edge_label(self):
        observation = self.check_fixture("SIGNOR-33633")
        before = deepcopy(observation)
        note = notes.case_notes(observation)["notes"][0]
        self.assertEqual(note["status"], "needs_review")
        self.assertIn("support gap", " ".join(note["what_is_not_established"]))
        self.assertEqual(observation, before)
        self.assertNotIn("truth_label", note)

    def test_crc_scope_is_all_five_selected_records_with_three_citation_groups(self):
        selected = {key: pin for key, pin in notes._ROW_PINS.items() if pin[3].startswith("CRC_")}
        self.assertEqual(set(selected), {"SIGNOR-235914", "SIGNOR-141814", "SIGNOR-273530",
            "SIGNOR-273531", "SIGNOR-60043"})
        self.assertEqual({pin[0] for pin in selected.values()}, {"16293724", "21779472", "9734785"})
        for key in selected:
            observation = self.check_fixture(key)
            before = deepcopy(observation)
            result = notes.case_notes(observation)
            self.assertEqual(result["notes"][0]["audit_scope"], "all_exact_crc_model_context_matches.v1")
            self.assertEqual(observation, before)
            changed = deepcopy(observation)
            changed["source_row"]["CELL_DATA"] = "BTO:0000007"
            changed["cell_context_raw"] = "BTO:0000007"
            self.assertEqual(notes.case_notes(changed)["status"], "not_examined")

    def test_mcc_note_keeps_cell_models_site_uncertainty_and_source_directness(self):
        for key in ("SIGNOR-273530", "SIGNOR-273531"):
            observation = self.check_fixture(key)
            note = notes.case_notes(observation)["notes"][0]
            text = " ".join([note["summary"], *note["conditions"], *note["what_is_not_established"]])
            for phrase in ("UV", "HCT116", "HCT15", "S118A/S120A", "other kinases", "Purified PRKDC", "DIRECT=t"):
                self.assertIn(phrase, text)
            self.assertTrue(note["useful_example"])
            self.assertTrue(observation["source_reported_direct"])
            self.assertFalse(note["biologically_validated"])
            self.assertNotIn("truth_label", note)

    def test_pik3ca_akt_notes_preserve_indirectness_and_isoform_model_limits(self):
        for key in ("SIGNOR-235914", "SIGNOR-141814"):
            observation = self.check_fixture(key)
            note = notes.case_notes(observation)["notes"][0]
            text = " ".join([note["summary"], *note["conditions"], *note["what_is_not_established"]])
            for phrase in ("PIK3CA", "AKT1", "AKT2", "HEK293T", "DLD-1", "indirect", "unconfirmed"):
                self.assertIn(phrase, text)
            self.assertFalse(observation["source_reported_direct"])
            self.assertFalse(note["useful_example"])

    def test_axin_apc_note_discloses_abstract_only_and_distinct_activity_readout(self):
        observation = self.check_fixture("SIGNOR-60043")
        note = notes.case_notes(observation)["notes"][0]
        self.assertEqual(note["status"], "limited_material_inspected")
        self.assertIn("SW480", note["summary"])
        self.assertIn("β-catenin", note["summary"])
        self.assertIn("full text was unavailable", " ".join(note["conditions"]))
        self.assertIn("APC activity", " ".join(note["what_is_not_established"]))

    def test_bto_label_selection_is_exact_versioned_attributed_and_safe(self):
        path = Path(notes.__file__).with_name("regulatory_context_labels.json")
        data = json.loads(path.read_text())
        seal = data.pop("content_sha256")
        self.assertEqual(seal, digest(data))
        self.assertEqual(len(data["labels"]), 35)
        self.assertEqual(data["ontology_version_iri"], "http://purl.obolibrary.org/obo/bto/releases/2021-10-26/bto.owl")
        self.assertEqual(data["license"]["id"], "CC-BY-4.0")
        self.assertIn("BRENDA Tissue Ontology", data["license"]["attribution"])
        self.assertIn("no synonym, subclass", data["matching_policy"])
        expected = {"BTO:0000038": "SW-480 cell", "BTO:0000586": "colonic cancer cell",
            "BTO:0001109": "HCT-116 cell", "BTO:0002882": "32D cell",
            "BTO:0004007": "porcine aortic endothelial cell", "BTO:0004055": "COS cell"}
        for key, label in expected.items():
            self.assertEqual(data["labels"][key]["label"], label)
        self.assertNotIn("BTO:9999999", data["labels"])
        for key, term in data["labels"].items():
            self.assertRegex(key, r"^BTO:[0-9]{7}$")
            self.assertEqual(term["iri"], "http://purl.obolibrary.org/obo/" + key.replace(":", "_"))
            self.assertTrue(term["url"].startswith("https://www.ebi.ac.uk/ols4/api/ontologies/bto/terms?iri="))
            self.assertTrue(_external_url(term["url"]))
            self.assertFalse(term["is_obsolete"])
            self.assertRegex(term["source_raw_sha256"], r"^[a-f0-9]{64}$")
        for key in ("url", "source_url", "license_source_url"):
            self.assertTrue(_external_url(data["license"][key]))

    def test_all_case_sources_have_safe_https_links_and_traceable_sections(self):
        for record_id in notes._ROW_PINS:
            observation = self.check_fixture(record_id)
            result = notes.case_notes(observation)
            self.assertEqual(result["status"], "examined_with_qualifications")
            for note in result["notes"]:
                self.assertEqual(note["audit_kind"], notes.AUDIT_KIND)
                self.assertFalse(note["human_reviewed"])
                self.assertFalse(note["novel_discovery"])
                self.assertTrue(note["conditions"])
                self.assertTrue(note["what_is_not_established"])
                for source in note["sources"]:
                    self.assertTrue(source["url"].startswith("https://"))
                    self.assertTrue(_external_url(source["url"]))
                    self.assertTrue(source["section"].strip())
                    self.assertTrue(source["material"].strip())


if __name__ == "__main__":
    unittest.main()
