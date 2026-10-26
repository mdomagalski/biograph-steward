#!/usr/bin/env python3
"""Publish the consumed assay panel as source-qualified observations, not new gold."""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import assess_lambourne_corroboration as assessment
from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import sha
from biograph_steward.gold_packet import _decode
from biograph_steward.lambourne_evidence import build_evidence

FORMAT = 'biograph-steward.lambourne-evidence-publication.v1'
MANIFEST = 'publication.json'
CODE = ('scripts/publish_lambourne_evidence.py',
        'biograph_steward/lambourne_evidence.py',
        'biograph_steward/assertions.py', 'biograph_steward/graph.py')


def _code():
    return {name: sha(ROOT / name) for name in CODE}


def _inputs(freeze, results):
    """Reuse the completed assessment's source/label verifier without relabeling."""
    report = assessment.verify(freeze, results)
    protocol, frozen = assessment.capture_bundle(freeze, 'protocol.json')
    captured_report, captured = assessment.capture_bundle(results, 'report.json')
    if captured_report != report:
        raise ValueError('Assessment changed during evidence publication.')
    audit = _decode(captured['assay_audit.json'])
    bindings = {'protocol_sha256': protocol['content_sha256'],
                'result_sha256': report['content_sha256'],
                'source_sha256': audit['source_sha256'],
                'artifact_sha256': {'rows': report['files']['rows.json'],
                                    'lookup': protocol['files']['lookup/pair_lookup.json']}}
    evidence = build_evidence(_decode(captured['rows.json']),
                              _decode(frozen['lookup/pair_lookup.json']), bindings)
    return evidence, protocol, frozen, report, captured


