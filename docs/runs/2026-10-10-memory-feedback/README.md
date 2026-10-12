# Korrekturen direkt im Gedächtnis

Basis: `6dade820f667e03cd2461176981bffa2afbc0d49` der gemeinsamen Vorschau.
Produktzweig: `feat/memory-feedback-20261010`. Nicht auf dem persönlichen Mac
installiert. Diese Lieferung ergänzt einen bestehenden Ablauf, keine neue
Gedächtnisarchitektur.

## Nutzerablauf

Unter Gedächtnis → Bereiche steht an jeder Quelle **Zuordnung ändern**. Erst
beim Öffnen lädt der Editor die aktuelle Zuordnung und die verfügbaren Bereiche.
Mehrere Bereiche sind wählbar; eine leere Auswahl entfernt nur die Themenhinweise.
Erst **Zuordnung speichern** schreibt. Ein Abbruch verwirft den Entwurf.

Eigene Zuordnung bleibt beim Neustart und bei automatischer Wiederprüfung
erhalten. Originaltext, Fakten und Identitäten werden durch diesen Editor nicht
geändert. Die aktuelle Bereichsseite wird nach Erfolg neu geladen, ohne auf
Seite eins zu springen. Die Quelle kann aus dem bisherigen Bereich verschwinden;
eine Statusmeldung erklärt den Wechsel und den Originalerhalt.

Das ist dauerhaftes Feedback für die konkrete Quelle. Kein Fine-Tuning,
automatischer Lerntransfer auf andere Quellen, allgemeines Sprachverständnis
für Korrekturen oder stilles Umklassifizieren des ganzen Bestands wird behauptet.

## Schutz beim Speichern

Die aktuelle Kategorieantwort enthält zusätzlich `revision`: einen Hash über
Originalfingerabdruck, Taxonomieversion und bisherige eigene Korrektur. Der neue
Editor sendet ihn als `expected_revision`; Quelle, Taxonomie und Korrektur werden
innerhalb der bestehenden Store-Transaktion erneut geprüft. Überholtes Feedback
ergibt 409 statt Überschreiben. Geschlossene oder ausgeschlossene Quellen liefern
keinen nutzbaren Revisionstoken. Fehlerhafte Tokens werden mit 422 abgewiesen.

Der bisherige Quellendetail-Editor nutzt ebenfalls den geprüften Token. Seine
regelmäßige Anzeigeaktualisierung darf diesen beim Bearbeiten nicht ersetzen.
Ein konkreter Komponententest fing genau diesen Fehler vor der finalen Fassung.
Eine erfolgreiche API-Antwort meldet die Änderung im aktuellen Fenster ohne
Quelleninhalt oder Kennung. Auch wenn der Editor inzwischen verlassen wurde,
lädt die aktive Bereichsansicht ihre aktuelle Seite erneut. Ein fehlgeschlagener
PUT löst diese Meldung nicht aus. Keine fensterübergreifende Synchronisation wird
damit behauptet. Die neue Bereichsaktion lädt weder im eingeklappten Zustand noch durch einen
eigenen Hintergrundtimer. Der alte API-Vertrag bleibt für ältere Clients ohne
Token kompatibel; solche Clients besitzen deshalb nicht den neuen Schutz vor
gleichzeitigen Änderungen. Die aktuelle Oberfläche sendet immer den Token und
verweigert das Bearbeiten bei einem älteren Dienst ohne Token.

Keine Schemaänderung, neue Modellrolle, Anbieteraktivierung, externe Aktion oder
zusätzliche Bibliothek. Kein Import wird gestartet und keine Systemfreigabe
verändert. Bereichskorrekturen bestätigen keine extrahierten Fakten.

## Nachweise

- Vor Umsetzung: neun neue Backendfälle fehlgeschlagen, eine Kompatibilitätskontrolle
  bestanden. Nach Umsetzung: elf neue Fälle bestanden, einschließlich echter
  Datenbank-Schließung/Wiederöffnung, konkurrierender eigener Korrektur,
  Quellen-/Taxonomieänderung, Entzug, leerer Auswahl und ungültiger Tokens.
