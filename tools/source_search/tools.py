"""Allowlisted BioMCP PubMed search and existing exact-PMID XML inspection.

Native JSON is kept intact alongside its bounded model-facing projection.
The immutable cache binds query, provider, binary, source helper and parser.
Native subprocess executions are not misreported as exact HTTP request counts.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError,URLError

from biograph_steward import literature
from biograph_steward.client import digest,utcnow,write_json
from biograph_steward.file_utils import sha
from .prepare import need,read_sealed,seal,native_environment

PMID=re.compile(r'[1-9][0-9]{0,9}')
MAX_NATIVE_BYTES=2000000


class SourceInputError(ValueError):
    """A bounded unsupported query, distinct from file/hash corruption."""


def checked_query(value):
    # Pass ordinary biomedical bracket/colon/URL text to the native parser.
    # Arguments are a list, never a shell command; there is no URL-fetch tool.
    if not(isinstance(value,str)and bool(value.strip())and len(value)<=2000 and '\x00'not in value):
        raise SourceInputError('Source search: unsupported empty/NUL/over2000character query.')
    return value


def search_projection(native):
    """Project a verified native JSON shape; unknown shapes fail, never guess."""
    need(isinstance(native,dict),'native search result is not an object.')
    # Exact native envelope/fields are qualified on the excluded manual query.
    need(isinstance(native.get('results'),list),'unqualified native search JSON shape.')
    plan=native.get('source_plan')
    need(isinstance(plan,dict)and plan.get('candidate_sources')==['pubmed']and plan.get('enrichment_sources')==[],
         'native evidence-provider plan differs from the fixed PubMed-only contract.')
    candidates=[];seen=set()
    for row in native['results']:
        need(isinstance(row,dict),'native candidate is not an object.')
        pmid=row.get('pmid')
        if pmid is None:continue
        need(isinstance(pmid,str)and PMID.fullmatch(pmid)and pmid not in seen,'native candidate PMID is malformed/duplicate.')
        need(row.get('source')=='pubmed'and row.get('matched_sources')==['pubmed'],
             'native candidate source differs from PubMed-only evidence.')
        seen.add(pmid)
        candidate={'pmid':pmid}
        for field in ('title','journal','date','year','doi','abstract','source','matched_sources','authors','is_retracted','ranking'):
            if field in row:candidate[field]=row[field]
        candidates.append(candidate)
    need(len(candidates)<=10,'native candidate limit exceeded.')
    metadata={k:native[k]for k in ('query','sort','source_plan','source_status','ranking_policy','pagination','complete','count','diagnostics','errors','_meta')if k in native}
    return {'candidates':candidates,'native_metadata':metadata,'native_error':native.get('error'),
        'native_status':native.get('status'),'scope':'PubMed source search candidates; relevance and biological entailment are not certified.'}


class SourceTools:
    def __init__(self,qualification,qualification_sha256,cache,*,runner=None,fetcher=None):
        q=read_sealed(qualification,qualification_sha256)
        need(q['format']=='biograph-steward.biomcp-binary-qualification.v1','unsupported binary receipt.')
        self.binary=Path(q['binary']['file']);self.binary_sha=q['binary']['sha256']
        need(self.binary.is_file()and not self.binary.is_symlink()and sha(self.binary)==self.binary_sha,'qualified binary changed.')
        self.qualification_sha256=qualification_sha256;self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.runner=runner or self._native;self.fetcher=fetcher or literature.fetch
        self.calls=[]
        self.pins={'binary_sha256':self.binary_sha,'adapter_sha256':sha(__file__),
            'native_environment_helper_sha256':sha(Path(__file__).with_name('prepare.py')),
            'pubmed_fetch_and_parser_sha256':sha(literature.__file__)}

    def _native(self,args,folder):
        stdout=folder/'native.stdout.json';stderr=folder/'native.stderr.log'
        with stdout.open('xb')as out,stderr.open('xb')as err:
            try:
                result=subprocess.run([str(self.binary),*args],env=native_environment(folder/'state'),stdout=out,stderr=err,timeout=75)
                code=result.returncode;status='returned'
            except subprocess.TimeoutExpired:code=None;status='timeout'
            except OSError as error:
                code=None;status='process_unavailable';err.write(json.dumps({'error_type':type(error).__name__}).encode())
        if stdout.stat().st_size>MAX_NATIVE_BYTES or stderr.stat().st_size>MAX_NATIVE_BYTES:
            return {'exit_code':code,'process_status':'output_bound_exceeded','stdout':b'','stderr':b''}
        return {'exit_code':code,'process_status':status,'stdout':stdout.read_bytes(),'stderr':stderr.read_bytes()}

    def _cached(self,kind,args,execute):
        need(self.binary.is_file()and not self.binary.is_symlink()and sha(self.binary)==self.binary_sha,'qualified binary changed during execution.')
        request={'tool':kind,'arguments':args,'source':'pubmed','pins':self.pins};key=digest(request);folder=self.cache/key
        if folder.exists():
            need(not folder.is_symlink(),'cache directory cannot be a symlink.')
            report=json.loads((folder/'result.json').read_text())
            need(report.get('content_sha256')==digest({k:v for k,v in report.items()if k!='content_sha256'})
                 and report['request']==request,'cached response identity differs.')
            for name,expected in report['files'].items():need(sha(folder/name)==expected,'cached native body changed.')
            cache_hit=True
        else:
            folder.mkdir();started=time.perf_counter();value=execute(folder)
            report=seal({'format':'biograph-steward.source-search-tool-cache.v1','created_at':utcnow(),'request':request,
                'result':value,'elapsed_seconds':time.perf_counter()-started,
                'files':{p.name:sha(p)for p in folder.iterdir()if p.is_file()},
                'exact_upstream_HTTP_request_count':None,
                'http_count_note':'Native provider retries and exchanges are not exposed as an exact request count; process executions are recorded separately.'})
            write_json(folder/'result.json',report);cache_hit=False
        event={'tool':kind,'cache_key':key,'cache_hit':cache_hit,'result_content_sha256':report['content_sha256'],
            'native_process_executions':int(kind=='search_pubmed'and not cache_hit),
            'direct_fetch_invocations':int(kind=='get_abstract'and not cache_hit),'upstream_HTTP_request_count':None}
        self.calls.append(event)
        return {**report['result'],'cache':event}

    def search(self,query):
        checked_query(query)
        def execute(folder):
            # Native short-keyword suggestions otherwise call EBI OLS4 even
            # when article source_plan reports PubMed with no enrichment.
            args=['--json','--no-cache','--disable-sources','ols4','search','article','--source','pubmed','--keyword',query,'--limit','10','--full']
            raw=self.runner(args,folder)
            # Test injection receives the same immutable body file contract.
            for key,name in [('stdout','native.stdout.json'),('stderr','native.stderr.log')]:
                if not (folder/name).exists():(folder/name).write_bytes(raw[key])
            try:native=json.loads(raw['stdout'])
            except (ValueError,UnicodeDecodeError):
                return {'tool':'search_pubmed','query':query,'status':'unavailable','candidates':[],
                    'reason':'native non-JSON/timeout/process failure','exit_code':raw['exit_code'],'native_process_status':raw['process_status']}
            try:projected=search_projection(native)
            except ValueError:
                return {'tool':'search_pubmed','query':query,'status':'unavailable','candidates':[],
                    'reason':'native JSON shape/provider plan not qualified','exit_code':raw['exit_code'],
                    'native_process_status':raw['process_status'],'native_error':native.get('error')if isinstance(native,dict)else None,
                    'native_body_sha256':sha(folder/'native.stdout.json')}
            complete=native.get('complete')is True
            failure=bool(native.get('error'))or bool(native.get('errors'))or raw['exit_code']!=0
            declared_status=native.get('status')
            if isinstance(declared_status,str)and declared_status.lower()in {'error','unavailable','failed','partial','incomplete'}:failure=True
            if complete and not failure:status='completed'if projected['candidates']else 'completed_empty'
            else:status='partial'if projected['candidates']else 'unavailable'
            return {'tool':'search_pubmed','query':query,'status':status,**projected,'exit_code':raw['exit_code'],
                'native_process_status':raw['process_status'],'native_body_sha256':sha(folder/'native.stdout.json')}
        return self._cached('search_pubmed',{'query':query,'limit':10},execute)

    def get(self,pmid):
        need(isinstance(pmid,str)and PMID.fullmatch(pmid),'exact PubMed ID required.')
        def execute(folder):
            url=literature.PUBMED+pmid
            try:
                raw=self.fetcher(url);need(isinstance(raw,bytes)and len(raw)<=20000000,'invalid bounded PubMed source body.')
                (folder/'pubmed.xml').write_bytes(raw);rows=literature.parse_pubmed(raw)
                need(set(rows)<={pmid},'PubMed returned an unrequested article.')
                record=rows.get(pmid)
                return {'tool':'get_abstract','pmid':pmid,'status':'completed'if record else 'empty','source_url':url,
                    'record':record,'identity_resolved':bool(record),'full_text_fetched':False,
                    'interpretation':'Exact source title/abstract and locators; PMID validity is not claim entailment.'}
            except (HTTPError,URLError,OSError,ValueError)as error:
                return {'tool':'get_abstract','pmid':pmid,'status':'unavailable','record':None,'identity_resolved':False,
                    'error_type':type(error).__name__,'source_url':url,'full_text_fetched':False}
        return self._cached('get_abstract',{'pmid':pmid},execute)
