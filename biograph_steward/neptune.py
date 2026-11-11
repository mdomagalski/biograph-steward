"""Lossless, immutable Neptune query mirror of an already verified graph.

The saved packet remains authoritative. This adapter does not infer predicates,
acceptance, symmetry or scientific truth. Each top-level array is an ordered
record inventory; its original JSON is retained, including unrecognized fields.
Neptune scalar properties are searchable indexes over those preserved records.

Uses AWS's openCypher CSV loader and optional boto3 ``neptunedata`` client:
https://docs.aws.amazon.com/neptune/latest/userguide/bulk-load-tutorial-format-opencypher.html
https://docs.aws.amazon.com/neptune/latest/userguide/opencypher-parameterized-queries.html
"""
from __future__ import annotations

from copy import deepcopy
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

from .assertions import QUALIFIERS, CONTEXT_QUALIFIERS
from .client import canonical, digest, utcnow, write_json

FORMAT = "biograph-steward.neptune-mirror.v1"
MANIFEST = "projection_manifest.json"
# An application bound, not a claim about Neptune's maximum property size.
# Neptune Database documents 55 MB per property/label, distinct from Analytics:
# https://docs.aws.amazon.com/neptune/latest/userguide/limits.html
MAX_RECORD_BYTES = 16 * 1024 * 1024
PAGE_SIZE = 500
MAX_INSPECT = 1000
LABELS = {"nodes": "Entity", "assertions": "Assertion", "context_records": "Context",
          "review_events": "ReviewEvent", "quarantine": "Quarantine",
          "assay_observations": "AssayObservation"}
QUALIFIER_FIELDS = tuple(dict.fromkeys(QUALIFIERS + CONTEXT_QUALIFIERS))
STRING_FIELDS = ("dataset_id", "inventory", "record_role", "source_id", "record_json", "record_sha256",
                 "predicate", "record_kind", "assertion_id", "assertion_db_id", "status",
                 "review_state", "symmetric", "qualifiers_json") + tuple("q_" + k for k in QUALIFIER_FIELDS)
PROPERTIES = [(name, "String") for name in STRING_FIELDS] + [("ordinal", "Long")]

# Fixed query text; values and cursors are always parameters, never interpolated.
_NODES = """MATCH (n)
WHERE (id(n) STARTS WITH $prefix OR n.dataset_id = $dataset_id) AND id(n) > $after
RETURN id(n) AS db_id, labels(n) AS labels, properties(n) AS props
ORDER BY db_id LIMIT 500"""
_EDGES = """MATCH (s)-[e]->(o)
WHERE (id(e) STARTS WITH $prefix OR e.dataset_id = $dataset_id
       OR id(s) STARTS WITH $prefix OR id(o) STARTS WITH $prefix) AND id(e) > $after
RETURN id(e) AS db_id, id(s) AS from_id, id(o) AS to_id, type(e) AS edge_type, properties(e) AS props
ORDER BY db_id LIMIT 500"""
_NODE = """MATCH (n) WHERE id(n) = $node_id
RETURN id(n) AS db_id, labels(n) AS labels, properties(n) AS props"""
_INCIDENT = """MATCH (s:Entity)-[e:EVIDENCE_RECORD]->(o:Entity)
WHERE id(s) = $node_id OR id(o) = $node_id
RETURN id(e) AS db_id, id(s) AS from_id, id(o) AS to_id, type(e) AS edge_type, properties(e) AS props
ORDER BY db_id LIMIT 1001"""
_ASSERTIONS = """MATCH (n:Assertion) WHERE id(n) IN $ids
RETURN id(n) AS db_id, labels(n) AS labels, properties(n) AS props
ORDER BY db_id"""


def _seal(value):
    value["content_sha256"] = digest(value)
    return value


def _sdk_call(function, **kwargs):
    """Translate optional SDK failures without exposing request/credential text.

    Import exception classes only on failure: injected clients and ordinary
    offline projection do not require boto3/botocore to be installed.
    Programming errors in an injected client retain their original exception.
    """
    try:
        return function(**kwargs)
    except Exception as exc:
        try:
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError:
            raise exc
        if not isinstance(exc, (BotoCoreError, ClientError)):
            raise
        code = type(exc).__name__
        if isinstance(exc, ClientError):
            response = getattr(exc, "response", None)
            error = response.get("Error") if isinstance(response, dict) else None
            candidate = error.get("Code") if isinstance(error, dict) else None
            if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", candidate):
                code = candidate
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", code):
            code = "SDKError"
        raise ValueError("Neptune API request failed (" + code + "). Check IAM permissions, endpoint and network configuration.") from None


