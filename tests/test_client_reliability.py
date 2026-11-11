"""Native Pharos retry observability with invented, offline HTTP responses."""
from copy import deepcopy
from http.client import IncompleteRead
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from biograph_steward.client import (ENDPOINT, VERSION, PharosClient,
                                    PharosError, digest)


RESPONSE = {"data": {"dbVersion": "INVENTED-CONTROL"}}
BODY = json.dumps(RESPONSE).encode()


class Response:
    status = 200

    def __init__(self, body=BODY, read_error=None):
        self.body, self.read_error = body, read_error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        if self.read_error is not None:
            raise self.read_error
        return self.body[:size]


def http_error(status, retry_after=None):
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    return HTTPError(ENDPOINT, status, "invented service error", headers,
                     BytesIO(b"invented error body"))


class ClientReliabilityTests(unittest.TestCase):
    def client(self, **kwargs):
        self.events = []
        return PharosClient(attempt_observer=self.events.append, **kwargs)

    def finished(self):
        return [event for event in self.events if event["phase"] == "finished"]

    def error(self, status, retry_after=None):
        error = http_error(status, retry_after)
        self.addCleanup(error.close)
        return error

    def test_timeout_then_success_preserves_attempts_and_one_logical_record(self):
        client = self.client()
        with patch("biograph_steward.client.urlopen",
                   side_effect=[TimeoutError("invented open timeout"), Response()]) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            self.assertEqual(client.execute(VERSION), RESPONSE["data"])
        self.assertEqual(opened.call_count, 2)
        slept.assert_called_once_with(1)
        self.assertEqual([event["phase"] for event in self.events],
                         ["started", "finished", "started", "finished"])
        first, second = self.finished()
        self.assertEqual((first["attempt"], first["stage"], first["outcome"],
                          first["error_type"], first["retry_wait_seconds"]),
                         (1, "open", "retry_scheduled", "TimeoutError", 1))
        self.assertIsNone(first["http_status"])
        self.assertEqual(first["response_bytes"], 0)
        self.assertEqual((second["attempt"], second["stage"], second["outcome"],
                          second["http_status"], second["response_bytes"]),
                         (2, "complete", "transport_succeeded", 200, len(BODY)))
        self.assertEqual(second["response_validation"], "pending")
        expected = digest({"endpoint": ENDPOINT,
                           "query": VERSION, "variables": {}})
        for event in self.events:
            self.assertEqual(event["request_sha256"], expected)
            self.assertEqual(event["operation_name"], "DatabaseVersion")
            self.assertEqual(event["timeout_seconds"], 30)
            self.assertNotIn("response", event)
        self.assertGreaterEqual(second["elapsed_seconds"], 0)
        self.assertEqual(len(client.records), 1)
        self.assertEqual(client.records[0]["response"], RESPONSE)
        self.assertNotIn("attempts", client.records[0])

    def test_bounded_exhaustion_retains_last_failed_attempt(self):
        client = self.client()
        with patch("biograph_steward.client.urlopen",
                   side_effect=TimeoutError("invented repeated timeout")) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaisesRegex(PharosError, "Cannot reach Pharos"):
                client.execute(VERSION)
        self.assertEqual(opened.call_count, 3)
        self.assertEqual([call.args[0] for call in slept.call_args_list], [1, 2])
        self.assertEqual([event["outcome"] for event in self.finished()],
                         ["retry_scheduled", "retry_scheduled", "failed"])
        self.assertEqual(self.finished()[-1]["retry_wait_seconds"], 0)
        self.assertEqual(client.records, [])

    def test_body_timeout_is_distinct_from_open_timeout(self):
        client = self.client(retries=0)
        with patch("biograph_steward.client.urlopen",
                   return_value=Response(read_error=TimeoutError("invented read timeout"))):
            with self.assertRaises(PharosError):
                client.execute(VERSION)
        event = self.finished()[0]
        self.assertEqual((event["stage"], event["http_status"], event["outcome"]),
                         ("read", 200, "failed"))
        self.assertEqual(event["error_type"], "TimeoutError")

    def test_retryable_http_statuses_use_existing_wait_policy(self):
        for status, retry_after, wait in ((429, "3", 3.0), (503, None, 1)):
            with self.subTest(status=status):
                client = self.client()
                with patch("biograph_steward.client.urlopen",
                           side_effect=[self.error(status, retry_after), Response()]) as opened, \
                        patch("biograph_steward.client.time.sleep") as slept:
                    self.assertEqual(client.execute(VERSION), RESPONSE["data"])
                self.assertEqual(opened.call_count, 2)
                slept.assert_called_once_with(wait)
                event = self.finished()[0]
                self.assertEqual(event["http_status"], status)
                self.assertEqual(event["outcome"], "retry_scheduled")
                self.assertEqual(event["retry_wait_seconds"], wait)
                self.assertEqual(event["response_bytes"], len(b"invented error body"))

    def test_http_400_is_terminal(self):
        client = self.client()
        with patch("biograph_steward.client.urlopen", side_effect=self.error(400)) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaisesRegex(PharosError, "HTTP 400"):
                client.execute(VERSION)
        self.assertEqual(opened.call_count, 1)
        slept.assert_not_called()
        self.assertEqual(self.finished()[0]["outcome"], "failed")
        self.assertEqual(self.finished()[0]["http_status"], 400)
        self.assertEqual(client.records, [])

    def test_invalid_json_is_terminal_and_not_cached(self):
        client = self.client()
        with patch("biograph_steward.client.urlopen", return_value=Response(b"<html>no</html>")) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaisesRegex(PharosError, "non-JSON"):
                client.execute(VERSION)
        self.assertEqual(opened.call_count, 1)
        slept.assert_not_called()
        self.assertEqual(self.finished()[0]["stage"], "decode")
        self.assertEqual(self.finished()[0]["outcome"], "failed")
        self.assertEqual(client.records, [])

    def test_graphql_errors_are_not_transport_retried_or_accepted(self):
        raw = json.dumps({"data": RESPONSE["data"],
                          "errors": [{"message": "invented partial failure"}]}).encode()
        client = self.client()
        with patch("biograph_steward.client.urlopen", return_value=Response(raw)) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaisesRegex(PharosError, "partial data rejected"):
                client.execute(VERSION)
        self.assertEqual(opened.call_count, 1)
        slept.assert_not_called()
        self.assertEqual(self.finished()[0]["outcome"], "transport_succeeded")
        self.assertEqual(self.finished()[0]["response_validation"], "pending")
        self.assertEqual(client.records, [])

    def test_verified_cache_hit_makes_no_open_or_attempt_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = self.client(cache_dir=Path(temporary))
            with patch("biograph_steward.client.urlopen", return_value=Response()) as opened:
                client.execute(VERSION)
                first = deepcopy(client.records[0])
                self.events.clear()
                self.assertEqual(client.execute(VERSION), RESPONSE["data"])
            self.assertEqual(opened.call_count, 1)
            self.assertEqual(self.events, [])
            self.assertTrue(client.records[-1]["loaded_from_cache"])
            self.assertEqual(client.records[-1]["retrieved_at"], first["retrieved_at"])
            self.assertEqual(client.records[-1]["response_sha256"], first["response_sha256"])

    def test_injected_transport_retains_its_explicit_no_native_retry_semantics(self):
        calls = []

        def transport(payload):
            calls.append(payload)
            raise TimeoutError("invented injected timeout")

        client = self.client(transport=transport)
        with patch("biograph_steward.client.urlopen") as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaises(TimeoutError):
                client.execute(VERSION)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.events, [])
        self.assertEqual(client.records, [])
        opened.assert_not_called()
        slept.assert_not_called()

    def test_started_observer_budget_failure_never_opens_or_retries(self):
        class BudgetFailure(OSError):
            pass

        def stop(event):
            raise BudgetFailure("invented durable budget stop")

        client = PharosClient(attempt_observer=stop)
        with patch("biograph_steward.client.urlopen") as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaisesRegex(BudgetFailure, "budget stop"):
                client.execute(VERSION)
        opened.assert_not_called()
        slept.assert_not_called()
        self.assertEqual(client.records, [])

    def test_finished_observer_failure_is_not_retried(self):
        class ReceiptFailure(OSError):
            pass

        events = []

        def stop(event):
            events.append(event)
            if event["phase"] == "finished":
                raise ReceiptFailure("invented receipt write failure")

        client = PharosClient(attempt_observer=stop)
        with patch("biograph_steward.client.urlopen", return_value=Response()) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaisesRegex(ReceiptFailure, "receipt write"):
                client.execute(VERSION)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual([event["phase"] for event in events], ["started", "finished"])
        slept.assert_not_called()
        self.assertEqual(client.records, [])

    def test_finished_observer_failure_stops_a_scheduled_retry(self):
        class ReceiptFailure(OSError):
            pass

        events = []

        def stop(event):
            events.append(event)
            if event["phase"] == "finished":
                raise ReceiptFailure("invented receipt failure after timeout")

        client = PharosClient(attempt_observer=stop)
        with patch("biograph_steward.client.urlopen", side_effect=TimeoutError("invented timeout")) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaises(ReceiptFailure):
                client.execute(VERSION)
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(events[-1]["outcome"], "retry_scheduled")
        slept.assert_not_called()
        self.assertEqual(client.records, [])

    def test_incomplete_read_preserves_observed_partial_byte_count_without_new_retry(self):
        client = self.client()
        with patch("biograph_steward.client.urlopen",
                   return_value=Response(read_error=IncompleteRead(b"partial", 12))) as opened, \
                patch("biograph_steward.client.time.sleep") as slept:
            with self.assertRaises(IncompleteRead):
                client.execute(VERSION)
        self.assertEqual(opened.call_count, 1)
        slept.assert_not_called()
        self.assertEqual(self.finished()[0]["response_bytes"], len(b"partial"))
        self.assertEqual(self.finished()[0]["stage"], "read")
        self.assertEqual(client.records, [])

    def test_no_observer_has_same_logical_record_as_observed_transport(self):
        plain, observed = PharosClient(), self.client()
        with patch("biograph_steward.client.urlopen", side_effect=[Response(), Response()]), \
                patch("biograph_steward.client.utcnow", return_value="2026-01-01T00:00:00+00:00"):
            self.assertEqual(plain.execute(VERSION), observed.execute(VERSION))
        self.assertEqual(plain.records, observed.records)


if __name__ == "__main__":
    unittest.main()
