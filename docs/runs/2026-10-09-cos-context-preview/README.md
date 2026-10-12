# Gemeinsame CoS-Vorschau mit aktueller Aufgabenbindung

Code **9544bc491c42ef2417870df362c738204166310a**, Version **1.0.6-preview.9544bc4**. Dieses neue Paket ergänzt die [vorherige gemeinsame Vorschau](../2026-10-09-cos-reviewed-preview/README.md) um [PR #47](https://github.com/Icarus-health/kingfisher-app/pull/47): Aufgabenprüfung bleibt an Quellengeneration und Metadaten gebunden. Kontakte/Beteiligung zu korrigieren darf weder alte Vorschläge wieder gültig machen noch eine erneute Prüfung nach früherem leerem Ergebnis verhindern. Alte Vorschläge mit ungültigem Quellenkopf, Anhang-Eltern- oder Berichtigungsbezug werden ebenfalls abgelehnt. Bestätigte Aufgaben und Originaltexte bleiben erhalten.

## Frische gemeinsame Nachweise

- Sauberes Gitarchiv des festgehaltenen Codes; **326 betroffene Backendtests bestanden**. Kein Backend-Gesamtlauf behauptet.
- TypeScript/Vite frisch gebaut, Grafikprüfung bestanden (16 Dateien, 16 Icons). UI und native Quellen sind gegenüber `311041f` bytegleich; **515 UI-Tests und 34 native Tests mit einem Plattformskip sind frühere Nachweise**, in dieser Runde nicht wiederholt. Bestehende Bündelgrößen-, Starlette/httpx- und hdiutil-Hinweise erhalten.
- ARM64-App/DMG frisch gebaut; strenge tiefe Ad-hoc-Signatur und DMG-Integrität geprüft. Nicht notarisiert, Intel nicht geprüft. Nur beim neu kopierten Vorschau-App-Bündel wurden Finder-/Resource-Metadaten entfernt; strenge Signatur und Programm-/DMG-/Archiv-Prüfsummen danach auch in der dauerhaften Ablage bestätigt.
- Tatsächliches Backend-/UI-Abbild aus vorhandener Basis ohne Pull oder Netzwerk gebaut: unveränderte Basisschichten, 268 Python- und 112 UI-Dateien gegen SHA-256-Manifest im laufenden Prüfprozess verglichen. Freigegebene Designquellen ebenfalls gegen ihr Manifest geprüft.
- Isolierter Paketablauf: kein Netzwerk, keine Ports/Hostmounts, schreibgeschützt mit leeren tmpfs. Bestehende Gesundheits-, künstliche Kalender-, RAM-, Quellenübersicht- und Mailaufgaben-Wiederholungsabläufe bestehen. Zusätzlich: Kontaktentzug verbirgt alten Aufgabenvorschlag, Übernahme liefert 409; Wiedereintragen allein reaktiviert ihn nicht; neue Prüfung erzeugt neue Bindung; ausdrücklich übernommene Aufgabe überlebt spätere Kontaktkorrektur. Ausschließlich künstliche Quellen und feste künstliche Prüfurteile, **keine echte Modellqualitätsprüfung**.
- Das [unabhängige enge Review und die Red-/Mutationsnachweise](../2026-10-09-task-source-context/README.md) der Aufgabenbindung bleiben getrennt erhalten. Kein neuer Integrationsreview oder Volltest behauptet; die Zusammenführung brachte keine Auflösung eines Laufzeitkonflikts mit sich.

## Grenzen und Übergabe

Dauerhafte Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-cos-context-9544bc4/`. Ältere Pakete bleiben erhalten. Abbild `sha256:92a841b76c80b4154751fb30f69b72c54f4c67a8e74db0b566689293b2dc01c2`; kompatibler **lokaler**, nicht veröffentlichter Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.9544bc4`.

Produktive App und persönlicher Import bleiben unverändert/pausiert. Kein Fenster, Mikrofon, EventKit, persönliche Mail-/Kalendertexte, Ollama oder Cloudmodell benutzt. Nutzerantwort: **Fenstertest später**. Native Darstellung, tatsächliche Kalender, persönliche Quellen-/Erkennungsqualität und RAM/Akku bleiben offen. Eine korrigierte alte Quelle hinter dem persistenten Scan-Cursor wird spätestens im nächsten Scan erneut betrachtet; kein sofortiger vollständiger Neuaufbau behauptet. Gültige alte ungebundene Vorschläge bleiben manuell prüfbedürftig; neue passende Prüfung ersetzt sie atomar. Kein perfektes Gedächtnis oder fertiger CoS behauptet.

`freeze.json`, `package-inputs.json`, `package-verification.json`, `verification.json`, `Dockerfile` und `probe-stdin.py` dokumentieren den festen Stand. Die Rohlogs sind verlustfrei komprimiert. Reproduktion mit lokal vorhandenem Abbild, ohne Modelle/Datenfreigabe:

```sh
docker run --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e ICARUS_DATA_DIR=/data --entrypoint python -i \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.9544bc4 - < probe-stdin.py
```

Keine CI-Wiederholung, Abonnements oder Check-ins. Diese Lieferung aktualisiert den bestehenden gemeinsamen Draft #46; die engere Korrektur steht zusätzlich in #47 zur getrennten Prüfung.
