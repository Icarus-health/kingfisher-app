# Der Weg zum Stabschef, der mitdenkt

Stand: 26. September 2026.

[`17-stabschef.md`](17-stabschef.md) beschreibt die fünf Etappen vom Gedächtnis
zum Urteil. Sie sind gebaut. Dieses Papier beschreibt, was danach fehlt, damit
aus einem Stabschef, den man aufsucht, einer wird, der die richtigen Dinge von
selbst parat hat: Pepper Potts, nicht ein weiteres Dashboard.

## Der Maßstab

> **Es zählt das Ziel, nicht der kürzeste Weg dorthin.**

Einen mittelmäßigen Assistenten gibt es schon, in jedem Mailprogramm und jedem
Chatfenster. Weniger als ein Stabschef, dem man blind vertraut, bringt
niemandem etwas. Daraus folgen drei Regeln für alles, was hier steht:

1. **Das Gedächtnis zuerst.** Jede Funktion hier liest aus dem Gedächtnis. Wenn
   es falsch einsortiert oder das Richtige nicht findet, ist jede Funktion
   darauf falsch, nur schneller. Keine Etappe beginnt, solange eine bekannte
   Gedächtnisschwäche sie untergräbt. Die Messungen aus
   [`release/TESTPLAN-MAC.md`](release/TESTPLAN-MAC.md) entscheiden, ob
   weitergebaut oder erst nachgebessert wird.
2. **Die Oberfläche als Zweites.** Eine Funktion ist erst fertig, wenn sie ohne
   Erklärung benutzt werden kann: so wenige Klicks wie möglich, so viel
   automatisch wie sicher vertretbar, jede Aktion antwortet. Eine richtige
   Antwort an der falschen Stelle ist keine.
3. **Gründlich statt schnell.** Lieber eine Etappe vollständig — echte Daten,
   echter Browser, Sabotageproben, im Alltag benutzt — als drei halb. Eine
   Etappe gilt erst als erledigt, wenn ihr „Fertig heißt“ unten erfüllt ist,
   nicht wenn der Code steht.

4. **Ehrlich über Grenzen.** Wo das Ziel mit dem heutigen Stand der Technik
   oder der verfügbaren Hardware nicht erreichbar ist, wird es so weit gebracht
   wie möglich und die Grenze ausdrücklich benannt, statt sie zu überdecken.
   Später lässt sich nachbessern; eine verschwiegene Grenze nicht.

Unverändert gilt: Verdichtung schlägt vor, sie schreibt nicht. Nichts
Außenwirksames ohne Freigabe. Was automatisch geschieht, lässt sich sehen und
zurücknehmen.

## Wo wir stehen

Vorhanden und geprüft: Gedächtnis mit Herkunft, Rückfragen per Klick und
Berichtigung; Morgenbriefing mit Urteil; Delegation und Warten; Personen,
Projekte, Entscheidungen, Ziele und Gewohnheiten mit Belegen; Mailaufnahme mit
Filter, Antwortvorschläge im eigenen Stil, Aufgabenerkennung; Mac-Kalender und
Abos mit einer Terminvorbereitung; ausdrücklich eingetragene öffentliche
Webquellen; Briefing zum Anhören; lokale und entfernte Modelle; MCP in beide
Richtungen; Sicherung und Update mit Rückweg.

Was fehlt, ist weniger eine Funktion als eine Haltung: Heute muss man
Kingfisher aufsuchen, auswählen und anstoßen. Ein Stabschef hat es schon
getan.

## Das Gedächtnis als Kern

Was das Gedächtnis leisten muss — alle Kanäle, richtig einsortiert, Personen,
Projekte und Zeitstrahl abgeleitet, ein Nutzermodell, das sich mit seinen
Zielen und seinem Umfeld weiterentwickelt, Zugriff in Informationstiefen,
modellunabhängig über Jahre —, und wie weit das heutige Konzept dafür trägt,
steht in [`25-gedaechtnis-konzeptpruefung.md`](25-gedaechtnis-konzeptpruefung.md).
Diese Prüfung wird bei jeder Etappe wiederholt: Ist das Konzept noch die beste
Lösung, oder nur eine, die funktioniert?

## Die Etappen

### 0. Das Gedächtnis auf dem Mac beweisen

Echtes Modell, echtes Postfach, gemessen statt vermutet: Einordnung und
Auswahl mit `qwen3.5:4b`, Zeit je Quelle, Bedeutungssuche mit `bge-m3`.
Bekannte Schwäche: Fragen mit anderen Worten als die Quelle findet die
Wortsuche heute kaum (3 von 16).

