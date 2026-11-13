"""Rebuild optional grounding-reference prerequisites from official native data.

Use ``python -m tools.grounding_claims.reproduce --help``. No command runs
predictions, reads curation categories, mutates a graph, or loads pickle data.
Raw reference artifacts are CC-BY-NC-SA-4.0 and belong in private storage.
"""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import inspect
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

LEGACY_PLAN_SHA = "40c9be9648f7ab0cb14b64db651398ab2d9c106da29652ce00e44611d63cb72b"
CORPUS_SHA = "bf048f3b485990e6d81ee0f2200ea17efe962268427b4f33af932b4f08a434de"
CURATIONS_SHA = "02ccca87fb4c8386ae49d420cb4c8257cf769bcaba5692a989bf295ba8d40da5"
SOURCE_CONTRACT = {
    "format": "biograph-steward.indra-official-json-source-contract.v1",
    "Zenodo_record": 7559353, "data_license": "CC-BY-NC-SA-4.0",
    "paper_DOI": "10.15252/msb.202211325", "pickle_permitted": False,
    "artifacts": [
        {"file": "indra_assembly_curations.json", "bytes": 1687078,
         "publisher_md5": "4a5b39066458e2112607bcb19e7a4d29", "sha256": CURATIONS_SHA},
        {"file": "indra_benchmark_corpus.json.gz", "bytes": 460045058,
         "publisher_md5": "82c01e9e100b296ba5b8fbbb2e39f5dc", "sha256": CORPUS_SHA}]}
GILDA_RESOURCE_HASHES = {
    "grounding_terms.tsv.gz": "b53169c4735d049c0443ab04830b26372dcfeba47845c1fe97392b64f08f2bb8",
    "gilda_models.json.gz": "62c888eeabe4afb484d17d90cf3e8304c9c3a8f1c97b5b3fb7ab41a458340e1f"}


def plain_encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def contract_hash():
    return hashlib.sha256(plain_encoded(SOURCE_CONTRACT)).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n")


def _publication_consensus(evidence):
    # Preserve the original join schema's strict metadata commitment. The later
    # prepare step applies its source-qualified retrieval policy independently.
    from .prepare import inventory_publication_consensus
    return inventory_publication_consensus(evidence)


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    # Standard published simplejson preserves Decimal numbers produced by
    # default ijson. This is canonical parsed-value JSON, not literal slices.
    return simplejson.dumps(value, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False, use_decimal=True,
                            allow_nan=False).encode("utf-8")


