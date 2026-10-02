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

**Ist es Material oder Farbe?** Eine Fläche liegt auf einem Grund: Lichtkante
oben, haarfeine Fassung, zwei Schatten — einer eng für die Kante, einer weit
für den Raum. Eine flache Farbe mit Rahmen sieht nach Formular aus.

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

## Die Werte

Alles steht in `app/kingfisher/src/theme.css` als Token. Keine Farbe, kein Abstand, keine
Schriftgröße außerhalb davon — ein Festwert im Verlauf ist genau die Stelle,
an der eine Palette beim nächsten Wechsel auseinanderfällt und nachts hell aus
einer dunklen Fläche leuchtet.

| | Tag | Nacht |
| --- | --- | --- |
| Grund | `#f4f4f1` → `#e7e8e3` | `#16191a` → `#101314` |
| Fläche | `#fcfcfa` | `#212527` |
| Tinte | `#171a1a` | `#e9ecea` |
| Akzent | `#2f5069` | `#7ba7c4` |
| Warnung | `#8a6a2c` | `#c2a061` |
| Gefahr | `#8f403a` | `#cc8078` |
| Bestätigt | `#3d6b52` | `#6ea88a` |

Der Akzent ist **Eisen und kaltes Wasser**, kein Weblau. Er soll nach Tinte
aussehen und nicht nach Verweis. Warnung, Gefahr und Bestätigt sind Ocker,
Ochsenblut und Flechte — gedeckt, keine Signalfarben.

Die Kingfisher-Oberfläche (`app/kingfisher/src/theme.css`) führt ihre Farben
ebenfalls als Variablen, getrennt nach Rolle: `--kf-flaeche-…`, `--kf-schrift-…`,
`--kf-rand-…`. Dieselbe Farbe braucht nachts als Fläche einen anderen Wert als
als Schrift. Der Nachtmodus folgt der Systemeinstellung und setzt die Tabelle
oben um: kühler Grund, helle Tinte, kräftige Akzentflächen bleiben. Schrift
über dem Landschaftsfoto bleibt dunkel, weil das Foto hell bleibt. Neue Farben
kommen als Variable mit Tag- und Nachtwert dazu, nie als Festwert.

**Neun Schriftstufen**, benannt, keine dazwischen. **Vier Radien.** Abstände
auf einem 4-Punkt-Raster. **44 px** ist die kleinste Fläche, die ein Finger
sicher trifft.

## Wo der Grundsatz vorgeht

Diese Seite steht unter `CLAUDE.md`, nicht daneben. Wenn Eleganz und
Verständlichkeit sich widersprechen, gewinnt Verständlichkeit — aber dann ist
die Aufgabe, das Verständliche schön zu machen, nicht das Schöne aufzugeben.

Und keine dieser Regeln hebt eine Sicherheitszusage auf. Eine Freigabekarte
darf ruhig unschön sein, solange sie vollständig ist.
