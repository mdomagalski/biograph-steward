// Run with: node --test tests/construction_ui.test.cjs
// Tests async state transitions; this is not browser/layout acceptance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

function harness() {
  const elements = new Map();
  function element(value = '') {
    const listeners = new Map();
    return {value, textContent: '', disabled: false, checked: false, children: [], options: [],
      elements: [], classList: {toggle() {}},
      addEventListener(event, callback) { listeners.set(event, callback); },
      dispatch(event) { listeners.get(event)?.({preventDefault() {}}); },
      reportValidity: () => true,
      replaceChildren() { this.children = []; },
      append(child) { this.children.push(child); }};
  }
  const $ = id => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  $('constructionProteins').value = 'P22674, P38936';
  $('constructionFocus').value = 'P22674';
  $('constructionProfile').value = 'ppi';
  $('constructionRelations').value = 'interactions';
  $('constructionAgentQuestion').value = 'Retrieve interaction candidates.';
  $('constructionForm').elements = ['constructionProteins', 'constructionFocus',
    'constructionProfile', 'constructionRelations', 'constructionAgentQuestion',
    'constructionRefresh', 'constructionPlanReviewed', 'constructionPlannedBuild'].map($);
  let resolve, reject;
  const pending = new Promise((yes, no) => { resolve = yes; reject = no; });
  const calls = [];
  const context = vm.createContext({$, el: () => element(), table: (headers, rows) => ({headers, rows}),
    api: (url, body) => { calls.push({url, body}); return calls.length === 1 ? pending : Promise.reject(new Error('Build inspection only')); },
    busy() {}, status() {}, switchQuestionWorkflow() {}, runId: 'original'});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../biograph_steward/construction.js'), 'utf8'), context);
  return {$, context, resolve, reject, calls};
}

const selection = {accessions: ['P22674', 'P38936'],
  focus_uniprot: 'P22674', profile: 'ppi', relations: ['interactions']};
const result = {plan_id: 'original_plan', trace: {status: 'validated',
  exact_selection: selection, model_construction_request: selection,
  construction_request: selection}};

async function ready(h, response = result) {
  const work = vm.runInContext('planConstructionGraph()', h.context);
  h.resolve(response);
  await work;
}

test('a matching plan sends the exact selection and requires explicit review', async () => {
  const h = harness();
  await ready(h);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls[0])), {url: '/api/construction-plan',
    body: {question: 'Retrieve interaction candidates.', accessions: selection.accessions,
      focus_uniprot: selection.focus_uniprot, exact_selection: selection}});
  assert.equal(vm.runInContext('constructionPlanId', h.context), 'original_plan');
  assert.equal(h.$('constructionPlannedBuild').disabled, true);
  assert.equal(h.$('constructionPlanReviewed').disabled, false);
  assert.equal(h.$('constructionPlanReviewed').checked, false);
  assert.equal(h.$('constructionPlanPreview').children.length, 2);
  assert.deepEqual(JSON.parse(JSON.stringify(h.$('constructionPlanPreview').children[0].headers)),
    ['Choice', 'Your exact selection', 'Model proposal']);
  await vm.runInContext('constructGraph("planned")', h.context);
  assert.equal(h.calls.length, 1);
  assert.match(h.$('constructionStatus').textContent, /review box/);
  h.$('constructionPlanReviewed').checked = true;
  h.$('constructionPlanReviewed').dispatch('change');
  assert.equal(h.$('constructionPlannedBuild').disabled, false);
  await vm.runInContext('constructGraph("planned")', h.context);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls[1])), {url: '/api/construct',
    body: {mode: 'planned', plan_id: 'original_plan', exact_selection: selection,
      plan_reviewed: true, refresh: false}});
});