def content_hash(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def exact_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Native ID is not an integer or decimal string")
    text = str(value)
    if not re.fullmatch(r"-?[0-9]{1,30}", text):
        raise ValueError("Native ID is not a signed decimal")
    if str(int(text)) != text:
        raise ValueError("Native ID is not canonical signed decimal")
    return text


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pubmed(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return str(int(text)) if re.fullmatch(r"[0-9]+", text) and int(text) > 0 else None


def publication_metadata(evidence):
    refs = evidence.get("text_refs")
    refs = refs if isinstance(refs, dict) else {}
    native_values = {"pmid": evidence.get("pmid"), "text_refs.PMID": refs.get("PMID")}
    supplied = {key: value for key, value in native_values.items() if value not in (None, "")}
    valid = {key: pubmed(value) for key, value in supplied.items()}
    malformed = [key for key, value in valid.items() if value is None]
    pmids = sorted({value for value in valid.values() if value is not None})
    tokens = {"PMID:" + value for value in pmids}
    for namespace in ("DOI", "PMCID"):
        value = refs.get(namespace)
        if isinstance(value, str) and value.strip():
            # Original literal values remain in complete native evidence.
            normalized = value.strip().lower() if namespace == "DOI" else value.strip()
            tokens.add(namespace + ":" + normalized)
    return {"native_publication_values": native_values, "qualified_PMIDs": pmids,
            "PMID_fields_conflict": len(pmids) > 1,
            "malformed_nonempty_PMID_fields": malformed,
            "single_PMID_consensus": _publication_consensus(evidence),
            "publication_group_tokens": sorted(tokens)}


def origin_metadata(evidence, deep_agents):
    annotations = evidence.get("annotations")
    annotations = annotations if isinstance(annotations, dict) else {}
    agents = annotations.get("agents")
    agents = agents if isinstance(agents, dict) else {}
    texts, groundings = agents.get("raw_text"), agents.get("raw_grounding")
    arrays = isinstance(texts, list) and isinstance(groundings, list)
    lengths_equal = arrays and len(texts) == len(groundings)
    positions = []
    if lengths_equal:
        for index, (text, grounding) in enumerate(zip(texts, groundings)):
            positions.append({"position": index,
                              "text_type": type(text).__name__,
                              "grounding_type": type(grounding).__name__,
                              "paired_None_consistent": (text is None) == (grounding is None),
                              "nonempty_explicit_text": isinstance(text, str) and bool(text.strip()),
                              "explicit_grounding_mapping": isinstance(grounding, dict),
                              "current_deep_sorted_Agent_None":
                                  (deep_agents[index] is None) if deep_agents is not None and index < len(deep_agents) else None})
    assigned_HGNC_ids = []
    all_actual_HGNC = bool(lengths_equal)
    actual_agents = 0
    if lengths_equal:
        for text, grounding in zip(texts, groundings):
            if text is None and grounding is None:
                assigned_HGNC_ids.append(None)
                continue
            actual_agents += 1
            identifier = grounding.get("HGNC") if isinstance(grounding, dict) else None
            valid_id = pubmed(identifier)  # Same positive-decimal lexical check; no HGNC remapping.
            assigned_HGNC_ids.append(valid_id)
            all_actual_HGNC = all_actual_HGNC and bool(valid_id) and isinstance(text, str) and bool(text.strip())
    all_actual_HGNC = all_actual_HGNC and actual_agents > 0
    payload = {"Evidence_text": evidence.get("text"), "source_api": evidence.get("source_api"),
               "source_id": evidence.get("source_id"), "pmid": evidence.get("pmid"),
               "text_refs": evidence.get("text_refs"), "epistemics": evidence.get("epistemics"),
               "context": evidence.get("context"),
               "raw_text_present": "raw_text" in agents,
               "raw_grounding_present": "raw_grounding" in agents,
               "raw_text": texts, "raw_grounding": groundings}
    return {"annotation_agent_keys": sorted(agents),
            "explicit_raw_text": texts, "explicit_raw_grounding": groundings,
            "both_origin_fields_are_arrays": arrays,
            "origin_array_lengths_equal": lengths_equal,
            "origin_array_length": len(texts) if isinstance(texts, list) else None,
            "actual_origin_agent_count": actual_agents,
            "raw_HGNC_ids_by_origin_position": assigned_HGNC_ids,
            "all_actual_origin_agents_have_explicit_text_and_HGNC_ID": all_actual_HGNC,
            "current_native_deep_sorted_agent_count": len(deep_agents) if deep_agents is not None else None,
            "origin_length_matches_current_deep_sorted_agents":
                lengths_equal and len(texts) == len(deep_agents) if deep_agents is not None else None,
            "positions": positions, "origin_payload_sha256": content_hash(payload),
            "representative_Agent_TEXT_fallback_used": False}



def join_native(data, output, *, minimum_free_bytes=700_000_000):
    """Stream the pinned source and preserve complete native objects, without labels."""
    global ijson, nx, simplejson, stmts_from_json
    import ijson
    import networkx as nx
    import simplejson
    from indra.statements import stmts_from_json
    HERE, OUT = Path(data).absolute(), Path(output).absolute()
    start = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=False)
    final_paths = [OUT/name for name in ("selected_statements.jsonl", "pair_join_inventory.json",
                                         "source_publication_ids.json", "exposure_groups.json", "join_report.json")]
    if any(path.exists() for path in final_paths):
        raise RuntimeError("Refusing to overwrite a prior blind-join audit")
    versions = {name: importlib.metadata.version(name) for name in ("indra", "ijson", "simplejson", "networkx")}
    if versions["indra"] != "1.24.0" or versions["ijson"] != "3.4.0.post0" or versions["simplejson"] != "4.3.0":
        raise RuntimeError("Native parser runtime differs from the qualified versions")
    corpus = HERE / "indra_benchmark_corpus.json.gz"
    if file_hash(corpus) != CORPUS_SHA:
        raise RuntimeError("Compressed corpus byte pin changed")
    inventory_path = HERE / "blind_identifier_inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory_seal = inventory.pop("content_sha256")
    PLAN_SHA = inventory["acquisition_plan_content_sha256"]
    if content_hash(inventory) != inventory_seal or PLAN_SHA not in {LEGACY_PLAN_SHA, contract_hash()}:
        raise RuntimeError("Blind identifier inventory or acquisition contract changed")
    if inventory["raw_curation_file_SHA256"] != CURATIONS_SHA:
        raise RuntimeError("Blind curation inventory binds different native bytes")
    if file_hash(HERE / "indra_assembly_curations.json") != CURATIONS_SHA:
        raise RuntimeError("Native curation byte pin changed")
    pair_rows = defaultdict(list)
    for row in inventory["identifier_rows"]:
        pair_rows[(row["pa_hash"], row["source_hash"])].append(row["record_index"])
    by_statement = defaultdict(set)
    for pa_hash, source_hash in pair_rows:
        by_statement[pa_hash].add(source_hash)
    pairs = {key: {"pa_hash": key[0], "source_hash": key[1],
                   "curation_record_ordinals": rows, "evidence_occurrences": []}
             for key, rows in pair_rows.items()}
    stats = Counter()
    statement_types = Counter()
    errors = []
    selected_ordinals = defaultdict(list)
    missing_source_hashes = []
    temporary = OUT / "selected_statements.jsonl.partial"
    if temporary.exists():
        raise RuntimeError("A prior partial audit exists; preserve it rather than overwrite")
    with temporary.open("xb") as output, gzip.open(corpus, "rb") as stream:
        parser = ijson.parse(stream, use_float=False)
        first = next(parser)
        if first != ("", "start_array", None):
            raise RuntimeError("Native JSON export is not a statement array")
        for ordinal, raw in enumerate(ijson.items(itertools.chain([first], parser), "item")):
            stats["corpus_statements_streamed"] += 1
            if not isinstance(raw, dict) or not isinstance(raw.get("evidence"), list) or "matches_hash" not in raw:
                raise RuntimeError("Native statement root/schema lacks declared hash/evidence array")
            pa_hash = exact_id(raw["matches_hash"])
            if pa_hash not in by_statement:
                continue
            stats["selected_statement_payloads"] += 1
            statement_types[str(raw.get("type"))] += 1
            canonical_sha = content_hash(raw)
            output.write(encoded({"corpus_ordinal": ordinal, "statement": raw,
                                  "canonical_statement_sha256": canonical_sha}) + b"\n")
            selected_ordinals[pa_hash].append(ordinal)
            native, deep_agents, native_pa_hash, family_token = None, None, None, None
            try:
                loaded = stmts_from_json([copy.deepcopy(raw)], on_missing_support="ignore")
                stats["native_reader_statements_returned"] += len(loaded)
                if len(loaded) != 1:
                    raise RuntimeError("Native reader did not return exactly one Statement")
                native = loaded[0]
                if len(native.evidence) != len(raw["evidence"]):
                    raise RuntimeError("Native current reader changed evidence cardinality")
                deep_agents = native.agent_list(deep_sorted=True)
                native_pa_hash = exact_id(native.get_hash(refresh=True))
                entity_keys = [agent.entity_matches_key() if agent is not None else None for agent in deep_agents]
                family_token = "native_entity_type_family:" + content_hash({"type": raw.get("type"), "entity_keys": entity_keys})
                stats["native_statement_hash_equal"] += native_pa_hash == pa_hash
                stats["native_statement_hash_changed"] += native_pa_hash != pa_hash
            except Exception as error:
                stats["native_current_reader_or_shape_failures"] += 1
                errors.append({"pa_hash": pa_hash, "corpus_ordinal": ordinal,
                               "error_type": type(error).__name__, "error": str(error)})
                native, deep_agents = None, None
            for evidence_ordinal, evidence in enumerate(raw["evidence"]):
                if not isinstance(evidence, dict):
                    raise RuntimeError("Native evidence array contains a non-object")
                try:
                    source_hash = exact_id(evidence.get("source_hash"))
                except ValueError:
                    stats["selected_evidence_without_declared_source_hash"] += 1
                    missing_source_hashes.append({"pa_hash": pa_hash, "corpus_ordinal": ordinal,
                                                  "evidence_ordinal": evidence_ordinal})
                    continue
                key = (pa_hash, source_hash)
                if key not in pairs:
                    continue
                native_source_hash = None
                if native is not None:
                    native_source_hash = exact_id(native.evidence[evidence_ordinal].get_source_hash())
                    stats["native_evidence_hash_equal"] += native_source_hash == source_hash
                    stats["native_evidence_hash_changed"] += native_source_hash != source_hash
                origin = origin_metadata(evidence, deep_agents)
                occurrence = {"corpus_ordinal": ordinal, "evidence_ordinal": evidence_ordinal,
                              "canonical_statement_sha256": canonical_sha,
                              "canonical_evidence_sha256": content_hash(evidence),
                              "source_api": evidence.get("source_api"), "source_id": evidence.get("source_id"),
                              "native_current_statement_hash": native_pa_hash,
                              "native_current_evidence_hash": native_source_hash,
                              "native_entity_type_family_token": family_token,
                              "publication": publication_metadata(evidence), "origin": origin}
                pairs[key]["evidence_occurrences"].append(occurrence)
                stats["exact_native_pair_evidence_occurrences"] += 1
            if content_hash(raw) != canonical_sha:
                raise RuntimeError("Native parsing mutated the preserved source object")
            if shutil.disk_usage(OUT).free < minimum_free_bytes:
                raise RuntimeError("Insufficient safe disk headroom for selected-source preservation")
    if any(stats[k] for k in ("native_current_reader_or_shape_failures", "native_statement_hash_changed", "native_evidence_hash_changed")):
        raise RuntimeError("Native reader/hash drift: preserve partial join; do not silently rename reference IDs")
    temporary.rename(final_paths[0])
    graph = nx.Graph()
    pubmed_ids, consensus_pmids = set(), set()
    pair_list = []
    for key in sorted(pairs):
        pair = pairs[key]
        occurrences = pair["evidence_occurrences"]
        pair["matched"] = bool(occurrences)
        pair["statement_payload_variant_count"] = len({x["canonical_statement_sha256"] for x in occurrences})
        pair["evidence_payload_variant_count"] = len({x["canonical_evidence_sha256"] for x in occurrences})
        pair["source_origin_payload_variant_count"] = len({x["origin"]["origin_payload_sha256"] for x in occurrences})
        pair["all_occurrences_have_explicit_all_HGNC_origins"] = bool(occurrences) and all(
            item["origin"]["all_actual_origin_agents_have_explicit_text_and_HGNC_ID"] for item in occurrences)
        pair["payload_variants_arbitrarily_selected"] = False
        pair_id = "pair:" + key[0] + ":" + key[1]
        tokens = {"statement:"+key[0], "source_hash:"+key[1]}
        for item in occurrences:
            publication = item["publication"]
            pubmed_ids.update(publication["qualified_PMIDs"])
            if publication["single_PMID_consensus"]:
                consensus_pmids.add(publication["single_PMID_consensus"])
            tokens.update(publication["publication_group_tokens"])
            if item["native_entity_type_family_token"]:
                tokens.add(item["native_entity_type_family_token"])
        graph.add_node(pair_id, kind="pair")
        graph.add_edges_from((pair_id, "group:"+token) for token in tokens)
        pair["candidate_exposure_group_tokens"] = sorted(tokens)
        pair_list.append(pair)
    groups = []
    for component in nx.connected_components(graph):
        members = sorted(node[5:] for node in component if node.startswith("pair:"))
        token_members = sorted(node[6:] for node in component if node.startswith("group:"))
        group_id = content_hash({"pairs": members})
        groups.append({"group_id": group_id, "pair_ids": members, "candidate_tokens": token_members})
    groups.sort(key=lambda group: group["group_id"])
    inventory_out = {"format": "biograph-steward.indra-blind-pair-join.v1", "created_at": now(),
                     "raw_curations_SHA256": CURATIONS_SHA, "corpus_compressed_SHA256": CORPUS_SHA,
                     "source_byte_binding": "Complete original compressed artifact plus native array ordinal; canonical parsed-value SHA is separately identified.",
                     "reference_categories_inspected": False, "pairs": pair_list}
    final_paths[1].write_bytes(encoded(inventory_out)+b"\n")
    final_paths[2].write_bytes(encoded({"format": "biograph-steward.indra-blind-publication-inventory.v1",
                                       "all_explicit_PMIDs": sorted(pubmed_ids, key=int),
                                       "single_consensus_PMIDs": sorted(consensus_pmids, key=int),
                                       "inconsistent_missing_or_malformed_source_refs_not_inferred": True,
                                       "labels_inspected": False})+b"\n")
    final_paths[3].write_bytes(encoded({"format": "biograph-steward.indra-blind-exposure-groups.v1",
                                       "scope": "Candidate conservative components using original Statement/source hashes, source publication identifiers, and a separately named coarse native-current entity/type family token. Not gold biological equivalence or a final split.",
                                       "groups": groups, "labels_inspected": False})+b"\n")
    matched = sum(pair["matched"] for pair in pair_list)
    stats.update({"reference_distinct_pairs": len(pair_list), "matched_distinct_pairs": matched,
                  "unmatched_distinct_pairs": len(pair_list)-matched,
                  "reference_distinct_statements": len(by_statement),
                  "matched_distinct_statement_hashes": len(selected_ordinals),
                  "pairs_with_multiple_statement_payloads": sum(pair["statement_payload_variant_count"] > 1 for pair in pair_list),
                  "pairs_with_multiple_evidence_payloads": sum(pair["evidence_payload_variant_count"] > 1 for pair in pair_list),
                  "pairs_with_multiple_origin_payloads": sum(pair["source_origin_payload_variant_count"] > 1 for pair in pair_list),
                  "pairs_with_explicit_all_HGNC_origins": sum(pair["all_occurrences_have_explicit_all_HGNC_origins"] for pair in pair_list),
                  "pairs_with_single_origin_and_explicit_all_HGNC": sum(pair["source_origin_payload_variant_count"] == 1 and pair["all_occurrences_have_explicit_all_HGNC_origins"] for pair in pair_list),
                  "candidate_exposure_components": len(groups), "explicit_unique_PMIDs": len(pubmed_ids)})
    report = {"format": "biograph-steward.indra-blind-native-join-report.v1", "created_at": now(),
              "acquisition_plan_content_sha256": PLAN_SHA, "runtime_versions": versions,
              "Python": sys.version, "ijson_backend": ijson.backend, "ijson_use_float": False,
              "writer": "simplejson use_decimal=True, canonical sorted compact JSON; not literal source slices",
              "source_compressed_SHA256": CORPUS_SHA, "curations_SHA256": CURATIONS_SHA,
              "blind_ID_inventory_content_sha256": inventory_seal,
              "native_reader_on_missing_support": "ignore only while loading one source object; all original supports/supported_by remain preserved in complete source wrappers",
              "native_reader_code_file_SHA256": file_hash(Path(inspect.getsourcefile(stmts_from_json))),
              "counts": dict(stats), "source_statement_types": dict(statement_types),
              "unmatched_original_pairs": [{"pa_hash": pair["pa_hash"], "source_hash": pair["source_hash"]} for pair in pair_list if not pair["matched"]],
              "native_current_reader_failures": errors,
              "selected_evidence_missing_declared_hash": missing_source_hashes,
              "all_original_pair_IDs_joined": matched == len(pair_list),
              "any_payload_variant_arbitrarily_selected": False,
              "source_origin_default_Agent_TEXT_fallback": False,
              "curation_tag_comment_or_correctness_fields_used": False,
              "grounder_or_model_predictions_run": False,
              "final_evaluation_contract_or_scoring_admitted": False,
              "elapsed_seconds": time.monotonic()-start,
              "outputs": {path.name: {"bytes": path.stat().st_size, "SHA256": file_hash(path)} for path in final_paths[:-1]}}
    report["content_sha256"] = content_hash(report)
    final_paths[4].write_bytes(encoded(report)+b"\n")
    return report


def download(url, path, *, expected_bytes=None, md5=None, sha256=None, cap=None):
    """Bounded ordinary HTTPS capture; preserve partial bytes and failure receipt."""
    path = Path(path)
    partial, receipt = path.with_name(path.name + '.part'), path.with_name(path.name + '.receipt.json')
    if any(p.exists() for p in (path, partial, receipt)):
        raise ValueError('refusing to overwrite acquisition state: ' + str(path))
    record = {'url': url, 'started_at': now(), 'labels_or_predictions_inspected': False}
    h, m, count = hashlib.sha256(), hashlib.md5(), 0
    started = time.monotonic()
    try:
        request = Request(url, headers={'User-Agent': 'BioGraph-Steward-grounding-reproduction/1.0'})
        with urlopen(request, timeout=45) as response, partial.open('xb') as stream:
            final = urlsplit(response.url)
            record.update(status=response.status,
                          final_url_without_query=urlunsplit(final._replace(query='', fragment='')),
                          redirect_query_present=bool(final.query))
            if response.status != 200:
                raise ValueError('expected complete HTTP200 response')
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                count += len(chunk)
                if count > (expected_bytes if expected_bytes is not None else cap):
                    raise ValueError('response exceeds declared byte bound')
                if time.monotonic() - started > 1200:
                    raise ValueError('acquisition exceeded20-minute bound')
                stream.write(chunk)
                h.update(chunk)
                m.update(chunk)
        if ((expected_bytes is not None and count != expected_bytes)
                or (md5 is not None and m.hexdigest() != md5)
                or (sha256 is not None and h.hexdigest() != sha256)):
            raise ValueError('official artifact bytes/checksum differ')
        partial.rename(path)
        record.update(success=True, bytes=count, sha256=h.hexdigest(), md5=m.hexdigest())
    except Exception as exc:
        record.update(success=False, bytes_received=count, received_sha256=h.hexdigest(),
                      received_md5=m.hexdigest(), error_type=type(exc).__name__, error=str(exc),
                      partial_file_preserved=partial.exists())
        raise
    finally:
        record['finished_at'] = now()
        write_json(receipt, record)
    return record


def acquire(output):
    """Download exactly the two JSON artifacts; inventory identity fields only."""
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'source_contract.json', {**SOURCE_CONTRACT, 'content_sha256': contract_hash()})
    metadata_path = output / 'zenodo_7559353.json'
    download('https://zenodo.org/api/records/7559353', metadata_path, cap=2_000_000)
    metadata = json.loads(metadata_path.read_text())
    native = {row['key']: row for row in metadata['files']}
    requests = []
    for item in SOURCE_CONTRACT['artifacts']:
        row = native[item['file']]
        if row['size'] != item['bytes'] or row['checksum'] != 'md5:' + item['publisher_md5']:
            raise ValueError('official release metadata differs from qualified JSON artifacts')
        url = row['links']['self']
        if urlsplit(url).scheme != 'https' or urlsplit(url).hostname != 'zenodo.org':
            raise ValueError('unexpected official artifact origin')
        requests.append((item, url))
    def fetch(pair):
        item, url = pair
        return download(url, output / item['file'], expected_bytes=item['bytes'],
                        md5=item['publisher_md5'], sha256=item['sha256'])
    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(fetch, requests))
    # Decode no tag, comment, curator identity, or correctness field.
    rows = json.loads((output / 'indra_assembly_curations.json').read_bytes())
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('unexpected native curation root/schema')
    identities = [{'record_index': n, 'pa_hash': exact_id(row.get('pa_hash')),
                   'source_hash': exact_id(row.get('source_hash'))} for n, row in enumerate(rows)]
    pairs = {(r['pa_hash'], r['source_hash']) for r in identities}
    inventory = {'format': 'biograph-steward.indra-blind-original-ID-inventory.v1',
        'created_at': now(), 'acquisition_plan_content_sha256': contract_hash(),
        'raw_curation_file_SHA256': CURATIONS_SHA,
        'native_schema_keys_only': sorted({k for row in rows for k in row}),
        'native_record_count': len(rows), 'original_identifier_record_count': len(identities),
        'distinct_pair_count': len(pairs), 'distinct_statement_count': len({p[0] for p in pairs}),
        'distinct_source_hash_count': len({p[1] for p in pairs}),
        'identifiers_are_signed_decimal_strings': True, 'identifier_rows': identities,
        'unresolved_identifier_rows': [],
        'tag_comment_or_correctness_fields_accessed_for_selection_printing_or_counts': False,
        'labels_or_model_predictions_inspected': False}
    inventory['content_sha256'] = hashlib.sha256(plain_encoded(inventory)).hexdigest()
    write_json(output / 'blind_identifier_inventory.json', inventory)
    result = {'format': 'biograph-steward.grounding-reference-acquisition.v1',
              'source_contract_content_sha256': contract_hash(), 'files': receipts,
              'blind_inventory_content_sha256': inventory['content_sha256'],
              'data_license': 'CC-BY-NC-SA-4.0', 'pickle_downloaded_or_loaded': False,
              'curation_labels_or_predictions_inspected': False}
    write_json(output / 'acquisition_report.json', result)
    return result


