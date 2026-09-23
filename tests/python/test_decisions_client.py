"""core.decisions.client — only DecisionUnavailable escapes; backoff trips."""

from __future__ import annotations

import email.message
import json
import urllib.error
from unittest.mock import patch

import pytest
from _decisions_helpers import FakeResponse, fake_ok, sent_payload

from core.decisions import backoff
from core.decisions.client import DecisionUnavailable, post_decision
from core.decisions.models import DecisionRequest, Question
from core.decisions.transport import Transport

URLOPEN = "core.decisions.client.urllib.request.urlopen"


@pytest.fixture(autouse=True)
def _cache_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(tmp_path / "cache"))


@pytest.fixture
def transport() -> Transport:
    return Transport(
        name="openrouter", url="https://example.test/decisions", key="k",
        model="typesafe/jev-1.13",
        headers={"Authorization": "Bearer k", "Content-Type": "application/json"},
        body_extras={"provider": {"data_collection": "deny"}},
    )


@pytest.fixture
def request_() -> DecisionRequest:
    return DecisionRequest(
        model="typesafe/jev-1.13", state={"prompt": "olá"},
        questions={"topic_drift__topic_shift": Question(type="noul", instructions="x")},
    )


def _http_error(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://example.test", code, "err", headers, None)


def _raises(transport, request_, side_effect) -> DecisionUnavailable:
    with patch(URLOPEN, side_effect=side_effect), pytest.raises(DecisionUnavailable) as info:
        post_decision(transport, request_, 1.5)
    return info.value


def test_success_returns_response_and_latency(transport, request_):
    with patch(URLOPEN, return_value=fake_ok({"topic_drift__topic_shift": {"noul": 0.96}})) as m:
        response, latency = post_decision(transport, request_, 1.5)
    assert response.answers["topic_drift__topic_shift"].noul == 0.96
    assert isinstance(latency, int) and latency >= 0
    req = m.call_args.args[0]
    assert m.call_args.kwargs == {"timeout": 1.5}
    assert (req.full_url, req.get_method()) == ("https://example.test/decisions", "POST")
    assert req.get_header("Authorization") == "Bearer k"
    body = sent_payload(m)
    assert body["provider"] == {"data_collection": "deny"}
    assert body["questions"]["topic_drift__topic_shift"]["type"] == "noul"
    assert body["state"] == {"prompt": "olá"}


def test_401_trips_one_hour(transport, request_):
    err = _raises(transport, request_, _http_error(401))
    assert err.reason == "http-401"
    assert backoff.blocked() == "http-401"
    assert backoff.blocked(now=__import__("time").time() + 3601) is None


@pytest.mark.parametrize(("header", "seconds"), [("30", 30), (None, 60), ("soon", 60),
                                                  ("0", 60), ("99999", 3600)])
def test_429_honours_retry_after(transport, request_, header, seconds):
    with patch("core.decisions.client.backoff.trip") as trip:
        err = _raises(transport, request_, _http_error(429, header))
    assert err.reason == "http-429"
    trip.assert_called_once_with("http-429", seconds)


def test_529_trips_two_minutes(transport, request_):
    with patch("core.decisions.client.backoff.trip") as trip:
        assert _raises(transport, request_, _http_error(529)).reason == "http-529"
    trip.assert_called_once_with("http-529", 120.0)


@pytest.mark.parametrize("code", [422, 500])
def test_other_http_errors_do_not_trip(transport, request_, code):
    with patch("core.decisions.client.backoff.trip") as trip:
        assert _raises(transport, request_, _http_error(code)).reason == f"http-{code}"
    trip.assert_not_called()


@pytest.mark.parametrize(("exc", "reason"), [
    (urllib.error.URLError(TimeoutError("slow")), "timeout"),
    (urllib.error.URLError("refused"), "network"),
    (TimeoutError("slow"), "timeout"),
    (ConnectionResetError("reset"), "network"),
    (RuntimeError("weird"), "network"),
])
def test_transport_failures(transport, request_, exc, reason):
    assert _raises(transport, request_, exc).reason == reason


@pytest.mark.parametrize(("body", "reason"), [
    (b"{not json", "invalid-json"),
    (b"\xff\xfe", "invalid-json"),
    (b"[1, 2]", "invalid-shape"),
    (json.dumps({"model": "m"}).encode(), "invalid-shape"),
    (json.dumps({"answers": {"k": {"noul": 7}}}).encode(), "invalid-shape"),
])
def test_bad_bodies(transport, request_, body, reason):
    assert _raises(transport, request_, lambda *a, **k: FakeResponse(body)).reason == reason


def test_unserialisable_payload_is_invalid_shape(transport, request_):
    bad = Transport(name="t", url=transport.url, key="k", model="m",
                    body_extras={"x": object()})
    with patch(URLOPEN) as m, pytest.raises(DecisionUnavailable) as info:
        post_decision(bad, request_, 1.0)
    assert info.value.reason == "invalid-shape"
    m.assert_not_called()


def test_exception_message_carries_detail():
    err = DecisionUnavailable("http-422", "bad criteria")
    assert (str(err), err.detail) == ("http-422: bad criteria", "bad criteria")
    assert str(DecisionUnavailable("timeout")) == "timeout"


def _serve(handler: type) -> tuple[str, object]:
    import http.server
    import threading

    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}", server