**Fertig heißt:** Die Schwellen aus dem Testplan sind erreicht oder die
Nachbesserung ist gebaut und nachgemessen. Eine Woche Alltag ohne eine Antwort,
die eine vorhandene Information übersieht oder eine falsche behauptet.

### 1. Einrichten in einem Durchgang

Heute verteilt sich die Einrichtung auf Reiter: Modell, Mail, Kalender, Ordner,
Einordnung. Ein erster Start führt stattdessen durch einen Ablauf, der erkennt,
was schon da ist (installiertes Ollama und seine Modelle, Mac-Kalender), nur
fragt, was niemand sonst wissen kann (Mail-Zugang, welcher Ordner), und mit
einem echten ersten Briefing endet.

**Fertig heißt:** Von der leeren Installation zum ersten Briefing mit eigenen
Daten in unter zehn Minuten, ohne einen Begriff wie Host, Port oder Modellname
eintippen zu müssen. Jeder Schritt lässt sich überspringen und später
nachholen.

### 2. Termine von selbst vorbereiten und nachbereiten

Die Vorbereitung existiert, verlangt aber, dass man Person und Projekt selbst
wählt, obwohl die Teilnehmer im Kalender stehen.

- **Vorher:** Teilnehmer werden bekannten Personen zugeordnet, das Projekt aus
  Titel, Teilnehmern und letzten Mails vorgeschlagen. Kurz vor dem Termin liegt
  bereit: letzter Kontakt, offene Punkte beider Seiten, Zusagen, die
  einschlägigen Mails. Das Briefing sagt „Um 14 Uhr Herr Meier. Vorbereitet.“
- **Nachher:** Kingfisher fragt „Was ist herausgekommen?“ und macht aus der
  Antwort oder einem Transkript Vorschläge für Aufgaben, Zusagen und
  Entscheidungen.

**Fertig heißt:** Bei einem normalen Arbeitstag ist jeder Termin mit bekannten
Teilnehmern ohne Klick vorbereitet, und eine falsche Zuordnung lässt sich mit
einem Klick berichtigen. Nichts aus der Nachbereitung wird Fakt ohne Annahme.

*Stand:* Vorher und Nachher sind umgesetzt, die Etappe ist im Code fertig und
wartet auf die Prüfung am echten Kalender.

