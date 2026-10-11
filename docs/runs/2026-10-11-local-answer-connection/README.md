# Lokale Antwort-KI einfacher verbinden, 11.10.2026

„Speichern und verbinden“ setzt jetzt ausdrücklich die lokale Antwortrolle, einschließlich `local_only`, bevor es den Standard speichert. Eine ältere Antwort-Sonderwahl kann dadurch nicht weiter Vorrang haben. Der tatsächliche Agent erhält beim Neubau dasselbe Ollama-Inventar wie die Rollenanzeige. Nicht lokal belegte Auswahl und widersprüchliche Cloudwahl werden nicht als einsatzbereit gemeldet. Quellenverarbeitung braucht weiterhin einen eigenen Klick; bestehende andere Rollen bleiben unverändert.

Die native App bietet für installiertes, gestopptes `/Applications/Ollama.app` einen bewussten Knopf „Ollama starten“. Der vorhandene HintBar-Handler öffnet diesen festen Dateipfad erst beim Klick. Kein automatischer Start, Download oder neuer WebView-Brückenbefehl. Läuft Ollama, fehlt der Hinweis; fehlt die App, bleibt der vorhandene Downloadlink.

## Nachweise

- Vier neue echte API-Regressionstests: drei scheiterten am ursprünglichen Produktcode, nach der Korrektur vier bestanden. Fake-Inventar vor App-Aufbau injiziert; ursprüngliche Lücke der Testisolation auf unabhängigen Reviewhinweis behoben. Keine echte Modellinferenz.
- 118 betroffene Backendtests bestanden: Modellrollen, Cloudzugänge/Einwilligungen, Ollama-Cloud, Inventar, lokale KI, Routing-Laufzeit und die vier Regressionen. Danach wurden nur Testisolation und frontendseitige Statusanzeige geändert; die vier isolierten Tests erneut bestanden. Kein neuer vollständiger Backendlauf.
- 19 UI-Logiktests bestanden, darunter sechs neue Fälle für Ablauf, Rollenabweisung, unbestätigte Lokalität, Startvorgaben, fehlgeschlagene Bereitschaft und fehlgeschlagenes Standardspeichern. Diese neuen Tests wurden zuerst ohne das noch nicht existierende Hilfsmodul ausgeführt; das ist kein Sabotagenachweis einer alten Funktion.
- Typprüfung und vollständiger Web-Build bestanden. Bekannte Bundlegrößenwarnung über 500 kB bleibt; kein Bundleoptimierungsnachweis.
- Reine Swift-App-Logik inklusive vier Zustände bestanden, mit expliziter Liste der versionierten Dateien plus neuer Datei und eigenem temporären Modulcache. Alle nativen App-Quellen für ARM64/macOS 11.3 typgeprüft. Der unveränderte pytest-Compilerwrapper scheiterte zuvor am gesperrten Standard-Modulcache; seine 26 übrigen Tests bestanden, ein Nicht-Mac-Fall ausgelassen. Der Wrapper-Gesamtlauf wird ausdrücklich nicht als grün ausgegeben. Unversionierte duplizierte Swift-Dateien nicht verändert.
- Unabhängige schreibfreie Prüfung des engen Native-/Backend-/Frontend-Diffs ohne bestätigten Produktblocker. Ein vermeintlich fehlender Downloadweg wurde am tatsächlichen Host verworfen: `Einstellungen/Seite.tsx` rendert `ModelRecommendation` mit Pull-Einrichtung unmittelbar oberhalb dieser Karte. Keine umfassende Sicherheits- oder Gedächtnisabnahme.

## Gerenderter Ablauf

Browser plugin not available; vorhandenes Playwright 1.62.1 verwendet. Echte React-Komponente und echte Produkt-API über ASGI TestClient plus getrennte Loopback-Brücke auf `127.0.0.1:18756/18757`; frischer künstlicher Datenordner, Fake-Ollama-Inventar und ausdrücklich simulierte Bereitschaftsantwort. Kein persönlicher Schlüsselbund, keine echten Modelle, Mails oder Kalender. Das ist kein nativer WKWebView- oder Modellqualitätsnachweis.

„Modell verwalten“ → Qwen9B wählen → „Speichern und verbinden“: Antwortrolle und Standard tatsächlich Qwen9B, `local_only:true`, `cloud:false`; frühere fehlende 12B-Rolle ersetzt, Hintergrundrolle weiterhin 4B. Genau drei schreibende Produktaufrufe: Rollenwahl, Standardwahl, Bereitschaftstest. Zeitplan weiter aus, kein Cloud-, Pull- oder Quellenstart. Simuliertes HTTP 200 mit `ok:false` entfernt „Zum Gespräch“/„Sortieren starten“ und nennt auch in der Kartenüberschrift die nicht bestätigte Verbindung.

| Prüfung | Ergebnis |
| --- | --- |
| URL/Titel und sinnvolle Anzeige | bestanden |
| Framework-Fehleroverlay | keines |
| Consolewarnungen/-fehler im finalen Browserlauf | keine |
| Interaktion und tatsächlicher API-Zustand | bestanden |
| Screenshot Desktop 1100×850 / Mobil 390×844 / Fehlerfall | gespeichert und Desktop/Mobil visuell gelesen; kein horizontaler Seitenüberlauf |

[Maschinenlesbares Ergebnis](ui-evidence.json), [SHA-256 der geprüften Quellen](source-hashes.json). Temporäre Treiber und Screenshots liegen unter `/private/tmp/kingfisher-local-connection-ui-20261011/`, außerhalb des Repositories. Zwei frühere Harnessversuche scheiterten vor Schreibaufrufen an einem zu strikten Feldlocator beziehungsweise der noch eingeklappten Karte; abschließender Lauf benutzt die tatsächliche Aufklappaktion. Testserver und Testbrowser anschließend beendet.

## Lieferung und Grenzen

Quelländerung für Draft #54 vorbereitet; noch kein neues gepaartes App-/Backend-Paket und keine persönliche Installation dieser Änderung. Der Mac wurde nach „Kalenderdialog bestätigt“ erneut gesperrt vorgefunden. Frühere lesende Kalenderbestätigung bleibt dokumentiert, neuer Fensternachweis fehlt. Persönliche Modellrollen, Kalender und pausierter großer Import in diesem Schritt unverändert; kein CI-Neustart, Registry-Upload oder neues Cloudguthaben verwendet.
