"""Bounded public-source retrieval. Missing text is an access gap, never a negative."""
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from .client import digest, utcnow, write_json

PUBMED = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id='
PMC = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&retmode=xml&id={}'


def text(node):
    return ' '.join(' '.join(node.itertext()).split()) if node is not None else ''


def fetch(url):
    req = Request(url, headers={'User-Agent': 'BioGraphSteward/source-retrieval read-only'})
    with urlopen(req, timeout=35) as response:
        raw = response.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError('Source exceeds the 20 MB retrieval budget.')
    return raw


def parse_pubmed(raw):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError('PubMed response is not valid XML; no source assessment was produced.') from None
    if root.tag != 'PubmedArticleSet':
        raise ValueError('Expected a PubMed XML article set.')
    records = {}
    for article in root.findall('PubmedArticle'):
        pmid = article.findtext('MedlineCitation/PMID', '')
        if not re.fullmatch(r'[1-9][0-9]{0,9}', pmid) or pmid in records:
            raise ValueError('Missing or duplicate PubMed identity.')
        ids = {n.get('IdType'): n.text for n in article.findall('PubmedData/ArticleIdList/ArticleId')}
        passages = [{'text': text(n), 'locator': f'PubmedArticle[PMID={pmid}]/MedlineCitation/Article/Abstract/AbstractText[{i + 1}]',
                     'section': n.get('Label') or n.get('NlmCategory') or 'Abstract'}
                    for i, n in enumerate(article.findall('MedlineCitation/Article/Abstract/AbstractText')) if text(n)]
        records[pmid] = {'pmid': pmid, 'pmcid': ids.get('pmc'), 'doi': ids.get('doi'),
                         'title': text(article.find('MedlineCitation/Article/ArticleTitle')),
                         'abstract': passages, 'copyright': article.findtext('.//CopyrightInformation'),
                         'publication_types': [text(n) for n in article.findall('.//PublicationType')],
                         'correction_types': [n.get('RefType') for n in article.findall('.//CommentsCorrections')]}
    return records


def parse_pmc(raw, pmid, pmcid):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError('PMC response is not valid XML; no source assessment was produced.') from None
    article = root if root.tag == 'article' else root.find('.//article')
    if article is None:
        raise ValueError('Expected full-text JATS article XML.')
    ids = {n.get('pub-id-type'): text(n) for n in article.findall('.//front/article-meta/article-id')}
    matching = ids.get('pmid') == pmid or 'PMC' + ids.get('pmc', '').removeprefix('PMC') == pmcid
    if not matching or ids.get('pmid', pmid) != pmid:
        raise ValueError('Full-text publication identity does not match the requested PubMed record.')
    passages = []
    def walk(node, path, section='Body'):
        if node.tag == 'sec':
            section = text(node.find('title')) or section
        if node.tag in {'p', 'table-wrap'} and text(node):
            passages.append({'text': text(node), 'locator': path, 'section': section})
            return
        counts = {}
        for child in node:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            walk(child, path + f'/{child.tag}[{counts[child.tag]}]', section)
    body = article.find('body')
    if body is not None:
        walk(body, '/article/body')
    return {'passages': passages, 'license': [text(n) for n in article.findall('.//permissions/license')]}


def collect_literature(pmids, output, *, transport=None):
    pmids = sorted(set(pmids), key=int)
    if not 1 <= len(pmids) <= 30 or any(not re.fullmatch(r'[1-9][0-9]{0,9}', p) for p in pmids):
        raise ValueError('Use 1–30 exact PubMed IDs.')
    output = Path(output)
    if output.exists():
        raise ValueError('Choose a new immutable literature directory.')
    output.mkdir(parents=True)
    transport = transport or fetch
    requests = []
    def retrieve(url, name):
        row = {'url': url, 'retrieved_at': utcnow(), 'raw_file': name}
        requests.append(row)
        try:
            raw = transport(url)
            if not isinstance(raw, bytes) or len(raw) > 20_000_000:
                raise ValueError('Invalid or over-budget source response.')
            (output / name).write_bytes(raw)
            row.update(status='downloaded', sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            return raw
        except (HTTPError, URLError, OSError, ValueError) as exc:
            row.update(status='unavailable', error_type=type(exc).__name__)
            if isinstance(exc, HTTPError):
                row['http_status'] = exc.code
            return None
    raw = retrieve(PUBMED + ','.join(pmids), 'pubmed.xml')
    parsed = parse_pubmed(raw) if raw is not None else {}
    if set(parsed) - set(pmids):
        raise ValueError('PubMed returned unrequested identities.')
    papers = []
    for pmid in pmids:
        paper = parsed.get(pmid, {'pmid': pmid, 'title': '', 'abstract': [], 'pmcid': None})
        paper.update(abstract_status='available' if paper['abstract'] else 'unavailable', full_text_status='no_linked_pmcid', full_text=[])
        pmcid = paper['pmcid']
        if pmcid and re.fullmatch(r'PMC[1-9][0-9]*', pmcid):
            if transport is fetch:
                time.sleep(.4)
            full = retrieve(PMC.format(pmcid[3:]), pmcid + '.xml')
            paper['full_text_status'] = 'unavailable'
            if full is not None:
                try:
                    data = parse_pmc(full, pmid, pmcid)
                    paper.update(full_text=data['passages'], license=data['license'],
                                 full_text_status='available' if data['passages'] else 'empty_body')
                except (ET.ParseError, ValueError):
                    paper['full_text_status'] = 'invalid_or_mismatched_document'
        papers.append(paper)
    write_json(output / 'papers.json', papers)
    manifest = {'format': 'biograph-steward.crc-literature.v1', 'created_at': utcnow(), 'requested_pmids': pmids,
                'papers_sha256': digest(papers), 'requests': requests,
                'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()},
                'policy': 'PubMed-linked PMC IDs only; bounded public XML. Access failure or omitted text is not biological absence.',
                'license_note': 'Paper-specific rights are retained where supplied; public accessibility is not a blanket redistribution license.'}
    manifest['manifest_sha256'] = digest(manifest)
    write_json(output / 'manifest.json', manifest)
    return manifest


def load_literature(path):
    path = Path(path); manifest = json.loads((path / 'manifest.json').read_text())
    if manifest['manifest_sha256'] != digest({k: v for k, v in manifest.items() if k != 'manifest_sha256'}):
        raise ValueError('Literature manifest changed.')
    for name, sha in manifest['files'].items():
        if Path(name).name != name or (path / name).is_symlink() or hashlib.sha256((path / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Frozen literature bytes changed.')
    papers = json.loads((path / 'papers.json').read_text())
    if digest(papers) != manifest['papers_sha256'] or {p['pmid'] for p in papers} != set(manifest['requested_pmids']):
        raise ValueError('Literature inventory changed.')
    return manifest, {p['pmid']: p for p in papers}
