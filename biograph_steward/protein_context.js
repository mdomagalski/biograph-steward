// Saved, exact-sequence source context. No prediction, retrieval or review edits.
(function () {
  'use strict';
  const make = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (cls) n.className = cls;
    return n;
  };
  const add = (parent, tag, text, cls) => {const n = make(tag, text, cls); parent.append(n); return n;};
  const literal = value => value === null || value === undefined || value === '' ? 'Not supplied' : String(value);
  const entry = match => match.signature?.entry || null;
  function entryLink(parent, id) {
    if (!/^IPR[0-9]{6}$/.test(String(id))) return add(parent, 'span', literal(id));
    const a = add(parent, 'a', id);
    a.href = 'https://www.ebi.ac.uk/interpro/entry/InterPro/' + id + '/';
    a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
  }
  function table(parent, headings, rows) {
    const t = add(add(parent, 'div', null, 'scroller'), 'table');
    const h = add(add(t, 'thead'), 'tr'); headings.forEach(v => add(h, 'th', v));
    const body = add(t, 'tbody');
    for (const values of rows) {
      const tr = add(body, 'tr');
      for (const value of values) {
        const td = add(tr, 'td');
        if (value && typeof value === 'object' && value.tagName) td.append(value);
        else add(td, 'span', literal(value));
      }
    }
    return t;
  }
  function details(parent, title, open = false) {
    const box = add(parent, 'details'); box.open = open; add(box, 'summary', title); return box;
  }
  function fragments(location) {
    const rows = location['location-fragments'];
    if (!Array.isArray(rows) || !rows.length) return 'Fragments not supplied';
    return rows.map(f => f.start + '–' + f.end + ' (' + literal(f['dc-status']) + ')').join('; ');
  }
  function regions(match) {
    return (match.locations || []).map(l =>
      'Reported span ' + l.start + '–' + l.end + '; fragments: ' + fragments(l)).join('\n');
  }
  function signature(match) {
    const s = match.signature || {}, release = s.signatureLibraryRelease || {};
    return [literal(s.accession), literal(release.library) + ' ' + literal(release.version), literal(match.source)].join(' · ');
  }
  function grouped(matches) {
    const groups = new Map();
    for (const match of matches) {
      const e = entry(match);
      if (!e) continue;
      // Grouping is visual only; member methods and versions remain individual rows.
      const key = String(match.source) + '|' + e.accession;
      if (!groups.has(key)) groups.set(key, {entry: e, source: match.source, matches: []});
      groups.get(key).matches.push(match);
    }
    return [...groups.values()];
  }
  function matchDetails(parent, match) {
    const raw = details(parent, 'Complete recorded signature match');
    add(raw, 'pre', JSON.stringify(match.native_match || match, null, 2));
    if (match.source_pointer) add(raw, 'p', 'Saved source locator: ' + match.source_pointer, 'small');
    if (match.decoded_text_pointer) add(raw, 'p', 'Within the decoded source text: ' + match.decoded_text_pointer, 'small');
  }
  function renderGroups(parent, matches, filter) {
    const q = filter.trim().toLowerCase();
    const groups = grouped(matches).filter(g => !q || JSON.stringify(g).toLowerCase().includes(q));
    add(parent, 'p', groups.length + ' entry/method groups. Overlapping signatures are not independent confirmations.', 'small');
    for (const group of groups) {
      const e = group.entry;
      const box = details(parent, [literal(e.name), e.accession, literal(e.type), group.source].join(' · '));
      const p = add(box, 'p'); entryLink(p, e.accession);
      add(box, 'p', 'Current entry page; its present contents may differ from this saved sequence lookup.', 'small');
      for (const m of group.matches) {
        const row = add(box, 'section', null, 'source-record');
        add(row, 'strong', signature(m));
        add(row, 'p', regions(m));
        matchDetails(row, m);
      }
    }
    if (!groups.length) add(parent, 'p', 'No integrated entry matches this display filter. Other signatures and predictions remain below.');
  }
  function renderSites(parent, matches) {
    const rows = [];
    for (const m of matches) for (const l of m.locations || []) for (const site of l.sites || []) {
      rows.push([literal(site.description), (site.siteLocations || []).map(s =>
        literal(s.residue) + ' · ' + s.start + '–' + s.end).join('; '),
      'Provider count: ' + literal(site.numLocations), signature(m)]);
    }
    const box = details(parent, 'Residue-site records supplied by signatures (' + rows.length + ')');
    add(box, 'p', 'These are source site records, potentially overlapping or repeated across methods. They are not a count of independent experiments or unique validated sites. Missing sites do not establish catalytic absence.', 'small');
    if (!rows.length) {add(box, 'p', 'No optional site records were supplied in this response.'); return;}
    table(box, ['Source description', 'Recorded residues and positions', 'Native count', 'Signature / library version / method'], rows.slice(0, 20));
    if (rows.length > 20) {
      const more = details(box, 'Show remaining ' + (rows.length - 20) + ' site records');
      table(more, ['Source description', 'Recorded residues and positions', 'Native count', 'Signature / library version / method'], rows.slice(20));
    }
  }
  function renderOther(parent, matches) {
    const other = matches.filter(m => !entry(m));
    const box = details(parent, 'Other signature and method records (' + other.length + ')');
    add(box, 'p', 'A record without an integrated InterPro entry is preserved here. InterPro-N predictions remain a separate method; their member-library versions may predate the current release. Scores are source-specific and are not acceptance probabilities.', 'small');
    for (const m of other) {
      const item = details(box, signature(m) + ' · ' + literal(m.signature?.name || m.signature?.description));
      add(item, 'p', regions(m)); matchDetails(item, m);
    }
  }
  function renderPharos(parent, result) {
    const context = result.pharos_context || {}, overlap = result.identifier_overlap || {};
    const box = details(parent, 'Already represented in Pharos');
    add(box, 'p', 'A repeated entry or signature identifier is reused context. Matching identifiers do not prove identical record versions or independent biological evidence.', 'small');
    table(box, ['Pharos cross-reference family', 'Preserved identifiers'],
      ['interpro', 'pfam', 'prosite', 'smart', 'panther'].map(key => [key,
        (context[key] || []).map(r => r.name + (r.value ? ' · ' + r.value : '')).join('; ') || 'No values supplied']));
    if (Array.isArray(overlap.shared_interpro_ids)) add(box, 'p', 'InterPro identifiers also returned by the sequence lookup: ' + (overlap.shared_interpro_ids.join(', ') || 'None in this response'));
    const annotations = context.sequence_annotations || [];
    const positions = details(box, 'Pharos sequence-annotation records (' + annotations.length + ')');
    add(positions, 'p', 'Native annotation types remain literal. A sequence annotation is not automatically a domain or an independently verified experiment.', 'small');
    table(positions, ['Native type', 'Native name', 'Start', 'End'], annotations.map(a => [a.type, a.name, a.startResidue, a.endResidue]));
  }
  function renderLineage(parent, lineage) {
    const records = lineage?.records || [], box = details(parent, 'Native GOA mapping lineage (' + records.length + ')');
    add(box, 'p', 'InterPro2GO feeds GOA as electronic annotation. Shared entry identifiers trace annotation context; they do not supply another independent experiment or identify the historical Pharos record. OR alternatives and AND groups stay intact.', 'small');
    add(box, 'p', 'Lookup state: ' + ({native_source_lineage_available: 'Verified saved rows available',
      not_configured: 'Native GOA source not supplied for this selection'}[lineage?.status] || literal(lineage?.status)));
    for (const item of records) {
      const r = item.native_record, record = details(box, [r.go_id, r.negated ? 'NOT' : 'Positive polarity', r.evidence_code, r.id].join(' · '));
      table(record, ['Native field', 'Value'], [
        ['Relation / qualifier', [r.relation_literal, ...(r.qualifier_tokens || [])].join(' · ')],
        ['References', (r.reference_identifiers || []).join('; ')],
        ['Product form', r.gene_product_form_id || 'No form supplied'],
        ['Mapping lineage', ({shared_interpro_identifier_in_IEA_chain: 'Shared entry identifier in an IEA / InterPro2GO chain',
          shared_interpro_identifier_only: 'Shared entry identifier; InterPro2GO derivation not established',
          no_shared_interpro_identifier: 'No shared InterPro identifier in this row'}[item.derivation_status] || literal(item.derivation_status))],
        ['IEA / InterPro2GO reference chain', typeof item.interpro2go_reference_chain === 'boolean' ? String(item.interpro2go_reference_chain) : 'Not supplied'],
        ['Coordinate/form compatibility', item.sequence_form_compatibility],
        ['Taxon', (r.taxon_ids || []).join('; ')],
        ['Assigned by / date', literal(r.assigned_by) + ' · ' + literal(r.annotation_date)],
        ['Native row', literal(r.source_line) + ' · GAF SHA256 ' + literal(r.source_gaf_sha256)],
        ['Annotation extension', r.annotation_extension_raw || 'No value supplied']]);
      for (const [i, group] of (item.with_from_groups || []).entries()) {
        add(record, 'p', 'Alternative ' + (i + 1) + ': ' + group.members.join(' AND '));
        const coverage = {complete_group: 'All identifiers in this alternative matched', partial_group: 'Partial identifier coverage',
          unmatched_group: 'No matched InterPro identifier'}[group.status] || literal(group.status);
        add(record, 'p', coverage + ' · Matched entry IDs: ' + (group.matched_interpro_ids.join(', ') || 'None'), 'small');
      }
      add(record, 'p', 'Identifiers and mappings are source context. Full-record identity and reference independence remain unresolved.', 'small');
    }
  }
  function renderEntryMetadata(parent, result) {
    const records = result.entry_metadata || [];
    const box = details(parent, 'Entry currency and annotation method (' + records.length + ' inspected)');
    add(box, 'p', 'Only explicitly inspected entries have metadata here. Entry retirement concerns a source identifier; it does not establish loss of the protein, its function or its interaction. Editorial flags describe the entry annotation, not the accuracy of a sequence match.', 'small');
    if (!records.length) {add(box, 'p', 'No entry lifecycle or editorial metadata was captured. No review status is inferred from an integrated entry label.'); return;}
    for (const record of records) {
      const body = record.native_record || {}, metadata = record.http_status === 200 ? (body.metadata || {}) : body;
      const item = add(box, 'section', null, 'source-record');
      const heading = add(item, 'p'); entryLink(heading, record.interpro_id);
      if (record.http_status === 410) {
        add(item, 'p', 'Retired source entry · deletion date: ' + literal(metadata.deletion_date), 'notice warn');
        add(item, 'p', 'The source record is preserved. No replacement identifier or graph change is inferred.');
      } else {
        add(item, 'p', 'Entry available when retrieved: ' + literal(record.retrieved_at));
        const flag = key => typeof metadata[key] === 'boolean' ? String(metadata[key]) : 'Not supplied';
        table(item, ['Native editorial flag', 'Recorded value'], [
          ['is_llm', flag('is_llm')], ['is_reviewed_llm', flag('is_reviewed_llm')], ['is_updated_llm', flag('is_updated_llm')]]);
        if (metadata.is_llm === true && metadata.is_reviewed_llm === false)
          add(item, 'p', 'The source flags this entry annotation as AI-generated and not yet reviewed. It is not an additional independent biological confirmation.', 'notice warn');
      }
      const raw = details(item, 'Complete native entry metadata');
      add(raw, 'pre', JSON.stringify(body, null, 2));
      add(raw, 'p', 'Saved source locator: ' + literal(record.source_pointer), 'small');
    }
  }
  function render(parent, result) {
    parent.replaceChildren();
    const seq = result.sequence || {}, versions = result.releases || {};
    add(parent, 'h4', result.protein + ' · saved sequence context');
    add(parent, 'p', 'Sequence length: ' + literal(seq.length) + ' residues · MD5: ' + literal(seq.md5));
    add(parent, 'p', 'Sequence retrieved from Pharos: ' + literal(seq.retrieved_at) + '. Positions are 1-based, inclusive and apply to that sequence. Historical graph-sequence identity has not been established; no mapping to an assay construct or another isoform is inferred.', 'small');
    add(parent, 'p', 'Pharos database: ' + literal(versions.pharos_database) + ' · InterPro release: ' + literal(versions.interpro_before?.release) + ' · Matches API: ' + literal(versions.interpro_before?.api));
    add(parent, 'p', 'Source annotations and computational matches; no function, interaction or review decision is accepted by this view.', 'notice');
    for (const warning of result.warnings || []) add(parent, 'p', warning, 'notice warn');
    const retired = (result.entry_metadata || []).filter(r => r.http_status === 410).length;
    const generated = (result.entry_metadata || []).filter(r => r.http_status === 200 && r.native_record?.metadata?.is_llm === true && r.native_record?.metadata?.is_reviewed_llm === false).length;
    if (retired) add(parent, 'p', retired + ' inspected source ' + (retired === 1 ? 'entry is' : 'entries are') + ' retired. Open “Entry currency and annotation method” below for the native record; no replacement is inferred.', 'notice warn');
    if (generated) add(parent, 'p', generated + ' inspected entry ' + (generated === 1 ? 'annotation is' : 'annotations are') + ' flagged as AI-generated and not yet reviewed. Native metadata is preserved below.', 'notice warn');
    if (seq.status !== 'sequence_available') {
      add(parent, 'p', 'No usable source sequence was available. No cross-version coordinate mapping was inferred.');
    } else if (result.precomputed_found === false) {
      add(parent, 'p', 'The exact sequence was not present in the precomputed lookup. This is not evidence that the protein lacks domains or functions.');
    } else if (!(result.matches || []).length) {
      add(parent, 'p', 'No matches were supplied for this indexed sequence. This does not establish biological absence.');
    } else {
      const label = add(parent, 'label', 'Filter integrated entries and signatures');
      const filter = add(label, 'input'); filter.type = 'search'; filter.maxLength = 120;
      const groups = add(parent, 'div');
      const update = () => {groups.replaceChildren(); renderGroups(groups, result.matches, filter.value || '');};
      filter.oninput = update; update(); renderSites(parent, result.matches); renderOther(parent, result.matches);
    }
    renderPharos(parent, result); renderEntryMetadata(parent, result); renderLineage(parent, result.goa_lineage);
    const scope = details(parent, 'Context source and limits');
    add(scope, 'p', 'Saved context: ' + result.context_id + ' · ' + literal(versions.context_created_at));
    add(scope, 'p', 'Sequence SHA256: ' + literal(seq.sha256));
    for (const key of ['pharos', 'sequence', 'interpro'])
      if (result.attribution?.[key]) add(scope, 'p', result.attribution[key], 'small');
    for (const limit of result.limitations || []) add(scope, 'p', limit, 'small');
  }
  function panel(guide, options) {
    const meta = guide.protein_context;
    if (!meta?.configured || !meta.eligible || !Array.isArray(meta.proteins) || !meta.proteins.length) return null;
    const box = make('details'); add(box, 'summary', 'Protein sequence & domain context');
    add(box, 'p', 'Inspect preserved sequence-matched source detail. This reads saved records and makes no model call or fresh source request.', 'small');
    const label = add(box, 'label', 'Exact protein'), select = add(label, 'select');
    for (const row of meta.proteins) {
      const option = add(select, 'option', options.labelForProtein?.(row.protein) || row.label || row.protein); option.value = row.protein;
    }
    const button = add(box, 'button', 'Inspect saved domains and sites', 'secondary'); button.type = 'button';
    const status = add(box, 'p', '', 'small'); status.setAttribute('role', 'status');
    const output = add(box, 'div'); let request = 0;
    select.onchange = () => {request++; output.replaceChildren(); status.textContent = ''; button.disabled = false;};
    button.onclick = async () => {
      if (!options.isCurrent()) return;
      const selected = select.value, context = meta.proteins.find(row => row.protein === selected), round = ++request;
      button.disabled = true; output.replaceChildren(); status.textContent = 'Reading preserved protein context…';
      const current = () => options.isCurrent() && round === request && select.value === selected;
      try {
        const result = await options.api('/api/protein-context', {run_id: guide.source_run,
          selection_id: guide.selection.id, protein: selected});
        if (!current()) return;
        if (result.format !== 'biograph-steward.protein-context-selection.v1' || result.source_run !== guide.source_run ||
            result.selection_id !== guide.selection.id || result.snapshot_sha256 !== guide.snapshot_sha256 ||
            result.graph_basis_sha256 !== guide.graph_basis_sha256 || result.protein !== selected ||
            !context || result.context_id !== context.context_id || result.context_manifest_sha256 !== context.manifest_sha256 || result.read_only !== true ||
            result.source_fetches !== 0 || result.model_calls !== 0 || result.source_graph_changed !== false || !Array.isArray(result.matches))
          throw new Error('Saved protein context does not match this selected source and protein.');
        render(output, result); status.textContent = 'Saved source context displayed. The graph, scores and review decisions are unchanged.';
      } catch (error) {if (current()) status.textContent = 'Protein context remains unresolved: ' + error.message;}
      finally {if (current()) button.disabled = false;}
    };
    return box;
  }
  window.ProteinContext = {panel, render};
}());
