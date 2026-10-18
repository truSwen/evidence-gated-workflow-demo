"""Exercise the real loopback adapter; no external service is contacted."""
import http.client
import json
import threading
import unittest
from http.server import HTTPServer
from demo import Handler


class LocalAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, body, origin=None, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        if host:
            headers["Host"] = host
        connection.request("POST", "/api/review", json.dumps(body), headers)
        response = connection.getresponse()
        result = response.read()
        status = response.status
        connection.close()
        return status, json.loads(result) if status == 200 else result

    def test_local_approval_and_write_are_separate(self):
        status, result = self.post({"action": "reset", "fixture": "valid"})
        self.assertEqual(status, 200)
        token = result["session_id"]
        self.assertEqual(result["view"]["status"], "READY")
        _, result = self.post({"action": "prepare", "session_id": token})
        pack = result["view"]["reviews"][-1]
        _, blocked = self.post({"action": "execute", "session_id": token, "review_id": pack["review_id"]})
        self.assertEqual(blocked["view"]["write_count"], 0)
        _, approved = self.post({"action": "approve", "session_id": token, "review_id": pack["review_id"], "reviewed_digest": pack["package"]["approval_digest"]})
        self.assertEqual(approved["view"]["status"], "APPROVED")
        self.assertEqual(approved["view"]["write_count"], 0)
        _, applied = self.post({"action": "execute", "session_id": token, "review_id": pack["review_id"]})
        self.assertEqual(applied["view"]["write_count"], 1)

    def test_source_change_invalidates_server_owned_approval(self):
        _, reset = self.post({"action": "reset", "fixture": "valid"})
        token = reset["session_id"]
        _, prepared = self.post({"action": "prepare", "session_id": token})
        r = prepared["view"]["reviews"][-1]
        self.post({"action": "approve", "session_id": token, "review_id": r["review_id"], "reviewed_digest": r["package"]["approval_digest"]})
        self.post({"action": "change_source", "session_id": token})
        _, blocked = self.post({"action": "execute", "session_id": token, "review_id": r["review_id"]})
        self.assertEqual(blocked["view"]["status"], "INVALIDATED")
        self.assertEqual(blocked["view"]["write_count"], 0)

    def test_sessions_do_not_share_approval(self):
        _, first = self.post({"action": "reset", "fixture": "valid"})
        _, second = self.post({"action": "reset", "fixture": "valid"})
        self.assertNotEqual(first["session_id"], second["session_id"])
        _, result = self.post({"action": "execute", "session_id": second["session_id"], "review_id": "review-0001"})
        self.assertEqual(result["view"]["status"], "BLOCKED")
        self.assertEqual(result["view"]["write_count"], 0)

    def test_cross_origin_and_unexpected_host_refused(self):
        self.assertEqual(self.post({"action":"reset","fixture":"valid"}, origin="https://example.org")[0], 403)
        self.assertEqual(self.post({"action":"reset","fixture":"valid"}, host="example.org")[0], 403)

    def test_unknown_command_and_extra_fields_refused(self):
        _, reset = self.post({"action": "reset", "fixture": "valid"})
        token = reset["session_id"]
        for body in ({"action":"overwrite","session_id":token}, {"action":"prepare","session_id":token,"approval":True}, {"action":"execute","session_id":token,"review_id":{}}, {"action":"reset","fixture":"real-data"}):
            self.assertEqual(self.post(body)[0], 400)

    def test_exact_ui_assets_are_served_and_private_files_are_not(self):
        for path, expected in (("/",200),("/entry.js",200),("/app.js",200),("/style.css",200),("/review.py",404),("/fixtures.json",404),("/../demo.py",404)):
            c = http.client.HTTPConnection("127.0.0.1",self.server.server_port)
            c.request("GET",path)
            r = c.getresponse()
            self.assertEqual(r.status,expected,path)
            r.read()
            c.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
