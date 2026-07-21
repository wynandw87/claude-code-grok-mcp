"""Regression tests for server.py. Run from the repo root: python3 test_server.py

No network access and no API key required - all HTTP is stubbed.
"""
import importlib.util, io, json, os, subprocess, sys, tempfile, time

os.environ["XAI_API_KEY"] = "dummy"
spec = importlib.util.spec_from_file_location("srv", "server.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.logger = m.setup_logging()

results = []
def check(name, fn):
    try:
        fn()
        results.append(("PASS", name, ""))
    except AssertionError as e:
        results.append(("FAIL", name, str(e)))
    except Exception as e:
        results.append(("ERROR", name, f"{type(e).__name__}: {e}"))

tmp = tempfile.mkdtemp()

# --- 1. image/video input validation -------------------------------------
def t_image_ext():
    secret = os.path.join(tmp, "credentials")
    open(secret, "w").write("aws_secret_access_key=hunter2")
    try:
        m.validate_image_path(secret)
        raise AssertionError("extensionless file accepted as image")
    except ValueError as e:
        assert "Unsupported image type" in str(e), e
check("image path rejects non-image extension", t_image_ext)

def t_image_size():
    big = os.path.join(tmp, "big.png")
    with open(big, "wb") as f:
        f.write(b"\0" * (m.MAX_IMAGE_SIZE_MB * 1024 * 1024 + 1))
    try:
        m.validate_image_path(big)
        raise AssertionError("oversized image accepted")
    except ValueError as e:
        assert "too large" in str(e), e
check("image path rejects oversized file", t_image_size)

def t_mime_raises():
    try:
        m.get_mime_type("/etc/passwd")
        raise AssertionError("get_mime_type defaulted instead of raising")
    except ValueError:
        pass
    assert m.get_mime_type("a.PNG") == "image/png"
check("get_mime_type raises on unknown ext", t_mime_raises)

def t_video_ext():
    f = os.path.join(tmp, "clip.mov")
    open(f, "wb").write(b"x")
    try:
        m.validate_video_path(f)
        raise AssertionError(".mov accepted")
    except ValueError as e:
        assert "Unsupported video type" in str(e), e
check("video path rejects non-mp4", t_video_ext)

# --- 2. save path overwrite protection -----------------------------------
def t_no_clobber():
    doc = os.path.join(tmp, "report.docx")
    open(doc, "w").write("important")
    try:
        m.resolve_save_path(doc)
        raise AssertionError("overwrite allowed by default")
    except ValueError as e:
        assert "Refusing to overwrite" in str(e), e
    assert m.resolve_save_path(doc, overwrite=True) == os.path.abspath(doc)
    assert open(doc).read() == "important", "file was modified"
check("save_path refuses to clobber existing file", t_no_clobber)

def t_atomic():
    target = os.path.join(tmp, "out", "a.bin")
    m.write_file_atomic(target, b"hello")
    assert open(target, "rb").read() == b"hello"
    assert not [p for p in os.listdir(os.path.dirname(target)) if p.endswith(".partial")]
check("atomic write leaves no partial file", t_atomic)

def t_atomic_cleanup():
    target = os.path.join(tmp, "out2", "b.bin")
    class Boom(bytes):
        pass
    try:
        m.write_file_atomic(target, None)  # TypeError inside write
    except Exception:
        pass
    d = os.path.dirname(target)
    leftovers = [p for p in os.listdir(d) if ".partial" in p] if os.path.isdir(d) else []
    assert not leftovers, f"partial files left: {leftovers}"
    assert not os.path.exists(target), "target created despite failure"
check("atomic write cleans up on failure", t_atomic_cleanup)

# --- 3/4. model config validation ----------------------------------------
def t_default_model_validation():
    orig = m.load_config
    m.load_config = lambda: {"model": "grok-4-1-fast-reasoning"}
    try:
        assert m.get_default_model() == "grok-4.5", m.get_default_model()
        m.load_config = lambda: {"model": "grok-imagine-video"}
        assert m.get_default_model() == "grok-4.5"
        m.load_config = lambda: {"model": "grok-4.3"}
        assert m.get_default_model() == "grok-4.3"
    finally:
        m.load_config = orig
check("get_default_model falls back on retired/non-text id", t_default_model_validation)

def t_config_cli_rejects_media_model():
    out = subprocess.run([sys.executable, "server.py", "config", "--model", "grok-imagine-video"],
                         capture_output=True, text=True)
    assert out.returncode == 1, out
    assert "image/video model" in out.stderr, out.stderr
check("config --model rejects image/video models", t_config_cli_rejects_media_model)

# --- 5. web_search filters nesting ---------------------------------------
def t_web_search_filters():
    spec_ = m.build_tool_spec("web_search", filters={"excluded_domains": ["x.com"]})
    assert spec_ == {"type": "web_search", "filters": {"excluded_domains": ["x.com"]}}, spec_
    xs = m.build_tool_spec("x_search", allowed_x_handles=["elonmusk"])
    assert xs == {"type": "x_search", "allowed_x_handles": ["elonmusk"]}, xs
check("web_search nests filters, x_search stays flat", t_web_search_filters)

# --- 6. session handling --------------------------------------------------
def t_window():
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(100):
        msgs.append({"role": "user", "content": str(i)})
        msgs.append({"role": "assistant", "content": str(i)})
    w = m.window_messages(msgs)
    assert len(w) == m.MAX_SESSION_MESSAGES, len(w)
    assert w[0]["role"] == "system", "system prompt dropped"
    assert w[-1] == msgs[-1], "did not keep most recent"
check("session message window keeps system + recent", t_window)

def t_lru():
    m.sessions.clear()
    for i in range(m.MAX_SESSIONS + 10):
        m.sessions[f"s{i}"] = {"model": "x", "messages": [], "created_at": 0, "last_active": i}
    m.evict_sessions_over_limit()
    assert len(m.sessions) == m.MAX_SESSIONS, len(m.sessions)
    assert "s0" not in m.sessions and f"s{m.MAX_SESSIONS + 9}" in m.sessions
    m.sessions.clear()
check("session count capped with LRU eviction", t_lru)

def t_rollback():
    m.sessions.clear()
    orig = m.call_grok_chat
    m.call_grok_chat = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("API down"))
    try:
        m.handle_chat({"message": "hi"})
        raise AssertionError("exception not propagated")
    except RuntimeError:
        pass
    finally:
        m.call_grok_chat = orig
    assert len(m.sessions) == 1
    sid = list(m.sessions)[0]
    assert m.sessions[sid]["messages"] == [], m.sessions[sid]["messages"]
    m.sessions.clear()