def resources(frame, output, *, max_bytes=150_000_000):
    """Use native Gilda/Adeft download helpers; select exact blind-frame mentions."""
    for package, version in [('gilda', '1.6.1'), ('adeft', '0.13.0')]:
        if importlib.metadata.version(package) != version:
            raise ValueError('install the pinned optional runtime: ' + package)
    if any(name == 'gilda' or name.startswith('gilda.') or name == 'adeft'
           or name.startswith('adeft.') for name in sys.modules):
        raise ValueError('run resource setup in a fresh Python process before native imports')
    from .run import load_frame
    _, cases = load_frame(frame)
    mentions = {a['mention'].strip() for c in cases for a in c['input']['agents']
                if isinstance(a.get('mention'), str) and a['mention'].strip()}
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    os.environ['GILDA_HOME'] = str(output / 'resources' / 'gilda')
    os.environ['PYSTOW_HOME'] = str(output / 'resources')
    os.environ['ADEFT_HOME'] = str(output / 'adeft_models')
    from gilda.resources import get_grounding_terms, get_gilda_models
    from adeft.download.download import get_s3_models, download_models
    from adeft import locations as loc
    import boto3
    from botocore import UNSIGNED
    from botocore.client import Config
    s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    available = get_s3_models()
    if not isinstance(available, dict) or not available:
        raise ValueError('native published Adeft availability metadata unavailable')
    shortforms = sorted(mentions.intersection(available))
    directories = sorted({available[s] for s in shortforms})
    if any(not isinstance(s, str) or Path(s).name != s or s in {'.', '..'} for s in directories):
        raise ValueError('unexpected native Adeft model-directory metadata')
    files = [('gilda', '1.6.1/' + name) for name in GILDA_RESOURCE_HASHES]
    adeft_files = [(loc.S3_BUCKET, '/'.join((loc.S3_KEY_PREFIX, 'Models', d, d + suffix)))
                   for d in directories for suffix in ('_grounding_dict.json', '_names.json', '_model.gz')]
    metadata = []
    for bucket, key in files + adeft_files:
        head = s3.head_object(Bucket=bucket, Key=key)
        metadata.append({'bucket': bucket, 'key': key, 'bytes': head['ContentLength'],
                         'etag': head.get('ETag'), 'version_id': head.get('VersionId'),
                         'last_modified': head['LastModified'].isoformat()})
    if sum(row['bytes'] for row in metadata) > max_bytes:
        raise ValueError('selected native resources exceed requested byte bound')
    write_json(output / 'resource_metadata.json', metadata)
    write_json(output / 'adeft_availability.json', available)
    native_paths = [Path(get_grounding_terms()), Path(get_gilda_models())]
    download_models(directories)
    captured = []
    for row, path in zip(metadata[:len(files)], native_paths):
        if path.stat().st_size != row['bytes'] or file_hash(path) != GILDA_RESOURCE_HASHES[path.name]:
            raise ValueError('Gilda1.6.1 resource content differs from evaluated pins; require a new qualification/freeze')
        captured.append({**row, 'local_file': str(path), 'sha256': file_hash(path)})
    adeft_captured = []
    for row in metadata[len(files):]:
        _, _, directory, filename = row['key'].split('/', 3)
        path = Path(loc.ADEFT_MODELS_PATH) / directory / filename
        if path.stat().st_size != row['bytes']:
            raise ValueError('native Adeft download byte length differs')
        etag = (row['etag'] or '').strip('"')
        if re.fullmatch(r'[0-9a-f]{32}', etag):
            if hashlib.md5(path.read_bytes()).hexdigest() != etag:
                raise ValueError('native Adeft publisher checksum differs')
        adeft_captured.append({'local_file': str(path), 'bytes': path.stat().st_size,
            'sha256': file_hash(path), 'publisher_etag_md5': etag,
            'source_url': 'https://' + row['bucket'] + '.s3.amazonaws.com/' + quote(row['key'], safe='/')})
    receipt = {'created_at': now(), 'resources': captured,
        'published_native_download_helpers_used': True, 'Adeft_models_included': True,
        'grounding_predictions_run': False, 'free_disk_bytes': shutil.disk_usage(output).free,
        'adeft': {'version': '0.13.0', 'cache_home': os.environ['ADEFT_HOME'],
            'selection': 'Exact stripped source mentions in the label-blind primary frame; no outcome-based model choice.',
            'source_frame_cases_sha256': file_hash(Path(frame) / 'cases.jsonl.gz'),
            'selected_directories': directories, 'selected_shortforms': shortforms,
            'files': adeft_captured,
            'official_availability_sha256': file_hash(output / 'adeft_availability.json')},
        'reproduction_boundary': 'New receipt pins current native assets; compare all hashes with the released evaluation receipt before claiming exact numerical replay.'}
    write_json(output / 'resource_receipt.json', receipt)
    return receipt


