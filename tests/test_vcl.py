"""edge/default.vcl in a real varnishd (skipped where varnishd is not installed; CI installs it)."""
import http.server
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from sep.edge.keys import MARKETING
from sep.edge.purge import Ban

ROOT = Path(__file__).resolve().parent.parent
VCL = (ROOT / "edge" / "default.vcl").read_text()


def test_vcl_strips_the_same_parameters_as_python():
    alt = re.search(r'\(utm_\[a-z\]\+\|([^)]*)\)=', VCL).group(1).split("|")
    py = MARKETING.pattern.strip("^$()").split("|")
    assert ["utm_[a-z]+", *alt] == py


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Origin(http.server.BaseHTTPRequestHandler):
    hits: dict = {}
    fail = False

    def do_GET(self):
        Origin.hits[self.path] = Origin.hits.get(self.path, 0) + 1
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if Origin.fail:
            self.send_response(503)
            self.end_headers()
            return
        tags = {"/p/12": "p-12", "/p/13": "p-13", "/c/3": "c-3,l-12,l-13"}.get(self.path.split("?")[0], "")
        self.send_response(200)
        if tags:
            self.send_header("X-Cache-Tags", tags)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"page {self.path} v{Origin.hits[self.path]}".encode())

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def varnish():
    if not shutil.which("varnishd"):
        pytest.skip("varnishd not installed")
    op, vp = _free_port(), _free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", op), Origin)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tmp = Path(tempfile.mkdtemp())
    tmp.chmod(0o755)                       # varnishd's child runs as an unprivileged user
    vcl = tmp / "test.vcl"
    vcl.write_text(VCL.replace("${ORIGIN_HOST}", "127.0.0.1").replace("${ORIGIN_PORT}", str(op)))
    proc = subprocess.Popen(["varnishd", "-F", "-f", str(vcl), "-a", f"127.0.0.1:{vp}", "-n", str(tmp / "work"),
                             "-s", "malloc,32m", "-p", "ban_lurker_sleep=0.01"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{vp}"
    for _ in range(150):
        try:
            if urllib.request.urlopen(base + "/health", timeout=1).status == 200:
                break
        except Exception:
            time.sleep(0.1)
    yield base
    proc.terminate()
    proc.wait(5)
    srv.shutdown()


def get(base, path, cookie=None):
    req = urllib.request.Request(base + path, headers={"Cookie": cookie} if cookie else {})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.headers.get("X-Cache"), r.read().decode()


def ban(base, b: Ban):
    req = urllib.request.Request(base + "/", method="BAN", headers={"X-Ban-Tags": b.header})
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 200


def test_second_view_is_a_hit_and_tracking_parameters_share_it(varnish):
    get(varnish, "/p/12")
    assert get(varnish, "/p/12")[0] == "HIT"
    assert get(varnish, "/p/12?gclid=Cj0K&utm_source=google")[0] == "HIT"
    assert get(varnish, "/p/12?fbclid=IwAR")[0] == "HIT"


def test_analytics_cookies_hit_and_session_cookies_pass(varnish):
    get(varnish, "/p/13")
    assert get(varnish, "/p/13", "_ga=GA1.2; OptanonConsent=yes")[0] == "HIT"
    assert get(varnish, "/p/13", "PHPSESSID=abc")[0] == "MISS"


def test_a_tag_ban_drops_the_product_and_its_listing_only(varnish):
    for p in ("/p/12", "/p/13", "/c/3"):
        get(varnish, p)
    ban(varnish, Ban(("p-12", "l-12")))
    time.sleep(0.2)
    assert get(varnish, "/p/12")[0] == "MISS"
    assert get(varnish, "/c/3")[0] == "MISS"
    assert get(varnish, "/p/13")[0] == "HIT"


def test_errors_are_not_cached(varnish):
    Origin.fail = True
    try:
        with pytest.raises(urllib.error.HTTPError):
            get(varnish, "/p/99")
    finally:
        Origin.fail = False
    assert get(varnish, "/p/99")[0] == "MISS"
