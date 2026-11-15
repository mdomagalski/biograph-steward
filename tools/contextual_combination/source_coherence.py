# SPDX-License-Identifier: GPL-3.0-only
"""Read-only PK source/known-mask coherence across dated snapshots.

Reuses certified official-parser sidecars and unchanged native reference/GT
helpers. Dates describe source rows, not publication or experimental novelty.
No labels, filters, performance endpoints or model choices are changed.
"""
import argparse
from datetime import datetime
from pathlib import Path
from collections import Counter,defaultdict
import csv,hashlib,json,re
from tools.learned_combination.native_adapter import native_ontologies
from .provenance import load_author,canonical_rows,check_gate,READER_SHA

NAMESPACE_ASPECT={'biological_process':'P','molecular_function':'F','cellular_component':'C'}

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for part in iter(lambda:stream.read(4*1024*1024),b''):h.update(part)
 return h.hexdigest()

def dump(path,value):
 with path.open('x') as stream:json.dump(value,stream,indent=2,sort_keys=True);stream.write('\n')

def context_key(row):return tuple(row['raw_fields'][i] for i in (0,1,3,4,5,6,7,8,12,14,15,16))
def curated(row,accepted):return not row['negated'] and row['evidence_code'] in accepted

def valid_date(value):
 if not isinstance(value,str) or not re.fullmatch(r'[0-9]{8}',value):return False
 try:datetime.strptime(value,'%Y%m%d')
 except ValueError:return False
 return True


def facts(row,matches,accepted,cutoff):
 return {'literal_T0_accession_GO_present':bool(matches),
  'literal_T0_same_pair_curated_positive_before_ontology_filter':any(curated(r,accepted) for r in matches),
  'literal_T0_same_pair_nonreference_positive':any(not r['negated'] and r['evidence_code'] not in accepted for r in matches),
  'literal_T0_same_pair_NOT_context':any(r['negated'] for r in matches),
  'same_evidence_code_and_qualifier_literal_T0':any(r['evidence_code']==row['evidence_code'] and r['raw_fields'][3]==row['raw_fields'][3] for r in matches),
  'same_evidence_qualifier_reference_and_literal_context_T0':any(context_key(r)==context_key(row) for r in matches),
  'exact_native_content_T0':any(r['raw_fields']==row['raw_fields'] for r in matches),
  'exact_native_content_except_annotation_date_T0':any(r['raw_fields'][:13]+r['raw_fields'][14:]==row['raw_fields'][:13]+row['raw_fields'][14:] for r in matches),
  'annotation_date_on_or_before_T0_header':(row.get('annotation_date')<=cutoff if valid_date(row.get('annotation_date')) else None)}

def frame_pairs(path,proteins,aspect):
 result=set()
 with Path(path).open() as stream:
  reader=csv.DictReader(stream,delimiter='\t');assert reader.fieldnames==['EntryID','term','aspect']
  for row in reader:
   if row['EntryID'] in proteins and row['aspect']==aspect:result.add((row['EntryID'],row['term']))
 return result

def mask_value(ground,ontology,protein,term):
 if protein not in ground.ids:return False
 # Preserve pinned gt_parser's PRIMARY-first then alternate-ID behavior.
 labels=[term] if term in ontology.terms_dict else ontology.terms_dict_alt.get(term,())
 return any(bool(ground.matrix[ground.ids[protein],ontology.terms_dict[t]['index']]) for t in labels)


def t0_presence(rows,graph,experimental,propagate,namespace,aspect):
 """Namespace/aspect I/O adaptation of the existing provenance presence view.

 Selection and native propagation are unchanged; only the formerly fixed BPO/P
 container labels are explicit. These are source-context markers,not truth.
 """
 import pandas as pd
 all_positive={};curated_rows={};nonreference={};codes={r['native']['evidence_code'] for r in rows}
 for name,admission in [('any',codes),('curated',experimental|{'IC','TAS'}),('nonreference',codes-experimental-{'IC','TAS'})]:
  selected=[{'EntryID':r['native']['subject'].split(':',1)[1],'term':r['canonical_term'],'aspect':aspect}
   for r in rows if r['canonical_in_view_graph'] and not r['native']['negated'] and r['native']['evidence_code'] in admission and graph.nodes[r['canonical_term']].get('namespace')==namespace]
  if not selected:continue
  frame=propagate(pd.DataFrame(selected),{aspect:graph});target=all_positive if name=='any' else curated_rows if name=='curated' else nonreference
  target.update({(p,t):True for p,t in frame[['EntryID','term']].itertuples(index=False,name=None)})
 return all_positive,curated_rows,nonreference


