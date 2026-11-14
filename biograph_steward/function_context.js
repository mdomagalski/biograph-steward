// Read-only historical LocalPlus forecasts. Source records remain model inputs,
// never accepted annotations; scores are uncalibrated weighted-neighbor sums.
(function () {
  'use strict';
  const make = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (cls) n.className = cls;
    return n;
  };
  const add = (parent, tag, text, cls) => {const n = make(tag, text, cls); parent.append(n); return n;};
  const score = value => Number(value).toFixed(6);
  const accession = value => String(value).replace(/^UniProtKB:/, '');
  const label = item => item.display_label || [item.symbol, accession(item.protein || item.id)].filter(Boolean).join(' · ');
  const aspects = {BPO: 'Biological process', MFO: 'Molecular function', CCO: 'Cellular component'};
  const orderedContributors = candidate => candidate.contributors.slice().sort((a, b) =>
    b.normalized_contribution - a.normalized_contribution || a.protein.localeCompare(b.protein));
  function table(parent, headings, rows) {
    const t = add(add(parent, 'div', null, 'scroller'), 'table'), tr = add(add(t, 'thead'), 'tr');
    headings.forEach(h => add(tr, 'th', h));
    const body = add(t, 'tbody');
    rows.forEach(values => {const row = add(body, 'tr'); values.forEach(value => add(row, 'td', value));});
    return t;
  }
  function link(parent, text, href) {
    const n = add(parent, 'a', text); n.href = href; return n;
  }
  function diagram(parent, answer, candidate) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 850 260'); svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Model-input diagram: query protein to three contributing neighbors, then their historical GO annotations. This is not an experimentally verified function for the query.');
    svg.style.width = '100%'; svg.style.minWidth = '720px'; svg.style.maxHeight = '290px';
    function s(tag, attrs, text) {const n = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k,v]) => n.setAttribute(k, String(v))); if (text) n.textContent = text; svg.append(n); return n;}
    const rows = orderedContributors(candidate).slice(0, 3);
    rows.forEach((c, i) => {
      const y = 46 + i * 78;
      s('line', {x1:195, y1:126, x2:325, y2:y, stroke:'#147c83', 'stroke-width':2});
      s('line', {x1:515, y1:y, x2:645, y2:126, stroke:'#536a7b', 'stroke-width':2});
      s('rect', {x:325, y:y-21, width:190, height:42, rx:8, fill:'#e5f3f3', stroke:'#147c83'});
      s('text', {x:420, y:y+5, 'text-anchor':'middle', 'font-size':13, fill:'#172b3a'}, label(c));
    });
    s('rect', {x:5, y:99, width:190, height:54, rx:8, fill:'#102e42'});
    s('text', {x:100, y:132, 'text-anchor':'middle', 'font-size':14, fill:'#fff'}, label(answer.query));
    s('rect', {x:645, y:99, width:200, height:54, rx:8, fill:'#fff5dc', stroke:'#9b650e'});
    s('text', {x:745, y:122, 'text-anchor':'middle', 'font-size':14, fill:'#172b3a'}, candidate.GO_ID);
    s('text', {x:745, y:142, 'text-anchor':'middle', 'font-size':12, fill:'#52697b'}, 'Historical neighbor annotation');
    s('text', {x:235, y:245, 'font-size':12, fill:'#52697b'}, 'Qualified STRING associations');
    s('text', {x:570, y:245, 'font-size':12, fill:'#52697b'}, 'Selected training triples');
    add(parent, 'div', null, 'graph-box').append(svg);
  }
  function renderAnnotationContext(parent, note) {
    if (!note) return;
    const box = add(parent, 'details'); add(box, 'summary', 'Existing annotation context · separate recorded comparison');
    if (note.july2026_goa.term_deprecated)
      add(parent, 'p', 'This term is obsolete in the July 2026 ontology. Its historical model score is preserved; it is not proposed as an active current annotation.', 'notice warn');
    add(box, 'p', note.pre_t0_all_evidence.literal_source_row
      ? 'This term already appears in the publisher’s broader pre-t0 annotation baseline. It adds no new annotation concept relative to that table. This concept match does not establish identical underlying evidence.'
      : note.pre_t0_all_evidence.author_admitted
      ? 'The publisher’s broader pre-t0 annotation table already implies this concept through the author parser’s ancestor or alias handling. It adds no new annotation concept relative to that table; the underlying records may differ.'
      : 'No matching term was found in the publisher’s broader pre-t0 target table. A missing match does not establish novelty or biological absence.');
    const current = note.july2026_goa, matches = current.positive_matches;
    if (matches.length) {
      add(box, 'p', 'The July 2026 GOA source has related positive annotation context. The compact comparison preserves the source relation, product/form, extension and an explicit ontology path. Ancestor matches are derived context rather than literal annotations of this term.', 'small');
      for (const m of matches) {
        const record = add(box, 'details');
        add(record, 'summary', m.membership === 'literal_term' ? 'Literal term · ' + m.evidence : 'Ancestor context from ' + m.source_term + ' · ' + m.evidence);
        table(record, ['Recorded field', 'Value'], [
          ['Native record', m.native_record_id + ' · GAF line ' + m.source_line],
          ['Native term and relation', m.source_term + ' · ' + m.source_relation],
          ['Product/form', m.product_form || 'Not recorded'], ['Annotation extension', m.extension || 'Not recorded'],
          ['With/from', (m.with_from || []).filter(Boolean).join('; ') || 'Not recorded'],
          ['Ontology path', m.ontology_path.join(' → ')],
          ['Path relations', m.path_predicates.join(' → ') || 'Literal term; no ancestor path']]);
        const refs = add(record, 'p', 'Recorded references: ');
        m.references.forEach((ref, i) => {
          if (i) add(refs, 'span', ' · ');
          if (/^PMID:[0-9]+$/.test(ref)) link(refs, ref, 'https://pubmed.ncbi.nlm.nih.gov/' + ref.slice(5) + '/');
          else add(refs, 'span', ref);
        });
      }
    } else add(box, 'p', 'No positive match was recorded in this dated GOA comparison. The result remains unknown.');
    if (current.exact_NOT_record_ids.length) add(box, 'p', 'Explicit NOT records are present: ' + current.exact_NOT_record_ids.join(', ') + '. Inspect their full scope; a NOT annotation does not negate every related context.', 'notice warn');
    add(box, 'p', 'This comparison did not change predictions, scores or benchmark results. Later source coverage and repeated references do not supply independent biological validation.', 'small');
  }
  function renderTermContent(parent, term, versions) {
    if (!term) return;
    const old = term.historical, current = term.comparison;
    const changed = Object.entries(term.flags).filter(([,value]) => value === true).map(([key]) => ({
      name_changed: 'label', definition_text_changed: 'definition', namespace_changed: 'namespace',
      synonym_scope_or_text_records_changed: 'scoped synonyms', explicit_is_a_part_of_records_changed: 'explicit parents'
    })[key]);
    const box = add(parent, 'details');
    add(box, 'summary', 'GO term content · ' + versions.historical_predictor + ' → ' + versions.comparison_snapshot
      + (current.state === 'obsolete' ? ' · obsolete at comparison date' : changed.length ? ' · recorded differences' : ''));
    add(box, 'p', 'The model keeps the historical term meaning. This separate dated comparison does not update its score or establish that an annotation is true or false. The Pharos annotation vintage remains unknown; the comparison date is not asserted to be the latest release.', 'small');
    const parents = value => value.parents.length ? value.parents.map(p => p.predicate + ' ' + p.object).join('; ') : 'No explicit admitted parent record';
    table(box, ['Recorded field', versions.historical_predictor + ' historical source', versions.comparison_snapshot + ' comparison source'], [
      ['Lifecycle', old.state, current.state], ['Label', old.name ?? 'Not recorded', current.name ?? 'Not recorded'],
      ['Definition', old.definition ?? 'Not recorded', current.definition ?? 'Not recorded'],
      ['Explicit is_a / part_of parents', parents(old), parents(current)]]);
    add(box, 'p', changed.length ? 'Compared records differ in: ' + changed.join(', ') + '.'
      : 'No difference was recorded in the compared fields. This does not establish full ontology equivalence.', 'small');
    if (term.flags.synonym_scope_or_text_records_changed) {
      const synonyms = value => value.synonyms.map(s => s.scope + ': ' + s.value).join('; ') || 'None recorded';
      table(box, ['Scoped synonym records', 'Literal values'], [[versions.historical_predictor, synonyms(old)], [versions.comparison_snapshot, synonyms(current)]]);
    }
    if (Object.values(term.flags).some(value => value === null))
      add(box, 'p', 'Some fields could not be compared because source content was missing; unassessed does not mean unchanged.', 'small');
    if (current.state === 'obsolete') add(box, 'p', 'This remains a historical forecast, not a proposed active current annotation. Lifecycle declarations are preserved in the content download; no replacement or pruning is applied.', 'notice warn');
    else add(box, 'p', 'A changed parent, label or definition requests source-scope inspection. No replacement, pruning or biological-falsehood verdict is inferred.', 'small');
  }
  function renderCandidate(parent, answer, candidate, note, content, versions) {
    parent.replaceChildren();
    add(parent, 'h4', candidate.GO_ID + ' · ' + candidate.label);
    add(parent, 'p', aspects[candidate.aspect] + ' · model ranking score ' + score(candidate.score), 'notice');
    add(parent, 'p', 'This term is absent from the selected benchmark training set for this protein. That does not establish a new discovery or absence from other annotation sources.', 'small');
    renderAnnotationContext(parent, note);
    renderTermContent(parent, content, versions);
    diagram(parent, answer, candidate);
    add(parent, 'p', 'LocalPlus adds the weights of qualified neighbors carrying this training term, then divides by the query protein’s total qualified weight (' + score(answer.weighted_degree) + '). The result ranks hypotheses; it is not a probability of biological correctness.', 'small');
    const contributors = orderedContributors(candidate);
    add(parent, 'h4', 'Why this term was ranked');
    add(parent, 'p', contributors.length + ' contributing protein records. The diagram and table initially show the largest three contributions. All contributions are preserved in the saved query JSON.', 'small');
    function showContributions(where, rows) {
      table(where, ['Contributing protein', 'Native STRING weight', 'Contribution to score', 'Source pair'], rows.map(c => [label(c), score(c.raw_STRING_weight), score(c.normalized_contribution), c.source_pair.pair_id]));
    }
    showContributions(parent, contributors.slice(0, 3));
    if (contributors.length > 3) {
      const all = add(parent, 'details'); add(all, 'summary', 'Inspect all ' + contributors.length + ' contributions');
      let shown = false;
      all.ontoggle = () => {if (all.open && !shown) {showContributions(all, contributors); shown = true;}};
    }
    const native = add(parent, 'details'); add(native, 'summary', 'What these records support');
    add(native, 'p', 'STRING combined scores support protein association, including functional context. They do not establish direct physical binding. The training snapshot supplies protein/GO/aspect triples without native GAF relations, assay conditions or individual publication references. Several records may reuse evidence.');
    add(native, 'p', 'No publication reference is inferred from these source pairs. Use the native GO inspector in Evidence for available current source annotations and their recorded references.');
    link(native, 'Open the current QuickGO entry for this term', 'https://www.ebi.ac.uk/QuickGO/term/' + candidate.GO_ID);
  }
  function render(parent, answer, summary, base, notes = null, contentNotes = null) {
    if (answer?.format !== 'biograph-steward.exact-onehop-LocalPlus-query.v1' || answer.curated_acceptance !== false || answer.uncalibrated_score !== true)
      throw new Error('Unsupported historical prediction response.');
    parent.replaceChildren();
    const noteFor = candidate => notes?.queries?.[answer.query.id]?.find(r => r.GO_ID === candidate.GO_ID && r.aspect === candidate.aspect);
    const contentFor = candidate => contentNotes?.terms?.[candidate.GO_ID];
    add(parent, 'h4', label(answer.query));
    add(parent, 'p', 'Historical model hypotheses · training cutoff ' + answer.source_versions.t0_date + ' · no annotation accepted', 'notice warn');
    add(parent, 'p', 'This saved context uses a separately qualified historical Pharos backbone. Opening it changes no workspace evidence or review decisions. Only the selected query has full-network scores; neighboring proteins supply context.', 'small');
    const queryLink = link(parent, 'Download the complete saved query JSON', base + 'query/' + accession(answer.query.id)); queryLink.download = accession(answer.query.id) + '_historical_context.json';
    if (!answer.candidates.length) {
      add(parent, 'p', answer.state === 'no_qualified_neighbor_context'
        ? 'Abstained: this archived protein record has no admitted neighbor context after source and identifier qualification. This does not imply that the protein has no biological function or evidence elsewhere.'
        : 'No additional terms are available from this selected training snapshot.', 'notice');
      (answer.source_qualification || []).forEach(row => add(parent, 'p', row.message, 'small'));
    } else {
      add(parent, 'p', answer.qualified_neighbor_count + ' qualified neighbors; ' + answer.known_training_term_count + ' training terms already known for this archived protein. Showing up to three other terms per GO aspect.', 'small');
      const t = add(add(parent, 'div', null, 'scroller'), 'table'), tr = add(add(t, 'thead'), 'tr');
      ['Inspect historical term', 'GO aspect', 'Ranking score', 'Contributors', ...(notes ? ['Annotation context'] : [])].forEach(h => add(tr, 'th', h));
      const tb = add(t, 'tbody'), detail = make('section'); detail.setAttribute('aria-label', 'Selected model hypothesis and its source contributions');
      answer.candidates.forEach(c => {
        const row = add(tb, 'tr'), cell = add(row, 'td'), button = add(cell, 'button', c.GO_ID + ' · ' + c.label, 'secondary');
        button.type = 'button'; button.onclick = () => renderCandidate(detail, answer, c, noteFor(c), contentFor(c), contentNotes?.source_versions);
        add(row, 'td', aspects[c.aspect]); add(row, 'td', score(c.score)); add(row, 'td', c.contributors.length);
        if (notes) {const n = noteFor(c); add(row, 'td', n.july2026_goa.term_deprecated ? 'Obsolete in July 2026'
          : n.pre_t0_all_evidence.literal_source_row ? 'In broader pre-t0 annotations'
          : n.pre_t0_all_evidence.author_admitted ? 'Implied by broader pre-t0 annotations'
          : 'No broader pre-t0 match recorded', n.july2026_goa.term_deprecated ? 'warning' : 'small');}
      });
      parent.append(detail); renderCandidate(detail, answer, answer.candidates[0], noteFor(answer.candidates[0]), contentFor(answer.candidates[0]), contentNotes?.source_versions);
    }
    const provenance = add(parent, 'details'); add(provenance, 'summary', 'Historical sources, exact inputs and method');
    Object.entries(answer.source_versions).forEach(([key, value]) => add(provenance, 'p', key.replaceAll('_', ' ') + ': ' + value, 'small'));
    if (notes) {
      add(provenance, 'p', 'Separate annotation comparison: July 2026 GOA and its matching ontology, plus the released pre-t0 all-evidence baseline. These sources were not model inputs. Record-level provenance is preserved in the comparison download.', 'small');
      link(provenance, 'Download the separate annotation-overlap comparison', base + 'download/annotation_overlap');
      add(provenance, 'p', 'Annotation comparison seal: ' + notes.content_sha256, 'small');
    }
    if (contentNotes) {
      add(provenance, 'p', 'Separate GO term-content qualification: exact candidate IDs projected offline from the full source-frozen used-term index. Only this small saved sidecar is read here; the historical publication and scores are unchanged.', 'small');
      link(provenance, 'Download the separate versioned term-content notes', base + 'download/term_content');
      add(provenance, 'p', 'Content comparison seal: ' + contentNotes.content_sha256, 'small');
    }
    const ul = add(provenance, 'ul'); (summary.limitations || []).forEach(value => add(ul, 'li', value));
    const downloads = add(provenance, 'ul');
    Object.keys(summary.downloads || {}).forEach(name => {
      if (!/^[a-z_]{1,80}$/.test(name)) return;
      link(add(downloads, 'li'), name.replaceAll('_', ' '), base + 'download/' + name);
    });
    link(provenance, 'Published LocalPlus / FastSinkSource method', 'https://doi.org/10.1093/bioinformatics/btaa885');
  }
  window.FunctionContext = Object.freeze({render});
}());

