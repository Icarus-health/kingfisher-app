#!/usr/bin/env python3
"""Verify the running Kingfisher container contract.

Usage:
    python scripts/verify_container.py --phase seed --state /tmp/kf-state.json
    python scripts/verify_container.py --phase verify --state /tmp/kf-state.json

The target URL and token may be supplied through ``ICARUS_VERIFY_BASE_URL``
and ``ICARUS_VERIFY_TOKEN``.  A token passed on the command line is accepted
for local use, but is never printed or written to the state file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


STATEMENT = "Dr. Kranz leitet Projekt Atlas."
QUESTION = "Was weißt du über Dr. Kranz?"
# Feste Texte von `EvidenceAnswer.render_readable` (sidecar/icarus_memory/evidence_answer.py).
EVIDENCE_INTRO = "Gespeicherte Aussagen mit Quellenbezug:"
FALLBACK_MARKERS = (
    "konnte die Auswahl nicht abschließen",
    "ließ sich nicht zuverlässig zuordnen",
    "Die Modellauswahl konnte nicht geprüft werden",
    "Das kann ich mit den gefundenen Belegen nicht beantworten",
)
# Quellenhinweis einer Gesprächsquelle (`quellenhinweis.text`): „Gespräch vom 1. Oktober 2026, 12:25 Uhr“.
READABLE_CHAT_SOURCE = re.compile(
    r"Gespräch vom \d{1,2}\. (Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
    r" \d{4}(, \d{2}:\d{2} Uhr)?")
# Was im sichtbaren Text nicht stehen darf: ISO-Zeiten und Kennungen von Gespräch, Nachricht, Claim, Quelle.
RAW_IN_REPLY = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}|conversation:|:message:|claim:|episode:")
ROUTES =("/","/today", "/settings", "/vorhaben", "/conversations", "/memory")


class VerificationError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        auth: bool = True,
        expected: set[int] | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        headers = {"Accept": "application/json"}
        if auth:
            headers["x-icarus-token"] = self.token
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
                text = response.read().decode("utf-8", errors="replace")
                response_headers = {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as response:
            status = response.code
            text = response.read().decode("utf-8", errors="replace")
            response_headers = {key.lower(): value for key, value in response.headers.items()}
        except (urllib.error.URLError, TimeoutError) as exc:
            raise VerificationError(f"{method} {path} nicht erreichbar: {exc.reason if hasattr(exc, 'reason') else exc}") from exc
        if expected is not None and status not in expected:
            raise VerificationError(f"{method} {path}: HTTP {status}, erwartet {sorted(expected)}")
        return status, text, response_headers

    def json(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
        status, text, _ = self.request(method, path, body=body, expected={200, 201})
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise VerificationError(f"{method} {path}: keine JSON-Antwort") from exc
        if not isinstance(payload, dict):
            raise VerificationError(f"{method} {path}: unerwartete JSON-Antwort")
        return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _json(payload: str, action: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{action}: keine JSON-Antwort") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{action}: unerwartete JSON-Antwort")
    return value


def source_ref(conversation_id: str, message_id: str) -> str:
    """Die Quellenkennung, unter der ein Merksatz aus dem Gespräch als Beleg gespeichert wird."""
    return f"conversation:{conversation_id}:message:{message_id}"


def evidence_reply(payload: dict[str, Any], statement: str, assertion_id: str, source: str) -> str:
    """Prüft eine belegte Gedächtnisantwort und gibt den sichtbaren Antworttext zurück.

    Die Antwort muss aus der Modellauswahl stammen (Status `evidence`, Modell
    gefragt, genau der bestätigte Claim gewählt), den gespeicherten Satz mit
    seiner Quelle zeigen und darf keine Rückfallantwort sein.
    """
    context = payload.get("context") or {}
    contract = context.get("answer_contract") or {}
    _require(any(item.get("statement") == statement and item.get("assertion_id") == assertion_id
                 for item in context.get("items") or []),
             "Der bestätigte Claim fehlt im Antwortkontext.")
    _require(context.get("answer_mode") == "memory_evidence",
             f"Die Frage lief nicht über die belegte Gedächtnisantwort (answer_mode={context.get('answer_mode')!r}).")
    _require(contract.get("status") == "evidence" and "reason" not in contract,
             f"Die Belegauswahl des lokalen Modells wurde nicht angenommen (status={contract.get('status')!r}, reason={contract.get('reason')!r}).")
    _require(contract.get("model_called") is True, "Die Belegauswahl hat das lokale Modell nicht gefragt.")
    _require(contract.get("selected_assertion_ids") == [assertion_id],
             f"Die Auswahl wählte nicht genau den bestätigten Claim: {contract.get('selected_assertion_ids')!r}.")
    assistant = [item for item in payload.get("messages") or [] if item.get("role") == "assistant"]
    _require(bool(assistant), "Die Antwort enthält keine Assistentenzeile.")
    reply = assistant[-1].get("content") or ""
    _require(not any(marker in reply for marker in FALLBACK_MARKERS), f"Kingfisher lieferte eine Rückfallantwort: {reply[:160]!r}")
    _require(reply.startswith(EVIDENCE_INTRO), f"Die Antwort ist keine belegte Auswahl: {reply[:160]!r}")
    _require(f"[1] Gespeicherte Aussage: {statement}" in reply, "Die Antwort zeigt die bestätigte Aussage nicht.")
    # Der Quellenhinweis steht in Alltagssprache im Text („Gespräch vom 1. Oktober 2026, 12:25 Uhr“);
    # welche Nachricht es ist, sagt das Datenfeld `quellen`. Beides muss zusammenpassen.
    quellen = context.get("quellen")
    _require(isinstance(quellen, list) and len(quellen) == 1 and isinstance(quellen[0], dict),
             f"Die Antwort nennt nicht genau eine Quelle als Datenfeld: {quellen!r}.")
    quelle = quellen[0]
    _require(quelle.get("nummer") == 1 and quelle.get("assertion_id") == assertion_id,
             f"Die Quelle [1] gehört nicht zum bestätigten Claim: {quelle!r}.")
    _require(quelle.get("art") == "chat" and quelle.get("source_ref") == source,
             f"Die Quelle des bestätigten Satzes ist nicht die Nachricht {source!r}: {quelle.get('source_ref')!r}.")
    teile = source.split(":")
    _require(len(teile) == 4 and (quelle.get("conversation_id"), quelle.get("message_id")) == (teile[1], teile[3]),
             "Die Quelle führt nicht zu der Nachricht, aus der der Satz stammt.")
    hinweis = quelle.get("text")
    _require(isinstance(hinweis, str) and READABLE_CHAT_SOURCE.fullmatch(hinweis) is not None,
             f"Der Quellenhinweis ist nicht in Alltagssprache: {hinweis!r}.")
    _require(f"Quelle [1]: {hinweis}" in reply, "Die Antwort nennt nicht die Quelle des bestätigten Satzes.")
    _require(source not in reply and RAW_IN_REPLY.search(reply) is None,
             f"Die Antwort zeigt Rohkennungen oder ISO-Zeiten: {reply[:200]!r}")
    return reply


def verify_surface(client: Client, conversation_id: str | None = None) -> None:
    _, health_body, health_headers = client.request("GET", "/health", auth=False, expected={200})
    health = _json(health_body, "GET /health")
    _require(health.get("status") == "ok", "Der Sidecar meldet keinen gesunden Zustand.")
    _require(health_headers.get("content-type", "").split(";", 1)[0] == "application/json", "/health liefert keinen JSON-Content-Type.")
    status, body, headers = client.request("GET", "/", auth=False, expected={200})
    _require("Kingfisher" in body, "Die Root-Seite enthält nicht den Kingfisher-Titel.")
    _require(headers.get("content-type", "").split(";", 1)[0] == "text/html", "Root liefert keinen HTML-Content-Type.")
    script_paths = set(re.findall(r'<script[^>]+src=["\']([^"\']+)', body))
    stylesheet_paths = set(re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)', body, re.IGNORECASE))
    _require(script_paths, "Die Root-Seite enthält kein JavaScript-Asset.")
    _require(stylesheet_paths, "Die Root-Seite enthält kein CSS-Asset.")
    for asset in sorted(script_paths | stylesheet_paths):
        _, _, asset_headers = client.request("GET", asset, auth=False, expected={200})
        media = asset_headers.get("content-type", "").split(";", 1)[0]
        _require(media in {"application/javascript", "text/javascript", "text/css"}, f"Asset {asset} hat unerwarteten Content-Type {media!r}.")
    routes = (*ROUTES, f"/conversations/{conversation_id}" if conversation_id else "")
    for route in routes:
        if not route:
            continue
        _, route_body, route_headers = client.request("GET", route, auth=False, expected={200})
        _require("Kingfisher" in route_body, f"SPA-Route {route} liefert nicht die Kingfisher-Seite.")
        _require(route_headers.get("content-type", "").split(";", 1)[0] == "text/html", f"SPA-Route {route} liefert keinen HTML-Content-Type.")


def verify_auth(client: Client) -> None:
    # A fresh opener deliberately has no browser session cookie.
    request = urllib.request.Request(client.base_url + "/api/v1/status", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
    except urllib.error.HTTPError as response:
        status = response.code
    except (urllib.error.URLError, TimeoutError) as exc:
        raise VerificationError(f"Authentifizierungsprobe nicht erreichbar: {exc}") from exc
    _require(status == 401, f"Die API ist ohne Token nicht gesperrt (HTTP {status}).")
    _require(client.json("GET", "/api/v1/status").get("chat") is True, "Der Chat ist im Container nicht als verfügbar gemeldet.")


def seed(client: Client, state_path: Path) -> None:
    verify_surface(client)
    verify_auth(client)
    # Eine frische Instanz ohne Postfach öffnet beim ersten Aufruf von /today den Einrichtungsassistenten
    # (`zeigen` in /api/v1/einrichtung). Der Vertragstest prüft eine eingerichtete Instanz mit verbundenem Modell;
    # er schließt den Assistenten deshalb ab, wie es ein Mensch mit „Zum Briefing“ täte.
    vorher = client.json("GET", "/api/v1/einrichtung")
    _require(vorher.get("zeigen") is True, "Eine frische Instanz ohne Postfach müsste den Einrichtungsassistenten zeigen.")
    nachher = client.json("PUT", "/api/v1/einrichtung", body={"abgeschlossen": True})
    _require(nachher.get("abgeschlossen") is True and nachher.get("zeigen") is False,
             "Der Einrichtungsassistent ließ sich nicht abschließen.")
    created = client.json("POST", "/api/v1/conversations", body={"title": "Vertragstest"})
    conversation = created.get("conversation") or {}
    conversation_id = conversation.get("id")
    _require(isinstance(conversation_id, str) and conversation_id, "Gespräch konnte nicht angelegt werden.")
    verify_surface(client, conversation_id)
    message_text = f"Merke dir: {STATEMENT}"
    sent = client.json("POST", f"/api/v1/conversations/{conversation_id}/messages", body={"message": message_text})
    cards = sent.get("memory_candidates") or []
    _require(len(cards) == 1, "Der ausdrückliche Merksatz erzeugte nicht genau einen Vorschlag.")
    card = cards[0]
    candidate = card.get("candidate") or {}
    _require(candidate.get("state") == "pending", "Der Gedächtnisvorschlag ist nicht pending.")
    _require(candidate.get("statement") == STATEMENT, "Der Vorschlag enthält nicht den erwarteten Satz.")
    _require(not any(item.get("kind") == "knowledge" for item in (sent.get("context") or {}).get("items", [])), "Ein unbestätigter Vorschlag wurde bereits als Kontext verwendet.")
    candidate_id = candidate.get("id")
    _require(isinstance(candidate_id, str) and candidate_id, "Vorschlags-ID fehlt.")
    accepted = client.json("POST", f"/api/v1/conversations/{conversation_id}/memory-candidates/{candidate_id}/accept", body={"replace_conflicts": False})
    accepted_card = next((item.get("candidate") for item in accepted.get("memory_candidates", []) if (item.get("candidate") or {}).get("id") == candidate_id), None)
    _require((accepted_card or {}).get("state") == "accepted", "Der Gedächtnisvorschlag ließ sich nicht sichtbar annehmen.")
    user_message_id = next((item.get("id") for item in sent.get("messages", []) if item.get("role") == "user"), None)
    _require(isinstance(user_message_id, str), "Die Nutzerzeile fehlt im persistenten Gespräch.")
    followup = client.json("POST", f"/api/v1/conversations/{conversation_id}/messages", body={"message": QUESTION})
    context_items = (followup.get("context") or {}).get("items") or []
    claim = next((item for item in context_items if item.get("statement") == STATEMENT), None)
    _require(claim is not None, "Bestätigtes Wissen wurde nicht in den nächsten lokalen Kontext aufgenommen.")
    claim_id = claim.get("assertion_id")
    _require(isinstance(claim_id, str) and claim_id.startswith("claim:"), "Der bestätigte Kontext enthält keine Claim-ID.")
    evidence_reply(followup, STATEMENT, claim_id, source_ref(conversation_id, user_message_id))
    state ={"conversation_id": conversation_id, "candidate_id": candidate_id, "claim_id": claim_id.removeprefix("claim:"), "statement": STATEMENT, "user_message_id": user_message_id}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"seed passed: conversation={conversation_id} candidate={candidate_id}")


def verify_restart(client: Client, state_path: Path) -> None:
    verify_surface(client)
    verify_auth(client)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"State-Datei kann nicht gelesen werden: {exc}") from exc
    conversation_id = state.get("conversation_id")
    statement = state.get("statement")
    claim_id = state.get("claim_id")
    _require(all(isinstance(value, str) and value for value in (conversation_id, statement, claim_id)), "State-Datei ist unvollständig.")
    payload = client.json("GET", f"/api/v1/conversations/{conversation_id}")
    messages = payload.get("messages") or []
    _require(any(item.get("content") == f"Merke dir: {statement}" for item in messages), "Das Gespräch wurde nach dem Neustart nicht erhalten.")
    _require(any((item.get("candidate") or {}).get("id") == state.get("candidate_id") and (item.get("candidate") or {}).get("state") == "accepted" for item in payload.get("memory_candidates", [])), "Der akzeptierte Vorschlag wurde nach dem Neustart nicht erhalten.")
    user_message_id = state.get("user_message_id")
    _require(isinstance(user_message_id, str) and user_message_id, "State-Datei ist unvollständig.")
    before_retract = client.json("POST", f"/api/v1/conversations/{conversation_id}/messages", body={"message": QUESTION})
    before_context = (before_retract.get("context") or {}).get("items") or []
    _require(any(item.get("statement") == statement and item.get("assertion_id") == f"claim:{claim_id}" for item in before_context), "Der bestätigte Claim ist nach dem Neustart nicht im nächsten Gesprächskontext.")
    evidence_reply(before_retract, statement, f"claim:{claim_id}", source_ref(conversation_id, user_message_id))
    response = client.json("POST", f"/api/v1/memory/claims/{claim_id}/retract", body={"reason": "contract verification"})
    _require((response.get("claim") or {}).get("status") == "retracted", "Der bestätigte Claim ließ sich nicht widerrufen.")
    after = client.json("POST", f"/api/v1/conversations/{conversation_id}/messages", body={"message": QUESTION})
    context_items = (after.get("context") or {}).get("items") or []
    _require(not any(item.get("statement") == statement for item in context_items), "Widerrufenes Wissen wurde weiter in den Gesprächskontext gegeben.")
    _require(f"claim:{claim_id}" not in ((after.get("context") or {}).get("answer_contract") or {}).get("selected_assertion_ids", []),
             "Die Antwort wählte nach dem Widerruf weiter den widerrufenen Claim.")
    print(f"verify passed: conversation={conversation_id} transcript preserved, claim retracted")


def verify_ui_restart(client: Client, state_path: Path) -> None:
    """Check the browser mutation after a second actual container restart."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    ui = state.get("ui_retraction") or {}
    _require(all(ui.get(key) for key in ("conversation_id", "candidate_id", "claim_id")),
             "Der Browser hat keinen vollständigen Widerrufsnachweis gespeichert.")
    path = f"/api/v1/conversations/{ui['conversation_id']}"
    payload = client.json("GET", path)
    card = next((item for item in payload["memory_candidates"]
                 if item["candidate"]["id"] == ui["candidate_id"]), None)
    _require(card is not None and card["claim"]["status"] == "retracted" and not card["claim_usable"],
             "Der im Browser widerrufene Claim ist nach dem Containerneustart nicht mehr widerrufen.")
    _require(card["candidate"]["state"] == "accepted", "Die historische Bestätigung wurde verfälscht.")
    after = client.json("POST", path + "/messages", body={"message": QUESTION})
    _require(not any(item.get("assertion_id") == f"claim:{ui['claim_id']}" for item in after["context"]["items"]),
             "Der im Browser widerrufene Claim wurde nach dem Neustart wieder verwendet.")
    _require(f"claim:{ui['claim_id']}" not in (after["context"].get("answer_contract") or {}).get("selected_assertion_ids", []),
             "Die Antwort wählte nach dem Neustart den im Browser widerrufenen Claim.")
    print("UI restart passed: source history preserved, browser retraction remains excluded")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None, help="Kingfisher URL; alternatively ICARUS_VERIFY_BASE_URL")
    parser.add_argument("--token", default=None, help="Token; alternatively ICARUS_VERIFY_TOKEN (never logged)")
    parser.add_argument("--phase", choices=("seed", "verify", "verify-ui"), required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    base_url = args.base_url or __import__("os").environ.get("ICARUS_VERIFY_BASE_URL")
    token = args.token or __import__("os").environ.get("ICARUS_VERIFY_TOKEN")
    if not base_url or not token:
        print("FEHLER: --base-url/ICARUS_VERIFY_BASE_URL und --token/ICARUS_VERIFY_TOKEN sind erforderlich.", file=sys.stderr)
        return 2
    try:
        client = Client(base_url, token)
        if args.phase == "seed":
            seed(client, args.state)
        elif args.phase == "verify-ui":
            verify_ui_restart(client, args.state)
        else:
            verify_restart(client, args.state)
    except VerificationError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
