# Integration der Cloud-PRs und des lokalen Mac-Stands

Stand: 7. September 2026. Basis: PR #4, Commit
`c5619d841ec72b44311d5e847d6c8e09e328ee39`; enthält die gestapelte Arbeit aus
PR #1–#4. Zusätzlich wurden die bislang lokalen Profil- und Nachrichtenänderungen
vom Checkout `integration/icarus-main` übernommen. Dieser Integrationszweig
wird gegen `integration/icarus-main` geprüft; ein Merge ersetzt die vorherige
PR-Kette inhaltlich. Die bestehenden PRs werden nicht automatisch geschlossen.

## Behobene Integrationsfehler

- Neue Personen-/Projektknoten öffnen ihr Profil über die stabile Registry-ID.
  Zwei gleichnamige Personen führen zu getrennten Profilen. Die Profilansicht
  zeigt eingehende und ausgehende aktuelle Aussagen sowie die Widerrufshistorie.
  Alte namensbasierte Profile bleiben separat erreichbar; sie werden nicht
  automatisch einer neuen Identität zugeordnet.
- Einstellungen → Integrationen bietet die lokale Ollama-Einrichtung an.
  Installierte Modelle werden abgefragt. Speichern und anschließender echter
  Modelltest sind getrennt geprüft; HTTP 200 mit `ok: false` ist ein Fehler.
  Abweichende aktive Startvorgaben werden erkannt. Die Gesprächsverfügbarkeit
  wird bei Navigation neu geladen.
- Die Browser-Einrichtung verwendet geschützte `/api/v1/setup`-Aliase.
  Das HttpOnly-Cookie bleibt auf `/api` begrenzt. Die CLI-Endpunkte bleiben
  erhalten; kein Token wird für JavaScript freigegeben.
- Containerveröffentlichungen verwenden den Kingfisher-Image-Namen.
  Lokale Node-Abhängigkeiten, Git-Metadaten und lokale Schlüsseldateien sind
  ausdrücklich vom Docker-Build-Kontext ausgeschlossen.
- Doppelter `/memory`-Handler und Konfliktstatus der Startanleitung bereinigt.
- Tests isolieren ergänzte Standard-Stores pro Test und sperren den Zugriff
  auf den echten Betriebssystem-Schlüsselbund. Dateibasierte Schlüsselspeicher
  bleiben testbar. Das verhindert Testdaten im lokalen Produktbestand und
  Umgebungsabhängigkeit auf macOS.

## Nachweise

- Vollständige Python-Suite: **776 bestanden**, eine bestehende
  Starlette/httpx-Deprecation-Warnung.
- TypeScript-/Vite-Produktionsbuild erfolgreich.
- Asset-Vertrag: **14 Dateien, 17 Icons** bestanden.
- Docker-Image unter macOS/Colima gebaut und separat auf
  `http://127.0.0.1:8891` gestartet; eigenes Volume und eigene Testschlüssel.
  Die bestehenden Instanzen auf 8890, 8765 und 8877 wurden nicht ersetzt.
- Echter Chromium-Browser, 1440 × 1000: Einrichtungsansicht lädt; fehlendes
  Modell zeigt einen Fehler; vorhandenes `qwen3.5:4b` antwortet über Ollama.
  Keine API-Antworten für diese Abläufe gemockt.
- Echtes Gespräch: Frage nach zwei plus zwei ergibt „Vier.“.
- Zwei synthetische gleichnamige Personen öffnen verschiedene Registry-URLs.
  Ein Projektprofil zeigt die eingehende bestätigte Beziehung. Nach Widerruf
  steht sie nur noch in der Historie. Diese Testdaten liegen ausschließlich
  im getrennten Testvolume.

- Nach Containerneustart: gespeichertes Modell erneut erfolgreich geprüft,
  vorheriges Gespräch wiedergefunden und eine neue Modellantwort erhalten.
  Der widerrufene Claim fehlt im Modellkontext und bleibt in der Profilhistorie.
  Die Antwort auf die Frage nach der widerrufenen Zuordnung lautet „Das weiß
  ich nicht.“.

## Abnahmegrenzen

Die neue Einrichtung und die reduzierte Registry-Profilansicht verwenden
bestehende Komponenten und Originalassets. Die vollständige visuelle
Produktabnahme bleibt offen; funktionierende Screenshots ersetzen sie nicht.
Die Registry-Profilansicht ist noch keine vollständige Personen-/Projektakte
mit Aufgaben, Quellennavigation und Beziehungseditor. Die Roadmap-Punkte 07/08
bleiben deshalb offen. Auch eine Neuinstallation mit Docker Desktop, Backup,
Update/Rückkehrweg und Alltagstest sind damit nicht abgenommen.

Die bestehenden Änderungen bleiben erhalten. Es werden weder ein produktives
Datenvolume migriert noch ursprüngliche lokale Änderungen entfernt.
