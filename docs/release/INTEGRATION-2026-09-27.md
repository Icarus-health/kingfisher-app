# Integrationsprüfung Kingfisher, 27. September 2026

## Umfang und Entscheidung

Alle 39 offenen PRs #71–#109 wurden anhand ihrer Beschreibungen,
Diskussionen, Abhängigkeiten und des resultierenden Codes geprüft.
Ausgangspunkt auf `main`: `985f6ec87e2b3f805f09aa92d44491404571a182`.
Code-Endstand: #109, `035371261f2ec00a403bfa29b46192c2d661eba8`.
Separate Dokumentation: #103, `fd43c13ce41ccef17dd12f22187934cadf809604`.

#102 enthält bereits sämtliche Änderungen aus #71–#101. Danach baut die
Kette #104 → #105 → #106 → #107 → #108 → #109 jeweils auf dem Vorgänger auf.
#103 zweigt von #102 ab und muss zusätzlich übernommen werden. Ein gemeinsamer
Integrationscommit mit beiden Endständen als Eltern bewahrt diese Abstammung
und ergänzt die Review-Korrekturen, bevor der Stand auf `main` gelangt.

Der Aufbau ist für das Ziel eines proaktiven Stabschefs sinnvoll: Quellen
bleiben die Grundlage, abgeleitete Ansichten sind keine zweite Wahrheit,
Korrektur und Entzug bleiben möglich. Projektmappen und Terminvorbereitung
nutzen dieses Fundament. Modellqualität und Alltagstauglichkeit auf dem Mac
sind damit noch nicht bewiesen.

## Korrekturen aus der Gegenprüfung

- Nachbereitungen unterschiedlicher Termine werden auch bei gleichem Titel,
  Beginn und Notiz getrennt gespeichert. Wiederholtes Senden bleibt
  idempotent; zusätzliche Notizen bleiben eigene Quellen.
- Gespeicherte semantische Antworten prüfen auch die Aktualität des
  durchsuchbaren Quellenbestands. Ein geänderter Bestand fordert vorsichtig
  zur Neuberechnung auf, ohne beim Anzeigen ein Modell aufzurufen.
- Kalender-Suchcache und laufende Abrufe müssen Quellenentzug und Wechsel
  respektieren. Die Gegenprüfung umfasst die echte lokale Kalenderauswahl.
- Berichtigungen werden als vollständige Änderung mit dem gesamten neuen
  Kontext geführt. Alte Absatz-Einordnungen werden nicht übernommen: Auch
  ein unveränderter Satz kann durch Text an anderer Stelle widerrufen werden.
  Das nimmt die automatische Teilübernahme aus #73 bewusst zurück; Original,
  neue Fassung und Verlauf bleiben erhalten.
- Modellfreie Projektmappen bleiben im Gespräch zugänglich. Allgemeine
  Modellfragen erklären weiterhin, wenn kein Modell verbunden ist.
- Eine verspätete Projektzuordnung überschreibt keine manuelle Auswahl.
  Während des Speicherns sind Änderungen an der Nachbereitung gesperrt;
  verspätete Dateileser setzen keine alten Inhalte wieder ein.
- Kalender-Umschalter sind im dunklen Farbschema lesbar. Der Zeitraumkopf
  darf bei wenig Platz umbrechen. Dies ist keine vollständige mobile
  Neugestaltung der Desktop-Anwendung.
- Verarbeitungsfortschritt unterscheidet fertig bearbeitet und vollständig
  eingeordnet. Das Einordnungsangebot gehört zum tatsächlich gespeicherten
  Modell, nicht zu einer noch ungespeicherten Auswahl.

## Nachweise

Verwendet wurden ausschließlich synthetische Prüfdaten.

- TypeScript/Vite-Produktionsbuild erfolgreich; Asset-Vertrag erfüllt
  (14 Dateien, 17 Icons); JavaScript-Syntaxprüfung erfolgreich.
- Echter Chromium-Browser mit lokalem Sidecar: ohne Modell eine Projektfrage
  stellen, Mehrdeutigkeit per Klick klären und die Mappe mit Originalquellen
  anzeigen. Auch „Erzähl mir was zu Mainz“ wurde geprüft.
- Verzögerte Zuordnungsantwort nach manueller Projektwahl: Auswahl erhalten.
  Verzögerter Speicheraufruf: Text, Projekt und Datei gesperrt; anschließende
  Speicherung bestätigt.
