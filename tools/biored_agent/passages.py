"""Literal source units using the author's existing sentence-boundary helper.

SciFact's official evidence format selects source sentence IDs rather than
generating replacement quotations. Here the unit IDs are mechanical references
to native BioRED text, not gold rationale annotations or proof of entailment.
"""
from pathlib import Path
import sys
from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from .prepare import need


def source_units(document,author_source):
    directory=Path(author_source)/'dataset_format_converter'
    need((directory/'sentence_spliter.py').is_file() and (directory/'document.py').is_file(),
         'author sentence helper is unavailable.')
    sys.path.insert(0,str(directory.resolve()))
    try:
        from sentence_spliter import regex_sentence_boundary_gen
    finally:
        sys.path.pop(0)
    text=document['text'];units=[]
    for start,end in regex_sentence_boundary_gen(text):
        need(type(start) is int and type(end) is int and 0<=start<end<=len(text),'invalid native sentence boundary.')
        native=text[start:end]
        identity={'pmid':document['pmid'],'document_text_sha256':digest(text),'start':start,'end':end}
        units.append({'id':'source-unit:'+digest(identity)[:20],'start':start,'end':end,'text':native,
            'kind':'author_algorithmic_sentence_span','curator_rationale':False})
    need(units and len({u['id'] for u in units})==len(units),'empty or duplicate source units.')
    covered=set(i for u in units for i in range(u['start'],u['end']))
    need(all(i in covered for i,char in enumerate(text) if not char.isspace()),'sentence helper omitted native text.')
    return units,{'method':'official BioREDirect regex_sentence_boundary_gen; unchanged native text slices',
        'helper_sha256':{n:sha(directory/n) for n in ('sentence_spliter.py','document.py')},
        'guiding_reference':'https://github.com/allenai/scifact/blob/master/doc/data.md',
        'gold_rationales':False,'entailment_verified':False}


def resolve_units(document,identifiers):
    need(isinstance(identifiers,list) and len(identifiers)<=3
         and all(isinstance(i,str) for i in identifiers) and len(set(identifiers))==len(identifiers),
         'select at most three distinct provided source units.')
    index={u['id']:u for u in document.get('source_units',[])}
    need(all(i in index for i in identifiers),'unprovided source unit identity.')
    result=[]
    for identifier in identifiers:
        unit=index[identifier]
        need(document['text'][unit['start']:unit['end']]==unit['text'],'source unit no longer reproduces native text.')
        result.append(dict(unit))
    return result
