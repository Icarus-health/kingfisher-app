# Ungespeicherte lokale Modellwahl beim erneuten Suchen erhalten

11. Oktober 2026. Code `d092006699bdfe89b390916ede8505bc7b3cac9f`, bestehender Draft #54; reine UI-Korrektur. **Noch nicht persönlich installiert**, App bleibt auf separat geprüftem `1.0.6-preview.45cb1c8`. Kein persönlicher Modellrollenwechsel, Download, Ollama-Start oder großer Import.

## Konkreter Produktfehler

Die [vorherige Erstansicht-Prüfung](../2026-10-11-visible-model-recovery/README.md) ließ einen zusätzlichen Status-Retry offen. Kontrollierte Folgeprobe zeigt einen wirklichen Produktfehler: Die abgeschlossene erneute Suche setzt `model` und `manual` jedes Mal aus dem gespeicherten Standard zurück. Eine gerade gewählte Alternative, getippter Name oder absichtlich geleertes Feld ging dadurch verloren. Kein Nachweis für ein allgemeines Browser-/Netzwerkrennen erforderlich; der Fehler tritt nach vollständig beendetem Retry reproduzierbar auf.

Jetzt wird eine ausdrückliche Auswahl als ungespeicherter Entwurf getrennt vom Serverstatus erhalten. Die erneute Suche aktualisiert Status und Inventar, ersetzt den Entwurf aber nicht. Verschwindet dessen Modell aus dem lokalen Inventar, bleibt sein Name manuell sichtbar mit Hinweis auf die fehlende Verfügbarkeitsbestätigung. Ein leeres Feld bleibt leer und kann nicht verbunden werden. Ohne eigenen Entwurf folgt die Karte weiterhin der neu gespeicherten Konfiguration. Erst bestätigte ausdrückliche Verbindung verwirft den Entwurf; Status-/Verbindungsfehler erhalten ihn. Der Entwurf lebt nur in der geöffneten Komponente, nicht als zusätzliche dauerhafte Modellkonfiguration.

## Tatsächliche Gegen- und Folgeprüfungen

Browser plugin not available; vorhandenes Playwright, tatsächliche React-Komponente auf `http://127.0.0.1:18762`, kontrollierte künstliche HTTP-Antworten. Eine kurze simulierte Antwortlatenz macht die vollständige Ladephase sichtbar; danach wird die tatsächliche Feldwahl gelesen. Keine echte Backendverbindung, Modellinferenz, persönlichen Daten oder Cloudanfrage.

Auf Baseline `3449e44` vier erwartete Fehler: vorhandene Alternative, eingetippter Name, leere manuelle Eingabe und inzwischen verschwundene Alternative. Unberührte Konfiguration als Erhaltungskontrolle bestand. Nach Fix alle fünf bestanden; in diesen Abrufen null schreibende API-Anfragen.

Vier weitere echte Komponentenabläufe mit abgefangenen, simulierten Schreibantworten:

- Erfolgreiche Verbindung → Entwurf beendet → später neu gespeicherte Konfiguration wird beim Lesen übernommen.
- Bereitschaft `ok:false` → kein Erfolg-/Sortierknopf → eigener Entwurf bleibt trotz später anderem gespeicherten Standard erhalten.
- Absichtlicher HTTP503 beim Setup-Lesen → sichtbarer Fehler → erneutes Lesen erhält eigene Auswahl, keine Schreibanfrage.
- Unbestätigte lokale Rollenwahl → nur simulierte Rollen-PUT-Anfrage; kein Standardspeichern/Bereitschaftstest → Entwurf bleibt erhalten.

Die drei zulässigen simulierten Verbindungsanfragen sind Rollen-PUT (`local_only:true`, `cloud:false`), Standard-PUT und Bereitschafts-POST. Sie erreichen ausschließlich den künstlichen Browserinterceptor, keinen persönlichen Dienst. Kein Quellenstart/-Pause-Aufruf.

Zusätzlich alle fünf Zustände des vorherigen Erstansicht-Treibers unverändert bestanden. 551 bestehende UI-Tests, Typprüfung, vollständiger Produktionsbuild und Assetvertrag bestanden. Bestehende Bundlegrößenwarnung über 500 kB bleibt. Keine neue Backend-Gesamtsuite für den UI-Diff.

| Gerenderte Prüfung | Ergebnis |
| --- | --- |
| Richtige URL/Titel und sinnvolle Anzeige | bestanden |
| Framework-Overlay / Seitenfehler | keine |
| Normale Konsolenwarnungen/-fehler | keine |
| Absichtlicher Fehlerweg | erwarteter HTTP503-Ressourcenfehler, kein Seitenfehler |
| Desktop 1100×850 / Mobil 390×844 | aufgenommen und visuell geprüft; kein horizontaler Seitenüberlauf |
| Auswahl nach beendetem Retry | erhalten |
| Bewusste Verbindung und Fehlergrenzen | vier künstliche Abläufe bestanden |

Unabhängiges enges statisches Review ohne konkreten Blocker. Reviewer las Code und bereitgestellte Nachherdaten; führte keine Tests aus. Testbrowser und Server anschließend beendet.

## Belege und Grenzen

`verification.json`, Vor-/Nachherdaten, Verbindungsergebnis, vorherige Erstansicht-Gegenprobe, ausführbare Treiber/Hostdateien und komprimierte Logs dokumentieren den engen Nachweis. Screenshots außerhalb Git: `/private/tmp/kingfisher-model-selection-refresh-20261011/after-installed-alternative.png` und `after-mobile.png`.

Kein allgemeiner Nachweis sämtlicher gleichzeitiger Eingaben, nativer WKWebView-Dialoge oder Modellqualität. Fehlendes Gemma12B und persönliche Frage-/Dateiaufnahmeprüfung bleiben offen. Eine separate konkrete Nutzerfrage zur vorhandenen lokalen Qwen9B-Antwortwahl ist gestellt; bis zur Antwort keine entsprechende persönliche Umstellung. Große Mailaufnahme bleibt pausiert. Beide UI-Korrekturen benötigen noch eine gepaarte Lieferung und persönliche Bedienprüfung.
