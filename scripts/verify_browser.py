#!/usr/bin/env python3
"""Run the Kingfisher browser smoke test against a seeded local container.

This intentionally drives the real UI and network.  It does not intercept or
replace API responses.  The seed file is made by ``verify_container.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_container import (  # noqa: E402 - Skriptordner erst oben eingetragen
    EVIDENCE_INTRO, QUESTION, VerificationError, evidence_reply, source_ref,
)

ASSET_RESOURCE_TYPES = {"document", "font", "image", "script", "stylesheet"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def write_summary(output: Path, summary: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_state(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"State-Datei kann nicht gelesen werden: {exc}") from exc
    required = ("conversation_id", "candidate_id", "claim_id", "statement", "user_message_id")
    require(isinstance(value, dict), "State-Datei ist kein JSON-Objekt.")
    require(all(isinstance(value.get(key), str) and value[key] for key in required), "State-Datei ist unvollständig.")
    return {key: value[key] for key in required}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8890", help="Kingfisher URL")
    parser.add_argument("--state", type=Path, required=True, help="State JSON produced by verify_container.py seed")
    parser.add_argument("--output", type=Path, default=Path("artifacts"), help="Directory for screenshots and summary.json")
    parser.add_argument("--timeout-ms", type=int, default=15_000, help="Per-step browser timeout")
    parser.add_argument("--phase", choices=("smoke", "memory-controls"), default="smoke")
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "ok": False,
        "base_url": args.base_url.rstrip("/"),
        "state": str(args.state),
        "checks": {},
        "screenshots": [],
        "errors": [],
        "visual_comparison": False,
        "validation_scope": "desktop interaction for the Mac-first release",
        "product_ready": False,
    }
    page = None
    browser = None
    playwright_runtime = None
    failure_recorded = False
    try:
        state = load_state(args.state)
        summary["conversation_id"] = state["conversation_id"]
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise VerificationError("Playwright ist nicht installiert; Browserprüfung konnte nicht ausgeführt werden.") from exc

        origin = f"{urlparse(args.base_url).scheme}://{urlparse(args.base_url).netloc}"
        playwright_runtime = sync_playwright().start()
        try:
            browser = playwright_runtime.chromium.launch()
        except Exception as exc:  # Playwright reports missing browser binaries here.
            raise VerificationError(f"Playwright-Browser konnte nicht gestartet werden: {exc}") from exc
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.set_default_timeout(args.timeout_ms)
            page.set_default_navigation_timeout(args.timeout_ms)
            page_errors: list[str] = []
            console_errors: list[str] = []
            asset_failures: list[str] = []

            def local_asset(url: str, resource_type: str) -> bool:
                return url.startswith(origin + "/") and resource_type in ASSET_RESOURCE_TYPES

            def on_page_error(error: Any) -> None:
                page_errors.append(str(error))

            def on_console(message: Any) -> None:
                if message.type == "error":
                    console_errors.append(message.text)

            def on_request_failed(request: Any) -> None:
                if local_asset(request.url, request.resource_type):
                    asset_failures.append(f"{request.method} {request.url}: {request.failure}")

            def on_response(response: Any) -> None:
                request = response.request
                if local_asset(response.url, request.resource_type) and response.status >= 400:
                    asset_failures.append(f"HTTP {response.status} {response.url}")

            page.on("pageerror", on_page_error)
            page.on("console", on_console)
            page.on("requestfailed", on_request_failed)
            page.on("response", on_response)

            def settle() -> None:
                try:
                    page.wait_for_load_state("networkidle", timeout=args.timeout_ms)
                except Exception:
                    # A long-lived fetch must not hide the DOM checks below.
                    pass
                page.wait_for_timeout(250)

            def audit(route_name: str) -> None:
                if page_errors:
                    raise VerificationError(f"JavaScript-Fehler auf {route_name}: {page_errors[-1]}")
                if console_errors:
                    raise VerificationError(f"Console-Fehler auf {route_name}: {console_errors[-1]}")
                if asset_failures:
                    raise VerificationError(f"Fehler beim Laden lokaler Assets auf {route_name}: {asset_failures[-1]}")
                overlays = page.locator("vite-error-overlay, vite-plugin-checker-error-overlay, #webpack-dev-server-client-overlay").count()
                require(overlays == 0, f"Framework-Fehleroverlay auf {route_name} sichtbar.")
                images = page.locator("img:visible").evaluate_all(
                    """(items) => items.map((img) => ({
                      src: img.currentSrc || img.src,
                      complete: img.complete,
                      naturalWidth: img.naturalWidth,
                      naturalHeight: img.naturalHeight
                    }))"""
                )
                broken = [item["src"] for item in images if not item["complete"] or item["naturalWidth"] <= 0 or item["naturalHeight"] <= 0]
                if broken:
                    raise VerificationError(f"Sichtbare Bilder auf {route_name} sind defekt: {broken[0]}")
                fonts = page.evaluate(
                    """async () => {
                      // A declared face can remain unloaded when this route does
                      // not use it. Explicitly load every approved weight so the
                      // check detects missing files without depending on page text.
                      const specs = [
                        '400 16px Inter', '500 16px Inter',
                        '600 16px Inter', '700 16px Inter',
                        '400 16px "Cormorant Garamond"',
                        '600 16px "Cormorant Garamond"'
                      ];
                      const faces = await Promise.all(specs.map(spec => document.fonts.load(spec)));
                      await document.fonts.ready;
                      return {
                        status: document.fonts.status,
                        count: document.fonts.size,
                        approved: faces.every(matches => matches.length > 0 && matches.every(face => face.status === 'loaded')),
                        inter: document.fonts.check('16px Inter'),
                        cormorant: document.fonts.check('16px "Cormorant Garamond"')
                      };
                    }"""
                )
                require(fonts["status"] == "loaded" and fonts["count"] > 0 and fonts["approved"] and fonts["inter"] and fonts["cormorant"], f"Schriften auf {route_name} wurden nicht vollständig geladen: {fonts}")

            def screenshot(name: str) -> None:
                target = args.output / f"{name}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(target), full_page=False)
                summary["screenshots"].append(str(target))

            def visible_evidence(reply: str, source: str, message_id: str) -> None:
                """Die geprüfte belegte Antwort steht vollständig und sichtbar in der letzten Kingfisher-Zeile.

                Ihre Quelle ist mit einem Klick erreichbar: Der Verweis trägt die Quellenkennung als Datenattribut
                (sichtbar ist sie nicht), und der Klick fokussiert genau die Nachricht, aus der der Satz stammt.
                """
                last = page.locator(".messages .message.assistant").last
                last.get_by_text(EVIDENCE_INTRO).wait_for(state="visible", timeout=args.timeout_ms)
                last.scroll_into_view_if_needed()
                shown = " ".join(last.inner_text().split())
                require(" ".join(reply.split()) in shown,
                        f"Die sichtbare Antwort zeigt nicht die belegte Aussage mit Quelle: {shown[:200]!r}")
                require(source not in shown, "Die sichtbare Antwort zeigt die Quellenkennung.")
                verweis = last.locator('[data-quelle="1"]')
                require(verweis.count() == 1 and verweis.get_attribute("data-quelle-ref") == source,
                        "Die Quelle [1] ist nicht als Verweis auf die richtige Nachricht erreichbar.")
                # Unter der Antwort steht sichtbar, worauf sie sich stützt: „Gestützt auf“ und derselbe Hinweis in
                # Alltagssprache wie im Text (Fremdprobe 2, Befund 13).
                hinweis = re.search(r"Quelle \[1\]: ([^\n]+)", reply)
                beleg = last.get_by_role("group", name="Worauf die Antwort sich stützt")
                require(hinweis is not None and beleg.is_visible() and "Gestützt auf" in beleg.inner_text()
                        and hinweis.group(1).strip() in " ".join(verweis.inner_text().split()),
                        f"Unter der Antwort steht nicht sichtbar, worauf sie sich stützt: {verweis.inner_text()!r}")
                verweis.get_by_role("button", name="Quelle 1 öffnen", exact=True).click()
                page.wait_for_function("id => document.activeElement && document.activeElement.id === 'message-' + id",
                                       arg=message_id, timeout=args.timeout_ms)

            def goto(path: str, name: str) -> None:
                page.goto(args.base_url.rstrip("/") + path, wait_until="domcontentloaded")
                settle()
                audit(name)

            if args.phase == "memory-controls":
                goto("/conversations", "conversation-history")
                page.get_by_role("button", name="Neues Gespräch", exact=True).click()
                page.wait_for_url("**/conversations/*")
                conversation_id = page.url.rsplit("/", 1)[-1]
                message_url = origin + f"/api/v1/conversations/{conversation_id}/messages"

                def send(text: str) -> dict[str, Any]:
                    page.get_by_label("Kingfisher fragen").fill(text)
                    with page.expect_response(lambda response: response.url == message_url
                                              and response.request.method == "POST"
                                              and response.status in {200, 201}) as result:
                        page.get_by_role("button", name="Nachricht senden", exact=True).click()
                    return result.value.json()

                proposed = send(f"Merke dir: {state['statement']}")
                card = proposed["memory_candidates"][0]
                candidate_id = card["candidate"]["id"]
                source_id = card["source_message_id"]
                memory_card = page.get_by_role("region", name="Gedächtnisvorschlag")
                memory_card.get_by_role("button", name="Quelle anzeigen", exact=True).click()
                require(page.locator(f"#message-{source_id}").evaluate("element => element === document.activeElement"),
                        "Quelle anzeigen fokussiert nicht die ursprüngliche Nutzerzeile.")
                memory_card.get_by_role("button", name="Bestätigen", exact=True).click()
                memory_card.get_by_text("Als Wissen bestätigt.", exact=True).wait_for(state="visible")
                before = send(QUESTION)
                accepted_card = next(item for item in before["memory_candidates"] if item["candidate"]["id"] == candidate_id)
                claim_id = accepted_card["claim"]["id"]
                require(any(item.get("assertion_id") == f"claim:{claim_id}" for item in before["context"]["items"]),
                        "Der im Browser bestätigte Claim fehlt im Antwortkontext.")
                visible_evidence(evidence_reply(before, state["statement"], f"claim:{claim_id}",
                                                source_ref(conversation_id, source_id)),
                                 source_ref(conversation_id, source_id), source_id)
                memory_card.scroll_into_view_if_needed()
                screenshot("memory-card-confirmed")
                retract_url = origin + f"/api/v1/conversations/{conversation_id}/memory-candidates/{candidate_id}/retract"
                with page.expect_response(lambda response: response.url == retract_url and response.status == 200) as result:
                    memory_card.get_by_role("button", name="Als falsch widerrufen", exact=True).click()
                retracted = result.value.json()
                require(not any(item.get("assertion_id") == f"claim:{claim_id}" for item in retracted["context"]["items"]),
                        "Der alte Kontext bleibt nach dem Widerruf sichtbar.")
                memory_card.get_by_text("Widerrufen. Wird nicht mehr als Wissen verwendet.", exact=True).wait_for(state="visible")
                require(memory_card.get_by_role("button", name="Als falsch widerrufen", exact=True).count() == 0,
                        "Ein widerrufener Claim bietet weiterhin Widerrufen an.")
                screenshot("memory-card-retracted")
                after = send(QUESTION)
                require(not any(item.get("assertion_id") == f"claim:{claim_id}" for item in after["context"]["items"]),
                        "Der im Browser widerrufene Claim gelangt erneut in den Modellkontext.")
                require(f"claim:{claim_id}" not in (after["context"].get("answer_contract") or {}).get("selected_assertion_ids", []),
                        "Die Antwort wählt den im Browser widerrufenen Claim weiter aus.")
                page.reload(wait_until="domcontentloaded")
                memory_card.get_by_text("Widerrufen. Wird nicht mehr als Wissen verwendet.", exact=True).wait_for(state="visible")
                settle()
                audit("memory-controls")
                memory_card.scroll_into_view_if_needed()
                screenshot("memory-card-reloaded")
                stored = json.loads(args.state.read_text(encoding="utf-8"))
                stored["ui_retraction"] = {"conversation_id": conversation_id, "candidate_id": candidate_id, "claim_id": claim_id}
                args.state.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                summary["checks"]["memory_controls"] = {"source_focus": True, "confirmation": True,
                    "retraction": True, "context_exclusion": True, "reload": True, "viewport": "1440x1000"}
            else:
                goto("/today", "today")
                require(page.title() == "Kingfisher", "Die gerenderte Seite hat nicht den Titel Kingfisher.")
                require(page.get_by_alt_text("Kingfisher").count() > 0, "Das sichtbare Kingfisher-Branding fehlt.")
                navigation = page.get_by_role("navigation", name="Hauptnavigation")
                require(navigation.count() == 1 and navigation.inner_text().strip(), "Die Hauptnavigation ist leer.")
                summary["checks"]["today"] = {"title": "Kingfisher", "navigation": True, "images": True, "fonts": True}
                screenshot("today")

                conversation_path = f"/conversations/{state['conversation_id']}"
                goto(conversation_path, "conversation")
                page.get_by_text("Als Wissen bestätigt.", exact=True).wait_for(state="visible")
                require(page.get_by_text(state["statement"], exact=True).count() > 0, "Der bestätigte Gedächtniskontext fehlt im Gespräch.")
                summary["checks"]["conversation_seed"] = {"confirmed": True, "context": True}
                question = page.get_by_label("Kingfisher fragen")
                question.fill(QUESTION)
                message_url = origin + f"/api/v1/conversations/{state['conversation_id']}/messages"
                assistant_count = page.locator(".messages .message.assistant").count()
                with page.expect_response(
                    lambda response: response.url == message_url
                    and response.request.method == "POST"
                    and response.status in {200, 201},
                    timeout=args.timeout_ms,
                ) as response_info:
                    page.get_by_role("button", name="Nachricht senden", exact=True).click()
                response_payload = response_info.value.json()
                context_items = (response_payload.get("context") or {}).get("items") or []
                require(any(item.get("statement") == state["statement"] for item in context_items), "Die Browser-Antwort enthielt keinen bestätigten Kontext.")
                page.wait_for_function(
                    "before => document.querySelectorAll('.messages .message.assistant').length > before",
                    arg=assistant_count,
                    timeout=args.timeout_ms,
                )
                reply = evidence_reply(response_payload, state["statement"], f"claim:{state['claim_id']}",
                                       source_ref(state["conversation_id"], state["user_message_id"]))
                visible_evidence(reply, source_ref(state["conversation_id"], state["user_message_id"]),
                                 state["user_message_id"])
                require(page.get_by_text(state["statement"], exact=True).count() > 0, "Der bestätigte Kontext fehlt nach der Browserfrage.")
                summary["checks"]["conversation_send"] = {"answer": "evidence", "statement": True, "source": True, "source_click": True, "context": True}
                screenshot("conversation")

                goto("/memory", "memory")
                require(page.get_by_role("button", name="Projekte", exact=True).count() == 1, "Der Projekte-Filter fehlt.")
                require(page.get_by_role("button", name="Menschen", exact=True).count() == 1, "Der Menschen-Filter fehlt.")
                screenshot("memory")
                page.reload(wait_until="domcontentloaded")
                settle()
                audit("memory-reload")
                screenshot("memory-reload")

                projects = page.get_by_role("button", name="Projekte", exact=True)
                people = page.get_by_role("button", name="Menschen", exact=True)
                projects.click()
                require(projects.get_attribute("aria-pressed") == "true" and people.get_attribute("aria-pressed") == "false", "Der Projekte-Filter wurde nicht aktiviert.")
                screenshot("memory-projects")
                people.click()
                require(people.get_attribute("aria-pressed") == "true" and projects.get_attribute("aria-pressed") == "false", "Der Menschen-Filter wurde nicht aktiviert.")
                summary["checks"]["memory"] = {"direct": True, "reload": True, "projects": True, "people": True}
                screenshot("memory-people")

            summary["ok"] = True
            context.close()
            browser.close()
        except Exception as exc:
            failure_recorded = True
            summary["errors"].append(str(exc))
            if page is not None:
                try:
                    failure = args.output / "failure.png"
                    failure.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(failure), full_page=False)
                    summary["screenshots"].append(str(failure))
                except Exception as screenshot_error:
                    summary["errors"].append(f"Fehler-Screenshot konnte nicht gespeichert werden: {screenshot_error}")
            raise
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright_runtime is not None:
                playwright_runtime.stop()
    except Exception as exc:
        if not failure_recorded:
            summary["errors"].append(str(exc))
        if not failure_recorded and page is not None:
            try:
                failure = args.output / "failure.png"
                failure.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(failure), full_page=False)
                summary["screenshots"].append(str(failure))
            except Exception as screenshot_error:
                summary["errors"].append(f"Fehler-Screenshot konnte nicht gespeichert werden: {screenshot_error}")
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
    finally:
        try:
            write_summary(args.output, summary)
        except OSError as exc:
            print(f"FEHLER: Zusammenfassung konnte nicht geschrieben werden: {exc}", file=sys.stderr)
            return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
