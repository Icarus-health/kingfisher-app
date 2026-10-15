# Gestaltung

Wonach die Oberfläche aussieht und warum. Wer etwas Neues baut, richtet sich
danach; wer davon abweicht, sagt hier warum.

## Das Gefühl

> **Alter Adel mit modernem Wikinger.**

So steht es im Produktauftrag, und es trifft es genauer als jede Fachbeschreibung. Was
es konkret heißt:

**Alter Adel** ist Zurückhaltung als Zeichen von Wert. Nichts ruft. Die Qualität
steckt im Material, im Abstand, im Satz — nicht in einem Effekt. Was teuer ist,
sagt es nicht.

**Moderner Wikinger** ist nicht Runenschrift und Hörner, sondern das nordische
Handwerk von heute: kühl, sachlich, aus wenigen guten Teilen, karg ohne arm zu
sein. Eiche, Wolle, Eisen, nasser Stein.

**Zusammen:** kühles Leinen statt warmem Pergament. Tinte statt Braun. Ein
einziger gedeckter Akzent statt einer Palette. Und immer: **make it simple.**

## Woran man das prüft

**Ist der Grund kühl?** Warmes Papier wirkt freundlich. Das hier soll nicht
freundlich wirken, sondern wertig. Der Ton zieht ins Grau-Grüne, nicht ins
Beige.

**Ruft irgendetwas?** Wenn ein Element auffällt, ohne dass es der wichtigste
Gegenstand der Ansicht ist, ist es zu laut. Genau ein gefüllter Knopf je
Ansicht. Die Akzentfarbe erscheint ein- bis zweimal auf dem Schirm, nicht
fünfmal.

**Ist die Hierarchie klar?** Die dunkle Navigation trägt die Marke. Der helle
Arbeitsplatz gehört dem Inhalt. Dünne Trennlinien ordnen Listen und Spalten;
Schatten sind auf seitliche Detailansichten begrenzt. Nicht jede Information
braucht eine eigene Karte.

**Trägt die Schrift?** Hierarchie entsteht über Größe und Strichstärke, nie
über einen Schriftwechsel. Eine zweite Familie in einer Anwendung sieht nach
Textverarbeitung aus. (Für Dokumente gilt das nicht — dort darf eine Serife
sprechen.)

**Steht Technik vorne?** Nie `state`, nie `0.72`, nie `confirm_strict`. Immer
der Satz, den ein Mensch dazu sagen würde.

## Zwei Ebenen, und eine Seite, die auch schmal geht

Kingfisher ist innen komplex; vorne darf es das nicht sein. In den Einstellungen steht vorne, was ein Mensch tun will
(Zugänge, Was Kingfisher darf, Kingfisher und du, Sicherung), in Alltagssprache und mit einem Satz, was den Rechner
verlässt. Alles, was ein Techniker einstellen könnte, liegt hinter „Für Techniker“, eingeklappt und mit dem Satz, dass
dort nichts geändert werden muss. Ein Fachwort vorne ist ein Fehler; ein Test sucht danach
([`47-einstellungen.md`](47-einstellungen.md)).

**Seitenbreite.** Keine Seite ist breiter als das Fenster, und es gibt keine Mindestbreite, auch nicht für einzelne
Seiten. Drei Stufen gelten überall (`Seitenbreite.css`): Unter 1100 px stapeln sich Spalten, unter 900 px wird die
Seitenleiste ein Streifen oben, unter 700 px haben Formulare und Raster eine Spalte. Was nicht passt, bricht um; nichts
zwingt zum seitlichen Scrollen, nichts wird am Rand abgeschnitten. Das gilt auch für den Streifen selbst: Alle Ziele
stehen ohne Rollen im Bild, das Zeichen über seinem Namen in kleiner Schrift; unter 700 px trägt nur der aktive Bereich
seinen Namen (Fremdprobe 3, Befund 14). Wer eine Seite baut, prüft sie bei 390, 768 und
1280 px (`scripts/probe_seiten_ui.py`).

## Freigegebene Gestaltung vom 15.10.2026

Der Nutzer hat die dritte Bildvariante gewählt: dunkle Kingfisher-Navigation,
helle Arbeitsflächen und Landschaft nur als ruhiger Akzent im Kopf. Diese
Entscheidung ersetzt die bisherige automatische Tag-/Nachtpalette. Auch bei
dunkler Systemeinstellung bleiben die Arbeitsflächen hell; die Navigation
bleibt dunkel. Dadurch ändern sich Leseflächen und ausgewählte Zustände nicht
unbemerkt mit dem Systemmodus.

| Rolle | Wert |
| --- | --- |
| Arbeitsgrund | `#f5f6f8` |
| Lesefläche | `#ffffff` |
| Navigation | `#082a3d` |
| Tinte | `#172635` |
| Hauptaktion | `#103e5c` |
| Auswahl | `#e8f2fd` mit Kante `#2869aa` |

Die semantischen Farbrollen stehen in `CalmUI.css`, die gemeinsame neue
Gestaltung in `NordicWorkspace.css`. `theme.css` erhält die bestehenden
Farbvariablen für ältere Komponenten. Keine neue Palette je Ansicht anlegen.
Navigation bleibt in `styles.css`; zentrale Breitenregeln in
`Seitenbreite.css`, die weiterhin zuletzt geladen wird.

Inter und die vorhandenen System-Fallbacks tragen die Oberfläche. Überschriften
liegen auf dem Desktop überwiegend bei 32 px, Lesetext bei 16 px; kleine
Metadaten treten zurück. Auswahl, Fokus, Warnung und Fehler bleiben unabhängig
von der dekorativen Landschaft erkennbar. Eigene Elemente brauchen geeignete
Tastaturziele und ausreichenden Kontrast.

Die freigegebenen Eisvogel-, Landschafts- und Symbolassets werden wiederverwendet.
Keine erdachten Vorschaubilder oder Dateigrößen: Ein Dokument zeigt den wirklich
gespeicherten Originaltext. Quellenstand, Originaldatum und Erfassungszeit
bleiben unterscheidbar. Auf schmalen Fenstern öffnet die Quelle allein; ein
sichtbarer Rückknopf und Escape führen zur ausgewählten Listenzeile zurück.

## Wo der Grundsatz vorgeht

Diese Seite steht unter `CLAUDE.md`, nicht daneben. Wenn Eleganz und
Verständlichkeit sich widersprechen, gewinnt Verständlichkeit — aber dann ist
die Aufgabe, das Verständliche schön zu machen, nicht das Schöne aufzugeben.

Und keine dieser Regeln hebt eine Sicherheitszusage auf. Eine Freigabekarte
darf ruhig unschön sein, solange sie vollständig ist.