def known_chain_flags(key,direct,propagated,toi,rawknown):
 return {'T0_native_direct_table_contains_source':key in direct,
  'T0_native_propagated_table_contains_source':key in propagated,
  'T0_source_term_in_classifier_TOI':key[1] in toi,
  'T0_source_term_present_in_raw_PK_known':key in rawknown,
  'T0_propagated_and_classifier_TOI_but_missing_from_PK_known':key in propagated and key[1] in toi and key not in rawknown}


def residual_mask_audit(pairs,gt,excluded,ontology):
 return {'residual_pairs_present_in_exact_parsed_known_exclusion':sum(mask_value(excluded,ontology,p,t) for p,t in pairs),
         'residual_pairs_absent_from_exact_parsed_GT':sum(not mask_value(gt,ontology,p,t) for p,t in pairs)}


def label_date_partition(pairs,source_links,source_rows,cutoff):
 dates=defaultdict(set)
 for identity,links in source_links.items():
  for pair,_ in links:dates[pair].add(source_rows[identity].get('annotation_date'))
 counts=Counter()
 for pair in pairs:
  values=dates[pair]
  if not values or not all(valid_date(value) for value in values):category='unknown_or_invalid_support_date'
  elif all(value<=cutoff for value in values):category='only_on_or_before_T0'
  elif all(value>cutoff for value in values):category='only_after_T0'
  else:category='mixed_on_or_before_and_after_T0'
  counts[category]+=1
 return {'counts':{k:counts[k] for k in ('only_on_or_before_T0','only_after_T0','mixed_on_or_before_and_after_T0','unknown_or_invalid_support_date')},
  'all_residual_positive_pairs':len(pairs),'annotation_date_cutoff':cutoff,
  'definition':'Disjoint counts of ALL residual-positive label pairs by dates of ALL supporting rows; any invalid/missing support date or absent support is unknown. No score/threshold/model filtering.',
  'performance_slice_or_publication_age':False}


def support_row_summary(rows):
 keys=sorted({key for row in rows for key,value in row.items() if type(value) is bool}|{'annotation_date_on_or_before_T0_header'})
 old=[row for row in rows if row.get('annotation_date_on_or_before_T0_header') is True]
 return {'support_audit_status':'eligible_support_present' if rows else 'no_eligible_support_rows',
  'unknown_or_invalid_annotation_date_support_rows':sum(row.get('annotation_date_on_or_before_T0_header') is None for row in rows),
  'all_support_row_boolean_counts':{key:sum(row.get(key) is True for row in rows) for key in keys},
  'old_dated_support_row_boolean_counts':{key:sum(row.get(key) is True for row in old) for key in keys},
  'old_annotation_date_support_rows':len(old)}


