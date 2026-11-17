// Invented source records test display fidelity and stale-response boundaries.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const clone = value => JSON.parse(JSON.stringify(value));
function element(tag, value) {
  return {tag, tagName: tag.toUpperCase(), textContent: value === undefined ? '' : String(value), children: [], attributes: {},
    append(...items) {this.children.push(...items); if(this.tag === 'select' && !this.value) this.value = items[0]?.value;},
    replaceChildren(...items) {this.children = [...items];}, setAttribute(k, v) {this.attributes[k] = v;}};
}
function nodes(node, tag) {return (node.tag === tag ? [node] : []).concat(...node.children.map(n => nodes(n, tag)));}
function text(node) {return node.textContent + ' ' + node.children.map(text).join(' ');}
function fixture() {
  const guide = {source_run: 'invented', selection: {id: 'claim:1'}, snapshot_sha256: 'snapshot', graph_basis_sha256: 'basis',
    protein_context: {configured: true, eligible: true, proteins: [
      {protein: 'UniProtKB:P04637', context_id: 'context', manifest_sha256: 'a'.repeat(64)},
      {protein: 'UniProtKB:P04637-2', context_id: 'other', manifest_sha256: 'b'.repeat(64)}]}};
  const signature = {accession: 'PF99999', name: '<script>invented</script>', type: 'Domain',
    signatureLibraryRelease: {library: 'Pfam', version: '39.0'},
    entry: {accession: 'IPR999999', name: 'Invented domain', type: 'Domain'}};
  const regular = {source: 'Pfam', signature, locations: [{start: 2, end: 20, 'location-fragments': [
    {start: 2, end: 8, 'dc-status': 'C_TERMINAL_DISC'}, {start: 15, end: 20, 'dc-status': 'N_TERMINAL_DISC'}],
    sites: [{description: 'Invented residue', numLocations: 1, siteLocations: [{start: 3, end: 3, residue: 'A'}]}]}]};
  const neural = clone(regular); neural.source = 'InterPro-N'; neural.signature.signatureLibraryRelease.version = '37.3'; neural.signature.entry = null;
  const result = {format: 'biograph-steward.protein-context-selection.v1', source_run: guide.source_run,
    selection_id: guide.selection.id, snapshot_sha256: guide.snapshot_sha256, graph_basis_sha256: guide.graph_basis_sha256,
    protein: guide.protein_context.proteins[0].protein, context_id: 'context', context_manifest_sha256: 'a'.repeat(64),
    read_only: true, source_fetches: 0, model_calls: 0, source_graph_changed: false, precomputed_found: true,
    sequence: {status: 'sequence_available', length: 40, md5: 'C'.repeat(32), sha256: 'd'.repeat(64), retrieved_at: '2026-01-01T00:00:00Z'},
    releases: {pharos_database: 'INVENTED', interpro_before: {release: '111.0', api: '0.6.0'}},
    matches: [regular, neural], pharos_context: {interpro: [{name: 'IPR999999', value: 'Invented'}], sequence_annotations: []},
    identifier_overlap: {shared_interpro_ids: ['IPR999999']}, goa_lineage: {status: 'not_configured', records: []}};
  return {guide, result};
}
function harness(api) {
  const context = vm.createContext({document: {createElement: tag => element(tag)}, window: {}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../biograph_steward/protein_context.js'), 'utf8'), context);
  const state = {current: true, calls: []};
  state.panel = guide => {
    const panel = context.window.ProteinContext.panel(guide, {isCurrent: () => state.current, labelForProtein: x => x,
      api: async (route, body) => {state.calls.push({route, body: clone(body)}); return api(route, body);}});
    // Browser select defaults to the first option after its value is assigned.
    if(panel) {const select = nodes(panel, 'select')[0]; select.value = select.children[0].value;}
    return panel;
  };
  state.render = result => {const root = element('div'); context.window.ProteinContext.render(root, result); return root;};
  return state;
}
test('inspection is collapsed, opt-in and bound to saved source identities', async () => {
  const {guide, result} = fixture(), h = harness(async () => result), panel = h.panel(guide);
  assert.equal(panel.tag, 'details'); assert.notEqual(panel.open, true); assert.equal(h.calls.length, 0);
  await nodes(panel, 'button')[0].onclick();
  assert.deepEqual(h.calls, [{route: '/api/protein-context', body: {run_id: 'invented', selection_id: 'claim:1', protein: result.protein}}]);
  assert.match(text(panel), /Saved source context displayed/);
  for(const field of ['snapshot_sha256', 'graph_basis_sha256', 'protein', 'context_id', 'context_manifest_sha256']) {
    const altered = {...result, [field]: 'wrong'}, bad = harness(async () => altered), p = bad.panel(guide);
    await nodes(p, 'button')[0].onclick(); assert.match(text(p), /does not match/); assert.doesNotMatch(text(p), /Sequence length:/);
  }
});
test('switching exact isoform or workspace while awaiting a response discards it', async () => {
  for(const change of ['protein', 'workspace']) {
    const {guide, result} = fixture(); let resolve;
    const h = harness(() => new Promise(r => {resolve = r;})), panel = h.panel(guide);
    const pending = nodes(panel, 'button')[0].onclick();
    if(change === 'protein') {const select = nodes(panel, 'select')[0]; select.value = 'UniProtKB:P04637-2'; select.onchange();}
    else h.current = false;
    resolve(result); await pending; assert.doesNotMatch(text(panel), /Sequence length:/);
  }
});
test('native split locations, site records and different method versions remain visible', () => {
  const {result} = fixture(), h = harness(), root = h.render(result), visible = text(root);
  for(const literal of ['2–8 (C_TERMINAL_DISC)', '15–20 (N_TERMINAL_DISC)', 'A · 3–3', 'Pfam 39.0', 'Pfam 37.3',
    'InterPro-N', '2026-01-01T00:00:00Z', '1-based, inclusive', 'not independent confirmations']) assert.ok(visible.includes(literal), literal);
  assert.equal(nodes(root, 'script').length, 0);
  assert.ok(visible.includes('<script>invented</script>')); // Literal text only.
  assert.ok(nodes(root, 'a').every(a => a.href.startsWith('https://www.ebi.ac.uk/interpro/entry/InterPro/IPR')));
});
test('no sequence, no precomputed result and found-empty preserve distinct uncertainty', () => {
  const {result} = fixture(), h = harness();
  const missing = clone(result); missing.sequence.status = 'sequence_unavailable'; missing.matches = [];
  assert.match(text(h.render(missing)), /No usable source sequence/);
  const absent = clone(result); absent.precomputed_found = false; absent.matches = [];
  assert.match(text(h.render(absent)), /not present in the precomputed lookup/);
  const empty = clone(result); empty.matches = [];
  assert.match(text(h.render(empty)), /No matches were supplied for this indexed sequence/);
  assert.match(text(h.render(empty)), /does not establish biological absence/);
});
test('GOA polarity, forms and full AND/OR groups are shown without accepting annotations', () => {
  const {result} = fixture(), h = harness();
  result.goa_lineage = {status: 'native_context_verified', records: [{native_record: {
    go_id: 'GO:9999999', id: 'native:1', negated: true, evidence_code: 'IEA', gene_product_form_id: 'UniProtKB:P04637-2',
    reference_identifiers: ['GO_REF:0000002'], qualifier_tokens: ['NOT', 'enables'], relation_literal: 'enables'},
    sequence_form_compatibility: 'coordinate_context_not_verified_for_product_form',
    with_from_groups: [{members: ['InterPro:IPR999999', 'UniProtKB:P00002'], status: 'partial_group', matched_interpro_ids: ['IPR999999']},
      {members: ['InterPro:IPR888888'], status: 'unmatched_group', matched_interpro_ids: []}]}]};
  const visible = text(h.render(result));
  for(const literal of ['NOT', 'GO_REF:0000002', 'UniProtKB:P04637-2', 'InterPro:IPR999999 AND UniProtKB:P00002',
    'Alternative 2:', 'Partial identifier coverage', 'reference independence remain unresolved']) assert.ok(visible.includes(literal), literal);
});
test('retired identifiers and native editorial flags are qualified without remapping or evidence votes', () => {
  const {result} = fixture(), h = harness();
  result.entry_metadata = [{interpro_id: 'IPR888888', http_status: 410, native_record: {
    accession: 'ipr888888', deletion_date: '2022-08-25', history: {names: ['Invented retired entry']}}},
  {interpro_id: 'IPR999999', http_status: 200, retrieved_at: '2026-01-01', native_record: {metadata: {
    accession: 'IPR999999', is_llm: true, is_reviewed_llm: false}}}];
  const visible = text(h.render(result));
  for (const value of ['Retired source entry', '2022-08-25', 'No replacement identifier', 'is_llm', 'is_reviewed_llm',
    'AI-generated and not yet reviewed', 'Not supplied', 'not an additional independent biological confirmation']) assert.ok(visible.includes(value), value);
});
test('native no-content responses remain explicit unknowns without a fabricated entry body', () => {
  const {result} = fixture(), h = harness();
  result.entry_unavailable = [{interpro_id: 'IPR888888', http_status: 204, status: 'no_content',
    retrieved_at: '2026-01-01', source_pointer: 'requests.json#/requests/1'}];
  const visible = text(h.render(result));
  for (const value of ['1 inspected', 'no content', 'HTTP 204', 'Retirement, replacement and editorial status remain unresolved',
    'requests.json#/requests/1']) assert.ok(visible.includes(value), value);
  assert.doesNotMatch(visible, /Retired source entry · deletion date|Entry available when retrieved/);
});
