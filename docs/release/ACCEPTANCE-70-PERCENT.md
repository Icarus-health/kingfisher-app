# Abnahme 70 Prozent: lokale Rollen, Lernen und öffentliche Quellen

Stand: 8. September 2026. 14/20 gleich gewichtete Abnahmepunkte; keine Zeit-
oder Qualitätsprognose. Die bestehenden Kriterien 13 und 14 werden geschlossen.
Die visuelle Neugestaltung und die vollständige Referenzabnahme bleiben offen.

## 13: Modellrouting und begrenzte Rollen

Die vorhandene Agentenlaufzeit bekommt begrenzte Rollen über dieselben Stores,
Werkzeuge, Regeln, Freigaben und dasselbe Audit. Ein mit „Recherchiere“ oder
„Research“ beginnender Auftrag erhält eine Lesewerkzeug-Auswahl und keinen
bisherigen Gesprächsverlauf. Andere Aufträge bleiben beim Chief of Staff mit
dessen bestehendem Freigabeverfahren. Es entstehen keine getrennten Gedächtnisse.

Die optionale lokale Modellauswahl prüft bis zu drei installierte Ollama-Modelle
am bereits eingerichteten Endpunkt mit einem neutralen Werkzeugaufruf. Kein
Download, kein persönlicher Kontext und keine echte Aktion sind Teil der Prüfung.
Geprüfte Profile gelten 14 Tage und nur am passenden Endpunkt. Auswahl: benötigte
Fähigkeiten, lokaler Betrieb, dann kleinere Modelldatei und gemessene Prüfzeit.
Das ist keine allgemeine Modellqualitätsbewertung und kein Geldkostenvergleich.
Bei Anbieterfehlern werden höchstens drei zugelassene lokale Kandidaten versucht;
ein Cloud-Ausweichen ist ausgeschlossen. Auswahl, Fehlversuche und Ergebnis
bleiben in der Gesprächsmetadatenansicht und im Audit nachvollziehbar.

Nachweise:
- Qwen 3.5 4B und Qwen 2.5 14B bestanden die echte neutrale Werkzeugprüfung.
  Granite 3.2 Vision 2B bestand sie nicht und blieb ausgeschlossen.
- Echte Ollama-Recherche mit `aktuelle_zeit`: Qwen 3.5 4B wurde ausgewählt,
  nutzte das Werkzeug und antwortete mit dessen Datum/Uhrzeit. Im neu gebauten
  Docker-Container wiederholt, einschließlich neuer Werkzeugantwort nach Neustart.
- Test mit unerlaubtem Schreibwerkzeug im Rechercheauftrag: kein Schreibzugriff.
- Gerouteter Chief-of-Staff-Mailauftrag bleibt bis zur Freigabe wartend;
  kontrolliertes Testwerkzeug wird erst danach genau einmal ausgeführt.
- Tests für fehlende/stale/ungültige Profile, geänderte Einrichtung während der
  Prüfung, lokale Ersatzmodelle, geschützte Schnittstellen und Metadaten-Persistenz.
- [Docker-Gespräch mit Auswahlbegründung](evidence-70/routing.png).

## 14: Ziele, Gewohnheiten, belegte Beobachtungen und Außenwelt

Bestehende Ziele bleiben führend. Gewohnheiten sind ausdrücklich erfasste,
sensible Zielangaben im selben Store; getrennte IDs verhindern das Vermischen
gleichnamiger Gewohnheiten. Ein Check-in gilt genau einem Tag (UTC). Wochenzahlen
zählen belegte Tage, nie vermutetes Verhalten oder fehlende Tage als Misserfolg.
Check-ins lassen sich zurücknehmen; ihre Quellen bleiben nachvollziehbar.

Ab drei belegten Tagen innerhalb von 30 Tagen entstehen prüfbare Beobachtungen
mit Originalstellen und Digests. Sie werden erst durch ausdrückliche Bestätigung
zu Wissen. Verwerfen, Widerruf und Quellenentzug bleiben erhalten. Entzogene
Belege machen abhängiges Wissen fraglich; die Oberfläche kennzeichnet das sofort.
Die regelbasierte Prüfung läuft auf Zuruf oder im eingeschalteten bestehenden
Zeitplan, ohne Modellkosten und ohne automatische Bestätigung.

