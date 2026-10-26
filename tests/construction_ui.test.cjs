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
    return {value, textContent: '', disabled: false, children: [], options: [],
      elements: [], classList: {toggle() {}}, addEventListener() {},
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
  let resolve, reject;
  const pending = new Promise((yes, no) => { resolve = yes; reject = no; });
  const context = vm.createContext({$, el: () => element(), table: () => element(),
    api: () => pending, busy() {}, switchQuestionWorkflow() {}, runId: 'original'});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../biograph_steward/construction.js'), 'utf8'), context);
  return {$, context, resolve, reject};
}

const result = {plan_id: 'original_plan', trace: {status: 'validated',
  construction_request: {accessions: ['P22674', 'P38936'],
    focus_uniprot: 'P22674', profile: 'ppi', relations: ['interactions']}}};

test('a current response exposes its plan for inspection', async () => {
  const h = harness();
  const work = vm.runInContext('planConstructionGraph()', h.context);
  h.resolve(result);
  await work;
  assert.equal(vm.runInContext('constructionPlanId', h.context), 'original_plan');
  assert.equal(h.$('constructionPlannedBuild').disabled, false);
  assert.equal(h.$('constructionPlanPreview').children.length, 2);
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