check("failed chat turn rolls back user message", t_rollback)

def t_override_warning():
    m.sessions.clear()
    m.call_grok_chat = lambda *a, **k: "ok"
    r1 = m.handle_chat({"message": "one"})
    r2 = m.handle_chat({"message": "two", "session_id": r1["session_id"], "model": "grok-4.3"})
    assert "warning" in r2 and "model" in r2["warning"], r2
    m.sessions.clear()
check("mid-session override reports being ignored", t_override_warning)

# --- 7. video model modality guard ---------------------------------------
def t_modality():
    try:
        m.call_grok_video_gen("x", model="grok-imagine-video-1.5")
        raise AssertionError("text-to-video allowed on image-only model")
    except ValueError as e:
        assert "image-to-video only" in str(e), e
check("grok-imagine-video-1.5 rejects text-to-video", t_modality)

def t_modality_edit():
    try:
        m.call_grok_video_edit("x", video_url="http://v/1.mp4", model="grok-imagine-video-1.5")
        raise AssertionError("video editing allowed on image-only model")
    except ValueError as e:
        assert "cannot edit video" in str(e), e
    assert "grok-imagine-video-1.5" not in m.VIDEO_EDIT_MODELS, m.VIDEO_EDIT_MODELS
check("grok-imagine-video-1.5 rejects video editing", t_modality_edit)

# --- 8. TTS length cap ----------------------------------------------------
def t_tts_cap():
    assert m.MAX_TTS_TEXT_LENGTH < m.MAX_PROMPT_LENGTH
check("TTS has its own length cap", t_tts_cap)

def t_overwrite_checked_before_spending():
    """A doomed save_path must be rejected before any billable API call."""
    existing = os.path.join(tmp, "taken.mp4")
    open(existing, "w").write("x")
    called = []
    m.GROK_AVAILABLE = True  # handler short-circuits without this
    orig_gen, orig_poll = m.call_grok_video_gen, m.poll_video_status
    m.call_grok_video_gen = lambda *a, **k: called.append("api") or "req"
    m.poll_video_status = lambda *a, **k: called.append("poll") or {}
    try:
        resp = m.handle_tool_call(1, {"name": "generate_video",
                                      "arguments": {"prompt": "x", "save_path": existing}})
        assert resp["result"].get("isError"), resp
        assert "Refusing to overwrite" in resp["result"]["content"][0]["text"], resp
        assert not called, f"billable call made before the overwrite check: {called}"
    finally:
        m.call_grok_video_gen, m.poll_video_status = orig_gen, orig_poll
check("overwrite is checked before any billable call", t_overwrite_checked_before_spending)

# --- 9. HTTP retry wrapper ------------------------------------------------
class FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = f"status {status_code}"