def _json(value):
    """Reject non-JSON values rather than silently coercing or dropping them."""
    def check(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
            return
        raise ValueError("Graph records must contain finite JSON values with string object keys.")
    check(value)
    result = canonical(value)
    # JSON escaping turns source NULs into literal backslash-u text, supported
    # by Neptune strings; csv.writer separately handles quotes/newlines/commas.
    if len(result.encode("utf-8")) > MAX_RECORD_BYTES:
        raise ValueError("A mirror record exceeds the local 16 MiB record-size bound; no data was omitted.")
    return result


def _db_id(dataset, inventory, identity):
    return dataset + ":" + inventory + ":" + digest(identity)


def _indexed(record):
    if not isinstance(record, dict):
        return {}
    result = {}
    for source, target in (("predicate", "predicate"), ("record_kind", "record_kind"),
                           ("kind", "record_kind"), ("assertion_id", "assertion_id"),
                           ("status", "status"), ("lifecycle_state", "review_state")):
        if isinstance(record.get(source), str) and record[source]:
            result[target] = record[source]
    if type(record.get("symmetric")) is bool:
        result["symmetric"] = "true" if record["symmetric"] else "false"
    qualifiers = record.get("qualifiers")
    if isinstance(qualifiers, dict):
        result["qualifiers_json"] = _json(qualifiers)
        for name in QUALIFIER_FIELDS:
            value = qualifiers.get(name)
            if value is not None and type(value) in (str, bool, int, float):
                # Every index is String; original JSON preserves the value type.
                rendered = value if isinstance(value, str) else canonical(value)
                if rendered:
                    result["q_" + name] = rendered
    return result


def _projection(graph):
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list) or not isinstance(graph.get("assertions"), list):
        raise ValueError("A verified graph requires node, evidence-edge and assertion inventories.")
    # Validate the entire graph, without imposing the per-record size bound on it.
    inventories = {key: value for key, value in graph.items() if isinstance(value, list)}
    metadata = {key: value for key, value in graph.items() if key not in inventories}
    _json(metadata)
    if any(not isinstance(name, str) for name in graph):
        raise ValueError("Graph keys must be strings.")
    indexes = {}
    for name, rows in inventories.items():
        seen = set()
        for row in rows:
            _json(row)
            if isinstance(row, dict) and "id" in row:
                uid = row["id"]
                if not isinstance(uid, str) or not uid or uid in seen:
                    raise ValueError("Inventory has an invalid or duplicate source identifier: " + name)
                seen.add(uid)
        indexes[name] = seen
    for name in ("nodes", "edges", "assertions"):
        if any(not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] for row in graph[name]):
            raise ValueError("Core mirror inventories require exact source identifiers: " + name)
    assertion_by_id = {row["id"]: row for row in graph["assertions"]}
    for edge in graph["edges"]:
        if (edge.get("subject") not in indexes["nodes"] or edge.get("object") not in indexes["nodes"]
                or edge.get("assertion_id") not in indexes["assertions"]):
            raise ValueError("Evidence refers to an unknown node or assertion.")
        assertion = assertion_by_id[edge["assertion_id"]]
        if ((edge.get("subject"), edge.get("predicate"), edge.get("object")) !=
                (assertion.get("subject"), assertion.get("predicate"), assertion.get("object"))
                or edge["id"] not in assertion.get("evidence_edge_ids", [])):
            raise ValueError("Evidence endpoints or support disagree with the saved assertion.")
    support_by_assertion = {uid: set() for uid in assertion_by_id}
    for edge in graph["edges"]:
        support_by_assertion[edge["assertion_id"]].add(edge["id"])
    for assertion in graph["assertions"]:
        support = assertion.get("evidence_edge_ids")
        if (assertion.get("subject") not in indexes["nodes"] or assertion.get("object") not in indexes["nodes"]
                or not isinstance(support, list) or any(not isinstance(uid, str) for uid in support)
                or len(support) != len(set(support))
                or set(support) != support_by_assertion[assertion["id"]]):
            raise ValueError("Assertion support does not match the evidence inventory.")
    graph_sha = digest(graph)
    dataset = "bgs:" + graph_sha
    vertices, relationships = {}, {}

    def properties(inventory, ordinal, source_id, record, role="inventory"):
        return {"dataset_id": dataset, "inventory": inventory, "record_role": role, "ordinal": ordinal,
                "source_id": source_id, "record_json": _json(record),
                "record_sha256": digest(record), **_indexed(record)}

    metadata_record = {"metadata": metadata, "inventories": {name: len(rows) for name, rows in inventories.items()}}
    meta_id = _db_id(dataset, "metadata", "metadata")
    vertices[meta_id] = {"db_id": meta_id, "labels": ["Metadata"],
                         "props": properties("metadata", 0, "metadata", metadata_record, "metadata")}
    for name, rows in inventories.items():
        for ordinal, record in enumerate(rows):
            source_id = record.get("id") if isinstance(record, dict) else None
            identity = ["id", source_id] if source_id is not None else ["ordinal", ordinal]
            source_id = source_id if source_id is not None else str(ordinal)
            uid = _db_id(dataset, name, identity)
            props = properties(name, ordinal, source_id, record)
            if name == "edges":
                props["assertion_db_id"] = _db_id(dataset, "assertions", ["id", record["assertion_id"]])
                relationships[uid] = {"db_id": uid,
                    "from_id": _db_id(dataset, "nodes", ["id", record["subject"]]),
                    "to_id": _db_id(dataset, "nodes", ["id", record["object"]]),
                    "edge_type": "EVIDENCE_RECORD", "props": props}
            else:
                vertices[uid] = {"db_id": uid, "labels": [LABELS.get(name, "Record")], "props": props}
    return {"dataset_id": dataset, "graph_sha256": graph_sha, "prefix": dataset + ":",
            "vertices": vertices, "relationships": relationships,
            "inventory_counts": {name: len(rows) for name, rows in inventories.items()}}


