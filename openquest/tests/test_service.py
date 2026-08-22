import json
import threading
import unittest
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from openquest.service import build_server, dispatch


class ServiceDispatchTests(unittest.TestCase):
    def valid_request(self):
        return {
            "name": "HTTP Hero",
            "ability_scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            "class_name": "Fighter",
            "species": "Human",
            "background": "Soldier",
            "skill_proficiencies": ["athletics", "perception"],
            "armor_class": 16,
        }

    def test_health(self):
        status, payload = dispatch("GET", "/health")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["status"], "PASS")

    def test_options(self):
        status, payload = dispatch("GET", "/v1/options?ruleset=srd-5.2.1")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["options"]["classes"], ("Fighter",))

    def test_create_character(self):
        body = json.dumps(self.valid_request()).encode()
        status, payload = dispatch("POST", "/v1/characters", body)
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertEqual(payload["status"], "PASS")
        self.assertTrue(payload["result"]["valid"])
        self.assertEqual(payload["result"]["character"]["hit_points"], 11)

    def test_invalid_character_is_unprocessable(self):
        request = self.valid_request()
        request["skill_proficiencies"] = ["athletics", "sleight of hand"]
        status, payload = dispatch("POST", "/v1/characters", json.dumps(request).encode())
        self.assertEqual(status, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(payload["status"], "FAIL")

    def test_bad_json_is_bad_request(self):
        status, payload = dispatch("POST", "/v1/characters", b"{")
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(payload["status"], "FAIL")


class LiveServiceTests(unittest.TestCase):
    def setUp(self):
        self.server = build_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def read_json(self, url, *, method="GET", payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(url, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_frontend_is_served_from_root(self):
        with urlopen(self.base + "/", timeout=2) as response:
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, HTTPStatus.OK)
            self.assertIn("text/html", response.headers["Content-Type"])
        self.assertIn("OpenQuest Character Creator", page)
        self.assertIn("/v1/options", page)
        self.assertIn("/v1/characters", page)
        self.assertIn("Download JSON", page)

    def test_live_health_and_options(self):
        status, health = self.read_json(self.base + "/health")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(health["status"], "PASS")
        status, options = self.read_json(self.base + "/v1/options")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(options["options"]["ruleset"], "srd-5.2.1")

    def test_live_create_and_fail_closed(self):
        valid = {
            "name": "Live Hero",
            "ability_scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            "class_name": "Fighter",
            "species": "Human",
            "background": "Soldier",
            "skill_proficiencies": ["athletics", "perception"],
        }
        status, payload = self.read_json(
            self.base + "/v1/characters", method="POST", payload=valid
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertTrue(payload["result"]["valid"])

        valid["background"] = "Unknown"
        request = Request(
            self.base + "/v1/characters",
            data=json.dumps(valid).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=2)
        self.assertEqual(caught.exception.code, HTTPStatus.UNPROCESSABLE_ENTITY)
        failure = json.loads(caught.exception.read())
        self.assertEqual(failure["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