for (const key of ['accessions', 'focus_uniprot', 'profile', 'relations']) {
  test(`a changed model ${key} is displayed and cannot execute`, async () => {
    const h = harness();
    const proposed = {...selection, [key]: {accessions: ['P22674'], focus_uniprot: 'P38936',
      profile: 'context', relations: ['shared_pathways']}[key]};
    await ready(h, {plan_id: 'mismatch', trace: {status: 'invalid_plan',
      exact_selection: selection, model_construction_request: proposed,
      construction_request: null, error: 'Model request differs from explicit selection.'}});
    assert.equal(vm.runInContext('constructionPlanId', h.context), null);
    assert.equal(h.$('constructionPlannedBuild').disabled, true);
    assert.equal(h.$('constructionPlanReviewed').disabled, true);
    const rows = h.$('constructionPlanPreview').children[0].rows;
    assert.equal(rows.length, 4);
    assert.ok(rows.some(row => row.cells[1] !== row.cells[2]));
    assert.match(h.$('constructionPlanStatus').textContent, /Build blocked/);
    h.$('constructionPlanReviewed').checked = true;
    await vm.runInContext('constructGraph("planned")', h.context);
    assert.equal(h.calls.length, 1);
  });
}

test('a validated status without an explicit-selection receipt fails closed', async () => {
  const h = harness();
  await ready(h, {plan_id: 'old_trace', trace: {status: 'validated', construction_request: selection}});
  assert.equal(vm.runInContext('constructionPlanId', h.context), null);
  assert.equal(h.$('constructionPlannedBuild').disabled, true);
});

for (const [id, event, value] of [
  ['constructionProteins', 'input', 'P22674'],
  ['constructionFocus', 'change', 'P38936'],
  ['constructionProfile', 'change', 'context'],
  ['constructionRelations', 'change', 'both'],
  ['constructionAgentQuestion', 'input', 'A different question'],
  ['constructionRefresh', 'change', true],
]) {
  test(`${id} changes reset the plan and its review`, async () => {
    const h = harness();
    await ready(h);
    h.$('constructionPlanReviewed').checked = true;
    h.$('constructionPlanReviewed').dispatch('change');
    if (id === 'constructionRefresh') h.$(id).checked = value;
    else h.$(id).value = value;
    h.$(id).dispatch(event);
    assert.equal(vm.runInContext('constructionPlanId', h.context), null);
    assert.equal(h.$('constructionPlanReviewed').checked, false);
    assert.equal(h.$('constructionPlanReviewed').disabled, true);
    assert.equal(h.$('constructionPlannedBuild').disabled, true);
    await vm.runInContext('constructGraph("planned")', h.context);
    assert.equal(h.calls.length, 1);
  });
}

test('programmatic form changes cannot execute a reviewed stale plan', async () => {
  const h = harness();
  await ready(h);
  h.$('constructionPlanReviewed').checked = true;
  h.$('constructionFocus').value = 'P38936';
  await vm.runInContext('constructGraph("planned")', h.context);
  assert.equal(h.calls.length, 1);
  assert.equal(vm.runInContext('constructionPlanId', h.context), null);
});

test('a late response cannot validate a programmatically changed form', async () => {
  const h = harness();
  const work = vm.runInContext('planConstructionGraph()', h.context);
  h.$('constructionAgentQuestion').value = 'Changed while waiting';
  h.resolve(result);
  await work;
  assert.equal(vm.runInContext('constructionPlanId', h.context), null);
  assert.equal(h.$('constructionPlannedBuild').disabled, true);
  assert.equal(h.$('constructionPlanPreview').children.length, 0);
});

for (const outcome of ['success', 'failure']) {
  test(`graph navigation invalidates a late planning ${outcome}`, async () => {
    const h = harness();
    const work = vm.runInContext('planConstructionGraph()', h.context);
    vm.runInContext('setupConstructionPublication({disease: {name: "Other graph"}})', h.context);
    if (outcome === 'success') h.resolve(result);
    else h.reject(new Error('Old request failed'));
    await work;
    assert.equal(vm.runInContext('constructionPlanId', h.context), null);
    assert.equal(h.$('constructionPlannedBuild').disabled, true);
    assert.equal(h.$('constructionPlanPreview').children.length, 0);
    assert.equal(h.$('constructionPlanStatus').textContent, '');
  });
}
