"""Invented XML packages/identities only; no study workbook is opened."""
from copy import deepcopy
from html import escape
import io
import json
import unittest
import zipfile

from measurement_adapter import (AdapterError, inspect_descriptor_rows, inspect_workbook_headers,
    qualify_protein_record, qualify_record, read_measurements)
from test_source_identity import fixture


def cell(address, text=None, typ="inlineStr", formula=None):
    if typ == "inlineStr":
        payload = "<is><t>" + escape(text or "") + "</t></is>"
    else:
        payload = "" if text is None else "<v>" + escape(str(text)) + "</v>"
    if formula is not None:
        payload += "<f>" + escape(formula) + "</f>"
    return f'<c r="{address}" t="{typ}">{payload}</c>'


def package(headers, rows, *, sheet="Measurements", state="visible", hidden_first=True,
            shared_strings=None, external=False):
    """Minimal in-memory XML parser fixtures, not authored user workbooks."""
    letters = lambda i: chr(65 + i)
    header = '<row r="1">' + ''.join(cell(letters(i) + "1", h) for i, h in enumerate(headers)) + '</row>'
    payload = '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + header + ''.join(rows) + '</sheetData></worksheet>'
    first = '<sheet name="Hidden wrong table" state="hidden" sheetId="1" r:id="r0"/>' if hidden_first else ''
    wb = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + first + f'<sheet name="{sheet}" state="{state}" sheetId="2" r:id="r1"/></sheets></workbook>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r0" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/hidden.xml"/><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/visible.xml"/></Relationships>'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/visible.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/hidden.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
        archive.writestr("xl/workbook.xml", wb); archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/hidden.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:A2"/><sheetData><row r="1">'+cell('A1','WRONG HIDDEN TABLE')+'</row></sheetData></worksheet>')
        archive.writestr("xl/worksheets/visible.xml", payload)
        archive.writestr("xl/sharedStrings.xml", shared_strings if shared_strings is not None else '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
        if external:
            archive.writestr("xl/externalLinks/externalLink1.xml", b'')
    return stream.getvalue()


def contract():
    return {"sheet_name": "Measurements", "headers": ["Protein", "Peptide", "Mods", "Positions", "Site", "Signal", "Signal"],
        "fields": {"accession": 0, "peptide": 1, "modification_names": 2, "modification_positions": 3, "protein_site": 4},
        "quant_columns": [{"index": 5, "sample_id": "replicate_1", "unit": "source-intensity"},
                          {"index": 6, "sample_id": "replicate_2", "unit": "source-intensity"}],
        "accession_syntax": "bare_uniprot", "accession_separator": ";", "peptide_syntax": "plain_uppercase",
        "modification_syntax": "alphabase_separate", "protein_site_syntax": "residue_position", "missing_tokens": ["NA"]}


def row_values(values=None, extra=""):
    values = values or ["P00001", "AMSTY", "Phospho@S", "3", "S4"]
    return '<row r="2">' + ''.join(cell(chr(65 + i) + '2', x) for i, x in enumerate(values)) + extra + '</row>'


def references():
    registry, captured = fixture(alias_collision=True, other_product=True)
    captured['P00001']['Sequence'] = 'MAMSTYK'
    return registry, captured


def counted_contract():
    c = contract()
    c.update(headers=['Protein', 'Peptide', 'Raw mods', 'Other mods', 'Phospho mods', 'Protein site', 'Signal', 'Signal'],
        fields={'accession':0, 'peptide':1, 'modifications_raw':2, 'other_modifications':3,
                'phospho_modifications':4, 'protein_site':5},
        quant_columns=[{'index':6, 'sample_id':'r1', 'unit':None}, {'index':7, 'sample_id':'r2', 'unit':None}],
        modification_syntax='counted_bracket_modifications.v1', unassessed_label_modifications=['TMT6plex'])
    return c


class MeasurementAdapterTests(unittest.TestCase):
    def test_exact_visible_selection_and_duplicate_headers(self):
        raw = package(contract()["headers"], [row_values()])
        meta = inspect_workbook_headers(raw, "Measurements")
        self.assertEqual(meta["headers"][-2:], ["Signal", "Signal"])
        self.assertEqual(meta["data_rows_parsed"], 0)
        self.assertEqual(meta["sheets"][0]["visibility"], "hidden")
        for name in ['Hidden wrong table', 'measurements']:
            with self.assertRaises(AdapterError): inspect_workbook_headers(raw, name)
        with self.assertRaises(AdapterError):
            inspect_workbook_headers(package(["A"], [], state="veryHidden"), "Measurements")

    def test_no_data_without_seal_and_exact_header_order(self):
        raw = package(contract()["headers"], [row_values()])
        with self.assertRaises(AdapterError) as error: read_measurements(raw, contract())
        self.assertEqual(error.exception.diagnostic["code"], "pre_access_seal_required")
        changed = contract(); changed["headers"][0] = "Different"
        with self.assertRaises(AdapterError): read_measurements(raw, changed, data_access_seal="0" * 64)

    def test_headers_and_descriptor_window_do_not_decode_quant_shared_string(self):
        raw = package(contract()["headers"], [row_values(extra=cell('F2', '999', 's'))],
            shared_strings='<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>UNREAD QUANT STRING</t></si></sst>')
        self.assertEqual(inspect_workbook_headers(raw, 'Measurements')['data_rows_parsed'], 0)
        window = inspect_descriptor_rows(raw, contract(), first_row=2, last_row=2,
            column_indices=range(5), data_access_seal='0' * 64)
        self.assertEqual(window['quantitative_cells_parsed'], 0)
        self.assertEqual(set(window['records'][0]['cells']), set(range(5)))
        with self.assertRaises(AdapterError): read_measurements(raw, contract(), data_access_seal='0' * 64)
        with self.assertRaises(AdapterError):
            inspect_descriptor_rows(raw, contract(), first_row=2, last_row=2, column_indices=[5], data_access_seal='0' * 64)

    def test_quant_columns_cannot_fabricate_replicates_or_overlap_descriptors(self):
        for index in [5, 0]:
            config = contract(); config['quant_columns'][1]['index'] = index
            with self.assertRaises(ValueError): read_measurements(b'', config, data_access_seal='0' * 64)

    def test_raw_zero_blank_missing_and_units_remain_distinct(self):
        raw = package(contract()["headers"], [row_values(extra=cell('F2', '0', 'n') + cell('G2', None, 'n'))])
        record = read_measurements(raw, contract(), data_access_seal='0' * 64)['records'][0]
        before = deepcopy(record); registry, captured = references()
        result = qualify_record(record, contract(), registry, captured)
        self.assertEqual(record, before)
        self.assertEqual(result['status'], 'qualified_reference_coordinate_context')
        self.assertEqual(result['canonical_site_id'], 'UniProtKB:P00001:S4')
        self.assertEqual(result['raw_quant_values'][0]['cell']['text'], '0')
        self.assertEqual(result['raw_quant_values'][0]['source_value_state'], 'source_literal')
        self.assertEqual(result['raw_quant_values'][1]['source_value_state'], 'blank')
        self.assertEqual(result['raw_quant_values'][0]['unit'], 'source-intensity')
        self.assertFalse(result['assay_proteoform_identity_established'])
        self.assertFalse(result['localization_confidence_established'])
        record['cells'].pop(6)
        self.assertEqual(qualify_record(record, contract(), registry, captured)['raw_quant_values'][1]['source_value_state'], 'missing_cell')
        record['cells'][6] = {'present': True, 'text': 'NA', 'state': 'source_literal', 'formula': None, 'cell_type': 'inlineStr'}
        self.assertEqual(qualify_record(record, contract(), registry, captured)['raw_quant_values'][1]['source_value_state'], 'declared_missing_token')

    def test_quant_formula_is_cell_only_and_descriptor_formula_still_blocks(self):
        raw = package(contract()["headers"], [row_values(extra=cell('F2', '0', 'n', formula='[external.xlsx]S!A1') + cell('G2','7','n'))])
        record = read_measurements(raw, contract(), data_access_seal='0' * 64)['records'][0]
        result = qualify_record(record, contract(), *references())
        self.assertEqual(result['status'], 'qualified_reference_coordinate_context')
        self.assertEqual(result['diagnostics'], [])
        self.assertEqual(result['quantitative_diagnostics'][0]['scope'], 'cell_only')
        self.assertEqual(result['raw_quant_values'][0]['cell']['formula']['text'], '[external.xlsx]S!A1')
        self.assertEqual(result['raw_quant_values'][1]['cell']['text'],'7')
        self.assertIsNone(result['raw_quant_values'][1]['cell']['formula'])
        self.assertFalse(result['quantitative_eligibility_assessed'])
        changed = deepcopy(record);changed['cells'][0]['formula'] = {'text':'S!A1','attributes':None}
        self.assertEqual(qualify_record(changed, contract(), *references())['status'],'unresolved')
        changed = deepcopy(record);changed['cells'][5].update(cell_type='e', text='#N/A', formula=None)
        result = qualify_record(changed, contract(), *references())
        self.assertEqual(result['status'],'qualified_reference_coordinate_context')
        self.assertEqual(result['raw_quant_values'][1]['cell']['text'],'7')
        self.assertEqual(result['quantitative_diagnostics'][0]['field'],'replicate_1')
        with self.assertRaises(AdapterError): inspect_workbook_headers(package(['A'], [], external=True), 'Measurements')

    def test_groups_isoforms_secondary_and_unknown_source_syntax_stay_unresolved(self):
        registry, captured = references()
        for accession in ['P00001;P00003', 'P00001-2', 'Q99999']:
            raw = package(contract()['headers'], [row_values([accession, 'AMSTY', 'Phospho@S', '3', 'S4'])])
            record = read_measurements(raw, contract(), data_access_seal='0' * 64)['records'][0]
            self.assertEqual(qualify_record(record, contract(), registry, captured)['status'], 'unresolved')
        config = contract(); config['modification_syntax'] = None
        record = read_measurements(package(config['headers'], [row_values()]), config, data_access_seal='0' * 64)['records'][0]
        self.assertEqual(qualify_record(record, config, registry, captured)['diagnostics'][0]['code'], 'unsupported_modification_syntax')

    def test_peptide_modification_site_conflicts_and_multisite_are_not_repaired(self):
        for values in [['P00001', 'AMATY', 'Phospho@S', '3', 'S4'],
                       ['P00001', 'AMSTY', 'Phospho@T', '3', 'S4'],
                       ['P00001', 'AMSTY', 'Phospho@S', '3', 'T5'],
                       ['P00001', 'AMSTY', 'Phospho@S;Phospho@T', '3;4', 'S4']]:
            record = read_measurements(package(contract()['headers'], [row_values(values)]), contract(), data_access_seal='0' * 64)['records'][0]
            result = qualify_record(record, contract(), *references())
            self.assertEqual(result['status'], 'unresolved')
            self.assertIsNone(result['canonical_site_id'])

    def test_lexical_fix_is_candidate_only_and_raw_is_preserved(self):
        record = read_measurements(package(contract()['headers'], [row_values([' P00001 ', 'AMSTY', 'Phospho@S', '3', 'S4'])]), contract(), data_access_seal='0' * 64)['records'][0]
        result = qualify_record(record, contract(), *references())
        self.assertEqual(result['status'], 'unresolved')
        self.assertFalse(result['candidate_fixes'][0]['applied'])
        self.assertEqual(result['raw_record']['cells'][0]['text'], ' P00001 ')

    def test_json_roundtrip_does_not_lose_positional_cell_identity(self):
        record = read_measurements(package(contract()['headers'], [row_values()]), contract(), data_access_seal='0'*64)['records'][0]
        restored = json.loads(json.dumps(record))
        self.assertEqual(qualify_record(restored, contract(), *references())['canonical_site_id'], 'UniProtKB:P00001:S4')
        restored['cells'][0] = restored['cells']['0']
        with self.assertRaises(AdapterError): qualify_record(restored, contract(), *references())

    def test_standard_reader_ignores_stale_dimension_and_preserves_bool_type(self):
        raw = package(contract()['headers'], [row_values(extra=cell('F2','1','b'))])
        source = zipfile.ZipFile(io.BytesIO(raw)); stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as target:
            for name in source.namelist():
                b = source.read(name)
                if name.endswith('visible.xml'):
                    b = b.replace(b'<sheetData>', b'<dimension ref="A1:A1"/><sheetData>')
                target.writestr(name,b)
        result = read_measurements(stream.getvalue(), contract(), data_access_seal='0'*64)
        self.assertEqual(result['data_rows_parsed'],1)
        self.assertEqual(result['records'][0]['cells'][5]['cell_type'],'b')
        self.assertEqual(result['reader']['version'],'3.1.5')
        self.assertFalse(result['reader']['cached_formula_values_used'])
        self.assertIsNone(result['records'][0]['cells'][5]['raw_xml_value'])

    def test_second_layout_uses_declared_indices_and_three_letter_site(self):
        config = contract(); config.update(sheet_name='Independent invented layout',
            headers=['Site address', 'Product', 'Relative position', 'Reporter', 'Bare peptide', 'Mod names'],
            fields={'protein_site':0, 'accession':1, 'modification_positions':2, 'peptide':4, 'modification_names':5},
            quant_columns=[{'index':3, 'sample_id':'other_reporter', 'unit':None}], protein_site_syntax='three_letter_position')
        row = '<row r="2">'+''.join(cell(chr(65+i)+'2', s) for i,s in enumerate(['Ser4','P00001','2;3','0','AMSTY','Oxidation@M;Phospho@S']))+'</row>'
        record = read_measurements(package(config['headers'],[row],sheet=config['sheet_name']), config, data_access_seal='0'*64)['records'][0]
        result = qualify_record(record, config, *references())
        self.assertEqual(result['status'], 'qualified_reference_coordinate_context')
        self.assertEqual(result['canonical_site_id'], 'UniProtKB:P00001:S4')
        self.assertIsNone(result['raw_quant_values'][0]['unit'])

    def test_shared_header_strings_with_xml_declaration_are_selected_only(self):
        raw = package(contract()['headers'], [])
        source = zipfile.ZipFile(io.BytesIO(raw)); stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as target:
            for name in source.namelist():
                if name == 'xl/sharedStrings.xml': continue
                b = source.read(name)
                if name.endswith('visible.xml'):
                    for i, header in enumerate(contract()['headers']):
                        b = b.replace(cell(chr(65+i)+'1', header).encode(), cell(chr(65+i)+'1', str(i), 's').encode())
                target.writestr(name, b)
            target.writestr('xl/sharedStrings.xml', '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'+''.join('<si><t>'+escape(h)+'</t></si>' for h in contract()['headers'])+'<si><t>UNREAD OUTCOME</t></si></sst>')
        self.assertEqual(inspect_workbook_headers(stream.getvalue(), 'Measurements')['headers'], contract()['headers'])

    def test_counted_blocks_reconcile_raw_processed_and_peptide_sites(self):
        c = counted_contract()
        values = ['P00001', 'AMSTY', '1xTMT6plex [N-Term]; 1xOxidation [M2(100)]; 1xPhospho [S3(91.6)]',
                  '1xOxidation [M2]', '1xPhospho [S3]', 'S4']
        record = read_measurements(package(c['headers'], [row_values(values)]), c, data_access_seal='0'*64)['records'][0]
        result = qualify_record(record, c, *references())
        self.assertEqual(result['status'], 'qualified_reference_coordinate_context')
        self.assertEqual(result['localization_scores_raw'], ['91.6'])
        self.assertFalse(result['localization_score_unit_or_calibration_inferred'])
        self.assertEqual(result['unassessed_source_label_modifications'][0]['raw'], '1xTMT6plex [N-Term]')
        self.assertFalse(result['localization_confidence_established'])

    def test_counted_conflicts_unlocalized_and_multisite_are_not_rescued(self):
        c = counted_contract()
        cases = [
            ['P00001', 'AMSTY', '1xPhospho [S3(99)]', '', '1xPhospho [T4]', 'S4'],
            ['P00001', 'AMSTY', '1xPhospho [S]', '', '1xPhospho [S]', 'NULL'],
            ['P00001', 'AMSTY', '2xPhospho [S3(99); T4(90)]', '', '2xPhospho [S3; T4]', 'S4;T5'],
            ['P00001', 'AMSTY', '1xCarbamidomethyl [C1]; 1xPhospho [S3(99)]', '1xCarbamidomethyl [C1]', '1xPhospho [S3]', 'S4'],
            ['P00001', 'AMSTY', '2xPhospho [S3(99)]', '', '1xPhospho [S3]', 'S4']]
        for values in cases:
            record = read_measurements(package(c['headers'], [row_values(values)]), c, data_access_seal='0'*64)['records'][0]
            result = qualify_record(record, c, *references())
            self.assertEqual(result['status'], 'unresolved')
            self.assertTrue(result['diagnostics'])
            self.assertIsNone(result['canonical_site_id'])

    def test_optional_corroboration_uses_declared_field_token_not_dataset_literal(self):
        c = counted_contract()
        c.update(optional_corroboration_fields=['other_modifications'],
                 unavailable_tokens_by_field={'other_modifications':['not supplied']})
        values=['P00001','AMSTY','1xPhospho [S3(91.6)]','not supplied','1xPhospho [S3]','S4']
        record=read_measurements(package(c['headers'],[row_values(values)]),c,data_access_seal='0'*64)['records'][0]
        original=deepcopy(record)
        result=qualify_record(record,c,*references())
        self.assertEqual(result['status'],'qualified_reference_coordinate_context')
        self.assertEqual(result['field_availability']['other_modifications']['state'],'not_reported')
        self.assertEqual(result['field_availability']['other_modifications']['raw_literal'],'not supplied')
        self.assertFalse(result['other_modification_corroboration']['absence_of_biological_PTMs_inferred'])
        self.assertEqual(record,original)
        self.assertEqual(result['raw_record']['cells'][3]['text'],'not supplied')
        # No global missing-marker interpretation or default source-specific fix.
        for change in ['not_optional','token_undeclared','wrong_field']:
            config=deepcopy(c)
            if change=='not_optional':config['optional_corroboration_fields']=[]
            if change=='token_undeclared':config['unavailable_tokens_by_field']={}
            if change=='wrong_field':config['unavailable_tokens_by_field']={'modifications_raw':['not supplied']}
            self.assertEqual(qualify_record(record,config,*references())['status'],'unresolved')

    def test_optional_other_still_rejects_present_contradiction_and_raw_uncertainty(self):
        c=counted_contract()
        c.update(optional_corroboration_fields=['other_modifications'],
                 unavailable_tokens_by_field={'other_modifications':['unavailable']})
        cases=[
            ['P00001','AMSTY','1xPhospho [S3(99)]','1xOxidation [M2]','1xPhospho [S3]','S4'],
            ['P00001','AMSTY','1xOxidation [M]; 1xPhospho [S3(99)]','unavailable','1xPhospho [S3]','S4'],
            ['P00001','AMSTY','1xPhospho [S3(99)]','unavailable','1xPhospho [T4]','S4'],
            ['P00001','AMSTY','2xPhospho [S3(99); T4(90)]','unavailable','2xPhospho [S3; T4]','S4;T5']]
        for values in cases:
            record=read_measurements(package(c['headers'],[row_values(values)]),c,data_access_seal='0'*64)['records'][0]
            result=qualify_record(record,c,*references())
            self.assertEqual(result['status'],'unresolved')
            self.assertIsNone(result['canonical_site_id'])

    def test_required_core_evidence_cannot_become_optional_corroboration(self):
        c=counted_contract();c['optional_corroboration_fields']=['protein_site']
        with self.assertRaises(ValueError):read_measurements(b'',c,data_access_seal='0'*64)
        c=counted_contract();c['unavailable_tokens_by_field']={'protein_site':['not reported']}
        values=['P00001','AMSTY','1xPhospho [S3(99)]','','1xPhospho [S3]','not reported']
        record=read_measurements(package(c['headers'],[row_values(values)]),c,data_access_seal='0'*64)['records'][0]
        result=qualify_record(record,c,*references())
        self.assertEqual(result['status'],'unresolved')
        self.assertEqual(result['diagnostics'][0]['code'],'required_descriptor_field_unavailable')

    def test_source_host_protein_conditions_do_not_claim_group_cardinality(self):
        c = {'sheet_name':'Measurements', 'headers':['UP', 'Gene', '#Groups', '#Unique', 'Signal'],
            'fields':{'accession':0, 'gene':1, 'source_group_count':2, 'source_unique_peptides':3},
            'quant_columns':[{'index':4, 'sample_id':'sample', 'unit':None}],
            'accession_syntax':'bare_uniprot', 'accession_separator':';'}
        record = read_measurements(package(c['headers'], [row_values(['P00001','ALPHA','1','2'])]), c, data_access_seal='0'*64)['records'][0]
        result = qualify_protein_record(record, c, *references())
        self.assertEqual(result['status'], 'qualified_reference_protein_context')
        self.assertEqual(result['protein_id'], 'UniProtKB:P00001')
        self.assertFalse(result['protein_group_cardinality_established'])
        self.assertFalse(result['direct_abundance_validation_performed'])
        for column, text in [(0,'P00001;P00003'), (0,'P00001-2'), (1,'BETA'), (2,'2'), (2,''), (3,'0')]:
            changed = deepcopy(record);changed['cells'][column]['text'] = text
            self.assertEqual(qualify_protein_record(changed, c, *references())['status'], 'unresolved')

    def test_protein_quant_error_is_cell_only_and_count_formula_blocks(self):
        c = {'sheet_name':'Measurements', 'headers':['UP','Gene','#Groups','#Unique','Bad group','Good group'],
            'fields':{'accession':0,'gene':1,'source_group_count':2,'source_unique_peptides':3},
            'quant_columns':[{'index':4,'sample_id':'bad_condition','unit':None},
                             {'index':5,'sample_id':'valid_condition','unit':None}],
            'accession_syntax':'bare_uniprot','accession_separator':';'}
        raw = package(c['headers'], [row_values(['P00001','ALPHA','1','2'],extra=cell('E2','#N/A','e')+cell('F2','7','n'))])
        record = read_measurements(raw,c,data_access_seal='0'*64)['records'][0]
        result = qualify_protein_record(record,c,*references())
        self.assertEqual(result['status'],'qualified_reference_protein_context')
        self.assertEqual(result['diagnostics'],[])
        self.assertEqual(result['quantitative_diagnostics'][0]['field'],'bad_condition')
        self.assertEqual(result['raw_quant_values'][1]['cell']['text'],'7')
        self.assertFalse(result['direct_abundance_validation_performed'])
        changed = deepcopy(record);changed['cells'][2]['formula']={'text':'1+0','attributes':None}
        self.assertEqual(qualify_protein_record(changed,c,*references())['status'],'unresolved')


if __name__ == '__main__': unittest.main()
