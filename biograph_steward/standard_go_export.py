"""Opt-in, source-preserving KGX projection of qualified native GO records.

The Reactome default remains separate. Only four reviewed relation mappings
and two registered assigning sources are admitted; unsupported records remain
in the complete source packet and mapping ledger, never biologically pruned.
"""
from copy import deepcopy
from pathlib import Path
import re

from .client import digest
from .goa_source import POLICY, validate_native_record
from .goa_questions import _record
from .normalization import GO_CATEGORIES
from .standard_export import _finish_projection
from .standards_validation import MODEL_VERSION, RESOURCE_HASHES

PROFILE='biograph-steward.kgx-qualified-native-go.v1'
SCOPE=('Only positive, source-replayed native GO annotations with one of four reviewed relations, '
       'an exact mapped protein/GO endpoint, no annotation extension or distinct product identifier, '
       'and registered assigning-source provenance are projected when the pinned supported BMT type check passes. '
       'The enables mapping is withheld under the current model constraint. All other source records and '
       'qualifications remain in the complete source packet/ledger. Source assertions remain subject '
       'to local review; this is not biological validation or full standard conformance.')
RELATIONS={
    'enables':('biolink:enables','RO:0002327','F'),
    'located_in':('biolink:located_in','RO:0001025','C'),
    'involved_in':('biolink:actively_involved_in','RO:0002331','P'),
    'acts_upstream_of':('biolink:acts_upstream_of','RO:0002263','P'),
}
ASSIGNERS={'BHF-UCL':'infores:bhf-ucl','MGI':'infores:mgi'}
REGISTRY_SHA256='f1691165e038d8f404ce4780e16506e29e1a3ac9c688c766eb84ae4a292f2e7a'


def mapping_contract():
    return {'profile':PROFILE,'biolink_model_version':MODEL_VERSION,
        'biolink_model_sha256':RESOURCE_HASHES['biolink-model.yaml'],
        'biolink_source':'https://github.com/biolink/biolink-model/blob/v4.4.6/biolink-model.yaml',
        'GAF_specification':'https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/',
        'relations':{r:{'predicate':p,'exact_RO_mapping':ro,'aspect':a} for r,(p,ro,a) in RELATIONS.items()},
        'pinned_model_constraint':{'excluded_relation':'enables',
            'reason':'BMT1.4.8 validate_edge(Protein,enables,MolecularActivity) returns false for Biolink4.4.6, including all mixins.',
            'supported_runtime_sensitivity':'Same result with biolink-model4.4.6 and linkml-runtime1.11.1.',
            'latest_release_checked':'https://github.com/biolink/biolink-model/releases/tag/v4.4.6',
            'source_meaning_not_changed':'The exact RO mapping is preserved in this contract and native sidecar; no category or predicate is weakened.'},
        'assigning_sources':deepcopy(ASSIGNERS),
        'GO_assigning_database_registry':{
            'url':'https://raw.githubusercontent.com/geneontology/go-site/master/metadata/db-xrefs.yaml',
            'reviewed_snapshot_sha256':'18102c84f89036897d325a1447a261c0faf557b6d5cae2391e222dc703cabe90'},
        'information_resource_registry':{'url':'https://raw.githubusercontent.com/biolink/information-resource-registry/main/infores_catalog.yaml',
            'retrieved_snapshot_sha256':REGISTRY_SHA256,'GOA_aggregator':'infores:goa',
            'unregistered_CAFA_assigner_not_invented':True,
            'NTNU_SB_not_equated_to_differently_scoped_IMEx_NTNU_resource':True},
        'unknown_relations_contexts_and_assigners':'unsupported; preserved in source packet and sidecar',
        'knowledge_level_and_agent_type':'not_provided; do not infer curation mechanism or local acceptance'}


def project_graph(graph):
    nodes={r['id']:r for r in graph['nodes']};assertions={r['id']:r for r in graph['assertions']}
    original_edges={r['id']:r for r in graph['edges']}
    primary={r['id'] for r in graph.get('targets',[]) if isinstance(r,dict)}
    edges=[];ledger=[];sidecar=[]
    for edge in graph['edges']:
        assertion=assertions[edge['assertion_id']];reasons=[];native=None;predicate=None
        if edge.get('record_kind')!='native_go_annotation':
            reasons.append('non_native_go_record_outside_this_profile')
        else:
            native=deepcopy(edge.get('evidence_record',{}).get('native_record'))
            sidecar.append({'source_edge_id':edge['id'],'source_assertion_id':assertion['id'],
                'source_edge_sha256':digest(edge),'native_record':deepcopy(native)})
            try:validate_native_record(native)
            except (ValueError,TypeError):reasons.append('outside_existing_native_positive_context_gate')
            if not reasons:
                relation=native['relation_literal'];mapping=RELATIONS.get(relation)
                if mapping is None:reasons.append('native_relation_outside_four_reviewed_RO_mappings')
                elif native['aspect']!=mapping[2]:reasons.append('native_relation_aspect_mismatch')
                else:predicate=mapping[0]
                if relation=='enables':
                    reasons.append('pinned_Biolink_Protein_enables_domain_incompatible_under_supported_BMT_API')
                if native['assigned_by'] not in ASSIGNERS:reasons.append('assigning_database_without_reviewed_registered_infores_mapping')
                if native['annotation_extension_raw'] or native['gene_product_form_id'] not in (None,native['subject']):
                    reasons.append('native_extension_or_different_product_identifier_requires_separate_mapping')
                subject=nodes.get(edge['subject'],{});obj=nodes.get(edge['object'],{})
                if (subject.get('category')!='biolink:Protein' or subject.get('identifier_mapped') is not True
                        or not re.fullmatch(r'UniProtKB:[A-Z0-9]+',edge['subject'])):
                    reasons.append('exact_mapped_protein_endpoint_required')
                if (obj.get('category')!=GO_CATEGORIES[native['aspect']] or obj.get('identifier_mapped') is not True
                        or not re.fullmatch(r'GO:[0-9]{7}',edge['object'])):
                    reasons.append('exact_mapped_GO_aspect_endpoint_required')
                if assertion.get('lifecycle_state') not in {'candidate','provisional','accepted'}:
                    reasons.append('local_review_state_excluded_from_inspectable_projection')
                # Reuse the existing complete annotation/assertion replay rather
                # than inventing a second native relation or source validator.
                if not reasons:
                    _record(edge['evidence_record'],graph,nodes,original_edges,assertions,primary,
                            edge['extension_publication_sha256'],POLICY)
        ledger.append({'source_edge_id':edge['id'],'source_assertion_id':assertion['id'],
            'source_kind':edge.get('record_kind'),'status':'excluded' if reasons else 'represented',
            'reasons':reasons,'projection_edge_id':None if reasons else edge['id'],
            'source_edge_sha256':digest(edge),'source_assertion_sha256':digest(assertion)})
        if not reasons:
            edges.append({'id':edge['id'],'subject':edge['subject'],'predicate':predicate,'object':edge['object'],
                'primary_knowledge_source':ASSIGNERS[native['assigned_by']],
                'aggregator_knowledge_source':['infores:goa'],
                'publications':deepcopy(native['reference_identifiers']),
                'knowledge_level':'not_provided','agent_type':'not_provided'})
    projection=_finish_projection(graph,edges,ledger,PROFILE)
    projection['native_go_records']=sidecar
    return projection


if __name__=='__main__':
    import argparse
    from .standard_export import export_standard
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet',required=True);parser.add_argument('--resources',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    print(export_standard(Path(args.packet),Path(args.out),Path(args.resources),profile=PROFILE))