def render_evidence_html(evidence):
    """Offline inspection; never turn assay observations into unqualified paths."""
    records = []
    for observation in evidence['observations']:
        original = observation['original']
        assay, comparator = original['assay'], original['comparator']
        records.append({'id': observation['id'], 'products': assay['products'],
                        'assay': assay, 'comparator': comparator,
                        'lookup': observation['lookup'],
                        'source_locators': observation['source_locators']})
    payload = json.dumps(records, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    summary = escape(json.dumps(evidence['summary'], indent=2))
    return '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioGraph Steward · Assay evidence</title>
<style>
:root{font:16px/1.5 system-ui,sans-serif;color:#192f3d;background:#f3f6f7}*{box-sizing:border-box}
body{margin:0}main{max-width:1250px;margin:auto;padding:28px}h1{font-size:30px;margin:8px 0}h2{font-size:21px}
a{color:#145a84}header,p{max-width:1000px}.note{border-left:4px solid #b97915;background:#fff8e9;padding:14px 18px}
.controls{display:flex;gap:14px;flex-wrap:wrap;padding:18px 0}label{display:grid;gap:5px;font-weight:600;font-size:14px}
input,select,button{font:inherit;padding:9px;border:1px solid #b9c9cf;border-radius:5px;background:white;color:inherit}
button{cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #3082a9}
.layout{display:grid;grid-template-columns:minmax(360px,1fr) minmax(420px,1.2fr);gap:22px}
.card{background:white;border:1px solid #dce4e7;border-radius:10px;padding:20px;min-width:0}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid #e3e9ec;padding:9px}
td button{text-align:left;border:0;padding:3px;color:#145a84}td button[aria-current=true]{font-weight:750;text-decoration:underline}
.pager{display:flex;gap:12px;align-items:center;margin-top:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
dl{display:grid;grid-template-columns:135px 1fr;gap:7px;margin:14px 0}dt{font-weight:650}dd{margin:0;overflow-wrap:anywhere}
svg{width:100%;height:190px;background:#f8fafb;border-radius:8px}details{margin-top:16px}summary{cursor:pointer}
.empty{padding:25px;color:#526775}.small{font-size:13px;color:#526775}#hits{font-weight:650}
@media(max-width:900px){.layout{grid-template-columns:1fr}main{padding:16px}}
</style>
<main><header><div class="small">BIOGRAPH STEWARD · SOURCE-QUALIFIED OBSERVATIONS</div>
<h1>Inspect the assay evidence alongside Pharos</h1>
<p>The published human Y2H-v1 panel is linked to the frozen Pharos PPI lookup.
All nominations remain visible, including failed tests and unresolved proteins.</p>
<p class="note">A detection is an assay-specific observation. Nondetection does not establish biological absence;
a failed assay is not a negative result. Pharos presence is specific to the saved lookup.
This layer has not been independently validated and does not demonstrate improved prediction.</p>
<p><a href="evidence.json">Complete observations and provenance (JSON)</a> ·
<a href="graph.json">Qualified observation graph (JSON)</a> ·
<a href="publication.json">Publication receipt</a> ·
<a href="source/results/report.html">Frozen comparison</a> ·
<a href="https://www.nature.com/articles/s41467-026-70942-x">Original study</a></p></header>
<div class="controls">
<label>Protein accession<input id="protein" placeholder="e.g. P04637" autocomplete="off"></label>
<label>Assay outcome<select id="outcome"><option value="all">All outcomes</option><option value="detected">Detected</option>
<option value="not_detected">Not detected</option><option value="excluded">Excluded / failed assay</option></select></label>
<label>Pharos lookup<select id="lookup"><option value="all">All lookup states</option>
<option value="present_in_raw_ppi">Represented</option><option value="no_match_both_endpoints_resolved">No match, both resolved</option>
<option value="no_match_one_endpoint_resolved">Unresolved endpoint</option></select></label>
<label>Shortcut<button id="missing">Detected + no resolved-profile match</button></label>
</div><p id="hits" role="status" aria-live="polite"></p>
<div class="layout"><section class="card"><h2>Assay observations</h2>
<table><thead><tr><th>Protein pair</th><th>Outcome</th></tr></thead><tbody id="rows"></tbody></table>
<div class="pager"><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button></div>
</section><section class="card" id="detail" aria-label="Selected observation"></section></div>
<details class="card"><summary>Full population accounting</summary><pre>''' + summary + '''</pre></details>
<p class="small">The paper reports IMEx deposition IM-30553. Its records were not available through the checked public queries;
these are source-bound author-table observations, not a claim of IMEx curation or PSI-MI/MITAB conformance.
The assay panel is consumed for future evaluation. Existing Pharos records and review decisions are unchanged.</p>
</main><script type="application/json" id="records">''' + payload + '''</script>
<script>
'use strict';
const records=JSON.parse(document.getElementById('records').textContent), size=25;
let filtered=records, page=0, selected=null;
const byId=id=>document.getElementById(id), label=s=>s.replaceAll('_',' ');
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function link(text,url){const n=el('a',text);n.href=url;return n;}
function field(dl,k,v){dl.append(el('dt',k),el('dd',v));}
function detail(r){selected=r.id;const box=byId('detail');box.replaceChildren(el('h2',r.products.join(' ↔ ')));
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 600 190');
 svg.setAttribute('role','img');svg.setAttribute('aria-label','Two protein nodes linked by a qualified assay observation and the saved Pharos lookup state.');
 function shape(tag,attrs,text){const n=document.createElementNS(svg.namespaceURI,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;svg.append(n);}
 shape('line',{x1:90,y1:75,x2:510,y2:75,stroke:'#527687','stroke-width':2,'stroke-dasharray':r.assay.evaluable?'0':'5 5'});
 shape('text',{x:300,y:55,'text-anchor':'middle',fill:'#192f3d','font-size':15},'Y2H-v1: '+label(r.assay.assay_status));
 shape('text',{x:300,y:140,'text-anchor':'middle',fill:'#526775','font-size':13},'Pharos: '+label(r.comparator.pharos_status));
 r.products.forEach((p,i)=>{const x=i?510:90;shape('circle',{cx:x,cy:75,r:34,fill:'#dcebf1',stroke:'#527687'});shape('text',{x,y:80,'text-anchor':'middle',fill:'#192f3d','font-size':13},p);});
 box.append(svg);
 const dl=el('dl');field(dl,'Observation',label(r.assay.assay_status));field(dl,'Eligibility',r.assay.evaluable?'Evaluable in this assay':'Excluded from assay comparison');
 field(dl,'Original result',r.assay.published_result);field(dl,'AD construct','CCSB ORF '+r.assay.ad_orf_id+' (activation-domain role)');
 field(dl,'DB construct','CCSB ORF '+r.assay.db_orf_id+' (DNA-binding-domain role)');
 field(dl,'Confirmation',r.assay.required_confirmation+'; 3AT='+String(r.assay.confirmation_3at)+'; LW='+String(r.assay.confirmation_lw));
 field(dl,'Source providers',r.comparator.provider_bundles.join('; ')||'No returned pair record');
 field(dl,'Prior overlaps','HuRI: '+String(r.comparator.huri_overlap)+'; INMC: '+String(r.comparator.inmc_overlap));
 field(dl,'Local review','Candidate; no automatic acceptance');box.append(dl);
 box.append(el('p','The sorted protein order does not assign AD/DB roles. Original construct IDs and their crosswalk are preserved.'));
 const p=el('p');r.products.forEach((a,i)=>{if(i)p.append(document.createTextNode(' · '));p.append(link(a+' in UniProt','https://www.uniprot.org/uniprotkb/'+encodeURIComponent(a)));});box.append(p);
 const sources=el('p');sources.append(link('Published assay table','source/freeze/source/panel.tsv'),document.createTextNode(' · '),link('Raw author assay','source/freeze/source/raw_human.tsv'),document.createTextNode(' · '),link('Construct crosswalk','source/freeze/source/orf_map.tsv'));box.append(sources);
 for(const [name,data]of [['Exact source locators',r.source_locators],['Original assay and comparison', {assay:r.assay,comparator:r.comparator}],['Original Pharos lookup evidence',r.lookup]]){
  const d=el('details');d.append(el('summary',name),el('pre',JSON.stringify(data,null,2)));box.append(d);}
 document.querySelectorAll('#rows button').forEach(b=>b.setAttribute('aria-current',String(b.dataset.id===r.id)));
}
function render(){byId('hits').textContent=filtered.length+' of '+records.length+' observations shown. Filters do not change the saved population.';
 const body=byId('rows');body.replaceChildren();for(const r of filtered.slice(page*size,(page+1)*size)){
 const tr=el('tr'),td=el('td'),b=el('button',r.products.join(' ↔ '));b.dataset.id=r.id;b.setAttribute('aria-current',String(r.id===selected));b.onclick=()=>detail(r);td.append(b);tr.append(td,el('td',label(r.assay.assay_status)));body.append(tr);}
 byId('page').textContent=filtered.length?('Page '+(page+1)+' / '+Math.ceil(filtered.length/size)):'No matches';byId('prev').disabled=page===0;byId('next').disabled=(page+1)*size>=filtered.length;
 if(!filtered.length){byId('detail').replaceChildren(el('p','No observations match these filters.'));selected=null;}
 else if(!filtered.some(r=>r.id===selected))detail(filtered[page*size]);
}
function filter(){const q=byId('protein').value.trim().toUpperCase().replace('UNIPROTKB:',''),s=byId('outcome').value,l=byId('lookup').value;
 filtered=records.filter(r=>(!q||r.products.some(p=>p.toUpperCase().includes(q)))&&(s==='all'||(s==='excluded'?!r.assay.evaluable:r.assay.assay_status===s))&&(l==='all'||r.comparator.pharos_status===l));page=0;render();}
['protein','outcome','lookup'].forEach(id=>byId(id).addEventListener('input',filter));
byId('missing').onclick=()=>{byId('protein').value='';byId('outcome').value='detected';byId('lookup').value='no_match_both_endpoints_resolved';filter();};
byId('prev').onclick=()=>{page--;render();};byId('next').onclick=()=>{page++;render();};render();
</script></html>'''


def publish(freeze, results, output):
    freeze, results, output = (Path(p).absolute() for p in (freeze, results, output))
    if output.exists() or output.is_symlink() or any(
            output.resolve() == source.resolve() or source.resolve() in output.resolve().parents
            or output.resolve() in source.resolve().parents for source in (freeze, results)):
        raise ValueError('Choose a new immutable output outside input directories.')
    evidence, protocol, frozen, report, captured = _inputs(freeze, results)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.assay-evidence-', dir=output.parent))
    try:
        for prefix, receipt, files, name in (
                ('source/freeze', protocol, frozen, 'protocol.json'),
                ('source/results', report, captured, 'report.json')):
            folder = stage / prefix
            folder.mkdir(parents=True)
            # Preserve original bytes, including the receipt representation.
            origin = freeze if name == 'protocol.json' else results
            (folder / name).write_bytes(assessment.ordinary(origin / name))
            for rel, raw in files.items():
                path = folder / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        write_json(stage / 'evidence.json', evidence)
        write_json(stage / 'graph.json', evidence['graph'])
        (stage / 'index.html').write_text(render_evidence_html(evidence), encoding='utf-8')
        manifest = assessment.seal({'format': FORMAT, 'created_at': utcnow(),
            'bindings': evidence['bindings'], 'summary': evidence['summary'],
            'implementation_sha256': _code(),
            'baseline_modified': False, 'automatic_pruning': False,
            'independent_validation_performed': False,
            'standard_conformance_claimed': False,
            'files': assessment.file_inventory(stage, MANIFEST)})
        write_json(stage / MANIFEST, manifest)
        verify(stage)
        if output.exists():
            raise ValueError('Publication output appeared during staging.')
        stage.rename(output)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify(output):
    output = Path(output)
    manifest, files = assessment.capture_bundle(output, MANIFEST)
    if (manifest.get('format') != FORMAT or manifest.get('implementation_sha256') != _code()
            or any(manifest.get(k) is not False for k in ('baseline_modified', 'automatic_pruning',
                       'independent_validation_performed', 'standard_conformance_claimed'))):
        raise ValueError('Publication implementation or interpretation changed.')
    evidence, *_ = _inputs(output / 'source/freeze', output / 'source/results')
    if (evidence != _decode(files['evidence.json'])
            or evidence['graph'] != _decode(files['graph.json'])
            or evidence['summary'] != manifest.get('summary')
            or evidence['bindings'] != manifest.get('bindings')
            or render_evidence_html(evidence).encode('utf-8') != files['index.html']):
        raise ValueError('Published evidence does not reproduce from original sources.')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    pub = sub.add_parser('publish')
    pub.add_argument('--freeze', type=Path, required=True)
    pub.add_argument('--results', type=Path, required=True)
    pub.add_argument('--out', type=Path, required=True)
    check = sub.add_parser('verify'); check.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    result = publish(args.freeze, args.results, args.out) if args.command == 'publish' else verify(args.out)
    print(json.dumps({'format': result['format'], 'summary': result['summary'],
                      'content_sha256': result['content_sha256']}, indent=2))


if __name__ == '__main__':
    main()
