# Konzeptprüfung des Gedächtnisses

Stand: 26. September 2026. Erste Fassung, von einem zweiten, unabhängigen
Durchgang gegen den Code geprüft und danach berichtigt (siehe „Gegenprüfung“
am Ende). Wird bei jeder Etappe aus [`24-weg-zum-jarvis.md`](24-weg-zum-jarvis.md)
erneut geprüft.

> Fortschreibung 27. September: Diese Bestandsaufnahme beschreibt den Stand
> vor #104–#109. Inzwischen wurden die Suchgrenzen, der Suchindex,
> Projektmappen im Gespräch sowie Terminvorbereitung/-nachbereitung ergänzt.
> Die Gegenprüfung und die verbleibenden Abnahmeaufgaben stehen in
> [release/INTEGRATION-2026-09-27.md](release/INTEGRATION-2026-09-27.md).
> Die Modellqualität auf dem Mac bleibt offen. Aussagen zu externen
> Chat-Schnittstellen sind vor einer Umsetzung anhand aktueller offizieller
> Anbieterunterlagen zu prüfen; daraus folgt hier noch keine Zusage für
> einen dauerhaften Zugriff auf private Nachrichten.

## Warum diese Prüfung

Das Gedächtnis ist die Grundlage von allem. Ein Stabschef, der falsch
einsortiert oder das Richtige nicht findet, ist schlimmer als keiner, weil man
ihm glaubt. Deshalb reicht es nicht, dass das heutige Gedächtnis funktioniert.
Es muss regelmäßig gefragt werden: **Ist das Konzept die beste Lösung für das
Problem, oder nur eine, die funktioniert?**

Diese Prüfung vergleicht das Gedächtnis mit dem, was es leisten soll, sagt
ehrlich, wo es heute steht, und leitet daraus die nächsten Schritte ab.

## Was das Gedächtnis leisten soll

| # | Anforderung |
| --- | --- |
| A1 | **Alle Kanäle** zusammenführen: Mail, Kalender, Dokumente, Notizen, Meeting-Transkripte, Chat-Nachrichten (WhatsApp, LinkedIn), Web. |
| A2 | Neues **richtig einsortieren**: nach Art, Person, Projekt, Zeit. |
| A3 | Daraus **Personen und Projekte ableiten**, ohne zu raten. |
| A4 | Alles in einen **Zeitstrahl** einordnen: wann ist was passiert. |
| A5 | Ein **Modell des Nutzers**, das sich weiterentwickelt: wer er ist, was er will, wie er kommuniziert, wie sich Ziele, Umfeld und er selbst verändern. Nichts festgeschrieben, alles fortgeschrieben. |
| A6 | **Schneller Zugriff in Informationstiefen**: erst der Überblick, dann Einzelheiten, dann die Quellen. „Erzähl mir was zu Mainz“ darf nicht Minuten dauern. |
| A7 | **Vernetzung**: Beziehungen zwischen Personen, Projekten, Entscheidungen, Quellen. |
| A8 | **Modellunabhängig**: kleine lokale Modelle, starke lokale Modelle und, wenn der Nutzer es ausdrücklich will, Cloud-Modelle. Das Gedächtnis bleibt beim Wechsel erhalten. |
| A9 | **Über Jahre bestehen**: wachsen, ohne langsamer oder unzuverlässiger zu werden. |

Und über allem: Nichts wird Fakt ohne Beleg und Annahme, nichts
Außenwirksames ohne Freigabe.

## Stand je Anforderung

Bewertung: **trägt** (gebaut und geprüft), **teilweise** (Grundlage da, Lücke
benannt), **fehlt**.

**A1 Kanäle — teilweise.** Mail (IMAP, fortlaufend, ohne Dubletten),
Mac-Kalender und Abos, Dokumente und Ordner (Text, PDF), Transkripte (SRT, VTT),
öffentliche Webseiten und MCP als allgemeine Tür sind da. Es fehlen
Chat-Kanäle: WhatsApp und LinkedIn haben keine offene Schnittstelle für
private Nachrichten, beide bieten aber einen **Datenexport** an (WhatsApp:
Chat als Text exportieren; LinkedIn: Datenkopie mit Nachrichten als CSV). Ein
Import dieser Exporte ist machbar, lokal und ohne Zugangsdaten. Laufend
mitlesen lässt sich beides ohne inoffizielle Umwege nicht; das wäre ein
Sicherheits- und Vertragsrisiko und ist bewusst ausgeschlossen.

