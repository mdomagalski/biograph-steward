"""Qualify source bytes and project only allowed BioASQ question fields.

The established ijson event parser may internally decode every JSON value.
Only id/body/type are retained, selected, emitted or available to model code.
This is not a claim that the raw reference bytes have never been decoded.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
from urllib.request import Request, urlopen

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import sha

FORMAT='biograph-steward.source-search-question-freeze.v1'
BINARY_RELEASE='https://github.com/genomoncology/biomcp/releases/download/v0.9.3/'
BINARY_NAME='biomcp-darwin-arm64.tar.gz'
BINARY_SHA='e637062c18c6692f3ec49c5847e69b29f6feee7f7909345970bd504d72174994'
BINARY_BYTES=16075492
DATA_URL='https://zenodo.org/api/records/7655130/files/training11b.json/content'
DATA_MD5='fc1fe03831b69157c82a746337c00712'
DATA_BYTES=37639648
SEED='biograph-source-search-20261114-v1'
EXCLUDED_IDS={'5118dd1305c10fae750000010','52bf1b0a03868f1b06000009'}
# Fixed, documented source/format illustrations and the sole manual preflight.
# These are question-text exclusions, never filters on the reference documents.
EXCLUDED_PATTERNS=[
 ('publisher_WDR5_pancreatic',r'\bwdr5\b.*pancrea|pancrea.*\bwdr5\b'),
 ('publisher_RUNX1T1_m6A',r'\brunx1t1\b.*(?:m6a|methyl)|(?:m6a|methyl).*\brunx1t1\b'),
 ('documentation_RA_sex',r'rheumatoid.*(?:sex|gender|men|women)|(?:sex|gender|men|women).*rheumatoid'),
 ('documentation_Wilson_inheritance',r'wilson.*inherit|inherit.*wilson'),
 ('documentation_CpG_TSS',r'cpg.*(?:transcription|\btss\b)|(?:transcription|\btss\b).*cpg'),
 ('documentation_mononucleosis',r'mononucleosis'),
 ('documentation_Raf_inhibitors',r'\braf\b.*inhibitor|inhibitor.*\braf\b'),
 ('documentation_dabigatran',r'dabigatran.*(?:aptt|atrial)|(?:aptt|atrial).*dabigatran'),
 ('documentation_HMM',r'hidden markov|\bhmms?\b.*(?:gene|neural)'),
 ('manual_Pharos_TCRD',r'\bpharos\b|\btcrd\b'),
]


def need(condition,message):
    if not condition:raise ValueError('Source search: '+message)


def seal(value):
    return {**value,'content_sha256':digest(value)}


def read_sealed(path,expected):
    p=Path(path);need(not p.is_symlink() and p.is_file() and sha(p)==expected,'pinned file changed.')
    value=json.loads(p.read_text())
    need(isinstance(value,dict) and value.get('content_sha256')==digest({k:v for k,v in value.items()if k!='content_sha256'}),'content seal changed.')
    return value


def download(url,path,expected_bytes,*,expected_sha256=None,expected_md5=None):
    p=Path(path);need(not p.exists(),'download output already exists.')
    request=Request(url,headers={'User-Agent':'BioGraphSteward/qualified-public-source-research'})
    with urlopen(request,timeout=60) as response,p.open('xb') as output:
        count=0
        while block:=response.read(1048576):
            count+=len(block);need(count<=expected_bytes,'publisher byte limit exceeded.');output.write(block)
    need(count==expected_bytes,'publisher byte count differs.')
    if expected_sha256:need(sha(p)==expected_sha256,'publisher SHA256 differs.')
    if expected_md5:need(hashlib.md5(p.read_bytes()).hexdigest()==expected_md5,'publisher MD5 differs.')
    return {'url':url,'file':str(p.resolve()),'bytes':count,'sha256':sha(p),'publisher_md5':expected_md5}


def native_environment(folder):
    """No inherited provider keys, endpoint overrides or proxy configuration."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    env={k:os.environ[k]for k in ('PATH','TMPDIR','SYSTEMROOT','SSL_CERT_FILE','SSL_CERT_DIR')if k in os.environ}
    env.update({'XDG_CACHE_HOME':str((folder/'cache').resolve()),'XDG_CONFIG_HOME':str((folder/'config').resolve()),
        'XDG_DATA_HOME':str((folder/'data').resolve()),'BIOMCP_CACHE_MODE':'off','NO_COLOR':'1','RUST_LOG':'debug'})
    return env


