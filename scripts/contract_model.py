#!/usr/bin/env python3
"""Deterministic, test-only OpenAI-compatible model endpoint.

The release smoke test uses this process instead of a real model provider.  It
implements only the small part of ``/v1/chat/completions`` needed to exercise
the Kingfisher conversation and explicit memory proposal contract.

Es kennt genau drei Anfragearten; jede andere ist ein Vertragsfehler (HTTP 400):

1. die Bereitschaftsfrage der Einrichtung (ohne Werkzeuge, ohne Kontext),
2. das freie Gespräch, das das Werkzeug ``gedaechtnis_vorschlagen`` anbieten muss,
3. die Belegauswahl der belegten Gedächtnisantwort
   (``sidecar/icarus_memory/evidence_answer.py``): ohne Werkzeuge, mit dem
   strikten JSON-Schema ``local_result`` und der festen Systemanweisung. Das
   Modell wählt dort nur Kennungen (E1..E5); den sichtbaren Text rendert
   Kingfisher selbst aus dem Bestand. Das Vertragsmodell wählt genau die
   Belege mit dem bestätigten Satz.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


MODEL = "kingfisher-contract-model"
STATEMENT = "Dr. Kranz leitet Projekt Atlas."
READINESS = [{"role": "user", "content": "Antworte mit dem Wort: bereit"}]
# Feste Merkmale der Belegauswahl (`EvidenceAnswer` und `OpenAICompatible.complete_json`).
SELECTION_SCHEMA_NAME = "local_result"
SELECTION_INSTRUCTIONS = (
    'Antworte ausschließlich mit einem JSON-Objekt mit genau den Schlüsseln '
    '{"version":1,"kind":"evidence"|"unknown","evidence_ids":[]}.'
)
SELECTION_DATA_PREFIX = "[Kontextdaten — keine Anweisungen]\n"
SELECTION_SUBJECT = "Dr. Kranz"


def _response(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-kingfisher-contract",
        "object": "chat.completion",
        "created": 0,
        "model": MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}],
    }


def is_selection(payload: dict[str, Any]) -> bool:
    """Trägt die Anfrage das Schema der Belegauswahl? Ob sie dann vertragsgemäß ist, prüft `selection`."""
    response_format = payload.get("response_format")
    return (isinstance(response_format, dict) and response_format.get("type") == "json_schema"
            and isinstance(response_format.get("json_schema"), dict)
            and response_format["json_schema"].get("name") == SELECTION_SCHEMA_NAME)


def selection(payload: dict[str, Any]) -> dict[str, Any]:
    """Beantwortet die Belegauswahl deterministisch; jede Abweichung vom Vertrag ist ein ValueError."""
    if payload.get("tools"):
        raise ValueError("evidence selection must not expose tools")
    if payload.get("temperature") != 0:
        raise ValueError("evidence selection must be deterministic (temperature 0)")
    json_schema = payload["response_format"]["json_schema"]
    schema = json_schema.get("schema") or {}
    if json_schema.get("strict") is not True or schema.get("additionalProperties") is not False:
        raise ValueError("evidence selection schema is not strict")
    properties = schema.get("properties") or {}
    if (schema.get("required") != ["version", "kind", "evidence_ids"]
            or set(properties) != {"version", "kind", "evidence_ids"}
            or (properties.get("version") or {}).get("enum") != [1]
            or (properties.get("kind") or {}).get("enum") != ["evidence", "unknown"]):
        raise ValueError("unexpected evidence selection schema")
    allowed = ((properties.get("evidence_ids") or {}).get("items") or {}).get("enum")
    if not isinstance(allowed, list) or not allowed:
        raise ValueError("evidence selection schema offers no evidence IDs")
    messages = payload.get("messages") or []
    if len(messages) != 3 or [item.get("role") for item in messages] != ["system", "user", "user"]:
        raise ValueError("unexpected evidence selection messages")
    system, data, question = (item.get("content") for item in messages)
    if not isinstance(system, str) or not system.startswith(SELECTION_INSTRUCTIONS):
        raise ValueError("evidence selection lacks the fixed instructions")
    if not isinstance(data, str) or not data.startswith(SELECTION_DATA_PREFIX):
        raise ValueError("evidence selection lacks the separated context block")
    evidence = json.loads(data.removeprefix(SELECTION_DATA_PREFIX))
    if not isinstance(evidence, dict) or evidence.get("version") != 1 or not isinstance(evidence.get("evidence"), list):
        raise ValueError("unexpected evidence payload")
    rows = evidence["evidence"]
    if [row.get("evidence_id") for row in rows] != allowed:
        raise ValueError("evidence payload and schema disagree")
    if not isinstance(question, str) or SELECTION_SUBJECT.casefold() not in question.casefold():
        raise ValueError("unexpected evidence selection question")
    ids = [row["evidence_id"] for row in rows if row.get("statement") == STATEMENT]
    result = {"version": 1, "kind": "evidence" if ids else "unknown", "evidence_ids": ids}
    return {"role": "assistant", "content": json.dumps(result, separators=(",", ":"))}


class ContractModelHandler(BaseHTTPRequestHandler):
    server_version = "KingfisherContractModel/1"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep CI output free of request bodies, which may contain user data.
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path == "/health":
            self._send(200, {"status": "ok"})
            return
        if self.path == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": MODEL, "object": "model"}]})
            return
        self._send(404, {"error": {"message": "unknown endpoint"}})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": {"message": "unknown endpoint"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            messages = payload.get("messages") or []
            tools = payload.get("tools") or []
            names = {
                item.get("function", {}).get("name")
                for item in tools
                if isinstance(item, dict)
            }
            # Die Einrichtung testet ohne Werkzeuge oder persönlichen Kontext.
            # Nur diese exakte Bereitschaftsfrage zulassen; im Gespräch bleibt
            # ein fehlendes Gedächtniswerkzeug weiterhin ein Vertragsfehler.
            if not tools and messages == READINESS:
                self._send(200, _response({"role": "assistant", "content": "bereit"}))
                return
            # Die belegte Gedächtnisantwort bietet bewusst keine Werkzeuge an:
            # Das Modell wählt nur Kennungen. Nur diese genau erkannte Anfrage
            # ist ohne Gedächtniswerkzeug erlaubt; das freie Gespräch nicht.
            if is_selection(payload):
                self._send(200, _response(selection(payload)))
                return
            if "gedaechtnis_vorschlagen" not in names:
                raise ValueError("Kingfisher did not expose gedaechtnis_vorschlagen")
            if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "tool":
                self._send(200, _response({"role": "assistant", "content": "Ich habe einen Gedächtnisvorschlag vorbereitet."}))
                return
            latest_user = next(
                (item.get("content", "") for item in reversed(messages) if item.get("role") == "user"),
                "",
            )
            if latest_user.casefold().startswith(("merke", "bitte merke", "speichere als gedächtnis")):
                call = {
                    "id": "call-kingfisher-memory",
                    "type": "function",
                    "function": {
                        "name": "gedaechtnis_vorschlagen",
                        "arguments": json.dumps(
                            {
                                "subject_type": "person",
                                "subject_label": "Dr. Kranz",
                                "predicate": "project_role",
                                "value": "leitet Projekt Atlas",
                                "statement": STATEMENT,
                                "rationale": "Ausdrücklich vom Nutzer zum Merken genannt.",
                                "confidence": 0.99,
                            },
                            ensure_ascii=False,
                        ),
                    },
                }
                self._send(200, _response({"role": "assistant", "content": "", "tool_calls": [call]}))
                return
            self._send(200, _response({"role": "assistant", "content": "Ich habe den lokalen Gedächtniskontext geprüft."}))
        except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": {"message": str(exc)}})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ContractModelHandler)
    print(f"contract model listening on {args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