- **Vorher (#108):** Teilnehmer über die Mailadresse, Projektvorschlag mit
  Grund, Berichtigung mit einem Klick, Briefing „Vorbereitet“.
- **Nachher (#109):** Nach einem Termin mit anderen fragt das Briefing
  48 Stunden lang einmal „Was ist herausgekommen?“. Die Antwort, getippt oder
  als SRT/VTT-Mitschrift aus Teams, Zoom oder Meet, wird eine Quelle mit den
  Teilnehmern, dem Projekt und dem Terminende. Einordnung und
  Aufgabenerkennung schlagen daraus Bitten und Zusagen vor; Fakt wird nichts
  ohne Annahme. „Nichts festzuhalten“ beendet die Nachfrage und lässt sich
  zurücknehmen. Eine Terminserie wird je Vorkommen nachbereitet.

Offen:

- **Messung auf dem Mac:** Wie oft „jeder Termin ohne Klick vorbereitet“ im
  echten Kalender gelingt. Dort zeigt sich auch, ob die Kennungen der Termine
  stabil genug sind; der Mac-Kalender nimmt den Beginn in die Kennung auf.
- **Tonaufnahmen:** Sie werden noch nicht umgeschrieben. Vorgesehen ist ein
  lokales faster-whisper als eigener, freiwilliger Schritt; die Oberfläche
  sagt bis dahin offen, dass nur Text und Untertitel gehen.
- **Vorschläge ohne lokales Modell:** Ohne eingeschaltete Einordnung mit
  lokalem Modell bleibt die Nachbereitung eine Quelle ohne Vorschläge. Das
  Programm sagt das nach dem Speichern.
- **Man selbst als Teilnehmer:** Ist kein Mailkonto eingerichtet, kennt das
  Programm die eigene Adresse nicht. Beim Mac-Kalender steht man dann als
  Teilnehmer im eigenen Termin, und auch Termine allein fragen nach. Abhilfe
  ist, dass der Mac-Adapter `isCurrentUser` mitliefert.
- **Serien aus CalDAV und iCalendar-Abos:** Sie kommen ohne Auflösung der
  Wiederholungen nur als erster Termin an. Die Nachbereitung je Vorkommen
  greift deshalb heute vor allem beim Mac-Kalender.
- **Mehrere Nachbereitungen eines Termins:** Ergänzen legt eine weitere
  Quelle an; das Fenster zeigt nur die neueste. Die früheren stehen in der
  Chronik des Projekts und der Personen.
- **Abruflast:** Das Nachbereitungsfenster lädt zum Finden des Termins den
  Jahreskalender. Bei CalDAV ist das ein größerer Abruf je Öffnen.

### 3. Der Zeitstrahl

Je Person, Projekt und Thema eine Chronik: wann ist was passiert, aus Mails,
Terminen, Entscheidungen, Aufgaben und Aussagen, jeweils mit Beleg. Dieselbe
Chronik beantwortet im Gespräch „Was ist bei Orion seit Juli passiert?“ und
zieht dabei auch Altes heran, das im Wortlaut nicht zur Frage passt.

**Fertig heißt:** Für ein echtes Projekt ergibt die Chronik ohne Nacharbeit
eine Geschichte, die der Nutzer als richtig und vollständig erkennt; Lücken
werden als Lücken gezeigt, nicht überbrückt.

### 4. Die Welt, soweit sie dich betrifft

Die Karte „Relevantes aus der Welt“ zeigt heute nur Beispielbilder. Echte
Quellen (Nachrichtenfeeds, Fachquellen, Regulierung) werden aus Projekten und
Zielen vorgeschlagen, lokal auf Relevanz gefiltert und mit dem Bestand
verknüpft: „Betrifft Projekt Alpha; dort gilt noch die Annahme …“.

**Fertig heißt:** Das Briefing zeigt an den meisten Tagen höchstens eine
Meldung, und die ist für den Nutzer tatsächlich einschlägig. Jede Meldung sagt,
warum sie da ist, und jede Quelle lässt sich mit einem Klick abbestellen.

### 5. Von sich aus melden

Kingfisher meldet sich heute nur, wenn man es öffnet. Wenige, wirklich
dringende Dinge — ein Termin gleich, jemand wartet zu lange, eine Annahme ist
gekippt — erscheinen als Benachrichtigung, zu Zeiten, die zum Nutzer passen.

**Fertig heißt:** Keine Benachrichtigung, die der Nutzer im Nachhinein für
überflüssig hält; eine Woche lang gezählt.

### 6. Verstehen, wie du arbeitest

Mailstil, Arbeitsvorlieben und Lernbeobachtungen gibt es. Sie fließen noch kaum
in Rangfolge, Zeitpunkt und Tonfall der Vorschläge ein. Was angenommen, was
liegen gelassen, was berichtigt wird, wird zur sichtbaren Hypothese — „Du
schiebst Buchhaltung meist auf Freitag“ — und erst nach Bestätigung zur Regel.

**Fertig heißt:** Nach einem Monat Nutzung sind die Vorschläge merklich
treffsicherer, und jede Anpassung lässt sich einsehen und zurücknehmen.

### Später

Spracheingabe (nur mit lokaler Spracherkennung — sonst gingen Aufnahmen an
einen Cloud-Dienst), Browser- und Computersteuerung, spezialisierte Agenten.
Groß und wertvoll, aber erst auf einem Alltag, der ohne sie trägt.

## Was noch dazukommt

- **Freie Schnittstellen** für Wetter, Feiertage, Verkehr, Wechselkurse und
  Ähnliches (Sammlungen wie „public-apis“ auf GitHub). Jede nur mit
  sichtbarer Freigabe und ohne persönliche Daten in der Anfrage.
- **Sprache** mit einem lokalen Sprachmodell (Sprache zu Sprache, etwa von
  Hugging Face), sobald eines auf einem normalen Mac flüssig genug läuft. Keine
  Aufnahme verlässt das Gerät.
- **Andere Modelle für andere Rechner.** Wer mehr Leistung hat, schließt ein
  stärkeres lokales Modell an; wer ausdrücklich will, ein Cloud-Modell. Das
  Gedächtnis bleibt dasselbe.

## Wie gearbeitet wird

- Jede Arbeit wird **gegengeprüft**: ein zweiter, unabhängiger Durchgang liest
  Konzept und Code gegen, bevor ein PR entsteht, und sucht nach Zusagen, die
  sich brechen lassen, ohne dass ein Test fällt.
- Jede Arbeit kommt als **eigener PR in einem Batch**. In
  [`release/MERGE-REIHENFOLGE.md`](release/MERGE-REIHENFOLGE.md) steht laufend,
  was auf was aufbaut und in welcher Reihenfolge zusammengeführt wird.
- Aussagen über Qualität stützen sich auf Messungen; ohne Messung sind sie als
  Vermutung gekennzeichnet.

## Reihenfolge

0 vor allem anderen. Danach 1 und 2, weil sie mit dem Vorhandenen am meisten
Klicks und Denkarbeit abnehmen; dann 3 und 4; dann 5 und 6. Jede Etappe als
eigene, einzeln geprüfte Arbeit, und keine beginnt, bevor die vorige ihr
„Fertig heißt“ erfüllt.

