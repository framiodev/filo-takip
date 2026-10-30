"""cPanel 'Setup Python App' (Passenger) için WSGI girişi: web arayüzünü yayınlar.
Toplayıcı ayrı çalışır (cron ile: python ego_tracker.py run --once)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ego_tracker as E  # noqa: E402
import ego_web  # noqa: E402

_H = ego_web.make_handler(E)


class _Cap(object):
    def __init__(self, path, headers=None, body=b""):
        import io
        self.path = path
        self.headers = headers or {}
        self.rfile = io.BytesIO(body)
        self.resp = (200, "text/html; charset=utf-8", b"", {})

    def _send(self, body, ctype="text/html; charset=utf-8", code=200, extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.resp = (code, ctype, data, extra or {})

    def _redirect(self, to):
        self.resp = (303, "text/plain", b"", {"Location": to})


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/") or "/"
    qs = environ.get("QUERY_STRING", "")
    hdrs = {"Host": environ.get("HTTP_HOST", ""), "Origin": environ.get("HTTP_ORIGIN", ""),
            "Referer": environ.get("HTTP_REFERER", ""), "Content-Length": environ.get("CONTENT_LENGTH", "0")}

    class _Hd(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d) or d
    body = b""
    if environ.get("REQUEST_METHOD") == "POST":
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            n = 0
        body = environ["wsgi.input"].read(min(n, 200000))
    cap = _Cap(path + ("?" + qs if qs else ""), _Hd(hdrs), body)
    if environ.get("REQUEST_METHOD") == "POST":
        _H.do_POST(cap)
    else:
        _H.do_GET(cap)
    code, ctype, data, extra = cap.resp
    hdr = [("Content-Type", ctype), ("Content-Length", str(len(data))), ("Cache-Control", "no-store")]
    hdr += list(extra.items())
    start_response("%d %s" % (code, "OK" if code < 300 else "Redirect" if code < 400 else "Error"), hdr)
    return [data]
