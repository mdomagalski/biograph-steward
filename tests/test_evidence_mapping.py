"""Invented endpoint records exercise identity boundaries, not biomedical truth."""
from copy import deepcopy
import csv
from io import StringIO
import json
import unittest

from biograph_steward.evidence_mapping import build_mapping_set, serialize_mapping_set


def endpoint(identifier="UniProtKB:P00001", *, role="baseline", endpoint_id=None, **changes):
    value = {"endpoint_id": endpoint_id or role + ":row1:A", "role": role,
             "resource_id": "https://example.org/" + role,
             "resource_version": "INVENTED-RELEASE-1", "record_locator":
                 "urn:sha256:" + ("a" if role == "baseline" else "b") * 64 + "#row=1&side=A",
             "entity_type": "protein", "identity_role": "source_primary",
             "primary_ids": [identifier]}
    value.update(changes)
    return value


def mapping(endpoints):
    return build_mapping_set(endpoints,
        mapping_set_id="https://example.org/maps/INVENTED.sssom.tsv",
        mapping_set_version="INVENTED-1", license_url="https://opensource.org/license/mit/",
        mapping_date="2026-10-27")


class EvidenceMappingTests(unittest.TestCase):
    def test_cross_resource_identifier_equality_preserves_graph_context(self):
        values = [endpoint(), endpoint(role="added")]
        original = deepcopy(values)
        result = mapping(values)
        self.assertEqual(values, original)
        row = result["mappings"][0]
        self.assertEqual(row["subject_id"], row["object_id"])
        self.assertEqual(row["predicate_id"], "owl:sameAs")
        self.assertEqual(row["mapping_justification"], "semapv:LexicalMatching")
        self.assertNotEqual(row["subject_source"], row["object_source"])
        self.assertEqual(row["subject_source_version"], "INVENTED-RELEASE-1")
        self.assertEqual(len(row["see_also"]), 2)
        comment = json.loads(row["comment"])
        self.assertEqual(comment["subject_record_locator"], original[0]["record_locator"])
        self.assertEqual(result["summary"]["matched_endpoints"], 2)
        self.assertFalse(result["summary"]["biological_equivalence_or_evidence_independence_measured"])

    def test_canonical_and_isoform_are_not_collapsed_but_same_isoform_can_match(self):
        values = [endpoint("UniProtKB:P00001"),
                  endpoint("UniProtKB:P00001-2", role="added")]
        self.assertEqual(mapping(values)["mappings"], [])
        values.append(endpoint("UniProtKB:P00001-2", endpoint_id="baseline:isoform"))
        result = mapping(values)
        self.assertEqual([row["subject_id"] for row in result["mappings"]], ["UniProtKB:P00001-2"])
        self.assertEqual([row["endpoint_id"] for row in result["unresolved"]], ["baseline:row1:A"])

    def test_graph_versions_are_not_claimed_as_uniprot_release_versions(self):
        result = mapping([endpoint(resource_version="Pharos-INVENTED-319"),
                          endpoint(role="added", resource_version="IntAct-INVENTED-2026-10-17")])
        row = result["mappings"][0]
        self.assertEqual(row["subject_source_version"], "Pharos-INVENTED-319")
        self.assertEqual(row["object_source_version"], "IntAct-INVENTED-2026-10-17")
        self.assertIn("not the UniProt identifier registry release", result["metadata"]["mapping_set_description"])
        self.assertIn("does not relicense upstream records", result["metadata"]["mapping_set_description"])

    def test_gene_xref_alias_or_evidence_ids_do_not_establish_protein_identity(self):
        identities = ["HGNC:1", "INTACT:EBI-123", "P00001", "uniprotkb:P00001", "UniProtKB:GENE1"]
        for value in identities:
            with self.subTest(value=value):
                result = mapping([endpoint(value), endpoint(value, role="added")])
                self.assertEqual(result["mappings"], [])
                self.assertEqual(len(result["unresolved"]), 2)
        for changes in [{"identity_role": "xref"}, {"entity_type": "gene"}]:
            with self.subTest(changes=changes):
                result = mapping([endpoint(**changes), endpoint(role="added")])
                self.assertEqual(result["mappings"], [])

    def test_ambiguous_primary_ids_are_preserved_without_choosing_supported_one(self):
        for primary in [["UniProtKB:P00001", "UniProtKB:P00002"],
                        ["UniProtKB:P00001", "HGNC:1"]]:
            with self.subTest(primary=primary):
                result = mapping([endpoint(primary_ids=primary), endpoint(role="added")])
                self.assertEqual(result["mappings"], [])
                rejected = next(row for row in result["unresolved"] if row["endpoint_id"].startswith("baseline"))
                self.assertEqual(rejected["reason"], "ambiguous_primary_identifiers")
                self.assertEqual(rejected["endpoint"]["primary_ids"], primary)

    def test_multiple_records_not_merged_or_deduplicated_and_no_added_added_matches(self):
        values = [endpoint(), endpoint(role="added"),
                  endpoint(role="added", endpoint_id="added:row2:A", record_locator="https://example.org/row2")]
        result = mapping(values)
        self.assertEqual(len(result["mappings"]), 2)
        self.assertEqual(len(set(row["mapping_id"] for row in result["mapping_records"])), 2)
        self.assertTrue(all(row["subject_endpoint_id"].startswith("baseline:") for row in result["mapping_records"]))
        self.assertEqual(result, mapping(list(reversed(values))))
        self.assertEqual(mapping(values[1:])["mappings"], [])

    def test_framing_errors_stop_instead_of_creating_partial_mapping_sets(self):
        for change in [{"record_locator": "local/file#row1"}, {"resource_id": "https://"},
                       {"resource_version": ""}, {"role": "other"}, {"record_locator": "urn:test:a|b"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                changed = endpoint(role="added")
                changed.update(change)
                mapping([endpoint(), changed])
        with self.assertRaises(ValueError):
            mapping([endpoint(), endpoint()])

    def test_empty_set_is_explicit_not_registry_wide_unmapped_assertion(self):
        result = mapping([])
        self.assertEqual(result["summary"]["mapping_rows"], 0)
        self.assertEqual(result["unresolved"], [])
        raw = serialize_mapping_set(result).decode("utf-8")
        self.assertIn("mapping_set_id:", raw)
        self.assertNotIn("NoTermFound", raw)

    def test_tsv_quoting_and_curie_map_preserve_urns_and_release_strings(self):
        result = mapping([endpoint(resource_version='INVENTED "graph" release'), endpoint(role="added")])
        raw = serialize_mapping_set(result)
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        text = raw.decode("utf-8")
        metadata, rows = [], []
        for line in text.splitlines():
            (metadata if line.startswith("# ") else rows).append(line)
        fields = list(csv.DictReader(StringIO("\n".join(rows)), delimiter="\t"))
        self.assertEqual(fields[0]["subject_source_version"], 'INVENTED "graph" release')
        self.assertEqual(json.loads(fields[0]["comment"])["subject_endpoint_id"], "baseline:row1:A")
        curie_map = json.loads(metadata[0].split(": ", 1)[1])
        for key, expected in (("subject_source", "https://example.org/baseline"),
                              ("object_source", "https://example.org/added")):
            prefix, local = fields[0][key].split(":", 1)
            self.assertEqual(curie_map[prefix] + local, expected)
        self.assertTrue(all(value.startswith("urn:sha256:") for value in fields[0]["see_also"].split("|")))
        self.assertNotIn("mapping_id\t", text)


if __name__ == "__main__":
    unittest.main()
