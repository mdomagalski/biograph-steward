"""Invented HTTP fixtures only: these tests never query STRING or use outcomes."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from itertools import combinations
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from biograph_steward.client import digest
from biograph_steward import physical_ranking as ranking
from biograph_steward import string_component as component


def _tsv(columns, rows):
    return ("\t".join(columns) + "\n" + "".join(
        "\t".join(str(row[column]) for column in columns) + "\n" for row in rows)).encode()


class Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, value):
        self.value += value


class FixtureSource:
    """A fully invented version/mapping/reciprocal-network REST source."""
    def __init__(self, *, mapping=None, physical=None, functional=None, absent_pairs=None):
        self.mapping = mapping or {}
        self.physical = physical or {}
        self.functional = functional or {}
        self.absent_pairs = absent_pairs or set()
        self.urls = []
        self.prepend = []

    def sid(self, accession):
        return self.mapping.get(accession, "9606.TEST" + accession)

    def __call__(self, url, *, timeout, max_bytes):
        self.urls.append(url)
        if self.prepend:
            value = self.prepend.pop(0)
            if isinstance(value, Exception):
                raise value
            status, body = value
            return {"status": status, "url": url, "body": body,
                    "headers": {"Content-Length": str(len(body))}}
        parsed = urlparse(url)
        method = parsed.path.rsplit("/", 1)[-1]
        query = parse_qs(parsed.query)
        identifiers = query.get("identifiers", [""])[0].split("\r")
        if method == "version":
            body = b"string_version\tstable_address\n12.5\thttps://version-12-5.string-db.org\n"
        elif method == "get_string_ids":
            rows = []
            for index, accession in enumerate(identifiers):
                values = self.sid(accession)
                if values is None:
                    continue
                for sid in values if isinstance(values, list) else [values]:
                    rows.append(dict(zip(component.MAPPING_COLUMNS,
                        (index, accession, sid, "9606", "Homo sapiens", "invented", "invented"))))
            body = _tsv(component.MAPPING_COLUMNS, rows)
        elif method == "network":
            rows = []
            for left, right in combinations(identifiers, 2):
                pair = tuple(sorted((left, right)))
                if pair in self.absent_pairs:
                    continue
                values = {column: "0" for column in component.FUNCTIONAL_COLUMNS}
                values.update({column: "-" for column in component.PHYSICAL_COLUMNS + component.REGULATORY_COLUMNS})
                values.update(stringId_A=left, stringId_B=right,
                    preferredName_A=left[5:], preferredName_B=right[5:], ncbiTaxonId="9606", sign="n/a",
                    functional_combined_score=self.functional.get(pair, "0.8"),
                    physical_combined_score=self.physical.get(pair, "0.2"))
                rows.extend([values, {**values, "stringId_A": right, "stringId_B": left,
                                     "preferredName_A": right[5:], "preferredName_B": left[5:]}])
            body = _tsv(component.NETWORK_COLUMNS, rows)
        else:
            raise AssertionError("Unplanned fixture request: " + url)
        return {"status": 200, "headers": {"Content-Type": "text/tab-separated-values; charset=utf-8",
                "string-api-version": "2", "Content-Length": str(len(body))}, "url": url, "body": body}


def fixture(neighbors=None):
    """Real-looking IDs deliberately wrap invented scores, not biological data."""
    neighbors = neighbors or ["P00533", "P15056", "P01116"]
    anchor = "UniProtKB:P04637"
    nodes = [{"id": anchor, "type": "protein", "sym": "invented anchor"}]
    nodes.extend({"id": "UniProtKB:" + accession, "type": "protein", "sym": "invented " + accession}
                 for accession in neighbors)
    graph = {"graph_format": "biograph-steward.evidence-graph.v1", "data_kind": "live_pharos",
             "snapshot_sha256": digest("invented fixture snapshot"), "nodes": nodes,
             "assertions": [], "review_events": []}
    candidates = [{"protein": deepcopy(node), "paths": [{"id": "invented-path"}],
                   "matched_relations": {"interaction": 1}, "eligible_path_count": 1}
                  for node in nodes[1:]]
    return graph, anchor, candidates


def capture(graph=None, anchor=None, candidates=None, source=None):
    if graph is None:
        graph, anchor, candidates = fixture()
    clock = Clock()
    return ranking.collect_ranking(graph, anchor, candidates, fetcher=source or FixtureSource(),
                                   clock=clock.now, sleep=clock.sleep)


def reseal(packet):
    packet["content_sha256"] = digest({key: value for key, value in packet.items()
                                       if key != "content_sha256"})
    return packet


def change_body(request, text):
    receipt = request["attempts"][-1]
    raw = text.encode()
    receipt.update(body_text=text, body_bytes=len(raw), body_sha256=hashlib.sha256(raw).hexdigest())
    receipt["headers"]["Content-Length"] = str(len(raw))


class CaptureTests(unittest.TestCase):
    def test_replay_binds_real_looking_fixture_nodes_without_mutating_graph(self):
        graph, anchor, candidates = fixture()
        before = deepcopy((graph, candidates))
        packet = capture(graph, anchor, candidates)
        self.assertEqual(ranking.verify_packet(packet, graph, candidates, anchor), packet)
        self.assertEqual((graph, candidates), before)
        self.assertEqual([request["kind"] for request in packet["requests"]], ["version", "mapping", "network"])
        self.assertEqual(len(packet["requested_candidates"]), 3)
        self.assertNotIn("paths", packet["requested_candidates"][0])
        ann = packet["annotations"]["UniProtKB:P00533"]
        self.assertEqual(ann["views"]["physical"]["native_score"], 0.2)
        self.assertEqual(ann["mapping_proof"][0]["correspondence"], "STRING_locus_representative_not_sequence_identity")
        self.assertEqual(ann["network_source_row_numbers"], [4, 5])
        self.assertEqual(packet["profile"]["required_score"], "0")

    def test_zero_and_missing_overlay_and_no_row_are_distinct(self):
        source = FixtureSource()
        anchor = source.sid("P04637")
        source.physical[tuple(sorted((anchor, source.sid("P00533"))))] = "0"
        source.physical[tuple(sorted((anchor, source.sid("P15056"))))] = "-"
        source.absent_pairs.add(tuple(sorted((anchor, source.sid("P01116")))))
        packet = capture(source=source)
        rows = packet["annotations"]
        self.assertEqual(rows["UniProtKB:P00533"]["views"]["physical"],
                         {"state": "numeric", "native_score": 0.0, "ranking_score": 0.0})
        self.assertEqual(rows["UniProtKB:P15056"]["views"]["physical"]["state"], "physical_not_returned_under_profile")
        self.assertEqual(rows["UniProtKB:P01116"]["views"]["physical"]["state"], "no_returned_functional_row")

    def test_pathway_only_is_retained_unqueried_and_no_eligible_calls_nothing(self):
        graph, anchor, candidates = fixture()
        candidates[0]["matched_relations"] = {"shared_pathway": 2}
        packet = capture(graph, anchor, candidates)
        self.assertNotIn("P00533", packet["mappings"])
        self.assertEqual(packet["annotations"]["UniProtKB:P00533"]["views"]["physical"]["state"], "not_interaction_path")
        for row in candidates:
            row["matched_relations"] = {"shared_pathway": 1}
        packet = capture(graph, anchor, candidates)
        self.assertEqual(packet["requests"], [])
        self.assertIsNone(packet["source_version"])

    def test_exact_isoform_unmapped_ambiguous_and_collapsed_remain_distinct(self):
        graph, anchor, candidates = fixture(["P00533-2", "P15056", "P01116", "P22674"])
        source = FixtureSource(mapping={"P00533-2": None, "P15056": ["9606.ONE", "9606.TWO"],
                                       "P01116": "9606.TESTP04637"})
        packet = capture(graph, anchor, candidates, source)
        self.assertIn("P00533-2", packet["mappings"])
        self.assertNotIn("P00533", packet["mappings"])
        states = {uid: row["views"]["physical"]["state"] for uid, row in packet["annotations"].items()}
        self.assertEqual(states["UniProtKB:P00533-2"], "unmapped")
        self.assertEqual(states["UniProtKB:P15056"], "ambiguous")
        self.assertEqual(states["UniProtKB:P01116"], "collapsed_representative")
        self.assertEqual(states["UniProtKB:P22674"], "numeric")

    def test_all_unmapped_needs_version_mapping_but_no_network(self):
        packet = capture(source=FixtureSource(mapping={"P04637": None}))
        self.assertEqual([row["kind"] for row in packet["requests"]], ["version", "mapping"])
        self.assertTrue(all(row["views"]["physical"]["state"] == "unmapped"
                            for row in packet["annotations"].values()))

    def test_demo_invalid_id_and_overlimit_fail_before_any_request(self):
        graph, anchor, candidates = fixture()
        source = FixtureSource()
        for invalid in ["synthetic_demo", "unknown"]:
            changed = deepcopy(graph); changed["data_kind"] = invalid
            with self.assertRaises(ValueError):
                capture(changed, anchor, candidates, source)
        for invalid in ["UniProtKB:FAKE01", "P04637", "UniProtKB:P04637-0", "UniProtKB:P04637\n"]:
            with self.assertRaises(ValueError):
                capture(graph, invalid, candidates, source)
        graph, anchor, candidates = fixture(["P%05d" % index for index in range(10000, 10101)])
        with self.assertRaises(ValueError):
            capture(graph, anchor, candidates, source)
        self.assertEqual(source.urls, [])

    def test_full_limit_has_exact_seven_logical_calls_and_100_coverage(self):
        graph, anchor, candidates = fixture(["P%05d" % index for index in range(10000, 10100)])
        packet = capture(graph, anchor, candidates)
        self.assertEqual(len(packet["requests"]), 7)
        self.assertEqual([len(row["identifiers"]) for row in packet["requests"]], [0, 100, 1, 26, 26, 26, 26])
        self.assertEqual(len(packet["annotations"]), 100)
        self.assertEqual(len(packet["queried_candidate_ids"]), 100)

    def test_default_transport_rate_gate_spans_concurrent_and_subsequent_answers(self):
        clock, source = Clock(), FixtureSource()
        start = threading.Barrier(4)
        observations = {"active": 0, "max_active": 0, "starts": []}
        observation_lock = threading.Lock()

        def transport(url, **kwargs):
            with observation_lock:
                observations["active"] += 1
                observations["max_active"] = max(observations["max_active"], observations["active"])
                observations["starts"].append(clock.now())
            # Give competing HTTP-handler threads an opportunity to call the
            # transport. This test waits only milliseconds, not provider time.
            time.sleep(0.002)
            try:
                return source(url, **kwargs)
            finally:
                with observation_lock:
                    observations["active"] -= 1

        def collect():
            start.wait(timeout=5)
            return ranking.collect_ranking(*fixture(), clock=clock.now, sleep=clock.sleep)

        with patch.object(ranking, "_SOURCE_LAST_START", None), patch.object(ranking, "_fetch", transport):
            with ThreadPoolExecutor(max_workers=3) as pool:
                work = [pool.submit(collect) for _ in range(3)]
                start.wait(timeout=5)
                packets = [future.result(timeout=5) for future in work]
            # A new answer must honor the previous answer's final send, too.
            packets.append(ranking.collect_ranking(*fixture(), clock=clock.now, sleep=clock.sleep))
        self.assertEqual(observations["max_active"], 1)
        starts = observations["starts"]
        self.assertEqual(len(starts), 12)
        self.assertTrue(all(right - left + 1e-9 >= 1.05 for left, right in zip(starts, starts[1:])))
        receipts = sorted(attempt["started_monotonic"] for packet in packets
                          for request in packet["requests"] for attempt in request["attempts"])
        self.assertEqual(receipts, starts)
        self.assertTrue(all(ranking.verify_packet(packet) == packet for packet in packets))

    def test_network_and_retryable_http_failures_preserve_each_attempt(self):
        source = FixtureSource()
        source.prepend = [OSError("invented connection failure"), (503, b"invented retry response")]
        packet = capture(source=source)
        attempts = packet["requests"][0]["attempts"]
        self.assertEqual([row["status"] for row in attempts], [None, 503, 200])
        self.assertEqual(attempts[1]["body_text"], "invented retry response")
        self.assertEqual(ranking.verify_packet(packet), packet)

    def test_429_and_nonretryable_http_stop_without_imputation(self):
        for status in [429, 400, 404, 302]:
            source = FixtureSource(); source.prepend = [(status, b"invented stop")]
            with self.subTest(status=status), self.assertRaises(ValueError):
                capture(source=source)
            self.assertEqual(len(source.urls), 1)

    def test_three_failed_network_attempts_stop(self):
        source = FixtureSource(); source.prepend = [OSError("invented")] * 3
        with self.assertRaises(ValueError):
            capture(source=source)
        self.assertEqual(len(source.urls), 3)

    def test_partial_body_unexpected_contenttype_redirect_and_malformed_tsv_stop(self):
        for field, value in [("headers", {"Content-Length": "999"}), ("url", "https://string-db.org"),
                             ("body", b"not a version TSV"), ("body", b"\xff")]:
            source = FixtureSource()

            def fetch(url, **kwargs):
                response = source(url, **kwargs)
                response[field] = value
                return response

            clock = Clock()
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                ranking.collect_ranking(*fixture(), fetcher=fetch, clock=clock.now, sleep=clock.sleep)
            self.assertEqual(len(source.urls), 1)

    def test_per_body_and_total_budgets_stop_before_a_partial_packet(self):
        for limit, value in [("max_body_bytes", 16), ("max_total_body_bytes", 80)]:
            source = FixtureSource()
            limits = {**ranking.LIMITS, limit: value}
            with self.subTest(limit=limit), patch.object(ranking, "LIMITS", limits), self.assertRaises(ValueError):
                capture(source=source)
            self.assertLessEqual(len(source.urls), 2)

    def test_bad_mapping_echo_and_incomplete_network_schema_are_not_missing_evidence(self):
        for method in ["get_string_ids", "network"]:
            source = FixtureSource()

            def fetch(url, **kwargs):
                response = source(url, **kwargs)
                if urlparse(url).path.rsplit("/", 1)[-1] == method:
                    body = response["body"]
                    body = (body.replace(b"P00533", b"P00534", 1) if method == "get_string_ids"
                            else b"\t".join(component.NETWORK_COLUMNS[:-1][i].encode()
                                             for i in range(len(component.NETWORK_COLUMNS) - 1)))
                    response["body"] = body
                    response["headers"]["Content-Length"] = str(len(body))
                return response

            clock = Clock()
            with self.subTest(method=method), self.assertRaises(ValueError):
                ranking.collect_ranking(*fixture(), fetcher=fetch, clock=clock.now, sleep=clock.sleep)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.graph, self.anchor, self.candidates = fixture()
        self.packet = capture(self.graph, self.anchor, self.candidates)

    def test_resealing_changed_projection_does_not_defeat_raw_replay(self):
        packet = deepcopy(self.packet)
        packet["annotations"]["UniProtKB:P00533"]["views"]["physical"]["native_score"] = 0.9
        with self.assertRaises(ValueError):
            ranking.verify_packet(reseal(packet))

    def test_raw_mapping_echo_or_reciprocal_change_even_resealed_fails(self):
        for index, transform in [(1, lambda text: text.replace("P00533", "P00534", 1)),
                                  (2, lambda text: "\n".join(text.splitlines()[:-1]) + "\n")]:
            packet = deepcopy(self.packet)
            request = packet["requests"][index]
            change_body(request, transform(request["attempts"][-1]["body_text"]))
            with self.subTest(index=index), self.assertRaises(ValueError):
                ranking.verify_packet(reseal(packet))

    def test_graph_review_basis_anchor_and_candidate_drift_fail(self):
        graph = deepcopy(self.graph); graph["review_events"].append({"invented": "new review"})
        with self.assertRaises(ValueError):
            ranking.verify_packet(self.packet, graph=graph)
        with self.assertRaises(ValueError):
            ranking.verify_packet(self.packet, anchor="UniProtKB:P00533")
        rows = deepcopy(self.candidates); rows[0]["matched_relations"] = {"shared_pathway": 1}
        with self.assertRaises(ValueError):
            ranking.verify_packet(self.packet, candidates=rows)

    def test_omitted_extra_coverage_and_wrong_query_even_resealed_fail(self):
        for mutate in [lambda p: p["requests"].pop(),
                       lambda p: p["requests"].append(deepcopy(p["requests"][-1])),
                       lambda p: p["queried_candidate_ids"].pop(),
                       lambda p: p["requests"][1]["parameters"].update(echo_query="0"),
                       lambda p: p["requested_candidates"][0].update(has_interaction=False)]:
            packet = deepcopy(self.packet); mutate(packet)
            with self.assertRaises(ValueError):
                ranking.verify_packet(reseal(packet))

    def test_rate_attempt_byte_release_and_header_tampering_fail(self):
        def mutate_body(packet):
            receipt = packet["requests"][0]["attempts"][0]
            receipt["body_text"] += "tampered"

        for mutate in [lambda p: p["requests"][1]["attempts"][0].update(started_monotonic=0),
                       lambda p: p["requests"][0]["attempts"][0].update(attempt=2),
                       lambda p: p["requests"][0]["attempts"][0].update(body_bytes=0),
                       lambda p: p.update(source_release="12.0"),
                       lambda p: p["requests"][0]["attempts"][0]["headers"].update({"string-api-version": "1"}),
                       mutate_body]:
            packet = deepcopy(self.packet); mutate(packet)
            with self.assertRaises(ValueError):
                ranking.verify_packet(reseal(packet))

    def test_retry_receipt_and_nonretryable_substitution_fail(self):
        source = FixtureSource(); source.prepend = [(503, b"invented retry")]
        original = capture(source=source)
        for mutate in [lambda p: p["requests"][0]["attempts"][0].update(status=429, error="HTTP 429"),
                       lambda p: p["requests"][0]["attempts"][0].update(error=None),
                       lambda p: p["requests"][0]["attempts"][0].update(final_url="https://example.org")]:
            packet = deepcopy(original); mutate(packet)
            with self.assertRaises(ValueError):
                ranking.verify_packet(reseal(packet))

    def test_content_seal_without_reseal_is_rejected(self):
        self.packet["annotations"]["UniProtKB:P00533"]["views"]["physical"]["native_score"] = 0.3
        with self.assertRaises(ValueError):
            ranking.verify_packet(self.packet)


if __name__ == "__main__":
    unittest.main()
