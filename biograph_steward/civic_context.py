"""Display existing CIViC record context without extracting new scientific claims."""
from collections import defaultdict
from copy import deepcopy
from html import escape

POLICY = 'civic-record-context.v1'
LEVELS_URL = 'https://docs.civicdb.org/en/latest/model/evidence/level.html'
LEVELS = {'A': 'Validated association', 'B': 'Clinical evidence', 'C': 'Case study',
          'D': 'Preclinical evidence', 'E': 'Inferential association'}
CONTEXT_NOTE = ('Study design, population, co-treatments and assay details are not structured in this extract. '
                'Read each source description and paper. Evidence levels are CIViC categories; '
                'paper verification is not recorded by this display.')


def record_context(edge):
    r = edge['evidence_record']; source = r.get('source') or {}
    therapies = r.get('therapies') or []; interaction = r.get('therapyInteractionType')
    pmid = str(source.get('citationId') or '')
    pubmed = source.get('sourceType') == 'PUBMED' and pmid.isdigit()
    reference = ('PMID:' + pmid if pubmed else 'CIViC.source:' + str(source['id']) if source.get('id') else None)
    separator = ' or ' if interaction == 'SUBSTITUTES' else ' / ' if interaction == 'SEQUENTIAL' else ' + '
    label = separator.join(t['name'] for t in sorted(therapies, key=lambda t: t['id']))
    if len(therapies) == 1:
        note = 'One drug is listed in CIViC; monotherapy is not established by the list.'
    elif interaction == 'SUBSTITUTES':
        note = 'Alternative therapies are listed as substitutes; the set does not resolve individual exposure.'
    elif interaction == 'SEQUENTIAL':
        note = 'The complete sequential therapy set is retained; administration order is not supplied.'
    elif interaction == 'COMBINATION':
        note = 'The complete combination therapy set is retained; an ingredient filter does not isolate a single-drug effect.'
    else:
        note = 'Treatment regimen is unresolved in the structured therapy list.'
    level = r.get('evidenceLevel')
    return {'evidence_id': 'CIViC.evidence:' + str(r['id']), 'evidence_url': 'https://civicdb.org/evidence/' + str(r['id']),
            'edge_id': edge['id'], 'record_locators': deepcopy(edge.get('record_locators', [])),
            'snapshot_sha256': edge['snapshot_sha256'], 'evidence_level': level,
            'evidence_level_label': LEVELS.get(level, 'Unmapped source level'),
            'evidence_direction': r.get('evidenceDirection'), 'significance': r.get('significance'),
            'variant_origin': r.get('variantOrigin'), 'therapy_members': deepcopy(therapies),
            'therapy_interaction': interaction, 'therapy_label': label, 'therapy_scope_note': note,
            'source_reference': reference, 'source_title': source.get('title') or 'Title not supplied',
            'source_citation': source.get('citation'), 'publication_year': source.get('publicationYear'),
            'publication_url': 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/' if pubmed else None,
            'description': r.get('description') or '', 'paper_check': 'not_recorded_in_context_display'}


def context_overview(records):
    # Repeated annotations are counted once per evidence item, not as experiments.
    records = list({r['evidence_id']: r for r in records}.values())
    sources = defaultdict(list)
    for r in records:
        if r['source_reference']: sources[r['source_reference']].append(r['evidence_id'])
    return {'displayed_records': len(records), 'cited_sources': len(sources),
            'unresolved_source_records': sum(not r['source_reference'] for r in records),
            'shared_references': [{'reference': ref, 'evidence_ids': sorted(ids)}
                                  for ref, ids in sorted(sources.items()) if len(ids) > 1],
            'scope_note': 'Counts cover displayed source items. Separate annotations do not establish independent experiments.'}