**A2 Einsortieren — teilweise, am Montag zu messen.** Die Einordnung je Absatz
(Bitte, Zusage, Stand, …) läuft lokal mit Modell, jede Angabe zeigt auf ihre
Textstelle, Berichtigungen und Entzug entwerten zuverlässig. Wie gut ein
kleines lokales Modell tatsächlich einsortiert, ist nicht gemessen. Das ist
der wichtigste offene Punkt überhaupt.

**A3 Personen und Projekte — teilweise.** Personen entstehen aus
Absenderadressen und bestätigten Aussagen; Gleichnamige werden nicht geraten
zusammengelegt. Projekte werden nicht automatisch angelegt; Quellen lassen sich
per Klick zuordnen, und die Zuordnung zu einem **bestehenden** Projekt wird aus
eigenen früheren Zuordnungen vorgeschlagen (`project_suggestions.py`). Es fehlt: ein Vorschlag „Das sieht nach einem neuen Projekt
aus“, wenn sich Quellen um ein wiederkehrendes Thema häufen.

**A4 Zeitstrahl — teilweise.** Jede Quelle trägt Quellenzeit und
Aufnahmezeit, Aussagen tragen Gültigkeit und Ersetzung, Fragen mit Zeitraum
(„letzte Woche“) werden berücksichtigt. Es fehlt die **Chronik als Ansicht und
als Antwort**: „Was ist bei Orion seit Juli passiert?“ ergibt heute eine
Auswahl von bis zu zwölf Quellen, keine geordnete Geschichte.

**A5 Nutzermodell — teilweise.** Das Selbstmodell führt Aussagen mit Herkunft,
Ersetzung und Verlauf; Ziele haben Abschluss und Wiederaufnahme; Gewohnheiten,
Mailstil und Arbeitsvorlieben existieren; Lernbeobachtungen werden als
Hypothesen vorgeschlagen. Es fehlt, dass **Veränderung selbst sichtbar** wird:
„Dein Schwerpunkt hat sich seit Juni von Vertrieb zu Produkt verschoben“ ist
heute nicht ableitbar, obwohl die Belege dafür vorliegen.

**A6 Informationstiefen und Tempo — teilweise, die größte Lücke.** Es gibt
Personen- und Projektakten (`graph.person_profile`, `graph.project_profile`):
Beteiligte, Quellen, Aufgaben, Notizen, aktuelle und ersetzte Aussagen, ohne
Modell aus dem Bestand berechnet. Das ist im Kern die Ebene „Quellen“ und ein
Teil der Ebene „Einzelheiten“. Sie sind aber nur als Ansicht im Gedächtnis
erreichbar, nicht als Antwort im Gespräch, und ihnen fehlen die Einordnungen
(offene Bitten, Zusagen), Entscheidungen, nächste Termine und eine kurze Lage.
Im Gespräch wird jede Frage im Moment der Frage beantwortet: Wortsuche, dann ein
Modellaufruf zur Auswahl, dann die Antwort. Mit einem kleinen lokalen Modell
kostet das je nach Rechner Sekunden bis Minuten, und bei einer offenen Frage
wie „Erzähl mir was zu Mainz“ ist die Auswahl auf zwölf Quellen begrenzt. Es
gibt keine vorbereitete Übersicht, die sofort da ist. Einzige Ausnahme sind
die Personen-Zusammenfassungen, die zwischengespeichert und bei geänderten
Quellen verworfen werden, aber nur für Personen und nur auf Knopfdruck.

**A7 Vernetzung — trägt, mit einer Grenze.** Der Graph verbindet Personen,
Projekte, Entscheidungen, Aussagen und Quellen und wird aus dem Bestand neu
berechnet, damit er nie eine zweite Wahrheit wird. Das ist richtig. Die Grenze:
Er wird bei jedem Aufruf neu gebaut, und zwar **nur aus den neuesten 5000
Quellen** (`graph.py`, `episodes.all_episodes(limit=5000)`, neueste zuerst).
Dasselbe gilt für die Projektakte (`by_project(…, limit=5000)`). Ältere Quellen
fallen ohne Hinweis aus Graph und Akten heraus. Das ist kein Tempo-, sondern
ein **Korrektheitsproblem**, das bei mehreren Jahren Mail schon heute eintritt.

**A8 Modellunabhängig — teilweise.** Das Gedächtnis selbst ist
modellunabhängig gespeichert; ein Modellwechsel verliert nichts. Für Gespräche
lassen sich lokale und entfernte Anbieter einstellen, und die Messung
verschiedener Modelle ist gebaut. Die Einordnung und Auswahl im Gedächtnis,
die Aufgabenerkennung und die Personen-Zusammenfassungen laufen aber **nur mit
lokalen Modellen**. Für Nutzer mit starkem Rechner ist
das richtig. Wer bewusst ein Cloud-Modell anschließen will, kann es für das
Gedächtnis heute nicht. Das braucht eine ausdrückliche, verständliche
Einwilligung, standardmäßig aus.