def freeze(frame, contexts, resource_receipt, curations, output, *,
           acknowledge_source_only=False, parent_freeze=None):
    """Validate local prerequisites and write the existing runner contract.

    The acknowledgement is an operator declaration, not proof of historical
    blinding or permission to reuse a consumed holdout as new validation.
    No curator JSON values or prediction files are decoded by this helper.
    """
    if acknowledge_source_only is not True:
        raise ValueError('record --acknowledge-source-only; this is a declaration, not automatic blinding proof')
    from biograph_steward.client import digest
    from .context import load_context
    from .prepare import ordinary
    from .run import ARMS, NATIVE_VERSIONS, load_frame, sealed
    frame, contexts = Path(frame).absolute(), Path(contexts).absolute()
    receipt_path, curations = ordinary(resource_receipt), ordinary(curations)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite an evaluation freeze')
    versions = {name: importlib.metadata.version(name) for name in NATIVE_VERSIONS}
    if versions != NATIVE_VERSIONS:
        raise ValueError('install the pinned native runtime before freezing')
    # Hash only: the reference's categories/comments never become helper input.
    if file_hash(curations) != CURATIONS_SHA:
        raise ValueError('original released curation bytes differ')
    report, cases = load_frame(frame)
    here = Path(__file__).resolve().parent
    repo = here.parent.parent
    implementation = [here / name for name in (
        '__init__.py', 'native.py', 'context.py', 'prepare.py', 'run.py', 'evaluate.py', 'score.py')]
    implementation += [repo / 'biograph_steward' / name for name in (
        'client.py', 'file_utils.py', 'literature.py')]
    code_pins = {str(p): file_hash(ordinary(p)) for p in implementation}
    if (report.get('implementation_sha256') != code_pins[str(here / 'prepare.py')]
            or report.get('native_adapter_sha256') != code_pins[str(here / 'native.py')]):
        raise ValueError('rebuild the source frame with the current pinned implementation')
    source_pins = report['input_files_sha256']
    for name, pin in source_pins.items():
        if file_hash(ordinary(name)) != pin:
            raise ValueError('prepared frame source changed: ' + name)
    join_paths = [Path(p) for p in source_pins if Path(p).name == 'join_report.json']
    if len(join_paths) != 1:
        raise ValueError('expected one source join provenance report')
    join_report = sealed(join_paths[0])
    if (join_report.get('source_compressed_SHA256') != CORPUS_SHA
            or join_report.get('curations_SHA256') != CURATIONS_SHA
            or join_report.get('all_original_pair_IDs_joined') is not True
            or join_report.get('curation_tag_comment_or_correctness_fields_used') is not False
            or join_report.get('grounder_or_model_predictions_run') is not False):
        raise ValueError('source join does not bind the original outcome-free JSON release')
    context_by_pmid = load_context(contexts)
    expected_pmids = {c['pmid'] for c in cases if c['pmid'] is not None}
    if set(context_by_pmid) != expected_pmids:
        raise ValueError('publication context inventory differs from the prepared source frame')
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('grounding_predictions_run') is not False or receipt.get('Adeft_models_included') is not True:
        raise ValueError('use a source-only receipt for the complete native disambiguation setup')
    resource_pins, gilda_paths = {}, {}
    for row in receipt['resources']:
        path = ordinary(row['local_file'])
        if (path.name in gilda_paths or path.name not in GILDA_RESOURCE_HASHES
                or path.stat().st_size != row['bytes'] or file_hash(path) != row['sha256']
                or row['sha256'] != GILDA_RESOURCE_HASHES[path.name]):
            raise ValueError('native Gilda resource bytes differ or repeat')
        gilda_paths[path.name] = path
        resource_pins[str(path)] = row['sha256']
    if (set(gilda_paths) != set(GILDA_RESOURCE_HASHES)
            or len({p.parent for p in gilda_paths.values()}) != 1
            or next(iter(gilda_paths.values())).parent.name != '1.6.1'):
        raise ValueError('expected both native Gilda1.6.1 resources in one version directory')
    adeft = receipt['adeft']
    if adeft['version'] != '0.13.0':
        raise ValueError('native Adeft resource version differs')
    adeft_home = Path(adeft['cache_home']).absolute()
    expected_adeft = set()
    for row in adeft['files']:
        path = ordinary(row['local_file'])
        if (path in expected_adeft or adeft_home not in path.parents
                or path.stat().st_size != row['bytes'] or file_hash(path) != row['sha256']):
            raise ValueError('native Adeft resource bytes differ or repeat')
        expected_adeft.add(path)
        resource_pins[str(path)] = row['sha256']
    model_root = adeft_home / '0.13.0' / 'models'
    if ({p.absolute() for p in model_root.rglob('*') if p.is_file()} != expected_adeft
            or any(p.is_symlink() for p in model_root.rglob('*'))):
        raise ValueError('unexpected native Adeft model files')
    groups = {'development': set(), 'test': set()}
    counts = Counter()
    for case in cases:
        if case['split'] not in groups:
            raise ValueError('unexpected prepared partition')
        groups[case['split']].add(case['group_id'])
        counts[case['split']] += 1
    if groups['development'].intersection(groups['test']):
        raise ValueError('an exposure component crosses the prepared partition')
    inputs = {str(frame / 'report.json'): file_hash(frame / 'report.json'),
              str(contexts / 'manifest.json'): file_hash(contexts / 'manifest.json'),
              str(receipt_path): file_hash(receipt_path), str(curations): CURATIONS_SHA}
    plan = {'format': 'biograph-steward.grounding-claim-evaluation-freeze.v1',
        'created_at': now(), 'curation_categories_or_predictions_inspected_before_freeze': False,
        'source_only_acknowledgement': {
            'operator_declared': True,
            'declaration': 'This local setup used source/identity metadata, without using curation categories or model predictions to select or change the fixed inputs or method.',
            'independently_verified_blinding': False,
            'does_not_reset_prior_exposure_or_consumed_holdouts': True},
        'arms': list(ARMS), 'frame_report_sha256': inputs[str(frame / 'report.json')],
        'contexts_manifest_sha256': inputs[str(contexts / 'manifest.json')],
        'resource_receipt_sha256': inputs[str(receipt_path)], 'raw_curations_sha256': CURATIONS_SHA,
        'implementation_pins': code_pins, 'native_versions': versions,
        'question': 'Does a source mention refer to its assigned human gene identity? Candidate conflicts are review proposals, not replacement labels.',
        'reference': {'DOI': SOURCE_CONTRACT['paper_DOI'], 'Zenodo': 7559353,
            'license': SOURCE_CONTRACT['data_license'],
            'curation_policy': 'Unanimous native correct vs unanimous native grounding only; other, mixed and absent tags remain outside endpoint.'},
        'method': {'native_Gilda_paper': '10.1093/bioadv/vbac034',
            'context': 'Lexical vs evidence sentence vs exact numeric PMID PubMed title plus abstract; unavailable remains unresolved.',
            'Adeft': 'Native resources and source-only mention selection recorded in the pinned resource receipt.',
            'model_threshold': 'Native Gilda load_gilda_models default0.7; no fitted project threshold.',
            'prediction_rule': 'Native top candidate and explicit native mapping aliases vs assigned HGNC identity; other namespace/granularity or unavailable context remains unresolved.'},
        'split': {'seed': report['split_seed'], 'unit': report['split_policy'],
            'development_cases': counts['development'], 'reserved_test_cases': counts['test'],
            'training_paper_overlap_unknown': True},
        'primary_metrics': ['full_denominator_error_recall', 'full_denominator_false_conflict_rate',
            'conflict_precision', 'coverage', 'resolved_accuracy_explicit_denominator'],
        'secondary_metrics': 'Common-resolved intersection and paired transitions; no new significance claim.',
        'boundaries': ['External curator-relative component evaluation, not independent experimental biological truth or whole-Pharos precision.',
            'Gene-level only, not exact protein form, isoform, construct or causal mechanism.',
            'Reader/mention-count-stratified sample; no population accuracy inference.',
            'Training overlap unestablished; project-reserved test is not proven model-unseen.',
            'No automatic identifier replacement, biological pruning or new AI-assigned gold labels.',
            'A reproduced consumed holdout remains consumed; local paths, timestamps and manifest seals are not byte-identical historical reproduction.'],
        'outcome_handling': 'Preserve failures; no tuning on reserved test. A changed technical freeze must link its predecessor. Reproduction does not renew an already inspected holdout.',
        'local_input_paths_sha256': inputs, 'freeze_producer_sha256': file_hash(Path(__file__))}
    if parent_freeze is not None:
        parent_path = ordinary(parent_freeze)
        parent = sealed(parent_path)
        if parent.get('format') != plan['format']:
            raise ValueError('parent freeze is not the existing evaluation contract')
        plan['parent_freeze_reference'] = {'source_file_sha256': file_hash(parent_path),
            'content_sha256': parent['content_sha256'],
            'implementation_content_hashes_match': sorted(parent['implementation_pins'].values()) == sorted(code_pins.values()),
            'native_versions_match': parent.get('native_versions') == versions,
            'raw_curations_sha256_match': parent.get('raw_curations_sha256') == CURATIONS_SHA,
            'reproduction_is_not_new_independent_validation': True}
    if any(file_hash(ordinary(p)) != h for pins in (inputs, code_pins, resource_pins, source_pins)
           for p, h in pins.items()):
        raise ValueError('input or implementation changed while creating the local freeze')
    plan['content_sha256'] = digest(plan)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(plan, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    acquisition = commands.add_parser('acquire', help='capture official metadata and exact two JSON artifacts; no labels')
    acquisition.add_argument('--out', type=Path, required=True)
    join = commands.add_parser('join', help='stream source JSON and join only original reference identity keys')
    join.add_argument('--data', type=Path, required=True)
    join.add_argument('--out', type=Path, required=True)
    join.add_argument('--minimum-free-bytes', type=int, default=700_000_000)
    resource = commands.add_parser('resources', help='capture native optional resources for exact blind-frame mentions')
    resource.add_argument('--frame', type=Path, required=True)
    resource.add_argument('--out', type=Path, required=True)
    resource.add_argument('--max-bytes', type=int, default=150_000_000)
    frozen = commands.add_parser('freeze', help='validate local source inputs and write the existing runner contract')
    for name in ('frame', 'contexts', 'resources', 'curations', 'out'):
        frozen.add_argument('--' + name, type=Path, required=True)
    frozen.add_argument('--parent-freeze', type=Path)
    frozen.add_argument('--acknowledge-source-only', action='store_true',
                        help='record source-only setup declaration; does not prove blinding or reset consumed holdouts')
    args = parser.parse_args()
    if args.command == 'acquire':
        result = acquire(args.out)
    elif args.command == 'join':
        result = join_native(args.data, args.out, minimum_free_bytes=args.minimum_free_bytes)
    elif args.command == 'resources':
        result = resources(args.frame, args.out, max_bytes=args.max_bytes)
    else:
        result = freeze(args.frame, args.contexts, args.resources, args.curations, args.out,
                        acknowledge_source_only=args.acknowledge_source_only,
                        parent_freeze=args.parent_freeze)
    print(json.dumps({'command': args.command, 'output': str(args.out),
                      'labels_or_predictions_run': False,
                      'report_format': result.get('format', 'native-resource-receipt')}, indent=2))


if __name__ == '__main__':
    main()