def qualify(output):
    """Download/hash-check official binary, then only version/help; no query."""
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    need(platform.system()=='Darwin' and platform.machine()=='arm64','this qualification targets the official Mac arm64 build.')
    archive=folder/BINARY_NAME
    source=download(BINARY_RELEASE+BINARY_NAME,archive,BINARY_BYTES,expected_sha256=BINARY_SHA)
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers();need(all(m.isfile() or m.isdir()for m in members),'nonordinary release member.')
        binaries=[m for m in members if m.isfile()and Path(m.name).name=='biomcp']
        need(len(binaries)==1 and binaries[0].size<=100000000,'release binary inventory differs.')
        binary=folder/'biomcp';binary.write_bytes(tar.extractfile(binaries[0]).read());binary.chmod(0o755)
        names=[{'name':m.name,'bytes':m.size,'ordinary_file':m.isfile()}for m in members]
    rows=[];env=native_environment(folder/'native_state')
    for label,args in [('version',['--version']),('help',['--help']),('article_search_help',['search','article','--help'])]:
        result=subprocess.run([str(binary.resolve()),*args],env=env,capture_output=True,timeout=20)
        need(len(result.stdout)+len(result.stderr)<200000,'unbounded help output.')
        (folder/(label+'.stdout')).write_bytes(result.stdout);(folder/(label+'.stderr')).write_bytes(result.stderr)
        rows.append({'name':label,'argv':args,'exit_code':result.returncode,'stdout_sha256':sha(folder/(label+'.stdout')),
            'stderr_sha256':sha(folder/(label+'.stderr'))})
        need(result.returncode==0,'native version/help failed.')
    need(re.search(rb'\b0\.9\.3\b',(folder/'version.stdout').read_bytes()),'native version is not the pinned release.')
    report=seal({'format':'biograph-steward.biomcp-binary-qualification.v1','created_at':utcnow(),'source':source,
        'repository':'https://github.com/genomoncology/biomcp','commit':'5641de7d7b79b53872f8599dbb4dba22e611dcaf',
        'license':'MIT; upstream provider/data rights remain separate','binary':{'file':str(binary.resolve()),'bytes':binary.stat().st_size,'sha256':sha(binary)},
        'archive_members':names,'checks':rows,'model_calls':0,'searches':0,'raw_reference_opened':False,
        'platform':platform.platform(),'implementation_sha256':sha(__file__)})
    write_json(folder/'qualification.json',report);return report


def projected_questions(stream,parser=None):
    """Established streaming parser; never construct an entire question object."""
    if parser is None:
        import ijson
        need(ijson.__version__=='3.4.0.post0','use the pinned isolated ijson parser.')
        parser=ijson.parse
    current=None;seen_fields=set()
    for prefix,event,value in parser(stream):
        if prefix=='questions.item' and event=='start_map':
            need(current is None,'nested question frame.');current={};seen_fields=set()
        elif current is not None and prefix in {'questions.item.id','questions.item.body','questions.item.type'}:
            key=prefix.rsplit('.',1)[1]
            need(event=='string' and key not in seen_fields,'invalid or repeated allowed question field.')
            need(isinstance(value,str)and 0<len(value)<=5000,'invalid allowed question value.')
            current[key]=value;seen_fields.add(key)
        elif prefix=='questions.item'and event=='end_map':
            need(set(current)=={'id','body','type'},'allowed question fields missing.')
            yield current;current=None
    need(current is None,'unterminated question projection.')