**A9 Über Jahre — teilweise.** Der kompakte Suchindex hält 3000 Mails in rund
18 MB; Sicherung, Update und Rückweg sind geprüft. Nicht gemessen ist, wie sich
Graph, Personenverzeichnis und Briefing bei zehntausenden Quellen verhalten;
bekannt ist bereits die stille 5000er-Grenze aus A7.

## Das Konzept gegen den Stand der Technik

Verbreitete Ansätze für Langzeitgedächtnis in KI-Systemen, und was davon hier
passt:

- **Stufenspeicher** (Arbeitskontext, Erinnerung, Archiv, wie bei MemGPT/Letta):
  entspricht den Schichten Gespräch, Episoden, Bestand. **Passt, ist da.**
- **Zeitlicher Wissensgraph** (Kanten mit Gültigkeit von/bis, wie bei
  Zep/Graphiti): Aussagen tragen hier Gültigkeit und Ersetzung. **Passt, ist
  weitgehend da.**
- **Hybride Suche** (Wortsuche, Bedeutungssuche, Graph kombiniert): Wortsuche
  und Graph sind da, Bedeutungssuche ist gebaut und aus. **Passt, Messung
  entscheidet.**
- **Hierarchische Verdichtung** (Zusammenfassungen über Zusammenfassungen, wie
  bei RAPTOR): Monatszusammenfassungen gibt es, aber nicht je Projekt, Person
  und Thema, und nicht als Einstieg für Fragen. **Passt, fehlt am wichtigsten
  Punkt.**
- **Vorberechnete Entitätsseiten** (jede Person, jedes Projekt hat eine
  laufend gepflegte Seite): fehlt, bis auf die Personen-Zusammenfassung.

Wo dieses Gedächtnis **strenger** ist als die genannten Systeme: Dort schreibt
meist das Modell Fakten direkt in den Speicher. Hier wird nichts Fakt ohne
Beleg und Annahme. Das kostet Bequemlichkeit, ist aber der Grund, warum man
dem Gedächtnis glauben kann. Das Konzept bleibt an dieser Stelle, wie es ist.

## Befund

Die Grundentscheidungen sind richtig und sollten bleiben: Rohmaterial
getrennt von Wissen, jede Angabe mit Beleg, Vorschläge statt stiller Fakten,
Graph als berechnete Ansicht statt zweiter Wahrheit, Gedächtnis unabhängig vom
Modell.

Falsch gewichtet ist die **Zeit, zu der gearbeitet wird**. Heute arbeitet das
Gedächtnis im Moment der Frage. Ein Stabschef arbeitet vorher: Er hat die Lage
zu jedem Projekt schon im Kopf, wenn gefragt wird. Daraus folgt die wichtigste
Änderung.

### Informationstiefen als vorbereitete Mappen

Jede Person, jedes Projekt und jedes wiederkehrende Thema erhält eine **Mappe**
in drei Tiefen. Sie baut auf den vorhandenen Akten auf, statt daneben zu
stehen:

1. **Lage** — drei bis fünf Sätze: Worum geht es, was ist der Stand, was ist
   offen. Mit Modell formuliert, im Hintergrund.
2. **Einzelheiten** — geordnete Punkte ohne Modell aus der Struktur
   abgeleitet: offene Bitten und Zusagen beider Seiten, letzte Entscheidungen,
   nächste Termine, Beteiligte, letzte Entwicklungen mit Datum.
3. **Quellen** — die Chronik: alle zugehörigen Quellen zeitlich geordnet, mit
   Einordnung, blätterbar statt abgeschnitten.

„Erzähl mir was zu Mainz“ liest dann die Mappe: Ebene 2 und 3 sind sofort da,
ohne Modellaufruf; die Lage steht dabei mit ihrem Stand („vorbereitet heute
8:10“). Wer tiefer will, klappt auf.

Regeln, damit die Mappe dem Gedächtnis nicht schadet:

- **Abgeleitet, nie Quelle.** Die Mappe ist weder Fakt noch Beleg und fließt
  nie als Material in einen weiteren Modellaufruf zurück, auch nicht in die
  nächste Lage. Grundlage jeder Lage sind immer die Quellen selbst, wie bei den
  Monatszusammenfassungen (`summaries.py`, `docs/10-verdichtung.md`,
  `docs/20-icarus-2.0.md` 5.1.1).