def with_stubbed_http(statuses, fn):
    """Run fn with requests.request returning the given statuses in order."""
    calls = []
    orig_request, orig_sleep = m.requests.request, m.time.sleep
    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        status = statuses[min(len(calls) - 1, len(statuses) - 1)]
        if isinstance(status, Exception):
            raise status
        return FakeResponse(status)
    m.requests.request = fake_request
    m.time.sleep = lambda s: None
    try:
        return fn(), calls
    finally:
        m.requests.request, m.time.sleep = orig_request, orig_sleep

def t_retry_429():
    (resp, calls) = with_stubbed_http(
        [429, 429, 200], lambda: m.request_with_retry("POST", "http://x", timeout=1)
    )
    assert resp.status_code == 200, resp.status_code
    assert len(calls) == 3, calls
check("429 is retried until success", t_retry_429)

def t_no_retry_500_on_post():
    (resp, calls) = with_stubbed_http(
        [500], lambda: m.request_with_retry("POST", "http://x", timeout=1)
    )
    assert resp.status_code == 500
    assert len(calls) == 1, f"POST retried an ambiguous 500 ({len(calls)} calls) - risks double billing"
check("ambiguous 500 is NOT retried on POST", t_no_retry_500_on_post)

def t_retry_500_on_get():
    (resp, calls) = with_stubbed_http(
        [500, 200], lambda: m.request_with_retry("GET", "http://x", timeout=1)
    )
    assert resp.status_code == 200 and len(calls) == 2, calls
check("500 is retried on read-only GET", t_retry_500_on_get)

def t_retry_gives_up():
    try:
        with_stubbed_http(
            [m.requests.RequestException("conn reset")],
            lambda: m.request_with_retry("POST", "http://x", timeout=1),
        )
        raise AssertionError("did not raise after exhausting retries")
    except RuntimeError as e:
        assert "failed after" in str(e), e
check("connection errors give up with a clear error", t_retry_gives_up)

def t_rewind_called():
    handle = io.BytesIO(b"payload")
    handle.read()  # consume it, as a real upload attempt would
    def run():
        return m.request_with_retry(
            "POST", "http://x", timeout=1, rewind=lambda: handle.seek(0)
        )
    with_stubbed_http([429, 200], run)
    assert handle.tell() == 0, "file handle was not rewound before retry"
check("multipart upload rewinds its file handle before retry", t_rewind_called)

# --- 10. cancellation -----------------------------------------------------
def t_cancel_detection():
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 9, "method": "tools/list"}),
        json.dumps({"method": "notifications/cancelled", "params": {"requestId": 7}}),
    ]
    orig_stdin, orig_has = sys.stdin, m._stdin_has_data
    m.pending_stdin_lines.clear()
    sys.stdin = io.StringIO("\n".join(lines) + "\n")
    m._stdin_has_data = lambda: sys.stdin.tell() < len(sys.stdin.getvalue())
    try:
        assert m.check_for_cancellation(7) is True, "cancel for request 7 not detected"
        assert len(m.pending_stdin_lines) == 1, m.pending_stdin_lines
        assert "tools/list" in m.pending_stdin_lines[0], "unrelated message was dropped"
    finally:
        sys.stdin, m._stdin_has_data = orig_stdin, orig_has
        m.pending_stdin_lines.clear()
check("cancellation detected, unrelated messages buffered", t_cancel_detection)

def t_cancel_wrong_id_ignored():
    orig_stdin, orig_has = sys.stdin, m._stdin_has_data
    m.pending_stdin_lines.clear()
    sys.stdin = io.StringIO(
        json.dumps({"method": "notifications/cancelled", "params": {"requestId": 99}}) + "\n"
    )
    m._stdin_has_data = lambda: sys.stdin.tell() < len(sys.stdin.getvalue())
    try:
        assert m.check_for_cancellation(7) is False, "cancelled the wrong request"
    finally:
        sys.stdin, m._stdin_has_data = orig_stdin, orig_has
        m.pending_stdin_lines.clear()
check("cancel for a different request id is ignored", t_cancel_wrong_id_ignored)

def t_poll_cancels():
    orig = m.requests.request
    m.requests.request = lambda *a, **k: FakeResponse(202)
    orig_json = None
    class Pending(FakeResponse):
        def json(self): return {"status": "pending"}
    m.requests.request = lambda *a, **k: Pending(200)
    try:
        m.poll_video_status("req-1", cancel_check=lambda: True)
        raise AssertionError("poll did not stop on cancellation")
    except m.RequestCancelled as e:
        assert "req-1" in str(e), e
    finally:
        m.requests.request = orig
check("video poll aborts on cancellation", t_poll_cancels)

for status, name, msg in results:
    print(f"{status:5} {name}" + (f"  -> {msg}" if msg else ""))
bad = [r for r in results if r[0] != "PASS"]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