def select_questions(rows,*,per_type=12,expected_counts=None):
    counts=Counter();exclusions=Counter();seen_ids=set();seen_bodies=set();pools={'factoid':[],'list':[]}
    for row in rows:
        need(set(row)=={'id','body','type'},'unexpected projected question field.')
        need(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',row['id'])and row['id']not in seen_ids,'duplicate/invalid question identity.')
        seen_ids.add(row['id']);counts[row['type']]+=1
        if row['type']not in pools:continue
        normalized=' '.join(row['body'].lower().split())
        reason='documentation_id'if row['id']in EXCLUDED_IDS else next((name for name,pattern in EXCLUDED_PATTERNS if re.search(pattern,normalized)),None)
        if reason:exclusions[reason]+=1;continue
        if normalized in seen_bodies:exclusions['duplicate_question_body']+=1;continue
        seen_bodies.add(normalized);pools[row['type']].append(row)
    if expected_counts is not None:need(dict(counts)==expected_counts,'publisher question counts differ.')
    selected=[]
    for kind,pool in pools.items():
        need(len(pool)>=per_type,'insufficient eligible question metadata.')
        selected.extend(sorted(pool,key=lambda r:hashlib.sha256((SEED+'|'+kind+'|'+r['id']).encode()).hexdigest())[:per_type])
    selected.sort(key=lambda r:hashlib.sha256((SEED+'|order|'+r['id']).encode()).hexdigest())
    return selected,{'source_question_counts':dict(counts),'eligible_counts':{k:len(v)for k,v in pools.items()},
        'excluded_counts':dict(exclusions),'selection_seed':SEED,'per_type':per_type}


def prepare(dataset,output,*,binary_qualification,binary_qualification_sha256,model_runtime,model_runtime_sha256,
            manual_qualification,manual_qualification_sha256,tokenizer_qualification,tokenizer_qualification_sha256):
    dataset=Path(dataset);need(dataset.is_file()and dataset.stat().st_size==DATA_BYTES and hashlib.md5(dataset.read_bytes()).hexdigest()==DATA_MD5,'official reference source differs.')
    qualification=read_sealed(binary_qualification,binary_qualification_sha256)
    need(qualification['format']=='biograph-steward.biomcp-binary-qualification.v1','wrong binary qualification.')
    manual=read_sealed(manual_qualification,manual_qualification_sha256)
    need(manual['excluded_from_evaluation']is True and manual['native_complete']is True
         and manual['source_plan']=={'candidate_sources':['pubmed'],'enrichment_sources':[]}
         and manual['observed_debug_connection_hosts']==['eutils.ncbi.nlm.nih.gov']
         and manual['native_disable_sources']==['ols4'],'manual provider qualification has not passed.')
    tokenizer=read_sealed(tokenizer_qualification,tokenizer_qualification_sha256)
    need(tokenizer['generation_requests']==0 and len(tokenizer['rows'])==2
         and all(r['result']['status']=='completed'and r['result']['within_budget']for r in tokenizer['rows']),
         'manual CPU tokenizer qualification has not passed.')
    runtime_path=Path(model_runtime);need(sha(runtime_path)==model_runtime_sha256,'model runtime observation differs.')
    runtime=json.loads(runtime_path.read_text());observation=runtime['derived_observation']
    need(observation['model']=='nvidia/Llama-3.1-Nemotron-Nano-8B-v1'
         and observation['model_revision']=='54641c1611fcff44fa4865626462445e0a153fc7'
         and observation['tokenizer_revision']==observation['model_revision']
         and observation['engine']=='V0'and observation['vllm_version']=='0.8.5'
         and observation['xgrammar_version']=='0.1.18','use the existing qualified model/runtime, not a replacement.')
    with dataset.open('rb')as stream:rows,stats=select_questions(projected_questions(stream),expected_counts={'factoid':1417,'yesno':1271,'summary':1130,'list':901})
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False)
    write_json(folder/'questions.json',rows)
    package=Path(__file__).parents[2]
    files={str(p.resolve()):sha(p)for p in (Path(__file__),Path(__file__).with_name('tools.py'),Path(__file__).with_name('agent.py'),Path(__file__).with_name('policy.py'),
        package/'biograph_steward/model_transport.py',package/'biograph_steward/literature.py')}
    from .policy import BASE_POLICY,SKILL,SKILL_SOURCES,MODEL,MAX_CALLS,MAX_OUTPUT_TOKENS
    source_folder=Path(dataset).parent
    for entry in SKILL_SOURCES:
        name='BioMCP.SKILL.md'if entry['repository']=='genomoncology/biomcp'else Path(entry['path']).parts[1]+'.SKILL.md'
        need(sha(source_folder/name)==entry['sha256'],'attributed raw skill source changed.')
    protocol=seal({'format':FORMAT,'created_at':utcnow(),'reference':{'doi':'10.5281/zenodo.7655130','version':'BioASQ11','license':'CC-BY-2.5',
        'file':str(dataset.resolve()),'bytes':DATA_BYTES,'publisher_md5':DATA_MD5,'sha256':sha(dataset)},
        'binary_qualification':{'file':str(Path(binary_qualification).resolve()),'sha256':binary_qualification_sha256,'content_sha256':qualification['content_sha256']},
        'manual_qualification':{'file':str(Path(manual_qualification).resolve()),'sha256':manual_qualification_sha256,'content_sha256':manual['content_sha256']},
        'tokenizer_qualification':{'file':str(Path(tokenizer_qualification).resolve()),'sha256':tokenizer_qualification_sha256,'content_sha256':tokenizer['content_sha256']},
        'model_runtime':{'file':str(runtime_path.resolve()),'sha256':model_runtime_sha256,'observation':observation,
            'readiness_note':'Read-only /v1/models readiness is rechecked before execution; no inference or serving changes during preparation.'},
        'questions_sha256':sha(folder/'questions.json'),'selected_questions':len(rows),'selection':stats,
        'fixed_exclusions':{'ids':sorted(EXCLUDED_IDS),'patterns':EXCLUDED_PATTERNS},
        'model':MODEL,'max_model_calls_per_case':MAX_CALLS,'max_output_tokens_per_call':MAX_OUTPUT_TOKENS,
        'maximum_total_output_tokens':len(rows)*2*MAX_CALLS*MAX_OUTPUT_TOKENS,
        'arms':['direct_native_query','unskilled_agent','procedure_skill_agent'],'source':'pubmed only; no source fallback',
        'native_disabled_sources':['ols4'],'evidence_scope':'Native PubMed candidates; optional ontology keyword suggestions suppressed using the published source-disable flag.',
        'budgets':{'agent_search_calls':2,'agent_exact_abstract_get_calls':1,'final_ranked_unique_PMIDs':10},
        'input_budget':{'conservative_context_tokens':8192,'reserved_output_tokens':MAX_OUTPUT_TOKENS,
            'enforcement':'Installed vLLM chat-tokenizer counts the exact Nano message transform before generation; failure/overflow means explicit no-inference outcome.',
            'projection':'PMID/title(up to400characters, flag if truncated)/date/source/availability; one exact abstract up to12000characters with explicit truncation. Full native bodies retained.'},
        'execution_order':'Question-blocked; direct query first, then both agent arms in counterbalanced12/12 fixed salted-SHA order; shared source cache keyed by literal query, binary and source-helper pins.',
        'base_policy_sha256':digest(BASE_POLICY),'skill_sha256':digest(SKILL),'skill_sources':SKILL_SOURCES,
        'primary_endpoint':'Paired mean question-level reference-PMID Recall@10: skill agent minus unchanged unskilled agent.',
        'uncertainty':{'method':'Paired question bootstrap; all questions retained, shared draws across arms. Conditional descriptive intervals, not model-unseen or independent-study evidence.',
            'draws':2000,'seed':20261114,'interval':'95 percent percentile'},
        'secondary':['reference_hit_at_10','returned_ID_validity','opened_abstract_IDs','unavailable/incomplete statuses','model/tool/cache/process/token costs'],
        'reference_release':'Only after every fixed arm output is complete and sealed plus independent/root review; exact selected IDs only.',
        'gold_fields_in_model_or_selection':False,'parser_boundary':'ijson internally decodes JSON events; only id/body/type are retained or exposed before release.',
        'exposure':'Public historical developer-new subset, not model-unseen/official competition/biological-accuracy evidence. Publisher/manual examples excluded by fixed rules.',
        'unknown_relevance_is_not_false':True,'freshness':'Live retrieval of historical positive document references; no new manual gold.',
        'files':files,'raw_references_or_answers_in_publication':False,'app_graph_changes':False})
    write_json(folder/'protocol.json',protocol);return protocol


def load_frame(folder,expected):
    folder=Path(folder);p=read_sealed(folder/'protocol.json',expected)
    need(p['format']==FORMAT and sha(folder/'questions.json')==p['questions_sha256'],'question freeze differs.')
    for path,expected_sha in p['files'].items():need(sha(path)==expected_sha,'frozen implementation differs.')
    rows=json.loads((folder/'questions.json').read_text())
    need(len(rows)==24 and all(set(r)=={'id','body','type'}for r in rows),'question payload boundary differs.')
    return p,rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('qualify');p.add_argument('--output',required=True)
    p=sub.add_parser('prepare')
    for key in ('dataset','output','binary-qualification','binary-qualification-sha256','model-runtime','model-runtime-sha256',
                'manual-qualification','manual-qualification-sha256','tokenizer-qualification','tokenizer-qualification-sha256'):p.add_argument('--'+key,required=True)
    args=vars(parser.parse_args());command=args.pop('command');r=globals()[command](**args)
    print(json.dumps({k:v for k,v in r.items()if k in ('format','content_sha256','selected_questions','maximum_total_output_tokens')},indent=2))