def export_projection(graph, output):
    """Write an official openCypher CSV package without changing input records.

    ``graph`` must first be verified by the existing saved-run/packet loader.
    The export rejects existing outputs and uses a sibling temporary directory.
    """
    projection = _projection(graph)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new Neptune projection output directory.")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".neptune-", dir=output.parent))
    try:
        for filename, collection, system in (
                ("nodes.csv", "vertices", [":ID", ":LABEL"]),
                ("relationships.csv", "relationships", [":ID", ":START_ID", ":END_ID", ":TYPE"])):
            with (stage / filename).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\r\n")
                writer.writerow(system + [name + ":" + kind for name, kind in PROPERTIES])
                for uid, row in sorted(projection[collection].items()):
                    fields = [uid, ";".join(row["labels"])] if collection == "vertices" else [uid, row["from_id"], row["to_id"], row["edge_type"]]
                    writer.writerow(fields + [row["props"].get(name, "") for name, _ in PROPERTIES])
        manifest = _seal({"format": FORMAT, "created_at": utcnow(),
            "dataset_id": projection["dataset_id"], "graph_sha256": projection["graph_sha256"],
            "prefix": projection["prefix"], "loader_format": "opencypher", "user_provided_edge_ids": True,
            "counts": {"vertices": len(projection["vertices"]), "relationships": len(projection["relationships"]),
                       "inventories": projection["inventory_counts"]},
            "files": {name: hashlib.sha256((stage / name).read_bytes()).hexdigest()
                      for name in ("nodes.csv", "relationships.csv")},
            "queryable": False, "biological_validation_performed": False,
            "note": "Query mirror only. The source packet remains authoritative. A completed loader job and full mirror verification are required before selection."})
        write_json(stage / MANIFEST, manifest)
        if output.exists() or output.is_symlink():
            raise ValueError("Projection output appeared during export.")
        stage.rename(output)
        return manifest
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