- **Jeder Satz der Lage belegt.** Jeder Satz verweist auf Quellen, und das
  zitierte Stück muss wörtlich in der Quelle stehen; sonst wird der Satz
  verworfen. Quelltext ist Daten, keine Anweisung.
- **Ebene 2 und 3 ohne Modell.** Sie werden bei jeder Änderung sofort neu
  berechnet und funktionieren auch ohne eingerichteten Anbieter.
- **Die Lage wird nicht bei jeder Mail verworfen.** Neue Quellen markieren sie
  als „älter als die neueste Quelle“ und werden in Ebene 2 sofort sichtbar;
  neu formuliert wird gebündelt (etwa höchstens stündlich je Mappe und nur für
  Mappen, die genutzt werden). Entzogene oder berichtigte Quellen verwerfen die
  Lage dagegen sofort, denn dann könnte sie Falsches sagen.
- **Keine stillen Grenzen.** Die Chronik wird geblättert, nicht bei einer
  festen Zahl abgeschnitten; wo doch begrenzt werden muss, steht es da.

Ehrlich: Das macht die Arbeit nicht kleiner, es verschiebt sie. Mit einem
kleinen lokalen Modell dauert das erste Vorbereiten der Lagen Stunden, und bei
Projekten mit täglichem Mailverkehr ist die Lage oft ein paar Stunden alt. Nur
Ebene 2 und 3 sind immer aktuell und immer sofort.

### Suchen in Stufen: erst klären, dann vertiefen

Vor der Tiefe steht die Frage, **was gemeint ist**. „Was ist mit Mainz los?“
kann das Projekt Mainz meinen, die Uniklinik Mainz oder einen Termin in Mainz.
Ein Stabschef sucht nicht erst alles durch, sondern klärt kurz und geht dann
gezielt in die Tiefe. Die Suche arbeitet deshalb in Stufen:

| Stufe | Was passiert | Modell | Dauer |
| --- | --- | --- | --- |
| 0 · Verzeichnis | Alle Bedeutungen des Begriffs einsammeln: Projekte, Personen, Organisationen, Orte, Termine, gehäufte Absender und Betreffe; je eine Zeile Kontext (Anzahl, zuletzt, nächster Termin) | nein | Millisekunden |
| Rückfrage | nur wenn mehrere Bedeutungen ähnlich stark sind; ein Klick je Bedeutung | nein | – |
| 1 · Lage | die vorbereitete Lage zur gewählten Bedeutung | vorbereitet | sofort |
| 2 · Einzelheiten | offene Punkte, Zusagen, Entscheidungen, nächste Termine | nein | sofort |
| 3 · Quellen | Chronik, blätterbar | nein | sofort |

Regeln:

- **Nur fragen, wenn es offen ist.** Gibt es eine klar stärkste Bedeutung, geht
  die Antwort direkt in die Tiefe; die übrigen stehen als eine Zeile darunter
  („Auch gefunden: Uniklinik Mainz, 3 Mails“).
- **Die Rückfrage rät nicht.** Sie zeigt nur Bedeutungen, für die es Belege
  gibt, jede mit ihrem Kontext.
- **Eine genaue Frage überspringt die Klärung.** „Wann liefert Anna die
  Prüfmuster für Mainz?“ geht wie heute direkt in die belegte Auswahl, nur mit
  der gewählten Bedeutung als Rahmen.

Ehrlich: Stufe 0 ist nur so gut wie das Verzeichnis. Organisationen und Orte
stehen heute nur darin, wenn sie bestätigt wurden. Zuerst tragen Projekte,
Personen, Termine sowie Absenderdomains und Betreffe als Gruppen, alles ohne
Modell. Organisationen und Orte als Vorschläge aus den Quellen folgen.

## Nächste Schritte

In dieser Reihenfolge, jeder als eigener PR mit Messung und Gegenprüfung:

1. **Stille 5000er-Grenze beheben** in Graph und Akten: vollständig lesen oder
   sichtbar begrenzen, mit Test bei mehr als 5000 Quellen. Korrektheit vor
   neuen Funktionen. *Umgesetzt in #104.*
2. **Suchen in Stufen, Stufe 0 und Rückfrage**: Verzeichnis aller Bedeutungen
   eines Begriffs ohne Modell, Rückfrage per Klick nur wenn offen.
   *Umgesetzt in #105.* Bedeutungen heute:
   Projekte, bestätigte Einträge, Absender (Domain oder Person), wiederkehrende
   Betreffe, Termine ±30 Tage, weitere Erwähnungen. Offen: getippte Antwort
   auf die Rückfrage statt Klick, Organisationen und Orte als Vorschläge aus
   den Quellen, Beschriftungen von Einträgen und Projekten werden beim Anzeigen
   nicht gegen Umbenennung geprüft.