let functionContextEpoch = 0;
async function initializeFunctionContexts() {
  const panel = document.getElementById('functionContextPanel');
  if (!panel) return;
  const select = document.getElementById('functionContextPublication'), protein = document.getElementById('functionContextProtein'),
    button = document.getElementById('functionContextOpen'), status = document.getElementById('functionContextStatus'),
    body = document.getElementById('functionContextBody');
  const epoch = ++functionContextEpoch;
  select.disabled = protein.disabled = button.disabled = true;
  try {
    const response = await fetch('/api/function-contexts'), value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Historical model contexts unavailable.');
    if (epoch !== functionContextEpoch) return;
    const contexts = value.contexts || [];
    panel.hidden = !contexts.length;
    select.replaceChildren();
    for (const item of contexts) {
      if (!/^[A-Za-z0-9_-]{1,80}$/.test(item.id)) throw new Error('Invalid historical publication identifier.');
      const opt = document.createElement('option'); opt.value = item.id; opt.textContent = item.purpose || item.id; select.append(opt);
    }
    select.disabled = !contexts.length;
    function choose() {
      ++functionContextEpoch; body.replaceChildren(); protein.replaceChildren();
      const context = contexts.find(c => c.id === select.value);
      for (const p of context?.proteins || []) {
        if (!/^UniProtKB:[A-Z0-9]{6}(?:[A-Z0-9]{4})?$/.test(p.id)) throw new Error('Invalid exact source protein.');
        const opt = document.createElement('option'); opt.value = p.id; opt.textContent = p.display_label; protein.append(opt);
      }
      protein.disabled = button.disabled = !context;
      status.textContent = 'Choose an exact archived protein and open its saved context. No model call or retrieval is needed.';
    }
    select.onchange = choose;
    protein.onchange = () => {++functionContextEpoch; body.replaceChildren(); button.disabled = false; status.textContent = 'Open the selected saved context.';};
    button.onclick = async () => {
      const request = ++functionContextEpoch, id = select.value, p = protein.value;
      const context = contexts.find(c => c.id === id);
      if (!context || !context.proteins.some(row => row.id === p)) return;
      const base = '/api/function-context/' + id + '/';
      body.replaceChildren(); button.disabled = true; status.textContent = 'Verifying saved context and exact contribution arithmetic…';
      try {
        const r = await fetch(base + 'query/' + p.slice(10)), result = await r.json();
        if (request !== functionContextEpoch) return;
        if (!r.ok) throw new Error(result.error || 'Saved model context unavailable.');
        if (result.context_id !== id || result.answer?.query?.id !== p) throw new Error('Saved context belongs to another selection.');
        FunctionContext.render(body, result.answer, context, base, result.display_notes || null, result.content_notes || null);
        status.textContent = 'Verified saved source files and contribution arithmetic. This historical model output is separate from curator-approved evidence.';
      } catch (error) {if (request === functionContextEpoch) {body.replaceChildren(); status.textContent = error.message;}}
      finally {if (request === functionContextEpoch) button.disabled = false;}
    };
    if (contexts.length) choose();
  } catch (error) {if (epoch === functionContextEpoch) {panel.hidden = false; status.textContent = error.message;}}
}