Öffentliche HTTPS-Quellen werden einzeln mit Themen vom Nutzer ausgewählt.
Manueller Abruf ist sofort möglich; wiederholte Abrufe verwenden den bestehenden
opt-in Zeitplan, solange die App läuft. Es gibt keine voreingestellten Nachrichten-
Abonnements. Gespeichert werden begrenzter Text, Herkunft und Abrufzeit. Nach
24 Stunden oder Abruffehlern ist der Stand sichtbar veraltet. Abrufzeit ist kein
Veröffentlichungsdatum und keine Wahrheitsbestätigung. Quellentext bleibt fremder
Inhalt. Gemeinsame explizite Themen ordnen Quellen bestehenden Zielen zu; sie
erscheinen dann im Tagesüberblick. Das ist eine Themenzuordnung, keine behauptete
persönliche Relevanz, Faktenprüfung oder vollständige Nachrichtenzusammenfassung.

Nachweise:
- Browser: Gewohnheit erstellen, drei datierte Check-ins, Belege öffnen,
  Beobachtung bestätigen, einen Check-in zurücknehmen: Wissen sofort fraglich.
  Derselbe Zustand bleibt nach Neuladen und Containerneustart erhalten.
- Reale öffentliche Quelle `https://www.w3.org/news/` im Browser registriert,
  abgerufen und geöffnet; Abrufzeit und Originalherkunft sichtbar. Ziel mit
  explizitem Thema „Web“ erzeugt die passende Tagesübersicht. Erneuter Abruf
  erzeugt keine zweite Fassung bei gleichem Inhalt. Deaktivierung entfernt die
  Quelle aus der Tagesübersicht und schließt den Beleg aus.
- Reale SQLite-Stores im kontrollierten Test: v1 bestätigen, gleiche Fassung
  erneut abrufen, Änderung zu v2: alter Beleg ausgeschlossen und Aussage fraglich.
- Tests: Quelle während Abruf deaktiviert; ältere Abfrage darf neue Fassung
  nicht überschreiben; Quellenfehler blockiert regelbasiertes Lernen nicht;
  Restore wechselt die verwendeten Stores; große fremde Archive blockieren
  die wenigen ausdrücklichen Check-ins nicht.
- Weiterleitungsziele werden vor Abruf geprüft, einschließlich des bestehenden
  Recherche-Webwerkzeugs. 512 KiB Abrufgrenze und 12.000 Zeichen gespeicherter
  Auszug; Begrenzung wird angezeigt. Kein Backdoor-freier oder vollständiger
  Security-Audit behauptet.
- [Korrektur im Docker-Browser](evidence-70/habits-correction.png),
  [Quelle im Tagesüberblick](evidence-70/world-radar.png) (der Name im Gruß wurde
  vor der Veröffentlichung nachträglich durch einen erfundenen ersetzt).

## Gemeinsame Prüfung und Auslieferung

- Vollständige lokale Python-3.12-Suite: 1.095 bestanden, 2 übersprungen;
  danach ergänzte Store-Wechsel-/Quellen-Lifecycle-Tests separat bestanden.
- UI-Typecheck/Build und Assetmanifest (14 Dateien, 17 Icons) bestanden.
- Echter Docker-Build `kingfisher:seventy-percent`, isolierte Abnahme auf Port
  8896 mit ausschließlich synthetischen persönlichen Daten und öffentlicher
  W3C-Quelle; neuer echter lokaler Modellaufruf nach `docker restart` bestanden.
- Browserkonsole des Docker-Ablaufs: keine Fehler oder Warnungen.
- Auf Port 8891 ausgeliefert. Vorherigen Container und Datenvolumen-Snapshot
  behalten; 181 kopierte Dateien byteweise per SHA-256 geprüft. Vorhandene
  Konten, Schlüssel, Modellkonfiguration und Daten bleiben erhalten. Die
  Testgewohnheit, das Testziel und die W3C-Testquelle wurden nicht in den
  persönlichen Bestand übertragen; neue Funktionen bleiben opt-in.

Die sechs offenen Punkte bleiben 07, 09, 15, 16, 17, 20. Insbesondere automatische
MacWhisper-Dateiaufnahme, Computer-/Browsersteuerung, natürliche Sprachausgabe,
vollständiger UI-Umbau und echter Alltagstest sind damit nicht abgeschlossen.