3. **Mappen, Ebenen 2 und 3**: Projekt- und Personenakte um Einordnungen,
   Entscheidungen, Termine und blätterbare Chronik erweitern. Gesprächsweg:
   „Erzähl mir was zu X“ und „Was ist bei X seit … passiert?“ antworten sofort
   aus der Mappe.
   *Profilseite umgesetzt in #106* (Stand der Dinge und Chronik), *Gesprächsweg
   für Projekte in #107*. Offen: Personenmappe im Gespräch, „Was ist bei X seit
   … passiert?“ als Zeitraum auf der Mappe.
4. **Mappen, Ebene 1**: Lage im Hintergrund, jeder Satz wörtlich belegt, nie
   zurückgespeist.
5. **Chat-Exporte** (WhatsApp, LinkedIn) als Quellen, über dieselbe Aufnahme
   wie Dokumente.
6. **Gedächtnis mit Cloud-Modell** nur nach ausdrücklicher Einwilligung, mit
   einem Satz, der sagt, was das Gerät verlässt.
7. **Veränderung sichtbar machen** im Nutzermodell: Ziele und Schwerpunkte
   früher gegen jetzt, als Hypothese.
8. **Neue Projekte vorschlagen** aus sich häufenden Themen, als Erweiterung von
   `project_suggestions.py`.
9. **Messung bei zehntausenden Quellen** für Graph, Verzeichnis und Mappen.
10. **Freigaben je Assistent an der MCP-Tür.** Jeder fremde Assistent wird
    erkannt und bekommt eigene Bereiche (etwa beruflich lesen, privat nicht,
    nie schreiben). Das Protokoll hält fest, welcher Assistent wann was
    gelesen hat, nicht nur, was ausgeführt wurde.
11. **Sensibilitätsklassen.** Gesundheit, Finanzen und Familie sind für fremde
    Assistenten standardmäßig gesperrt und stehen nicht im allgemeinen
    Suchindex.
12. **Veraltetes zur Bestätigung vorlegen.** „Diese Angabe wurde seit 14
    Monaten nicht mehr verwendet. Soll sie weiter gelten?“ Ein Satz, ein
    Klick, gebündelt statt als neue Liste.

Die Punkte 10 bis 12 stammen aus einem Abgleich mit einem allgemeinen
Konzept für eine persönliche Gedächtnisschicht über mehrere KI-Dienste. Der
übrige Teil jenes Konzepts ist hier bereits umgesetzt: Quellenbezug,
Vorschlag statt stiller Fakten, Gültigkeit und Ablösung, Konflikte,
Audit-Protokoll, Export, MCP-Tür. Nicht übernommen werden Cloud-Betrieb und
Mandantenfähigkeit: Sie widersprechen der Produktvision (lokal, einfach) und
lösen kein Problem, das Kingfisher hat.

## Wie dieses Konzept geprüft bleibt

- Jede Etappe beginnt mit einem Blick in diese Prüfung: Stimmt der Befund
  noch? Neue Messungen werden hier eingetragen.
- Jede Änderung am Gedächtnis wird vor dem PR von einem zweiten, unabhängigen
  Durchgang gegengelesen: Stimmt der Code mit dem, was er behauptet? Welche
  Zusage lässt sich brechen, ohne dass ein Test fällt?
- Messwerte stehen unter `docs/evaluations/memory-quality/`; eine Aussage über
  Qualität ohne Messung wird als Vermutung gekennzeichnet.

## Gegenprüfung

Die erste Fassung wurde von einem unabhängigen Durchgang Behauptung für
Behauptung gegen den Code geprüft. Berichtigt wurde:

- A6 war zu hart: Personen- und Projektakten existieren als modellfreie
  Projektionen; es fehlen Einordnungen, Lage und der Weg ins Gespräch.
- A7 hatte eine echte Lücke übersehen: die stille 5000er-Grenze in Graph und
  Projektakte. Sie ist jetzt Schritt 1.
- A3 nennt jetzt `project_suggestions.py` als Grundlage für Projektvorschläge.
- Der Mappen-Entwurf hatte keine Zitatprüfung für die Lage, keine Sperre gegen
  Rückfluss in weitere Modellaufrufe und hätte bei jedem neuen Mail die Lage
  verworfen. Alle drei Punkte sind jetzt Regeln des Entwurfs.

