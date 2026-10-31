# Bewährte Abläufe neben dem Gedächtnis

Das Gedächtnis hält Originale, Fakten, Beziehungen und zeitliche Gültigkeit.
Ein Ablauf beschreibt dagegen, **wie** Kingfisher eine Aufgabe bearbeitet.
Eine Personenakte braucht deshalb keinen eigenen Skill. Aktuelle Fakten und
bestätigter Kontaktstil werden bei jeder Anwendung aus ihren bestehenden
Speichern gelesen, statt im Ablauf dupliziert zu werden.

## Einordnung und Finden

Die Bibliothek trennt drei Dinge:

| Merkmal | Bedeutung |
|---|---|
| Grundverfahren / bei Bedarf | Die zwei essenziellen Grundverfahren gelten immer. Weitere mitgelieferte und alle eigenen Skills werden passend zur Aufgabe geladen. Ein Lernvorschlag kann sich nicht selbst zum Grundverfahren machen. |
| Kategorie | Suchen & Prüfen, Kommunikation, Planung & Arbeit, Gedächtnispflege oder Sonstiges. Vorschläge bekommen eine Einordnung; ohne Angabe folgt die Vorgabe aus dem bestehenden Aufgabenbereich. |
| Anwendungskontext | Allgemeiner Ablauf oder bis zu vier ausdrücklich genannte Kontexte, etwa Zunft. Bei mehreren genügt einer. Kontexte sind keine Personen- oder Projektidentitäten. |

Suche und Kategoriefilter arbeiten auf den kleinen Metadaten. Der direkt aus
einem Gespräch angeforderte Vorschlag bleibt trotz Filter sichtbar. Die
optionale Einordnung lässt sich unter „Einordnung anpassen“ in einer neuen
Fassung ändern. Alte Fassungen erhalten nur eine abgeleitete Anzeige; ihre
gespeicherten Markdown-Dateien und Versionsbelege werden nicht umgeschrieben.

Die Kategorie ordnet die Bibliothek, aktiviert aber keinen Ablauf. Die Auswahl
verlangt weiterhin passenden Aufgabenbereich und einen positiven Auslöser in der
eigenen ersten Anfragezeile. Angegebene Kontexte müssen dort als zusammenhängende
Wortfolge stehen. Zitierte Abschnitte und verneinte Teilsätze sind keine positiven
Kontexte; bei Unsicherheit bleibt das persönliche Zusatzverfahren weg. Auch
„Zunftmail“ oder „Projektmails“ werden in einer ausdrücklichen Schreibbitte als
Mailaufgabe erkannt. Freie Paraphrasen versteht diese begrenzte Auswahl nicht
vollständig. Eine Verbesserung der Modellqualität oder Geschwindigkeit folgt
nicht allein aus der Kategorisierung.

Ein gemeinsamer Mailablauf kann bestätigten Kontaktstil und aktuelle Akten nutzen.
Für jede Person eine Kopie anzulegen würde Fakten und Arbeitsweise vermischen.
Besondere Abläufe sind erst sinnvoll, wenn das Vorgehen tatsächlich verschieden
und wiederverwendbar ist. Kategorien erlauben weder neue Werkzeuge noch eine
selbstständige Veränderung des Gedächtnisbestands.

## Benutzen

Im Gespräch ausdrücklich schreiben: „Lerne diesen Ablauf: …“. Anlass, Schritte
und ein Gegenbeispiel helfen. Das lokale Modell erstellt daraus einen
Vorschlag; es aktiviert nichts. „Ablauf prüfen“ führt direkt zur Prüfung in
Einstellungen → Kingfisher und du → Bewährte Abläufe und öffnet den betreffenden
Vorschlag direkt. Dort Schritte und Beispiele
ansehen, gegebenenfalls eine neue Fassung vorschlagen, dann „Geprüft übernehmen“.
Ein übernommener Ablauf wird bei einer passenden Anfrage automatisch ausgewählt.
„Zurücknehmen“ beendet seine Anwendung; der Verlauf bleibt nachvollziehbar.

Auch eine klare dauerhafte Ablaufkorrektur kann direkt einen Vorschlag erzeugen:
„Bei Zunftmails bitte künftig zuerst den Anlass prüfen, dann den Entwurf gegenlesen.“
Oder: „Merke dir für Zunftmails: zuerst Anlass prüfen, danach gegenlesen.“ Die
begrenzte Erkennung verlangt eine direkte Daueranweisung und zwei erkennbare
Arbeitsschritte. Reine Stilwünsche, Fragen, Zitate und einmalige Aufgaben lösen
keinen Lernaufruf aus. Für andere Formulierungen bleibt „Lerne diesen Ablauf: …“
verfügbar. Alle Fassungen bleiben bis zur Prüfung und Bestätigung inaktiv.