- Kalender bei 1440 Pixeln dunkel und 1280 Pixeln hell/dunkel geprüft, keine
  Browserfehler. Die Listenseite passt bei 1280 Pixeln ohne horizontalen
  Überlauf. Bei 390 Pixeln greift die bestehende Mindestbreite von 1280:
  Smartphone-Nutzung ist noch keine unterstützte Ansicht.
- Vollständiger Abschlusslauf auf sauberem Stand mit Python 3.12.14:
  **2399 Sidecar-Tests bestanden** (361,93 Sekunden; zwei bestehende
  Deprecation-Warnungen), **235 Diagnostiktests bestanden** (9,16 Sekunden).
  `scripts/ci_lokal.sh sidecar app` beendete sich mit Status 0; Schema und
  Frontend-Syntax bestanden. Die Python-Abhängigkeiten einschließlich der
  für diese Proxy-Umgebung benötigten `socksio`-Bibliothek waren vorhanden.
- Die abschließende Browserprobe prüfte zusätzlich die vollständige
  Berichtigungsvorschau und erfolgreiches Speichern gegen den echten lokalen
  Sidecar (HTTP 201). Keine Browserfehler.
- Rust/Tauri nicht ausgeführt, weil `cargo` in dieser Umgebung fehlt.
  Mac-Berechtigungen und echte Modelle bleiben für die Abnahme offen.

## Morgen auf dem Mac

Den [Testplan](TESTPLAN-MAC.md) am aktualisierten `main` ausführen. Priorität:
Sicherung/Rückweg, echtes Modell, Quellenkorrektur und -entzug, Projektfragen,
Terminidentität und Zuordnungen, danach Oberflächenbedienung. Native
Berechtigungen, Keychain, Apple-Kalender, Rust/Tauri und tatsächliche
Modellgeschwindigkeit benötigen den Mac. Die optionale Bedeutungssuche bleibt
bis zum belegten Qualitätsgewinn ausgeschaltet.

## Nächste Entwicklung

1. **Gedächtnis messen und nachbessern.** Trefferqualität bei direkten und
   umschriebenen Fragen, Widersprüche, zeitliche Gültigkeit und Aufwand je
   Quelle mit dem echten Modell messen. Große Bestände gesondert prüfen;
   sichtbare Suchgrenzen sind ehrlicher, ersetzen aber keine vollständige
   Suche. Die konservative Entwertung semantischer Antworten kann zusätzliche
   Aktualisierungen auslösen; bei Bedarf genauer versionieren, ohne den
   Quellenentzug zu schwächen.
2. **Einrichtung und Tagesablauf vereinfachen.** Nach den Mac-Ergebnissen
   Modell, Mail, Kalender und erste Einordnung in einen überspringbaren Ablauf
   führen. Ein erstes belegtes Briefing ist das Ziel. Vorbereitungen und
   Erinnerungen müssen Herkunft und Unsicherheit zeigen und sich abstellen
   lassen. Rückfragen bündeln und nur bei relevanter Mehrdeutigkeit,
   persönlicher Festlegung oder außenwirksamer Aktion verlangen.
3. **Konnektoren als zweite Runde.** Bereits vorhanden: Mailaufnahme und
   Antwortentwürfe, lokale/abonnierte Kalender, Dokumente und Transkripte,
   ausdrücklich eingerichtete Webquellen sowie MCP. Zuerst diese Wege mit
   echten Daten abnehmen. Für WhatsApp und LinkedIn anschließend aktuelle
   offizielle Zugriffs- und Exportmöglichkeiten prüfen; eine laufende
   Synchronisierung privater Nachrichten ist hier weder implementiert noch
   zugesagt. Ein lokal überprüfbarer Exportimport wäre ein begrenzter erster
   Versuch, wenn die Datenformate und Nutzerfreigaben passen.

Für jeden neuen Kanal gelten dieselben Anforderungen: stabile Quellkennung,
Quellenzeit und Aufnahmezeit, Dublettenschutz, ursprünglicher Text mit Beleg,
saubere Personen-/Projektzuordnung, sichtbarer Umfang, Korrektur und Entzug.
Aus einer importierten Aussage darf ohne passende Bestätigung keine
persönliche Festlegung oder versendete Nachricht werden. Proaktivität entsteht
auf diesem Fundament; sie darf keine unsicheren Vermutungen festschreiben.
