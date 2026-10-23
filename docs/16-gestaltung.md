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
zwingt zum seitlichen Scrollen, nichts wird am Rand abgeschnitten (einzige Ausnahme: Segmentleisten rollen in sich, siehe
„Grundlage vom 23.10.2026“). Das gilt auch für den Streifen selbst: Alle Ziele
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

Inter und die vorhandenen System-Fallbacks tragen die Oberfläche (seit dem 23.10. die Systemschrift zuerst, siehe
„Grundlage vom 23.10.2026“). Überschriften
liegen auf dem Desktop überwiegend bei 32 px, Lesetext bei 16 px; kleine
Metadaten treten zurück. Auswahl, Fokus, Warnung und Fehler bleiben unabhängig
von der dekorativen Landschaft erkennbar. Eigene Elemente brauchen geeignete
Tastaturziele und ausreichenden Kontrast.

Die freigegebenen Eisvogel-, Landschafts- und Symbolassets werden wiederverwendet.
Keine erdachten Vorschaubilder oder Dateigrößen: Ein Dokument zeigt den wirklich
gespeicherten Originaltext. Quellenstand, Originaldatum und Erfassungszeit
bleiben unterscheidbar. Auf schmalen Fenstern öffnet die Quelle allein; ein
sichtbarer Rückknopf und Escape führen zur ausgewählten Listenzeile zurück.

## Grundlage vom 23.10.2026

Der Nutzer nach zwei Wochen Test: „große Flächen, wenig geschrieben, sehr adaptiv, Verständnis auf einen Blick, optische
Wertigkeit, im Prinzip als hätte Apple das Programm geschrieben“. Die Grundrichtung vom 15.10. bleibt (dunkle Navigation,
helle Arbeitsflächen, ein gedeckter Akzent, eine Schrift); diese Grundlage macht sie messbar und gibt den Seiten
gemeinsame Bausteine.

**Maßstab „wie von Apple“.** Woran man es prüft:

1. **Ein Blick reicht.** Jede Ansicht hat genau eine Hauptsache, die man in einer Sekunde sieht.
2. **Wenig Text.** Ein Titel, höchstens eine Zeile darunter. Erklärungen nur, wo ohne sie ein Fehler passiert, und dann
   als Fußnote unter der Gruppe. Keine Absicherungsprosa.
3. **Große, ruhige Flächen.** Gruppierte Flächen statt vieler Kästen, Haarlinien statt Rahmen, keine Karten in Karten.
4. **Große Ziele.** Alles Anklickbare mindestens 44 px hoch, ganze Zeilen anklickbar.
5. **Adaptiv.** Bei 390, 768, 1280 und 1600 px gewollt, nicht nur passend. Schmal: eine Spalte, Aktionen erreichbar.
6. **Material statt Farbe.** Ein Akzent, Tinte, Weiß, kühles Grau. Bilder nur im Kopf von Heute.
7. **Bewegung leise.** 150–250 ms, `prefers-reduced-motion` wird respektiert.
8. **Systemnah.** Systemschrift des Macs, sonst Inter; großer Titel, Segmente, gruppierte Listen, Seitenleiste.

**Wo es steht.** `app/kingfisher/src/Grundlage.css` (geladen direkt vor `Seitenbreite.css`, die zuletzt bleibt) und die
Bausteine in `app/kingfisher/src/grundlage/` (nur Darstellung, keine Seitenlogik; Einstieg `grundlage/index.ts`).
Geprüft von `tests/grundlage.test.mjs`.

### Werte (`:root`, Präfix `--g-`)

| Rolle | Wert |
| --- | --- |
| Schrift `--g-schrift` | `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", sans-serif` |
| Großer Titel `--g-titel-gross` | 34/1.15, 700, −0,022em (schmal unter 700 px: 28) |
| Titel `--g-titel` | 22/1.25, 650 |
| Überschrift `--g-ueberschrift` | 17/1.35, 600 |
| Text `--g-text` | 16/1.5 |
| Neben `--g-neben` | 14/1.45, `--calm-muted` |
| Fußnote `--g-fussnote` | 13/1.4, `--calm-muted` |
| Abstände `--g-a1` … `--g-a8` | 4, 8, 12, 16, 24, 32, 48, 64 |
| Radien | Fläche 14, Bedienelement 10, Pille 999 |
| Fläche `--g-flaeche`, `--g-schatten` | Weiß ohne Rahmen, `0 0 0 1px rgba(23,38,53,.05), 0 1px 2px rgba(23,38,53,.04)` |
| Trenner `--g-linie` | `rgba(23,38,53,.08)`, eingerückt |
| Grund `--g-grund` | `#f5f6f8` |
| Getönt `--g-getoent` | die Hauptaktionsfarbe zu 8 % |
| Ziele | `--g-ziel` 44, `--g-ziel-kompakt` 36, `--g-zeile` 52 |
| Bewegung `--g-bewegung` | 200 ms |

Tinte, Akzent, Verweis und Auswahl kommen aus `CalmUI.css` und `NordicWorkspace.css`; es gibt keine neue Palette.
Schriftstufen gibt es auch als Klassen: `g-titel-gross`, `g-titel`, `g-ueberschrift`, `g-text`, `g-neben`, `g-fussnote`.

### Bausteine