def run(config,output):
 assert config['format']=='biograph-steward.postseal-source-coherence.v1'
 gate=dict(config,format='biograph-steward.postseal-provenance.v1');cfg,_=check_gate(gate)
 import networkx as nx
 import obonet
 from cafaeval.parser import gt_parser,gt_exclude_parser,update_toi
 NS=config['namespace'];aspect=NAMESPACE_ASPECT[NS]
 cutoff=config['annotation_date_cutoff'];assert datetime.strptime(cutoff,'%Y%m%d').strftime('%Y%m%d')==cutoff
 R=Path(config['provenance_results_directory']);OUT=Path(output)
 assert sha(R/'report.json')==config['provenance_report_sha256']
 report=json.loads((R/'report.json').read_text());assert report['forecast_seal_sha256']==config['forecast_seal_sha256']
 from biograph_steward import go_qualification
 assert sha(go_qualification.__file__)==READER_SHA
 required=[str(R/'report.json'),str(R/'T0_native_selected.jsonl'),str(R/'T1_native_selected.jsonl'),config['t0_native_direct_terms'],config['t0_native_propagated_terms'],*config['classifier_toi'].values()]
 required.extend(v['complete_label_support_file'] for v in report['views'].values())
 for view in ('native','fixed_T0'):
  required.extend(str(Path(config['assessment_directory'])/view/'PK'/name) for name in ('truth.tsv','known.tsv'))
  required.extend(cfg['references'][view][role]['file'] for role in ('obo','toi'))
 assert set(required)<=set(config['input_pins'])
 for path,pin in config['input_pins'].items():assert sha(path)==pin
 for row in report['source_receipts'].values():
  assert row['parser']=={'package':'biopython','version':'1.88','function':'Bio.UniProt.GOA.gafiterator'}
 OUT.mkdir(parents=True,exist_ok=False)
 helpers,accepted,experimental,source=load_author(config['democafa_root']);t0obo=cfg['references']['fixed_T0']['obo']['file'];t0graph=helpers['clean_ontology_edges'](obonet.read_obo(t0obo));assert nx.is_directed_acyclic_graph(t0graph)
 cases={};source_ids=set();link_terms={};pairsets={}
 for view in ('native','fixed_T0'):
  spec=report['views'][view];path=Path(spec['complete_label_support_file']);assert sha(path)==spec['sha256'];links=defaultdict(list);pairs=set()
  with path.open() as stream:
   for line in stream:
    row=json.loads(line);pair=(row['accession'],row['GO_ID']);assert pair not in pairs;pairs.add(pair)
    for match in row['positive_support']:links[match['native_record_id']].append((pair,match['canonical_source_term']))
  assert len(links)==spec['aggregate']['distinct_native_support_rows'];source_ids.update(links);cases[view]=links;pairsets[view]=pairs
 t1={}
 with (R/'T1_native_selected.jsonl').open() as stream:
  for line in stream:
   row=json.loads(line)
   if row['id'] in source_ids:t1[row['id']]=row
 assert set(t1)==source_ids
 proteins={row['subject'].split(':',1)[1] for row in t1.values()};t0=[]
 with (R/'T0_native_selected.jsonl').open() as stream:
  for line in stream:
   row=json.loads(line)
   if row['subject'].split(':',1)[1] in proteins:t0.append(row)
 literal=defaultdict(list)
 for row in t0:literal[(row['subject'],row['go_id'])].append(row)
 canon=canonical_rows(t0,t0graph,helpers['replace_alternate_GO_terms']);canon_index=defaultdict(list)
 for row in canon:
  if row['canonical_in_view_graph']:canon_index[(row['native']['subject'],row['canonical_term'])].append(row['native'])
 t0mapped={row['native']['id']:row for row in canonical_rows(list(t1.values()),t0graph,helpers['replace_alternate_GO_terms'])}
 _,t0_curated_closure,t0_nonreference_closure=t0_presence(canon,t0graph,experimental,helpers['propagate_terms'],NS,aspect)
 direct=frame_pairs(config['t0_native_direct_terms'],proteins,aspect);propagated=frame_pairs(config['t0_native_propagated_terms'],proteins,aspect)
 output={'format':'biograph-steward.postseal-source-date-coherence.v1','private_parent_provenance_report_sha256':sha(R/'report.json'),'forecast_seal_sha256':report['forecast_seal_sha256'],'namespace':NS,'native_aspect':aspect,'scope':'Every distinct eligible T1support row for the declared namespace in both native/fixed-T0 PK reference views, regardless of prediction performance.','annotation_date_cutoff':cutoff,'views':{},'new_labels_rules_scores_thresholds_or_model_choices':False,'existing_native_alias_evidence_propagation_and_GT_exclusion_reused':True,'source_policy':source,'chronology':'Separate post-opening descriptive/source-coherence audit after immutable numerical archive preservation.','limits':['Old annotation dates are not proof a row existed in the earlier snapshot.','Observed presence/admission/identifier differences do not establish an underlying curation or biological mechanism.','Source rows and inherited labels are not independent assays; no new accuracy endpoint is computed.','TOI means the original classifier term intersection; evaluation uses the separately frozen primary term mask.']}
 for view in ('native','fixed_T0'):
  refs=cfg['references'][view];ont=update_toi(native_ontologies(refs['obo']['file']),refs['toi']['file']);truth=Path(config['assessment_directory'])/view/'PK/truth.tsv';known_path=truth.with_name('known.tsv');gt=gt_parser(str(truth),ont);ex=gt_exclude_parser(str(known_path),{NS:gt[NS]} if NS in gt else {},ont);o=ont[NS]
  rawknown=frame_pairs(known_path,proteins,aspect)
  classifier_toi=Path(config['classifier_toi'][view]);toi=set(classifier_toi.read_text().splitlines());eval_toi=set(Path(refs['toi']['file']).read_text().splitlines())
  mask_audit=(residual_mask_audit(pairsets[view],gt[NS],ex[NS],o) if NS in gt else {'residual_pairs_present_in_exact_parsed_known_exclusion':0,'residual_pairs_absent_from_exact_parsed_GT':len(pairsets[view])});pair_known=mask_audit['residual_pairs_present_in_exact_parsed_known_exclusion'];pair_not_GT=mask_audit['residual_pairs_absent_from_exact_parsed_GT'];rows=[];categories=Counter();old_categories=Counter();known_chain_discrepancies=0
  for identity,links in sorted(cases[view].items()):
   row=t1[identity];protein=row['subject'].split(':',1)[1];record=facts(row,literal[(row['subject'],row['go_id'])],accepted,cutoff);mapped=t0mapped[identity];term0=mapped['canonical_term'];canonical_matches=canon_index[(row['subject'],term0)] if mapped['canonical_in_view_graph'] else []
   source_terms={term for pair,term in links};assert len(source_terms)==1;term=next(iter(source_terms));key=(protein,term0)
   record.update(T0_graph_native_mapping_active=mapped['canonical_in_view_graph'],T0_graph_curated_alias_pair_present=any(curated(r,accepted) for r in canonical_matches),T0_graph_any_alias_pair_present=bool(canonical_matches),T0_graph_nonreference_alias_pair_present=any(not r['negated'] and r['evidence_code'] not in accepted for r in canonical_matches),T0_graph_curated_closure_contains_source=bool(t0_curated_closure.get(key)),T0_graph_nonreference_closure_contains_source=bool(t0_nonreference_closure.get(key)),T0_native_direct_table_contains_source=key in direct,T0_native_propagated_table_contains_source=key in propagated,T0_source_term_in_classifier_TOI=term0 in toi,T0_source_term_in_evaluation_TOI=term0 in eval_toi,T0_source_term_present_in_raw_PK_known=key in rawknown,view_source_term_differs_from_T0_native_mapping=term!=term0,view_source_term_in_exact_parsed_known_exclusion=mask_value(ex[NS],o,protein,term) if NS in ex else False,supported_residual_pair_links=len(links))
   record.update(known_chain_flags(key,direct,propagated,toi,rawknown))
   known_chain_discrepancies+=record['T0_propagated_and_classifier_TOI_but_missing_from_PK_known']
   if record['literal_T0_same_pair_curated_positive_before_ontology_filter']:category='literal_T0_curated_pair_present_before_ontology_filter'
   elif record['T0_graph_curated_alias_pair_present']:category='T0_native_alias_curated_pair_present'
   elif record['literal_T0_same_pair_nonreference_positive'] or record['T0_graph_nonreference_alias_pair_present']:category='T0_nonreference_positive_pair_without_curated_pair'
   elif record['literal_T0_accession_GO_present']:category='T0_literal_pair_other_context_only'
   elif record['T0_graph_any_alias_pair_present']:category='T0_native_alias_pair_other_context_only'
   else:category='T0_pair_absent_literal_and_T0_native_alias_identity'
   categories[category]+=1
   if record['annotation_date_on_or_before_T0_header']:old_categories[category]+=1
   record.update(native_record_hash=identity,raw_line_sha256=row['raw_line_sha256'],source_annotation_date=row.get('annotation_date'),descriptive_presence_category=category);rows.append(record)
  assert len(rows)==report['views'][view]['aggregate']['distinct_native_support_rows']
  path=OUT/(view+'_private_hashed_row_coherence.jsonl')
  with path.open('x') as stream:
   for row in rows:stream.write(json.dumps(row,sort_keys=True)+'\n')
  row_summary=support_row_summary(rows);bool_counts=row_summary['all_support_row_boolean_counts'];old_bool=row_summary['old_dated_support_row_boolean_counts'];old_count=row_summary['old_annotation_date_support_rows']
  output['views'][view]={'support_rows':len(rows),'support_audit_status':row_summary['support_audit_status'],'unknown_or_invalid_annotation_date_support_rows':row_summary['unknown_or_invalid_annotation_date_support_rows'],'old_annotation_date_support_rows':old_count,'all_support_row_boolean_counts':bool_counts,'old_dated_support_row_boolean_counts':old_bool,'descriptive_presence_categories':dict(categories),'old_dated_presence_categories':dict(old_categories),'residual_positive_pairs_checked':len(pairsets[view]),'residual_pairs_present_in_exact_parsed_known_exclusion':pair_known,'residual_pairs_absent_from_exact_parsed_GT':pair_not_GT,'source_to_PK_known_chain_discrepancies':known_chain_discrepancies,'label_pair_support_date_partition':label_date_partition(pairsets[view],cases[view],t1,cutoff),'private_hashed_cases_sha256':sha(path),'case_details_contain_literal_protein_GO_or_PMID_IDs':False}
  print('SOURCE_DATE_COHERENCE_VIEW',view,json.dumps(output['views'][view],sort_keys=True),flush=True)
 dump(OUT/'aggregate_report.json',output);return output

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();run(json.loads(Path(args.config).read_text()),args.output)


if __name__=='__main__':main()