Die erste Fassung unterstützt gelernte Zusatzverfahren für Mailentwürfe,
Planung und Analysen. Feste Such-, Personen-, Quellen- und Antwortprüfungen
bleiben im vorhandenen Gedächtnispfad. Gelernter Freitext ersetzt sie nicht.
Persönliche Verfahren bleiben beim lokalen Modell; Cloudanfragen erhalten
sie nicht. Kontobezogene Schreibpräferenzen bleiben im vorhandenen Stilprofil.

## Hauptverteiler und Grundverfahren

`procedure_skills/*/SKILL.md` liefert fünf geprüfte Grundverfahren:

- `skill-router`: ausdrückliche Aufgabe erkennen, vorhandene passende Verfahren
  auswählen; bei Konkurrenz beim Grundverfahren bleiben.
- `source-safety`: Identität, Belege, Zeit, Zuständigkeit und Freigaben beachten.
- `memory-recall`: fester Belegpfad für Gedächtnisfragen.
- `mail-draft`: Konto, Empfänger, bestätigten Stil und Entwurfsgrenzen beachten.
- `task-planning`: Bedingung, Zuständigkeit, neue Frist und historische Anfrage trennen.

Die ersten beiden gelten allgemein, weitere nach Aufgabe. Der Hauptverteiler
ist begrenzter Code, kein zusätzliches Sprachmodell: er erkennt den bestehenden
Aufgabenbereich und ganze Auslöserwörter in der ersten Nutzerzeile. Er lädt nur
passende aktive Fassungen. Bei mehreren passenden Zusatzverfahren wird keines
willkürlich gewählt. Diese Auswahl versteht nicht jede freie Formulierung.

Neue Verfahren entstehen aus ausdrücklichen eigenen Lernbitten oder manuellen
Vorschlägen. Unbekannte Mailinhalte und ein einzelner vermeintlicher Modellerfolg
werden nicht automatisch zu dauerhaften Arbeitsanweisungen. Bei einer erkannten
Lernbitte wird zunächst auf Wiederverwendung geprüft. Das ist prozedurales
Gedächtnis, kein Training von Modellgewichten und kein unbegrenztes Selbstlernen.

Die Wiederverwendung berücksichtigt auch bereits offene passende Vorschläge.
Der kleine Metadatenkatalog nennt Status und Fassung, pro Name den jüngsten
noch gültigen Stand. Zurückgewiesene, zurückgenommene und überholte Vorschläge
werden nicht angeboten. Höchstens acht Einträge und 2.400 Bytes gelangen in
den Lernauftrag; ein offener Vorschlag wird dadurch nicht aktiviert.

## Prüfen, ändern und sichern

Ein Vorschlag nennt Zweck, Bereich, Auslöser, Schritte, Positiv- und
Gegenbeispiel. Automatisch geprüft werden Form, Größenbegrenzung und
Beispielauswahl. **Die fachliche Richtigkeit bestätigt der Nutzer.** Es gibt
keine Behauptung, dass ein bestandener Formtest ein Verfahren fehlerfrei macht.

Eigene Fassungen liegen kanonisch in `procedures.sqlite3`; der Export heißt
`SKILL.md`. Er enthält Markdown und JSON-Frontmatter (auch gültiges YAML).
Bearbeiten geschieht über „Neue Fassung“, damit alte Fassungen erhalten bleiben.
Eine neue Version ersetzt die bisherige erst nach Bestätigung. Ein veralteter
Bestätigungsknopf kann keine zwischenzeitliche Änderung überschreiben.

Aus einer Gesprächsquelle gelernte Verfahren tragen deren Fingerabdruck.
Änderung, Ersetzung oder Entzug sperren sie bei Auswahl und Bestätigung.
Verfahren werden vor der Modellausgabe und vor Freigaben erneut geprüft.
Ein Wechsel oder Widerruf setzt den Modellverlauf dauerhaft zurück, sodass alte
Ableitungen auch in späteren Gesprächsrunden nicht wieder auftauchen.

Die Datenbank gehört zur verschlüsselten Gesamtsicherung und zum normalen
Wiederherstellungs- und Updateweg. Verfahren erteilen keine Werkzeugrechte,
installieren keine Skripte und erlauben keine ungefragte Außenaktion.

Der Lernaufruf reserviert bei Ollama 8K Kontext statt des großen Gesprächsfensters
und höchstens 1.200 Ausgabetokens. Vor persönlichem Verfahrenskontext wird ein
konfigurierbares lokales Modell zusätzlich anhand installierter Gewichte geprüft.
Lokale Modellaufrufe übernehmen keine Systemproxys. Das verhindert, dass ein
Loopback-Name oder eine Proxyvariable die zugesagte lokale Verarbeitung umgeht.