| Baustein | Props | Klassen |
| --- | --- | --- |
| `Seitenkopf` | `titel`, `zeile?` (eine Zeile), `aktionen?`, `className?` | `g-seitenkopf`, `-text`, `-titel`, `-zeile`, `-aktionen`; klebende Leiste `g-kopfleiste` (erscheint, sobald der Titel oben hinausrollt; `--g-kopf-rand` dehnt sie über den Seitenrand) |
| `Gruppe` | `titel?` (klein über der Fläche), `fussnote?` (ein Satz darunter), `frei?` (freier Inhalt mit Innenabstand statt Zeilen), `children` | `g-gruppe`, `g-gruppe-kopf`, `g-gruppe-titel`, `g-flaeche` (`g-flaeche-frei`), `g-gruppe-fussnote` |
| `Zeile` | `titel`, `neben?`, `wert?` (rechts), `symbol?` (links, etwa `<InterfaceIcon name="mail" />`); klickbar mit `onClick` **oder** `href`, dazu `pfeil?` (Vorgabe: bei Verweisen), `aktiv?`, `deaktiviert?`; statisch mit `zusatz?` (Schalter rechts) – nie beides, keine Knöpfe im Knopf | `g-zeile`, `-symbol`, `-text`, `-titel`, `-neben`, `-wert`, `-zusatz`, `-pfeil`; mindestens 52 px |
| `Segmente` | `optionen` (`{wert, titel, zahl?, deaktiviert?}`), `wert`, `onWahl(wert)`, `label`, `kompakt?` | `g-segmente`, `g-segment`, `g-segment-zahl`; Pille, rollt waagrecht statt umzubrechen; Pfeiltasten, Pos1, Ende (Modell `segmentTasten.ts`); Zahl nur über null |
| `Leer` | `satz` (genau einer), `zeichen?` (Name eines `InterfaceIcon`), `aktion?` (höchstens ein Knopf) | `g-leer`, `-zeichen`, `-satz`, `-aktion` |
| `Aufklapper` | `titel`, `neben?` (leise rechts), `offen?`, `onToggle?(offen)`, `children` | `g-aufklapper`, `-titel`, `-neben`, `-inhalt` |

**Knöpfe** sind Klassen, keine Bausteine: `g-knopf` (gefüllt, genau einer je Ansicht), `g-knopf-getoent` (der zweite),
`g-knopf-schlicht` (nur Text). Höhe 44, mit `g-kompakt` 36. Was etwas unwiderruflich entfernt, bleibt rot.

### Was global umgestellt ist (ohne Seitenlogik)

- Eine Schriftfamilie überall (`--g-schrift`, die Familie einmal mit `!important`, weil der Bestand sie in vielen
  `font:`-Kurzformen auf Inter setzt); Code behält seine Schrift. Grundtext 16/1.5.
- Grund `#f5f6f8` ohne Landschaft auf allen Seiten außer Heute; die Seitenleiste dunkel und ruhig ohne Landschaftsbild,
  das Logo bleibt.
- Die Köpfe der Seiten (`.tasks-heading`, `.settings-heading`, `.inbox-heading`, `.history-heading`, `.profile-heading`,
  Gedächtnis, Kalender, Prüfen, Welt, Akte, leeres Gespräch) als großer Titel ohne Bild und ohne Überzeile; die Zeile
  darunter leise, die Aktion rechts, schmal darunter.
- Die Reiterleisten (`.task-tabs`, `.profile-tabs`, `.view-switch`, `.memory-area-tabs`, `.inbox-filter`, die Reiter im
  Gedächtnis) in der Optik der Segmente; die Bereichsliste der Einstellungen als ruhige Seitenliste.
- `details > summary` überall mit dem eigenen, sich drehenden Pfeil statt `▶` (abwählbar mit `g-ohne-pfeil`).
- Eingabefelder 44 px, Radius 10, ruhiger Fokusring; Fokus von Knöpfen und Verweisen 2 px in der Auswahlkante.
- Knöpfe des Bestands auf die drei Stufen: `.primary-action`, `.tasks-add`, `.mail-reader-primary`, `.memory-confirm`,
  `.people-review-action` gefüllt; `.secondary-action`, `.mail-reader-secondary`, `.mail-reader-close`,
  `.memory-reject`, `.people-review-secondary`, `.chronik-mehr` getönt; `button.text-action` schlicht. Ob je Ansicht nur
  einer gefüllt ist, entscheiden die Seiten.
- Flächen (Profilkarten, Quellen, Aufgabentabelle, Kalenderblatt, Nachrichten, Gesprächsliste …) weiß ohne Rahmen mit
  Haarschatten; Fläche in Fläche wird flach. Listentrenner als Haarlinie.

### Was sich gegenüber dem 15.10. ändert

- **Landschaft nur noch im Kopf von Heute.** Nicht mehr hinter allen Seiten, nicht in den Köpfen, nicht im Gedächtnis
  und nicht in der Seitenleiste (Test: `tests/grundlage.test.mjs`).
- **Systemschrift.** Auf dem Mac San Francisco, sonst Inter; Hierarchie weiter nur über Größe und Strichstärke.
- **Große Titel** (34 statt 32 px, 700) und **Segmente** statt unterstrichener Reiter.
- **Segmentleisten rollen waagrecht**, statt umzubrechen; das ist die eine gewollte Ausnahme von „nichts rollt
  seitlich“. Die Seite selbst rollt nie (`scripts/probe_seiten_ui.py` misst die Leiste, nicht ihre Glieder).

## Wo der Grundsatz vorgeht

Diese Seite steht unter `CLAUDE.md`, nicht daneben. Wenn Eleganz und
Verständlichkeit sich widersprechen, gewinnt Verständlichkeit — aber dann ist
die Aufgabe, das Verständliche schön zu machen, nicht das Schöne aufzugeben.

Und keine dieser Regeln hebt eine Sicherheitszusage auf. Eine Freigabekarte
darf ruhig unschön sein, solange sie vollständig ist.