- **99 betroffene Backendfälle bestanden**, eine vorhandene Starlette/httpx-Warnung.
  Kein vollständiger Backend-Gesamtlauf in dieser Lieferung.
- Neun neue tatsächliche Komponenten-/Transportprüfungen bestanden: explizites
  Speichern, keine Ladearbeit im geschlossenen Zustand, kein Schreiben beim
  Ankreuzen/Abbrechen, Konflikt mit erhaltenem Entwurf, nicht verfügbarer/alter
  Dienst, späte Leseantwort, Fehler und Wiederholen, geprüfter Token trotz Polling.
  Vor dem neuen Editor scheiterten sechs Fälle an der fehlenden Aktion; der
  spätere Polling-Gegenfall scheiterte separat mit dem falschen Revisionstoken.
  Der unabhängige Reviewer fand eine veraltete Anzeige bei Bereichswechsel vor
  Abschluss des Schreibens; als weiterer echter Handler-/Transportfehler
  reproduziert und korrigiert. Seine Nachprüfung bestätigt keinen Blocker im
  engen Diff, ohne eine eigene Test- oder native Bedienprüfung zu behaupten.
- **524 UI-Tests bestanden**, Typprüfung und Produktionsbuild bestanden.
  Vorhandene Node-MockTimers-Hinweise; Build meldet einen großen JS-Chunk und
  Plugin-Zeitanteile. Diese Ergebnisse sind keine native Fenstertestung.
- Grafik-/Assetvertrag: bestanden, 16 Dateien und 16 Icons. Keine neuen Grafiken.

Die fertige Funktion ist Code mit gebauter Weboberfläche. Ein neues gekoppeltes
ARM-App/Backend-Paket und die tatsächliche Bedienung sind noch offen; das ältere
DMG enthält diese Ergänzung nicht. Die unabhängige Prüfung ersetzt diese Nachweise
nicht.

Kommandos vom Repository aus:

```sh
/private/tmp/kingfisher-review-20261006-venv/bin/python -m pytest \
  sidecar/tests/test_category_feedback.py sidecar/tests/test_memory_categories.py \
  sidecar/tests/test_memory_areas.py sidecar/tests/test_local_category_quotes.py \
  sidecar/tests/test_category_diagnostics.py sidecar/tests/test_mail_intake_routes.py -q
/private/tmp/kingfisher-review-20261006-venv/bin/python scripts/check_asset_manifest.py
cd app/kingfisher
npm test
npm run build
```

## Nächster Produktweg

Keine weitere allgemeine Architekturüberarbeitung als Voraussetzung für jeden
Usability-Schritt. Sicherheitsrelevante Fehler in Person, Frist, Bedingung und
Quellenentzug bleiben Freigabeblocker des jeweiligen Ablaufs. Ungeprüfte Themen
bleiben sichtbar korrigierbar; nicht jeder neue Randfall blockiert alle Bereiche.

1. Persönliche Sicherung prüfen, gekoppelte neue Vorschau vorbereiten und die
   Kalender-/Gedächtnis-Kette auf dem Mac abnehmen. Aktuell installiert ist die
   ältere `1.0.6-local.3403623`; diese Funktion ist dort noch nicht vorhanden.
2. Bestehende Projekte und Aufgaben als kompakte Arbeitsübersicht darstellen:
   nächste Schritte, offene/erledigte Aufgaben, Zuständigkeit, Fristen und
   wartende Punkte aus vorhandenen Daten. Keine erfundenen Termine oder zweite
   Aufgabenverwaltung. Klassische PMO-Ansichten dienen als Vorbild, nicht als
   Anlass für ein großes neues Projektsystem.
3. Bestehende Health-Messwerte nach Messgröße und Zeit darstellen; Belege,
   Einheiten und Korrekturen erhalten. Keine automatische medizinische Bewertung.
4. Bestehenden Dateiimport und lokalen Diktatentwurf im Gespräch leichter
   erreichbar machen. Explizites Prüfen/Speichern beziehungsweise Senden behalten.

Der günstige Bestandsaufnahme-Agent bestätigte dafür vorhandene Health-,
Aufgaben-/Projekt-, Dateiimport- und Diktatkomponenten. Er prüfte nur Code,
keine installierte App und keine persönlichen Daten.
