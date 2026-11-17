"""Synthetic native-identifier and source-version controls, not truth labels."""
from copy import deepcopy
import unittest

from tools.pathway_history.models import archive_member_id, assess_subject, inspect_fields, inspect_model, GPML
from test_cohort_mapping import gene, protein, registry


def model_xml(*, database="Entrez Gene", identifier="1", node_type="GeneProduct",
              organism="Homo sapiens", version="20110318", extras=""):
    return (f'<Pathway xmlns="{GPML}" Name="Invented software fixture" Organism="{organism}" Version="{version}">'
            f'<DataNode GraphId="node1" GroupRef="group1" TextLabel="IGNORED LABEL" Type="{node_type}">'
            f'<Xref Database="{database}" ID="{identifier}"/></DataNode>{extras}</Pathway>').encode()


def inspected(raw, **kwargs):
    return inspect_model(raw, full_source_id="WP1_r99", archive_member="Hs_Invented_WP1_99.gpml",
                         validate=lambda raw: {"executed": True, "passed": True, "synthetic_mock": True}, **kwargs)


class HistoricalModelTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry([gene("HGNC:1", "INVENTED", products="P04637")],
                                 [protein("P04637", "HGNC:1", "INVENTED")])

    def test_native_archive_revision_is_separate_from_optional_genmapp_version(self):
        for author_version in ["20110318", "WP999_r888", "Version one"]:
            with self.subTest(author_version=author_version):
                model = inspected(model_xml(version=author_version))
                self.assertTrue(model["exact_publisher_revision_binding"])
                self.assertEqual(model["publisher_member_full_source_id"], "WP1_r99")
                self.assertEqual(model["xml_author_version"], author_version)
                self.assertFalse(model["xml_version_is_wiki_revision_asserted"])
                self.assertFalse(model["xml_author_version_equals_full_source_id"])
        raw = model_xml().replace(b' Version="20110318"', b'')
        self.assertIsNone(inspected(raw)["xml_author_version"])

    def test_member_identification_never_uses_dates_current_redirects_or_fuzzy_ids(self):
        self.assertEqual(archive_member_id("Hs_A_name_WP123_456.gpml"), "WP123_r456")
        self.assertEqual(archive_member_id("folder/Hs_A_name_WP123_456.gpml"), "WP123_r456")
        for value in [None, "WP123.gpml", "WP123_r456.gpml", "Hs_A_WP0123_456.gpml",
                      "Hs_A_WP123_0.gpml", "/Hs_A_WP123_456.gpml", "../Hs_A_WP123_456.gpml",
                      "folder/../Hs_A_WP123_456.gpml", "Hs_A_WP123_456.gpml\n"]:
            with self.subTest(value=value):
                self.assertIsNone(archive_member_id(value))
        # Modern publisher files end in a last-edit date, not a MediaWiki id.
        self.assertIsNone(archive_member_id("Hs_A_WP123_20251203.gpml"))
        with self.assertRaisesRegex(ValueError, "not the exact requested"):
            inspect_model(model_xml(), full_source_id="WP1_r98", archive_member="Hs_A_WP1_99.gpml")

    def test_exact_protein_reference_and_gene_compatibility_are_separate(self):
        direct = assess_subject("UniProtKB:P04637", inspected(model_xml(database="Uniprot-TrEMBL", identifier="P04637")), self.registry)
        gene_level = assess_subject("UniProtKB:P04637", inspected(model_xml()), self.registry)
        self.assertEqual(direct["status"], "explicitly_encoded_protein_xref")
        self.assertEqual(gene_level["status"], "compatible_gene_level_xref")
        self.assertFalse(gene_level["gene_bridge"]["historical_registry_identity_established"])
        self.assertTrue(all(not x["protein_form_or_construct_equivalence_established"]
                            for x in direct["exact_protein_matches"] + gene_level["compatible_gene_matches"]))

    def test_declared_hgnc_symbol_namespace_is_not_hgnc_accession_namespace(self):
        for database, identifier in [("HGNC", "INVENTED"), ("HGNC Accession number", "1"),
                                     ("HGNC Accession number", "HGNC:1")]:
            with self.subTest(database=database, identifier=identifier):
                result = assess_subject("UniProtKB:P04637", inspected(model_xml(database=database, identifier=identifier)), self.registry)
                self.assertEqual(result["status"], "compatible_gene_level_xref")
        for database, identifier in [("HGNC", "HGNC:1"), ("HGNC Accession number", "INVENTED"),
                                     ("GenBank", "INVENTED-HGNC:1")]:
            with self.subTest(database=database, identifier=identifier):
                self.assertEqual(assess_subject("UniProtKB:P04637", inspected(model_xml(database=database, identifier=identifier)), self.registry)["status"], "unresolved")

    def test_names_wrong_namespaces_and_isoforms_do_not_force_identity(self):
        for database, identifier in [("GenBank", "INVENTED-HGNC:1"), ("Unknown", "P04637"),
                                     ("Uniprot-TrEMBL", "P04637-2"), ("Entrez Gene", "999")]:
            with self.subTest(database=database, identifier=identifier):
                result = assess_subject("UniProtKB:P04637", inspected(model_xml(database=database, identifier=identifier)), self.registry)
                self.assertEqual(result["status"], "unresolved")
                self.assertFalse(result["absence_is_biological_negative"])
        isoform = inspected(model_xml(database="Uniprot-TrEMBL", identifier="P04637-2", node_type="Protein"))
        self.assertEqual(assess_subject("UniProtKB:P04637-2", isoform, self.registry)["status"], "explicitly_encoded_protein_xref")

    def test_groups_modifications_and_linked_pathways_stay_literal(self):
        extras = ('<Group GroupId="group1" Style="Complex" TextLabel="Invented group"/>'
                  '<State GraphRef="node1" TextLabel="p" StateType="Phosphorylated"/>'
                  '<DataNode GraphId="sub" Type="Pathway" TextLabel="Linked"><Xref Database="WikiPathways" ID="WP2"/></DataNode>')
        model = inspected(model_xml(extras=extras))
        node = model["data_nodes"][0]
        self.assertEqual(node["referenced_group_records"][0]["attributes"]["Style"], "Complex")
        self.assertEqual(node["attached_state_records"][0]["attributes"]["StateType"], "Phosphorylated")
        result = assess_subject("UniProtKB:P04637", model, self.registry)
        self.assertEqual(result["status"], "compatible_gene_level_xref")
        self.assertIn("groups_preserved_without_complex_or_family_expansion", result["unresolved_context"])
        self.assertFalse(result["direct_binding_or_causal_relation_inferred"])
        self.assertFalse(model["group_or_pathway_expansion_performed"])

    def test_nonprotein_entities_organism_and_unrun_schema_remain_unresolved(self):
        rna = inspected(model_xml(node_type="Rna"))
        result = assess_subject("UniProtKB:P04637", rna, self.registry)
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(len(result["other_entity_diagnostics"]), 1)
        self.assertFalse(result["absence_is_biological_negative"])
        nonhuman = inspected(model_xml(organism="Mus musculus"))
        self.assertEqual(assess_subject("UniProtKB:P04637", nonhuman, self.registry)["status"], "unresolved")
        no_schema = inspect_model(model_xml(), full_source_id="WP1_r99", archive_member="Hs_A_WP1_99.gpml")
        self.assertEqual(assess_subject("UniProtKB:P04637", no_schema, self.registry)["status"], "unresolved")

    def test_same_content_under_different_publisher_revisions_remains_distinct(self):
        first = inspected(model_xml())
        other = inspect_model(model_xml(), full_source_id="WP1_r100", archive_member="Hs_A_WP1_100.gpml")
        self.assertEqual(first["gpml_sha256"], other["gpml_sha256"])
        self.assertNotEqual(first["full_source_id"], other["full_source_id"])

    def test_current_native_fields_do_not_manufacture_revision_binding(self):
        fields = inspect_fields(model_xml(version="WP123_r99"))
        self.assertNotIn("exact_publisher_revision_binding", fields)
        self.assertEqual(fields["xml_author_version"], "WP123_r99")
        self.assertFalse(fields["xml_version_is_wiki_revision_asserted"])

    def test_producer_schema_receipt_is_byte_bound_and_never_reexecuted(self):
        raw = model_xml(); original = inspected(raw)
        receipt = {**original["author_schema_validation"], "gpml_sha256": original["gpml_sha256"]}
        replay = inspect_model(raw, full_source_id="WP1_r99", archive_member="Hs_A_WP1_99.gpml", validation_receipt=receipt)
        self.assertFalse(replay["author_schema_validation"]["executed"])
        self.assertFalse(replay["author_schema_validation"]["reexecuted"])
        self.assertEqual(assess_subject("UniProtKB:P04637", replay, self.registry)["status"], "compatible_gene_level_xref")
        with self.assertRaisesRegex(ValueError, "does not bind"):
            inspect_fields(raw + b" ", validation_receipt=receipt)
        with self.assertRaisesRegex(ValueError, "not both"):
            inspect_fields(raw, validation_receipt=receipt, validate=lambda _: {})

    def test_native_publications_preserve_whole_model_and_element_links_separately(self):
        raw = model_xml().replace(b'</DataNode>', b'<BiopaxRef>nodeCitation</BiopaxRef></DataNode>')
        extras = ('<BiopaxRef>modelCitation</BiopaxRef><Biopax xmlns:bp="http://www.biopax.org/release/biopax-level3.owl#" '
                  'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                  '<bp:PublicationXref rdf:id="modelCitation"><bp:DB>PubMed</bp:DB><bp:ID>111</bp:ID></bp:PublicationXref>'
                  '<bp:PublicationXref rdf:id="nodeCitation"><bp:DB>PubMed</bp:DB><bp:ID>222</bp:ID></bp:PublicationXref>'
                  '</Biopax>')
        raw = raw.replace(b'</Pathway>', extras.encode() + b'</Pathway>')
        fields = inspect_fields(raw)
        self.assertEqual(len(fields["publication_records"]), 2)
        whole, node = fields["publication_records"]
        self.assertEqual(whole["native_exact_reference_links"][0]["scope"], "whole_model")
        self.assertEqual(node["native_exact_reference_links"][0]["scope"], "native_element_attached")
        self.assertEqual(node["native_exact_reference_links"][0]["owner_attributes"]["GraphId"], "node1")
        self.assertFalse(fields["publication_support_for_membership_inferred"])
        self.assertFalse(whole["supports_all_members_asserted"])


if __name__ == "__main__":
    unittest.main()
