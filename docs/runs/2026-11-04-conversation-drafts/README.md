# Lokale Gesprächsentwürfe

## Problem und Änderung

Die bisherige Map/sessionStorage-Ablage hielt ungesendete Texte nur während
einer Browsersitzung. Der erste Composer hatte zudem noch keine Conversation-ID;
sein während einer Antwort neu geschriebener Text konnte beim Wechsel verloren
gehen.

Entwürfe liegen jetzt versioniert in `conversations.sqlite3`. Die Migrationen
v2/v3 erhalten die vorhandenen Nachrichten. Ein atomarer Übergang bindet den
Starttext an genau ein Gespräch. Der separat gespeicherte Sendeversuch wird
nicht nach einem unklaren Ausgang erneut ausgeführt. Nach bestätigter Annahme
wird dessen zusätzliche Textkopie entfernt; Folgetext bleibt erhalten.

Die UI sichert nach kurzer Schreibpause und vor dem Senden. Parallele Fassungen
werden sichtbar zur Auswahl gestellt. Schreibaufträge und entwurfsgebundene
Nachrichten tragen die zuvor gelesene Server-Startkennung; eine alte Seite kann
nach einem Instanzwechsel keine neuen Schreibaufträge einschleusen. Ein Neustart
löscht keinen bereits gespeicherten Entwurf.

Die Mac-Hülle fragt vor Schließen, Beenden und Neuladen nach dem Speicherstand,
mit höchstens drei Sekunden Wartezeit. Fehlender Nachweis führt zur Warnung.
Beim Abbruch wird die Eingabe wieder freigegeben. Reload-Fehler sind an die
konkrete Navigation gebunden, damit alte Rückmeldungen keine neue Sperre lösen.

## Nachweise

- 42 Store-/API-Tests für Migration, zwei konkurrierende Schreiber, exakte
  Wiederholung, Tombstones, Instanzwechsel, Bindung/Claim, Rollback und Backup.
- 191 angrenzende Backendtests bestanden; nach letzter Textbereinigung die 42
  betroffenen Draft-/Handofftests erneut bestanden.
- Tatsächliche `create_app`-Registrierung und neuer App-Start über denselben
  künstlichen Bestand geprüft. Alte Message-Nonce wurde zunächst reproduzierbar
  bis zum Modell-Lock durchgelassen; nach Korrektur 409 davor. Zusammen mit
  vorhandenen ConversationActions vier Tests bestanden.
- Native Bool-/Timeoutprobe bestanden. 36 weitere native Tests bestanden, einer
  übersprungen. Ein bestehender Swift-Test scheiterte zunächst am im Sandboxlauf
  nicht schreibbaren Standardcache; mit explizitem temporärem Cache bestanden.
- Haupt-App und alte Fensterhülle typgeprüft. Normaler ARM-DMG-Bau und strikte
  Signaturprüfung bestanden. Testpaket mit bestehender Versionsmarke 1.0.44,
  keine neue Veröffentlichung/Installation. SHA-256:
  `6e0dc01eefb406825f051ef16fdf9baffcbf8d84f56c705cedc3675a5a3dc179`.
- Unabhängiges Backendreview ohne bestätigten Befund. Unabhängiges natives
  Review fand den eingefrorenen Composer nach Reload-Fehler; behoben und erneut
  typgeprüft.
- Vollständiger UI-Lauf: **1.107/1.107 bestanden**. Produktionsbuild bestanden;
  die bestehende Warnung zur Bundlegröße bleibt. Der erste Gesamtlauf hatte
  1.104/1.105 bestanden: drei feste Farbrückfälle verletzten den vorhandenen
  Farbrollenvertrag. Auf bestehende Rollen und Schriftgrößen korrigiert.
- Der unabhängige Frontendreview fand zwei wichtige Fehler: Ein alter
  abgeschlossener Übergang konnte den Status einer späteren Nachricht löschen
  oder ihre Anzeige mit einem verspäteten Abruf ersetzen; eine laufende
  Spracheingabe konnte beim Verlassen unbemerkt verworfen werden. Beide wurden
  reproduziert und korrigiert. Vier unabhängige Gegenproben sowie 67 gezielte
  Tests einschließlich Sprachsteuerung bestanden danach.

Gezielte Wiederholung ohne Modelle:

```sh
python -m pytest sidecar/tests/test_conversation_drafts.py sidecar/tests/test_conversation_draft_server.py -q
python -m pytest macos/test_draft_leave.py macos/test_recovery_native_ui.py -q
cd app/kingfisher
npm test
npm run build
```

Der vorherige veröffentlichte PR-Stand `d9e710e` bestand inzwischen sämtliche
GitHub-Prüfungen (Mac-App, Container, UI, Python 3.10/3.12). Das ist getrennte
Evidenz und kein CI-Nachweis für die hier ergänzte Entwurfssicherung.

## Grenzen

Nur künstliche Daten; keine Cloud-/Ollamaaufrufe, kein fortgesetzter Mailimport.
Ein Prozessabsturz vor Speicherbestätigung ist nicht verlustfrei garantiert.
Der normale Nachrichten-POST ist weiterhin nicht idempotent; bei unklarem
Ausgang wird der Verlauf zur Prüfung geöffnet, nicht automatisch neu gesendet.
Entwürfe sind keine Gedächtnisaussagen, Suchtreffer oder Modellhistorie.

Das native Testfenster wurde nicht gestartet: Die dafür gesondert angefragte
Freigabe ist weiterhin offen. Logiktests und Paketbau ersetzen weder dessen
Bedienprüfung noch ein persönliches Update oder eine Alltagsabnahme.