def citation_context(citation):
    records = [record_context(e) for e in sorted(citation['evidence_records'], key=lambda e: e['evidence_record']['id'])]
    overview = context_overview(records)
    levels = '; '.join(r['evidence_id'] + ' — ' + str(r['evidence_level']) + ' (' + r['evidence_level_label'] + ')' for r in records)
    summary = (f"{overview['displayed_records']} CIViC record(s), {overview['cited_sources']} distinct cited source(s). "
               f"Evidence levels by record: {levels}.")
    if overview['unresolved_source_records']: summary += ' Some source references are unresolved.'
    notes = list(dict.fromkeys(r['therapy_scope_note'] for r in records))
    return {'policy': POLICY, 'summary': summary, 'therapy_notes': notes,
            'context_note': CONTEXT_NOTE, 'level_definitions_url': LEVELS_URL,
            'overview': overview, 'records': records}


def context_text(citation):
    context = citation.get('study_context')
    if not context: return ''
    lines = [f"[{citation['id']}] Source context", context['summary'], *context['therapy_notes'], context['context_note']]
    for group in context['overview']['shared_references']:
        lines.append(group['reference'] + ' is shared by ' + ', '.join(group['evidence_ids']) + '; independent experiment count is unresolved.')
    for r in context['records']:
        lines += [r['evidence_id'] + ' | ' + str(r['source_reference'] or 'Reference unresolved'),
                  r['source_title'], 'CIViC therapy list: ' + r['therapy_label'],
                  'Source description (as reported): ' + r['description'],
                  'Record locator: ' + '; '.join(r['record_locators'])]
    return '\n'.join(lines)


def overview_text(overview):
    lines = [f"Displayed sources: {overview['displayed_records']} CIViC items / {overview['cited_sources']} distinct cited sources. " + overview['scope_note']]
    for group in overview['shared_references']:
        lines.append(group['reference'] + ' is shared by ' + ', '.join(group['evidence_ids']) + '.')
    if overview['unresolved_source_records']:
        lines.append(str(overview['unresolved_source_records']) + ' displayed items have unresolved source references.')
    if not overview['displayed_records']:
        lines.append('No source items are shown in this view. An empty result does not establish biological absence.')
    return '\n'.join(lines)


def overview_html(overview):
    return '<div class="source-context-overview">' + ''.join('<p>' + escape(line, quote=True) + '</p>' for line in overview_text(overview).splitlines()) + '</div>'


def context_html(citation):
    context = citation.get('study_context')
    if not context: return ''
    esc = lambda s: escape(str(s), quote=True)
    records = []
    for r in context['records']:
        publication = (' · <a href="' + esc(r['publication_url']) + '">' + esc(r['source_reference']) + '</a>') if r['publication_url'] else ''
        records.append('<div class="source-record"><p><strong>' + esc(r['evidence_id'] + ' | ' + str(r['evidence_level']) + ' — ' + r['evidence_level_label'])
                       + '</strong></p><p>' + esc(r['source_title']) + '</p><details><summary>Source description and references — ' + esc(r['evidence_id']) + '</summary><p>CIViC therapy list: ' + esc(r['therapy_label']) + '</p>'
                       + '<p>Source description (as reported): ' + esc(r['description']) + '</p>'
                       + '<a href="' + esc(r['evidence_url']) + '">Open CIViC record</a>' + publication
                       + '<p>Record locator: ' + esc('; '.join(r['record_locators'])) + '</p></details></div>')
    shared = ''.join('<p>' + esc(g['reference'] + ' is shared by ' + ', '.join(g['evidence_ids']) + '; independent experiment count is unresolved.') + '</p>' for g in context['overview']['shared_references'])
    return ('<div class="source-context"><p><strong>Source context</strong></p><p>' + esc(context['summary']) + '</p>'
            + ''.join('<p>' + esc(note) + '</p>' for note in context['therapy_notes']) + shared
            + '<p>' + esc(context['context_note']) + ' <a href="' + LEVELS_URL + '">CIViC level definitions</a>.</p>'
            + ''.join(records) + '</div>')