def test_redirect_never_carries_the_key_nor_its_answer(request_):
    # Two real local servers on different origins. Kills: sending
    # Authorization as a normal header (B sees the key) and dropping the
    # final-URL check (B's body would be parsed as the decision).
    import http.server

    seen: dict[str, object] = {}
    ok = json.dumps({"answers": {"topic_drift__topic_shift": {"noul": 0.99}}}).encode()

    class Other(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen["auth"] = self.headers.get("Authorization")
            seen["body"] = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Length", str(len(ok)))
            self.end_headers()
            self.wfile.write(ok)

        def log_message(self, *_a: object) -> None:
            pass

    other_url, other = _serve(Other)

    class Redirector(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            # Drain the body first: closing on unread data resets the socket.
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(302)
            self.send_header("Location", f"{other_url}/steal")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_a: object) -> None:
            pass

    origin_url, origin = _serve(Redirector)
    t = Transport(name="openrouter", url=f"{origin_url}/decisions", key="sk-or-secret",
                  model="m", headers={"Authorization": "Bearer sk-or-secret"})
    try:
        with pytest.raises(DecisionUnavailable) as info:
            post_decision(t, request_, 3.0)
    finally:
        origin.shutdown()
        other.shutdown()
    assert info.value.reason == "redirected"
    assert seen.get("auth") is None and not seen.get("body")


def test_key_is_an_unredirected_header(transport, request_):
    with patch(URLOPEN, return_value=fake_ok({})) as m:
        post_decision(transport, request_, 1.5)
    req = m.call_args.args[0]
    assert "Authorization" not in req.headers
    assert req.unredirected_hdrs["Authorization"] == "Bearer k"


def test_error_body_is_never_read_into_the_exception(transport, request_):
    # A 401 body echoing the key must not reach reason/detail/str.
    import io

    body = io.BytesIO(b'{"error": "bad key Bearer k-echo"}')
    err = urllib.error.HTTPError("https://example.test", 401, "Unauthorized",
                                 email.message.Message(), body)
    exc = _raises(transport, request_, err)
    assert "k-echo" not in f"{exc} {exc.reason} {exc.detail}"


# --- wall-clock deadline and transport-failure breaker (QG r1 B1/B2) ------


def test_dripping_server_is_cut_at_the_deadline(request_):
    # 1 byte every 0.4 s for 30 bytes (~12 s): each socket read succeeds, so
    # urlopen(timeout=) alone never fires. Kills: calling _send directly.
    import http.server
    import threading
    import time as _time

    stop = threading.Event()

    class Drip(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Length", "30")
            self.end_headers()
            try:
                for _ in range(30):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    if stop.wait(0.4):
                        return
            except OSError:
                pass

        def log_message(self, *_a: object) -> None:
            pass

    url, server = _serve(Drip)
    t = Transport(name="openrouter", url=f"{url}/decisions", key="k", model="m",
                  headers={"Authorization": "Bearer k"})
    start = _time.monotonic()
    try:
        with pytest.raises(DecisionUnavailable) as info:
            post_decision(t, request_, 1.0)
    finally:
        elapsed = _time.monotonic() - start
        stop.set()
        server.shutdown()
    assert info.value.reason == "timeout"
    assert elapsed <= 1.0 + 0.1, elapsed


def test_abandoned_call_never_trips_the_breaker_late(transport, request_):
    # The late 401 lands in the abandoned thread. Kills: mapping HTTP
    # errors (and tripping backoff) inside the worker thread.
    import time as _time

    def slow_401(*_a: object, **_k: object) -> None:
        _time.sleep(0.3)
        raise _http_error(401)

    with patch(URLOPEN, side_effect=slow_401):
        with pytest.raises(DecisionUnavailable) as info:
            post_decision(transport, request_, 0.05)
        _time.sleep(0.5)
    assert info.value.reason == "timeout"
    assert backoff.blocked() is None


def test_three_timeouts_open_the_breaker_and_success_resets(transport, request_):
    # Kills: dropping record_failure (never blocked) or record_success
    # (count survives the success, so the 5th call trips).
    slow = urllib.error.URLError(TimeoutError("slow"))
    for _ in range(2):
        _raises(transport, request_, slow)
    with patch(URLOPEN, return_value=fake_ok({})):
        post_decision(transport, request_, 1.5)
    for _ in range(2):
        _raises(transport, request_, slow)
    assert backoff.blocked() is None
    _raises(transport, request_, slow)
    assert backoff.blocked() == "timeout"
