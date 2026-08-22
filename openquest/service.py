from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from openquest.builder import build_level_one_character, list_options
from openquest.validator import export_character

API_SCHEMA = "openquest.http.v1"
MAX_BODY_BYTES = 64 * 1024


def dispatch(method: str, target: str, body: bytes = b"") -> tuple[int, dict[str, Any]]:
    parsed = urlparse(target)
    if method == "GET" and parsed.path == "/health":
        return HTTPStatus.OK, {"schema": API_SCHEMA, "status": "PASS"}

    if method == "GET" and parsed.path == "/v1/options":
        ruleset = parse_qs(parsed.query).get("ruleset", ["srd-5.2.1"])[0]
        try:
            options = list_options(ruleset)
        except ValueError as exc:
            return HTTPStatus.BAD_REQUEST, _failure("OPTION_GATE", str(exc))
        return HTTPStatus.OK, {
            "schema": API_SCHEMA,
            "status": "PASS",
            "options": asdict(options),
        }

    if method == "POST" and parsed.path == "/v1/characters":
        if len(body) > MAX_BODY_BYTES:
            return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, _failure(
                "REQUEST_GATE", "Request body exceeds 65536 bytes"
            )
        try:
            request = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return HTTPStatus.BAD_REQUEST, _failure("REQUEST_GATE", f"Invalid JSON: {exc}")
        if not isinstance(request, dict):
            return HTTPStatus.BAD_REQUEST, _failure("REQUEST_GATE", "JSON body must be an object")

        required = {
            "name",
            "ability_scores",
            "class_name",
            "species",
            "background",
            "skill_proficiencies",
        }
        missing = sorted(required - request.keys())
        if missing:
            return HTTPStatus.BAD_REQUEST, _failure(
                "REQUEST_GATE", f"Missing fields: {', '.join(missing)}"
            )

        ability_scores = request["ability_scores"]
        skills = request["skill_proficiencies"]
        if not isinstance(ability_scores, dict) or not isinstance(skills, list):
            return HTTPStatus.BAD_REQUEST, _failure(
                "REQUEST_GATE", "ability_scores must be an object and skill_proficiencies a list"
            )

        try:
            normalized_abilities = {str(k): int(v) for k, v in ability_scores.items()}
            normalized_skills = [str(skill) for skill in skills]
            armor_class = int(request.get("armor_class", 10))
        except (TypeError, ValueError) as exc:
            return HTTPStatus.BAD_REQUEST, _failure("REQUEST_GATE", f"Invalid field type: {exc}")

        result = build_level_one_character(
            name=str(request["name"]),
            ability_scores=normalized_abilities,
            class_name=str(request["class_name"]),
            species=str(request["species"]),
            background=str(request["background"]),
            skill_proficiencies=normalized_skills,
            ruleset=str(request.get("ruleset", "srd-5.2.1")),
            armor_class=armor_class,
        )
        if not result.valid or result.character is None:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {
                "schema": API_SCHEMA,
                "status": "FAIL",
                "gates": [
                    {"gate": gate.gate, "status": gate.status.value, "detail": gate.detail}
                    for gate in result.gates
                ],
            }

        character_payload = json.loads(export_character(result.character, list(result.gates)))
        return HTTPStatus.CREATED, {
            "schema": API_SCHEMA,
            "status": "PASS",
            "result": character_payload,
        }

    return HTTPStatus.NOT_FOUND, _failure("ROUTE_GATE", "Unknown route")


def _failure(gate: str, detail: str) -> dict[str, Any]:
    return {
        "schema": API_SCHEMA,
        "status": "FAIL",
        "gates": [{"gate": gate, "status": "FAIL", "detail": detail}],
    }


class OpenQuestHandler(BaseHTTPRequestHandler):
    server_version = "OpenQuestHTTP/1"

    def do_GET(self) -> None:
        self._respond(*dispatch("GET", self.path))

    def do_POST(self) -> None:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self._respond(
                HTTPStatus.BAD_REQUEST,
                _failure("REQUEST_GATE", "Invalid Content-Length"),
            )
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._respond(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                _failure("REQUEST_GATE", "Request body exceeds 65536 bytes"),
            )
            return
        body = self.rfile.read(length)
        self._respond(*dispatch("POST", self.path, body))

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _respond(self, status: int, payload: dict[str, Any]) -> None:
        data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def build_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), OpenQuestHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenQuest local HTTP/JSON service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = build_server(args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