class Mirror:
    """IAM-signed Neptune Database client; no arbitrary application query API."""

    def __init__(self, endpoint, region, client=None):
        parsed = urlsplit(endpoint) if isinstance(endpoint, str) else None
        if (parsed is None or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region)):
            raise ValueError("Supply a credential-free HTTPS Neptune endpoint and AWS region.")
        self.endpoint, self.region = endpoint.rstrip("/"), region
        if client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise ValueError("Neptune requires the optional AWS boto3 dependency.") from exc
            client = _sdk_call(boto3.client, service_name="neptunedata", endpoint_url=self.endpoint, region_name=region,
                config=Config(connect_timeout=10, read_timeout=120, retries={"total_max_attempts": 1}))
        self.client = client
        self._verified = {}

    def load(self, source_s3_uri, role_arn, *, parallelism="LOW"):
        """Start, never silently retry, a standard bulk load from a CSV-only prefix.

        Upload just nodes.csv and relationships.csv under the source prefix;
        manifests/source packets belong outside it. A load response alone does
        not make a dataset queryable. Use loader_status and verify afterwards.
        """
        parsed = urlsplit(source_s3_uri) if isinstance(source_s3_uri, str) else None
        if (parsed is None or parsed.scheme != "s3" or not parsed.netloc or parsed.username or parsed.password
                or not parsed.path.strip("/") or parsed.query or parsed.fragment
                or not isinstance(role_arn, str) or not re.fullmatch(r"arn:[a-z0-9-]+:iam::\d{12}:role/[A-Za-z0-9+=,.@_/-]+", role_arn)
                or parallelism not in {"LOW", "MEDIUM", "HIGH", "OVERSUBSCRIBE"}):
            raise ValueError("Supply an S3 data prefix, loader IAM role ARN and supported parallelism.")
        self._verified.clear()
        return _sdk_call(self.client.start_loader_job, source=source_s3_uri, format="opencypher",
            s3BucketRegion=self.region, iamRoleArn=role_arn, mode="NEW", failOnError=True,
            parallelism=parallelism, updateSingleCardinalityProperties=False,
            userProvidedEdgeIds=True)

    def loader_status(self, load_id):
        if not isinstance(load_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", load_id):
            raise ValueError("Supply the loader job identifier.")
        return _sdk_call(self.client.get_loader_job_status, loadId=load_id, details=True, errors=True)

    def _query(self, query, parameters):
        response = _sdk_call(self.client.execute_open_cypher_query, openCypherQuery=query, parameters=canonical(parameters))
        rows = response.get("results") if isinstance(response, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Neptune returned an invalid query result.")
        return rows

    @staticmethod
    def _check(row, expected):
        if row != expected:
            raise ValueError("Neptune mirror differs from the preserved graph record or endpoint.")
        # Checking the whole property map also detects changed searchable indexes.
        record = json.loads(row["props"]["record_json"])
        if digest(record) != row["props"]["record_sha256"]:
            raise ValueError("Neptune record content does not match its saved hash.")

    def verify(self, graph):
        """Rescan all IDs, labels, full records, indexes and edge endpoints.

        Keyset pages are fixed at 500. A successful receipt is cached only for
        this immutable graph digest; inspect validates its returned rows again.
        """
        projection = _projection(graph)
        receipt, _ = self._verified_read(projection)
        return receipt

    def _verified_read(self, projection, *, collect=False):
        """One shared paged scan for parity audits and actual DB reconstruction."""
        key = projection["graph_sha256"]
        self._verified.pop(key, None)
        counts = {}
        records = [] if collect else None
        for collection, query in (("vertices", _NODES), ("relationships", _EDGES)):
            expected = projection[collection]
            seen, after = set(), ""
            while True:
                rows = self._query(query, {"prefix": projection["prefix"], "dataset_id": projection["dataset_id"], "after": after})
                if len(rows) > PAGE_SIZE:
                    raise ValueError("Neptune verification exceeded the fixed page bound.")
                for row in rows:
                    uid = row.get("db_id")
                    if not isinstance(uid, str) or uid <= after or uid in seen or uid not in expected:
                        raise ValueError("Neptune mirror has missing, duplicate, unordered or unknown identifiers.")
                    self._check(row, expected[uid])
                    if records is not None:
                        records.append(row)
                    seen.add(uid)
                    after = uid
                if len(rows) < PAGE_SIZE:
                    break
                if len(seen) > len(expected):
                    raise ValueError("Neptune mirror contains extra records.")
            if seen != set(expected):
                raise ValueError("Neptune mirror is incomplete; source inventory identifiers are missing.")
            counts[collection] = len(seen)
        receipt = _seal({"format": FORMAT + ".verification", "dataset_id": projection["dataset_id"],
            "graph_sha256": key, "verified_at": utcnow(), "endpoint": self.endpoint,
            "region": self.region, "counts": counts, "complete_record_parity": True,
            "biological_validation_performed": False,
            "note": "Complete mirror parity at the recorded time; immutable namespace and write-revocation policy must be maintained. Source artifacts remain authoritative."})
        self._verified[key] = deepcopy(receipt)
        return receipt, records

    def export_graph(self, graph, output):
        """Reconstruct this adapter's exact canonical graph from verified DB rows.

        Always makes a fresh complete paged read, even if inspect has a cached
        receipt. This is the inverse of our lossless projection, not a general
        export of arbitrary Neptune data. AWS's official ``neptune-export``
        remains the tool for a raw database export:
        https://docs.aws.amazon.com/neptune/latest/userguide/neptune-export.html
        """
        projection = _projection(graph)
        output = Path(output)
        if output.exists() or output.is_symlink():
            raise ValueError("Choose a new verified Neptune graph-export directory.")
        verification, rows = self._verified_read(projection, collect=True)
        metadata = [json.loads(row["props"]["record_json"]) for row in rows
                    if row["props"]["record_role"] == "metadata"]
        if len(metadata) != 1:
            raise ValueError("Verified mirror must have one reconstruction metadata record.")
        reconstructed = deepcopy(metadata[0]["metadata"])
        for inventory, length in metadata[0]["inventories"].items():
            inventory_rows = [row for row in rows if row["props"]["record_role"] == "inventory"
                              and row["props"]["inventory"] == inventory]
            inventory_rows.sort(key=lambda row: row["props"]["ordinal"])
            if [row["props"]["ordinal"] for row in inventory_rows] != list(range(length)):
                raise ValueError("Verified mirror cannot reconstruct a complete ordered inventory.")
            reconstructed[inventory] = [json.loads(row["props"]["record_json"]) for row in inventory_rows]
        if digest(reconstructed) != projection["graph_sha256"]:
            raise ValueError("Database reconstruction does not reproduce the complete source graph digest.")
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".neptune-export-", dir=output.parent))
        try:
            write_json(stage / "graph.json", reconstructed)
            receipt = _seal({"format": FORMAT + ".export", "exported_at": utcnow(),
                "dataset_id": projection["dataset_id"], "graph_sha256": projection["graph_sha256"],
                "reconstructed_from_database": True, "complete_graph_parity": True,
                "verification": verification,
                "files": {"graph.json": hashlib.sha256((stage / "graph.json").read_bytes()).hexdigest()},
                "biological_validation_performed": False,
                "note": "Actual database records reconstructed through this adapter's projection inverse. Saved source artifacts remain authoritative; this is not a general Neptune database export or biological validation."})
            write_json(stage / "export_receipt.json", receipt)
            if output.exists() or output.is_symlink():
                raise ValueError("Graph-export output appeared during reconstruction.")
            stage.rename(output)
            return receipt
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise

    def inspect(self, graph, node_id, limit=100):
        """Return incident source evidence, without biological/review filtering.

        Incidence is not acceptance or physical binding. This is not an inverse
        assertion: original subject/object direction remains in each record.
        Successful full parity is cached; each selected record is checked fresh.
        """
        if type(limit) is not int or not 1 <= limit <= MAX_INSPECT:
            raise ValueError("Use an inspection limit from 1 to 1000.")
        projection = _projection(graph)
        if not isinstance(node_id, str) or node_id not in {row["id"] for row in graph["nodes"]}:
            raise ValueError("Choose an exact node identifier from the saved graph.")
        key = projection["graph_sha256"]
        receipt = self._verified.get(key)
        if receipt is None:
            receipt = self.verify(graph)
        node_db_id = _db_id(projection["dataset_id"], "nodes", ["id", node_id])
        node_rows = self._query(_NODE, {"node_id": node_db_id})
        if len(node_rows) != 1:
            raise ValueError("Neptune mirror is missing the selected entity.")
        self._check(node_rows[0], projection["vertices"][node_db_id])
        expected = {uid: row for uid, row in projection["relationships"].items()
                    if node_db_id in (row["from_id"], row["to_id"])}
        rows = self._query(_INCIDENT, {"node_id": node_db_id})
        if [row.get("db_id") for row in rows] != sorted(expected)[:MAX_INSPECT + 1]:
            raise ValueError("Neptune incident evidence is missing, extra, duplicated or unordered.")
        for row in rows:
            self._check(row, expected[row["db_id"]])
        selected = rows[:limit]
        assertion_ids = sorted({row["props"]["assertion_db_id"] for row in selected})
        assertions = self._query(_ASSERTIONS, {"ids": assertion_ids}) if assertion_ids else []
        if [row.get("db_id") for row in assertions] != assertion_ids:
            raise ValueError("Neptune incident assertion support is incomplete.")
        for row in assertions:
            self._check(row, projection["vertices"][row["db_id"]])
        evidence = [json.loads(row["props"]["record_json"]) for row in selected]
        source_assertions = [json.loads(row["props"]["record_json"]) for row in assertions]
        return {"format": FORMAT + ".inspection", "dataset_id": projection["dataset_id"],
            "graph_sha256": key, "node_id": node_id, "limit": limit,
            "edge_ids": [row["id"] for row in evidence],
            "assertion_ids": [row["id"] for row in source_assertions],
            "node": json.loads(node_rows[0]["props"]["record_json"]),
            "edges": evidence, "assertions": source_assertions,
            "truncated": len(rows) > limit, "full_parity_verified_at": receipt["verified_at"],
            "verification_receipt_sha256": receipt["content_sha256"],
            "interpretation": "Incident source records with unchanged direction, qualifiers and review states. Incidence does not establish acceptance, physical binding or biological validity. Full parity was audited at the recorded time; returned records were checked again."}
