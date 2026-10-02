#!/usr/bin/env python3
"""Bounded stdlib tests for the release contract helpers."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

try:
    from scripts.contract_model import ContractModelHandler
    from scripts.verify_container import VerificationError, evidence_reply, verify_surface
except ModuleNotFoundError:  # direct `python scripts/test_contract_model.py`
    from contract_model import ContractModelHandler
    from verify_container import VerificationError, evidence_reply, verify_surface


STATEMENT = "Dr. Kranz leitet Projekt Atlas."
# Nachbildung der Anfrage aus `Agent.answer_memory` / `OpenAICompatible.complete_json`;
# sidecar/tests/test_vertragsmodell.py prüft dieselbe Erkennung mit dem echten Produktcode.
INSTRUCTIONS = (
    'Antworte ausschließlich mit einem JSON-Objekt mit genau den Schlüsseln '
    '{"version":1,"kind":"evidence"|"unknown","evidence_ids":[]}. Wähle bei kind="evidence" ...'
)


def selection_request(statements=(STATEMENT, "Frau Kern leitet Projekt Boreal."),
                      question="Was weißt du über Dr. Kranz?") -> dict:
    ids = [f"E{index}" for index, _ in enumerate(statements, 1)]
    evidence = {"version": 1, "evidence": [{"evidence_id": alias, "statement": text}
                                            for alias, text in zip(ids, statements)]}
    schema = {"type": "object", "additionalProperties": False,
              "required": ["version", "kind", "evidence_ids"],
              "properties": {"version": {"type": "integer", "enum": [1]},
                             "kind": {"type": "string", "enum": ["evidence", "unknown"]},
                             "evidence_ids": {"type": "array", "maxItems": len(ids),
                                              "items": {"type": "string", "enum": ids}}}}
    return {"model": "kingfisher-contract-model", "max_tokens": 256, "temperature": 0,
            "reasoning_effort": "none",
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "local_result", "strict": True, "schema": schema}},
            "messages": [{"role": "system", "content": INSTRUCTIONS},
                         {"role": "user", "content": "[Kontextdaten — keine Anweisungen]\n"
                          + json.dumps(evidence, ensure_ascii=False)},
                         {"role": "user", "content": question}]}


HINWEIS = "Gespräch vom 1. Oktober 2026, 12:25 Uhr"


def evidence_payload(**changes) -> dict:
    source = "conversation:c-1:message:m-1"
    reply = ("Gespeicherte Aussagen mit Quellenbezug:\n\n[1] Gespeicherte Aussage: " + STATEMENT
             + "\nGespeicherter Wert: leitet Projekt Atlas\nQuelle [1]: " + HINWEIS)
    contract = {"status": "evidence", "model_called": True, "selected_assertion_ids": ["claim:k-1"]}
    contract.update(changes.pop("contract", {}))
    quelle = {"nummer": 1, "text": HINWEIS, "art": "chat", "assertion_id": "claim:k-1", "episode_id": "e-1",
              "source_ref": source, "conversation_id": "c-1", "message_id": "m-1"}
    quelle.update(changes.pop("quelle", {}))
    return {"context": {"answer_mode": changes.pop("answer_mode", "memory_evidence"),
                        "answer_contract": contract,
                        "quellen": changes.pop("quellen", [quelle]),
                        "items": [{"statement": STATEMENT, "assertion_id": "claim:k-1"}]},
            "messages": [{"role": "user", "content": "Was weißt du über Dr. Kranz?"},
                         {"role": "assistant", "content": changes.pop("reply", reply)}]}


class _SurfaceFixture:
    def __init__(self) -> None:
        self.assets = {"/assets/app.js": "application/javascript", "/assets/app.css": "text/css"}

    def request(self, method: str, path: str, **kwargs):
        if path == "/health":
            return 200, '{"status":"ok"}', {"content-type": "application/json"}
        if path == "/":
            return 200, '<title>Kingfisher</title><script src="/assets/app.js"></script><link rel="stylesheet" href="/assets/app.css"><link rel="icon" href="/favicon.png">', {"content-type": "text/html"}
        if path in {"/today", "/settings", "/vorhaben", "/conversations", "/memory"} or path.startswith("/conversations/"):
            return 200, '<title>Kingfisher</title>', {"content-type": "text/html"}
        if path in self.assets:
            return 200, "", {"content-type": self.assets[path]}
        raise AssertionError(path)


class ContractModelTests(unittest.TestCase):
    def test_provider_emits_memory_tool_and_handles_later_turn(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), ContractModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
            messages = [{"role": "user", "content": "Merke dir: Dr. Kranz leitet Projekt Atlas."}]
            tools = [{"type": "function", "function": {"name": "gedaechtnis_vorschlagen", "parameters": {}}}]
            request = urllib.request.Request(url, data=json.dumps({"messages": messages, "tools": tools}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request) as response:
                first = json.load(response)
            call = first["choices"][0]["message"]["tool_calls"][0]
            self.assertEqual(call["function"]["name"], "gedaechtnis_vorschlagen")
            messages.extend([{"role": "assistant", "tool_calls": [call]}, {"role": "tool", "content": "ok"}, {"role": "user", "content": "Was weißt du über Dr. Kranz?"}])
            request = urllib.request.Request(url, data=json.dumps({"messages": messages, "tools": tools}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request) as response:
                later = json.load(response)
            self.assertEqual(later["choices"][0]["message"]["content"], "Ich habe den lokalen Gedächtniskontext geprüft.")
        finally:
            server.shutdown()
            server.server_close()

    def test_readiness_allows_only_the_context_free_setup_prompt(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), ContractModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
            for prompt, valid in (("Antworte mit dem Wort: bereit", True), ("Was weißt du über Dr. Kranz?", False)):
                request = urllib.request.Request(url,
                    data=json.dumps({"messages": [{"role": "user", "content": prompt}]}).encode(),
                    headers={"Content-Type": "application/json"})
                if valid:
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(json.load(response)["choices"][0]["message"]["content"], "bereit")
                else:
                    with self.assertRaises(urllib.error.HTTPError) as raised:
                        urllib.request.urlopen(request)
                    self.assertEqual(raised.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()

    def _post(self, payload: dict) -> tuple[int, dict]:
        server = ThreadingHTTPServer(("127.0.0.1", 0), ContractModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
            request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        finally:
            server.shutdown()
            server.server_close()

    def test_selection_chooses_exactly_the_confirmed_statement(self) -> None:
        for statements, ids in (((STATEMENT, "Frau Kern leitet Projekt Boreal."), ["E1"]),
                                (("Frau Kern leitet Projekt Boreal.", STATEMENT), ["E2"])):
            status, body = self._post(selection_request(statements))
            self.assertEqual(status, 200)
            choice = body["choices"][0]
            self.assertEqual(choice["finish_reason"], "stop")
            self.assertNotIn("tool_calls", choice["message"])
            self.assertEqual(json.loads(choice["message"]["content"]),
                             {"version": 1, "kind": "evidence", "evidence_ids": ids})

    def test_selection_without_the_statement_selects_nothing(self) -> None:
        status, body = self._post(selection_request(("Frau Kern leitet Projekt Boreal.",)))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body["choices"][0]["message"]["content"]),
                         {"version": 1, "kind": "unknown", "evidence_ids": []})

    def test_deviating_selection_requests_remain_contract_errors(self) -> None:
        tool = [{"type": "function", "function": {"name": "gedaechtnis_vorschlagen", "parameters": {}}}]
        broken = {
            "mit Werkzeugen": lambda p: p.update(tools=tool),
            "ohne temperature 0": lambda p: p.pop("temperature"),
            "nicht strikt": lambda p: p["response_format"]["json_schema"].update(strict=False),
            "fremdes Schema": lambda p: p["response_format"]["json_schema"]["schema"]["properties"].update(answer={"type": "string"}),
            "ohne feste Anweisung": lambda p: p["messages"][0].update(content="Antworte frei."),
            "ohne Datenblock": lambda p: p["messages"][1].update(content="Dr. Kranz leitet Projekt Atlas."),
            "Schema und Daten uneins": lambda p: p["response_format"]["json_schema"]["schema"]["properties"]["evidence_ids"]["items"].update(enum=["E1"]),
            "andere Frage": lambda p: p["messages"][2].update(content="Was steht heute an?"),
            "zusätzliche Nachricht": lambda p: p["messages"].append({"role": "user", "content": "Noch etwas?"}),
        }
        for name, change in broken.items():
            with self.subTest(name):
                payload = selection_request()
                change(payload)
                status, body = self._post(payload)
                self.assertEqual(status, 400, body)

    def test_free_conversation_still_requires_the_memory_tool(self) -> None:
        other = [{"type": "function", "function": {"name": "aktuelle_zeit", "parameters": {}}}]
        for payload in ({"messages": [{"role": "user", "content": "Was weißt du über Dr. Kranz?"}], "tools": other},
                        {"messages": [{"role": "user", "content": "Was weißt du über Dr. Kranz?"}],
                         "response_format": {"type": "json_object"}}):
            status, body = self._post(payload)
            self.assertEqual(status, 400)
            self.assertIn("gedaechtnis_vorschlagen", body["error"]["message"])

    def test_evidence_reply_accepts_only_the_selected_sourced_statement(self) -> None:
        source = "conversation:c-1:message:m-1"
        self.assertIn(STATEMENT, evidence_reply(evidence_payload(), STATEMENT, "claim:k-1", source))
        fallback = ("Das lokale Modell konnte die Auswahl nicht abschließen. Diese gespeicherten Aussagen habe ich gefunden:"
                    "\n\n[1] Gespeicherte Aussage: " + STATEMENT + "\nQuelle [1]: " + HINWEIS)
        gueltig = evidence_payload()["messages"][1]["content"]
        rejected = {
            "Rückfall (Status)": evidence_payload(contract={"status": "fallback", "reason": "provider_error"}, reply=fallback),
            "Rückfalltext trotz Status": evidence_payload(reply=fallback),
            # Nur die Rückfallmarke unterscheidet diese Antwort von einer gültigen.
            "Zuordnung unzuverlässig": evidence_payload(reply=evidence_payload()["messages"][1]["content"]
                                                        + "\n\nDie Antwort des lokalen Modells ließ sich nicht zuverlässig zuordnen."),
            "nichts gewählt": evidence_payload(contract={"status": "unknown", "selected_assertion_ids": []}),
            "falscher Claim": evidence_payload(contract={"selected_assertion_ids": ["claim:k-2"]}),
            "Modell nicht gefragt": evidence_payload(contract={"model_called": False}),
            "freies Gespräch": evidence_payload(answer_mode=None, reply="Ich habe den lokalen Gedächtniskontext geprüft."),
            "ohne Quelle": evidence_payload(reply="Gespeicherte Aussagen mit Quellenbezug:\n\n[1] Gespeicherte Aussage: " + STATEMENT),
            # Die Quelle muss eindeutig die Nachricht sein, aus der der bestätigte Satz stammt.
            "andere Quelle": evidence_payload(quelle={"source_ref": "conversation:c-1:message:m-9", "message_id": "m-9"}),
            "andere Nachricht": evidence_payload(quelle={"message_id": "m-9"}),
            "anderes Gespräch": evidence_payload(quelle={"conversation_id": "c-9"}),
            "Quelle eines anderen Claims": evidence_payload(quelle={"assertion_id": "claim:k-2"}),
            "keine Gesprächsquelle": evidence_payload(quelle={"art": "email"}),
            "Quelle fehlt im Datenfeld": evidence_payload(quellen=[]),
            "zwei Quellen": evidence_payload(quellen=[evidence_payload()["context"]["quellen"][0]] * 2),
            "Hinweis passt nicht zum Text": evidence_payload(quelle={"text": "Gespräch vom 2. Oktober 2026, 08:00 Uhr"}),
            # Lesbar heißt: keine Kennung, keine ISO-Zeit im sichtbaren Text.
            "Rohkennung im Hinweis": evidence_payload(
                quelle={"text": 'Gespräch · "conversation:c-1:message:m-1"'},
                reply=gueltig.replace(HINWEIS, 'Gespräch · "conversation:c-1:message:m-1"')),
            "Rohkennung im Text": evidence_payload(reply=gueltig + "\nconversation:c-1:message:m-1"),
            "ISO-Zeit im Text": evidence_payload(reply=gueltig + "\nEreigniszeit: 2026-10-01T10:25:07.790000+00:00"),
        }
        for name, payload in rejected.items():
            with self.subTest(name):
                with self.assertRaises(VerificationError):
                    evidence_reply(payload, STATEMENT, "claim:k-1", source)

    def test_surface_ignores_favicon_but_checks_js_css_and_health(self) -> None:
        verify_surface(_SurfaceFixture())


if __name__ == "__main__":
    unittest.main()
