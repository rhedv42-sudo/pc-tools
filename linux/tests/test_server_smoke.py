"""Smoke-Test: Server mit --no-browser starten, Token-Schutz prüfen, beenden."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from urllib.parse import urlparse, parse_qs

from tests import helpers


def request(url, token=None, host=None, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    if token:
        req.add_header("X-PCT-Token", token)
    if host:
        req.add_header("Host", host)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class ServerSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        env = dict(os.environ, XDG_CONFIG_HOME=cls.tmp.name, PCTOOLS_TEST_ALLOW_ROOT="1",
                   PYTHONPATH=str(helpers.ROOT))
        cls.proc = subprocess.Popen([sys.executable, "-m", "pctools", "--no-browser"], cwd=str(helpers.ROOT),
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        line = cls.proc.stdout.readline().strip()
        if not line.startswith("http://127.0.0.1:"):
            cls.proc.kill()
            raise RuntimeError("Server lieferte keine URL: %r %s" % (line, cls.proc.stderr.read()))
        u = urlparse(line)
        cls.base = "http://%s" % u.netloc
        cls.token = parse_qs(u.query)["t"][0]

    @classmethod
    def tearDownClass(cls):
        if cls.proc.poll() is None:
            cls.proc.kill()
        cls.proc.wait(timeout=10)
        cls.proc.stdout.close()
        cls.proc.stderr.close()
        cls.tmp.cleanup()

    def test_1_token_required(self):
        code, _ = request(self.base + "/api/overview")
        self.assertEqual(code, 403)
        code, _ = request(self.base + "/api/overview", token="falsch")
        self.assertEqual(code, 403)

    def test_2_host_check(self):
        code, _ = request(self.base + "/api/overview", token=self.token, host="evil.example:80")
        self.assertEqual(code, 403)

    def test_3_overview(self):
        code, body = request(self.base + "/api/overview", token=self.token)
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertIn("health", data)
        self.assertTrue(0 <= data["health"]["score"] <= 100)
        self.assertIn("distro", data["info"])

    def test_4_static(self):
        code, body = request(self.base + "/")
        self.assertEqual(code, 200)
        self.assertIn(b"app.js", body)
        self.assertEqual(request(self.base + "/../pctools/server.py")[0], 404)
        self.assertEqual(request(self.base + "/lang/de-DE.json")[0], 200)
        self.assertEqual(request(self.base + "/lang/..%2Fkeys.json")[0], 404)

    def test_5_unknown_job(self):
        code, _ = request(self.base + "/api/jobs/start", token=self.token, data=b'{"kind": "rm -rf"}')
        self.assertEqual(code, 400)

    def test_9_shutdown(self):
        code, _ = request(self.base + "/api/shutdown", token=self.token, data=b"{}")
        self.assertEqual(code, 200)
        self.proc.wait(timeout=15)
        self.assertEqual(self.proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
