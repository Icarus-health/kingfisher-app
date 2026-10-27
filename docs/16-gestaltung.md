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
Seitenleiste ein Streifen oben, unter 700 px haben Formulare und Raster eine Spalte, und die Navigation ist eine feste,
beschriftete Leiste unten (seit Paket H, siehe „Handy“). Was nicht passt, bricht um; nichts
zwingt zum seitlichen Scrollen, nichts wird am Rand abgeschnitten (einzige Ausnahme: Segmentleisten rollen in sich, siehe
„Grundlage vom 23.10.2026“). Das gilt auch für den Streifen selbst: Alle Ziele
stehen ohne Rollen im Bild, das Zeichen über seinem Namen in kleiner Schrift (Fremdprobe 3, Befund 14). Unter 700 px
trug bis 1.0.29 nur der aktive Bereich seinen Namen; seit Paket H steht dort die Leiste unten, jedes Ziel mit Namen. Wer eine Seite baut, prüft sie bei 390, 768 und
1280 px (`scripts/probe_seiten_ui.py`).

## Freigegebene Gestaltung vom 15.10.2026

Der Nutzer hat die dritte Bildvariante gewählt: dunkle Kingfisher-Navigation,
helle Arbeitsflächen und Landschaft nur als ruhiger Akzent im Kopf. Diese
Entscheidung ersetzt die bisherige automatische Tag-/Nachtpalette. Auch bei
dunkler Systemeinstellung bleiben die Arbeitsflächen hell; die Navigation
bleibt dunkel. Dadurch ändern sich Leseflächen und ausgewählte Zustände nicht
unbemerkt mit dem Systemmodus.
*(Am 25.10.2026 ersetzt: Die Arbeitsflächen folgen seitdem dem Systemmodus, siehe „Dunkelmodus vom 25.10.2026“.
Die Navigation bleibt dunkel; die Werte unten gelten weiter für den hellen Modus.)*

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
| `Segmente` | `optionen` (`{wert, titel, zahl?, deaktiviert?}`), `wert`, `onWahl(wert)`, `label`, `kompakt?` | `g-segmente`, `g-segment`, `g-segment-zahl`; Pille, rollt waagrecht statt umzubrechen (`data-rollt="waagrecht"`, Rand blendet aus, wo etwas verborgen ist); Pfeiltasten, Pos1, Ende (Modell `segmentTasten.ts`); Zahl nur über null |
| `Leer` | `satz` (genau einer), `zeichen?` (Name eines `InterfaceIcon`), `aktion?` (höchstens ein Knopf) | `g-leer`, `-zeichen`, `-satz`, `-aktion` |
| `Aufklapper` | `titel`, `neben?` (leise rechts), `offen?`, `onToggle?(offen)`, `children` | `g-aufklapper`, `-titel`, `-neben`, `-inhalt` |
| `Schalter` (V4) | `titel`, `satz?`, `an`, `onWechsel(an)`, `deaktiviert?` | jedes `input[role=switch]` ist ein Umlegeschalter rechts in seiner Zeile (`#root .shell …`); vorher lokal in `Einstellungen.css` |
| `Unterkopf` (V4) | `titel`, `zeile?`, `aktion?` | `g-unterkopf`, `g-unterkopf-zeile`; Kopf einer Unteransicht (Gedächtnis: Verarbeitung, Aussagen prüfen) |
| `Bestaetigung` (V4) | `titel`, `label`, `knoepfe?`, `children` (der Satz als `<strong>`) | `g-bestaetigung`, `-titel`, `-knoepfe`; Freigabe, Gedächtnisvorschlag, Vorschlag für die Akte |
| `HinweisAnzeige` (V4) | einmal in `main.tsx`; die Seiten rufen `zeigeHinweis({ text, rueckgaengig?, danach?, verweis?, fehler? })` | `g-hinweis-ort`, `g-hinweis`, `-text`, `-aktionen`, `-punkt`, `-knopf` |
| `Rueckfrage` (B3) | `frage`, `satz?`, `bestaetigen`, `abbrechen?` (Vorgabe „Abbrechen“), `onBestaetigen`, `onAbbrechen`, `arbeitet?`, `gesperrt?`, `rot?`, `start?` (`"feld"`, wenn erst etwas einzutragen ist), `fehler?`, `children?`; die Seite zeigt sie, solange gefragt wird | `g-rueckfrage`, `-frage`, `-satz`, `-fehler`, `-knoepfe`, `g-knopf-rot`; modaler `<dialog>` mit `role=alertdialog` über allem (Portal in `body`) |
| `AnsageAnzeige` (B1) | einmal in `main.tsx`; die Seiten rufen `sageAn(satz)` | unsichtbarer Ort `role=status`, `aria-live=polite`; leert sich vor jedem Satz, damit auch ein gleicher angesagt wird |
| `Seitenwechsel`, `Sprunglink` (B2) | einmal in `main.tsx`, vor der App | Fenstertitel je Seite (`seitenTitel`), Fokus auf die Hauptüberschrift nach einem Wechsel; `g-sprunglink` |

Seit B5 (27.10.2026) hat `Gruppe` eine Stufe (`stufe?`: 2, 3 oder 4) für ihre Überschrift: 3, wenn die Gruppe in
einem Abschnitt mit eigener h2 steht (die Gruppen der Aufgabenliste unter „Meine Aufgaben“).

Seit V4 (25.10.2026) kann `Gruppe` mehr: `zahl?` und `aktion?` rechts im Kopf, `fussAktion?` rechts unter der Fläche
neben der Fußnote (Klassen `g-gruppe-zahl`, `g-gruppe-aktion`, `g-gruppe-fuss`; so die Zugänge der Einstellungen),
`label?` und `flaecheKlasse?`. `Zeile` kann `links?` (ein eigenes Bedienelement links, etwa der Kreis zum Erledigen:
der Knopf in der Mitte deckt die Zeile, das Element liegt darüber; Klassen `g-zeile-bedient`, `g-zeile-ziel`,
`g-zeile-links`, `g-zeile-ueber` – die Aufgabenzeile benutzt diese Mechanik), `label?`, `wertZeit?` und `wertKlasse?`.
Die feinen Rastermaße des Kalenders stehen als `--g-kal-*` (Zeitspalte, Tag, Stunde, Punkte, Monatstag, Jahr); in der
Jahresansicht ist jeder Tag ein Ziel von 44 px (`--g-kal-jahr-tag`), schmal steht ein Monat je Zeile.

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
  seitlich“. Merkmal ist `data-rollt="waagrecht"` am Behälter (der Baustein `Segmente` setzt es), dazu
  `overflow-x: auto`; wo links oder rechts noch etwas verborgen ist, blendet der Rand sichtbar aus
  (`data-rand-links`/`data-rand-rechts`). `scripts/probe_seiten_ui.py` zählt die Glieder einer solchen Leiste nicht als
  Überstand, misst aber die Leiste selbst und die Seite: Die Seite rollt nie seitlich. Die alten Reiterleisten
  (`.task-tabs` usw.) gelten als solche, bis die Seiten den Baustein einsetzen.

## Hinweis mit „Rückgängig“ (25.10.2026, V4)

Was sich zurücknehmen lässt, fragt nicht vorher, sondern sagt danach in einer Zeile, was passiert ist, und bietet
„Rückgängig“ an – wie Mail auf dem iPhone: „„Angebot prüfen“ erledigt · Rückgängig“ (CLAUDE.md, Prüfpunkte 4 und 5).

- **Ein Ort, ein Hinweis.** Unten mittig über allem, dunkel (`--g-tinte`), schmal in voller Breite mit 16 px Rand. Ein
  neuer Hinweis ersetzt den alten. Er gehört der App, nicht der Seite: Er bleibt, wenn die Zeile mit der Aktion
  verschwindet oder die Seite wechselt (etwa nach „Akte anlegen“).
- **Zeit (Paket Z2, 27.10.2026).** Er steht mindestens 10 s, bei langem Satz länger (4 s plus 80 ms je Zeichen); Maus,
  Finger (gedrückt) oder sichtbarer Tastaturfokus halten ihn, danach beginnt die Zeit von vorn. Ein Fehler (auch ein
  misslungenes Zurücknehmen: „Nicht zurückgenommen. Die Änderung gilt weiter.“ mit „Erneut versuchen“) steht mindestens
  15 s und wird als Fehler angesagt. Bis 1.0.29 waren es 6 s, und Berühren am Handy hielt ihn nicht.
- **Nie der einzige Weg zurück (Z2).** Was der Hinweis anbietet, steht auch an der Sache selbst: Zurückgenommenes unter
  „Erledigt → Zurückgenommen“ mit „Wiederherstellen“, ein übernommener Vorschlag in der Aufgabe mit „Zurück zur
  Prüfung“, Erledigtes unter „Erledigt“. Deshalb ist die Zeitgrenze des Hinweises keine Grenze für das Zurücknehmen
  (WCAG 2.2.1).
- **Bedienung und Fokus (Z3).** Escape schließt ihn, ⌘Z bzw. Strg+Z nimmt zurück, aber nie in einem Eingabefeld. Der
  Fokus springt **nie** auf „Rückgängig“: Bis 1.0.29 tat er das, wenn der auslösende Knopf mit seiner Zeile verschwand,
  und ein zweites Enter nahm dann alles sofort zurück. Jetzt bleibt er am Auslöser (Umbenennen: auf dem Namen), wartet,
  solange der Auslöser gesperrt ist, und geht sonst auf die Liste oder den Abschnitt, in dem die Zeile stand
  (`grundlage/fokusZiel.ts`; `tabindex=-1`, kein neuer Tab-Halt). Dort löst ein zweites Enter nichts aus, Tab führt zur
  nächsten Zeile. Den Hinweis erreicht man mit Tab oder dem Kürzel, vorausgewählt ist er nicht.
- **Vorleser.** Der Ort ist immer da (`role=status`, `aria-live=polite`, `aria-atomic`), jeder neue Satz wird angesagt,
  bei „Rückgängig“ mit „Zurücknehmen mit Steuerung Z.“ (am Mac „Befehl Z“), nur für Vorleser; „Rückgängig“ nennt seine
  Tasten (`aria-keyshortcuts`). Bewegung 200 ms, bei reduzierter Bewegung keine.
- **Am Handy (Paket H).** Mit der Navigationsleiste unten hat er einen festen Platz direkt darüber. Lag dort etwas
  Bedienbares, rückt die Seite um diesen Platz nach oben: Was eben zu sehen war, bleibt zu sehen, er verdeckt nichts.
  Die Regel unten (Z3) gilt nur noch ohne Leiste (Einrichtung).
- **Am Handy ohne Leiste (Z3).** Bis 700 px steht er oben, wenn er unten Bedienbares verdecken würde und oben nicht. Solange er
  steht, hat die Seite unten Platz in seiner Höhe (`html.g-hinweis-offen`, `--g-hinweis-platz`), und was man gerade
  bedient hat, rückt aus ihm heraus. In einer dichten Liste kann er für seine Standzeit eine Zeile am Rand überdecken;
  sie lässt sich darunter hervorrollen.
- **Nie erfunden.** Ein Hinweis hat nur dann „Rückgängig“, wenn es dafür schon einen Weg im Sidecar gibt (die Gegenroute).
  Wo es keinen gibt, sagt er nur, was passiert ist, und eine Rückfrage davor bleibt.

| Aktion | Weg zurück (Sidecar) |
| --- | --- |
| Aufgabe erledigen / wieder öffnen (Liste, Heute, Aufgabe) | `POST /tasks/{id}/reopen` ↔ `/done` |
| Aufgabe verwerfen / wieder aufnehmen | `POST /tasks/{id}/reopen` ↔ `/drop` |
| „Warte auf …“ / „Zurück zu mir“ | `POST /tasks/{id}/zurueckholen` ↔ `/warten` (mit dem bisherigen Namen) |
| Aus deiner Post: „Ja, erledigt“ / „Ja, wieder bei mir“ | `POST /tasks/{id}/rueckgaengig` |
| Akte: Erledigt, Gilt nicht mehr, Gilt weiter, Abgesagt; „Rückgängig“ an einer Zeile | `PUT /akten/entscheidung` mit dem Vorwert ↔ `DELETE /akten/entscheidung` |
| Neue Akte? „Akte anlegen“ / „Nein danke“ (Akte und Heute) | `POST /akten/vorschlaege/{k}/zuruecknehmen` |
| Kreis wählen, „Wieder offen lassen“ | `PUT /kreis` mit dem Kreis von vorher ↔ `DELETE /kreis` |
| Art der Akte | `PUT /akten/art` mit der Art von vorher ↔ `DELETE /akten/art` |
| Alle Kollegen-Vorschläge festlegen (jetzt ohne Rückfrage) | `DELETE /kreis/sammel?sammlung=…` |
| Quelle: „Gehört nicht dazu“, „Doch zuordnen“, „Wer ist gemeint?“ | `PUT`/`DELETE /akten/quellen/{id}/zuordnung` |
| Quelle einem Projekt zuordnen; weitere Mails desselben Absenders | `PUT /episodes/{id}/project` mit dem Projekt von vorher; `PUT /episodes/projects` |
| Gruppenvorschlag für Organisationen ablehnen | `POST /organisation-group-suggestions/{id}/undo-dismissal` |
| Vorschlag übernehmen (einzeln, Z4) | `POST /task-candidates/aufgabe/{id}/zurueck` (auch später: „Zurück zur Prüfung“ in der Aufgabe) |
| „+ Aufgabe“ (Z4: bleibt in der Liste, „Öffnen“ im Hinweis) | `POST /tasks/{id}/drop` |
| Von Kingfisher angelegt: zurücknehmen / wiederherstellen | `POST /aufgaben-von-selbst/{id}/rueckgaengig` ↔ `/wiederherstellen` (auch später unter „Erledigt → Zurückgenommen“) |
| Welt-Meldung abbestellen (Quelle oder Sache; Paket S) | `POST /welt/abbestellen/rueckgaengig`: Feed, Weltquelle oder Sache wie vorher, die Meldung des Tages steht wieder da (später auch unter „Was Kingfisher darf“) |
| Mitschrift „Zu diesem Termin“ / „Gehört nicht hierher“ (Paket S) | `POST /transkripte/{id}/zuordnung/rueckgaengig`: genau der Stand von vorher, auch die Sperre nach dem Lösen fällt weg |

Ohne „Rückgängig“ (kein vollständiger Weg zurück), die Rückfrage bleibt, und sie ist seit B3 ein Dialog (`Rueckfrage`): Entscheidung zurücknehmen („Wirklich
zurücknehmen?“), eine Quelle nicht mehr verwenden (was daraus folgte, kommt nicht von selbst zurück), Sortierergebnis
verwerfen, eine Quelle entfernen. Ohne Rückfrage und ohne Zurück wie bisher: einen Vorschlag aus
der Post verwerfen, einen Aufgabenvorschlag ablehnen. Eigene „…rückgängig“-Knöpfe mit Versionen (Ordner, Bilder,
Gruppierungen im Gedächtnis) bleiben, wo sie sind.

**Abbestellen und Mitschrift zuordnen (Paket S, 27.10.2026).** Hier stand bis Paket B, beide fragten vorher; der Code
fragte nicht, und es gab auch keinen Weg zurück. Entschieden nach Prüffrage 5 („Kann er es rückgängig machen? Wo ja,
braucht es keine Rückfrage“): Beide bekamen einen vollständigen Weg zurück (die Meldung des Tages kommt wieder, die
Sperre nach dem Lösen fällt weg), und deshalb keine Rückfrage, sondern den Hinweis mit „Rückgängig“. Eine Rückfrage vor
einem Klick, der sich ganz zurücknehmen lässt, wäre eine Entscheidung zu viel.

## Barrierefreiheit (Paket B, 27.10.2026)

Maßstab ist WCAG 2.2 AA, geprüft mit Tastatur und dem Barrierefreiheitsbaum (Protokoll:
[`runs/2026-10-26-befunde-barrierefrei`](runs/2026-10-26-befunde-barrierefrei/README.md)).

- **Rückfragen sind Dialoge.** Eine Frage vor etwas, das sich nicht zurücknehmen lässt, steht nicht mehr als Satz in der
  Zeile, sondern als ruhiges Blatt über der Seite (`Rueckfrage`): die Frage in einem Satz, höchstens ein Satz dazu, rechts
  „Abbrechen“ (vorausgewählt) und die Aktion, rot getönt, wenn sie etwas entfernt. Tab bleibt im Dialog, Escape bricht ab,
  danach steht der Fokus wieder am Auslöser, und ist der mit seiner Zeile verschwunden, auf der Liste (`fokusZiel`, Z3).
  Solange die Aktion läuft, bleiben die Knöpfe stehen (`aria-disabled`), und ein Fehler steht im Dialog. Kein eigenes
  `role=alertdialog` und keine Bestätigungsgruppe in einer Zeile (`tests/rueckfrage.test.mjs` sucht danach).
- **Wo bin ich?** Jede Seite trägt ihren Namen im Fenstertitel („Aufgaben – Kingfisher“, ein Gespräch oder eine Akte mit
  ihrem Namen davor). Geht beim Seitenwechsel der Fokus verloren, steht er auf der Hauptüberschrift (`tabindex=-1`, kein
  Tab-Halt); was die neue Seite selbst fokussiert, bleibt. „Zum Inhalt springen“ ist der erste Tab-Halt und erscheint nur
  mit Fokus. Kein `scrollIntoView` ohne Fokus: Chrome setzt damit den Ausgangspunkt für Tab (`segmentInsBild`).
- **Die Antwort wird angesagt.** Ist eine Antwort im Gespräch fertig, sagt der Ort für Ansagen ihren Anfang einmal an
  (ein bis zwei Sätze, ohne Markdown und Belegnummern, `antwortAnsage.ts`); den Zwischenstand sagt nur die Wartezeile in
  Schritten. Der Fokus bleibt im Eingabefeld, auch nach dem Sendeknopf und wenn die Frage auf einer anderen Seite begann.
- **Fokus sichtbar.** Felder zeigen ihn als Kante von 2 px in der Auswahlfarbe (`outline`, nicht als Schatten, den lokale
  Regeln überschreiben); Felder, deren Rahmen fokussiert wird (Suche und Eingabe im Gespräch), am Rahmen. Keine Regel nimmt
  den Fokus weg, ohne dass ein Rahmen ihn zeigt.
- **Kontrast.** Platzhalter haben eine Rolle, `--g-platzhalter` `#5a6776` hell und `#9aa6b2` dunkel, mindestens 4,8:1
  auf jedem Feldgrund (bis 1.0.29 `#8592a0`, 2,6–3,2:1). Auf dem Bergbild von Heute steht der Stand in Tinte und tritt über
  die Strichstärke zurück, nicht über die Farbe. Die Zahl im Segment ist Tinte zu 72 %.
- **Kalendermonat.** Ein Raster (`role=grid`, Wochen als Zeilen über `subgrid`, Wochentage als Spaltenköpfe) mit einem
  Tab-Halt auf dem gewählten Tag. Pfeiltasten von Tag zu Tag, Pos1/Ende zur Woche, Bild auf/ab einen Monat; Enter öffnet
  die Termine des Tages in der Liste darunter. Jeder Tag heißt „Dienstag, 27. Oktober, 2 Termine, heute“ und ist als ganze
  Fläche das Ziel; die Termine im Tag sind Zeichen ohne eigenen Tab-Halt, mindestens 24 px hoch (`calendarGrid.ts`).
- **Überschriften.** Ein h1 je Seite, keine Sprünge, keine doppelten h1/h2. Was unter dem Seitentitel als Liste steht,
  trägt seinen Namen als h2 (sichtbar steht er im Segment); die Mail im Lesebereich beginnt mit ihrem Betreff als h2.

## Handy (Paket H, 27.10.2026)

Maßstab: ein Daumen, 390 px, oft dunkel (Persona „Leon Krüger“; Protokoll:
[`runs/2026-10-26-befunde-handy`](runs/2026-10-26-befunde-handy/README.md)). Alles gilt bis 700 px Breite bzw. mit
grobem Zeiger; breit bleibt die Oberfläche, wie sie war.

- **Navigation unten.** Eine feste Leiste wie am iPhone, über `safe-area-inset-bottom` (`viewport-fit=cover`): Heute,
  Gespräche, Aufgaben, Kalender, jedes mit Zeichen und Namen, und „Mehr“. „Mehr“ klappt darüber Nachrichten, Gedächtnis
  („Menschen, Dokumente und Suche“) und Einstellungen auf, je mit einem Satz; Escape oder ein Tipp daneben klappt zu.
  Steht die Seite unter „Mehr“, trägt „Mehr“ die Markierung. Warum diese vier: Unterwegs entscheidet man, was dran ist,
  fragt, hakt ab und sieht nach, wann und wo; Post hat das Handy selbst (das Wichtige daraus steht auf Heute), das
  Gedächtnis fragt man meist über Gespräche ab. Die Seite hat unten Platz in Höhe der Leiste (`--g-unten`); was unten
  klebt (Hinweis, Auswahl unter „Zur Prüfung“, Detailpaneel), steht darüber (`HandyLeiste.tsx`, `handyZiele.ts`).
- **Projekte an einem Ort.** Sie stehen unter Aufgaben → Projekte (anlegen, Status, Aufgaben, Board), jedes mit „Akte
  öffnen“. „Gedächtnis → Projekte“ zeigte dieselben Projekte noch einmal; es ist kein Segment mehr, das Gedächtnis
  verweist mit „Projekte unter Aufgaben“ dorthin, und alte Verweise (`/memory?tab=projects`) führen dorthin
  (`projekteOrt.ts`).
- **Kalender.** Vorgabe am Handy ist die Liste: die nächsten sieben Tage ab heute, je Termin Uhrzeit, ganzer Titel und
  Ort. Breit bleibt es der Monat. Gemerkt wird nur, was der Nutzer im Umschalter wählt (`kalenderAnsicht.ts`); bis 1.0.29
  schrieb die Seite jede Ansicht zurück, auch die Vorgabe. Die Woche zeigt schmal alle sieben Tage (je mindestens 44 px),
  der Monat rollt beim Öffnen die Woche des gewählten Tages ins Bild (ohne `scrollIntoView`). Titel brechen an
  Wortgrenzen und trennen mit Strich (`hyphens: auto`, `lang="de"`), nie `overflow-wrap: anywhere`.
- **Tippziele 44 × 44.** Mit grobem Zeiger (`pointer: coarse`) hat jedes Bedienelement eine Trefffläche von mindestens
  44 × 44 px. Das Bild bleibt ruhig: Leise Knöpfe, Verweise, Segmente und Belegnummern bekommen eine unsichtbare Fläche
  (`::after`, mittig, `max(100%, 44px)`); getönte Knöpfe, Felder und Aufklapper werden 44 hoch. Im Zeitstrahl der Akte ist
  am Finger die ganze Spur das Ziel, ein Tipp wählt den nächsten Punkt (wie der Tag im Monat).
  `scripts/probe_tippziele_ui.py` misst die wirksame Fläche aller Bedienelemente auf 29 Seiten und Zuständen und meldet
  jedes unter 44 px.

## Dunkelmodus vom 25.10.2026

**Entscheidung des Nutzers** am 25.10.2026 („Mach alles“ auf die Frage nach dem Dunkelmodus): Die Arbeitsflächen folgen
dem Systemmodus des Macs (`prefers-color-scheme`). Das ersetzt die Festlegung vom 15.10. („auch bei dunkler
Systemeinstellung bleiben die Arbeitsflächen hell“). Der helle Modus bleibt Pixel für Pixel, wie er war; die
Navigation bleibt in beiden Modi dunkel.

**Alle Farben sind Rollen.** Farbwerte stehen nur noch in den `:root`-Blöcken von `theme.css` (Werte des Bestands),
`CalmUI.css` (`--calm-*`), `NordicWorkspace.css` (`--nordic-*`) und `Grundlage.css` (`--g-*`), jeweils mit einem
Block `@media (prefers-color-scheme: dark) { :root { … } }` darunter. Alles andere – die übrigen CSS-Dateien,
Inline-Stile, Skripte (Kalender, Karte) – benutzt Rollen; Hauch, Haarlinie und Schatten mit eigener Deckkraft als
`rgba(var(--g-tinte-rgb), .05)` bzw. `rgba(var(--g-schatten-rgb), .06)`. `tests/farbrollen.test.mjs` verbietet harte
Werte außerhalb dieser Blöcke (auch Ersatzwerte in `var(--x, #…)`) und prüft, dass jede helle Rolle einen dunklen Wert
hat.

| Rolle | hell | dunkel |
| --- | --- | --- |
| Grund `--g-grund`, `--calm-inset` | `#f5f6f8` | `#181d23` (gedämpftes Schiefer, kein Schwarz) |
| Fläche `--calm-surface` | `#ffffff` | `#222931` (eine Stufe heller als der Grund) |
| Weich `--calm-soft` | `#e7eff8` | `#2c3640` |
| Tinte `--calm-ink` | `#172635` | `#e3e8ed` (nicht reinweiß) |
| Leise `--calm-muted` | `#5e6c7c` | `#a8b4c0` |
| Linie `--calm-line`, `--g-linie` | `#dfe5eb`, Tinte 8 % | `#38414b`, Tinte 10 % |
| Akzent und Verweis `--calm-primary`, `--calm-link` | `#103e5c`, `#18578c` | `#96bde0` (ein Akzent; der Text darauf `#0f1923`) |
| Auswahl `--nordic-selection` / Kante | `#e8f2fd` / `#2869aa` | `#263a4e` / `#79aee0` |
| Rot `--g-rot`, Grün `--g-gruen` | `#bf3b44`, `#197a58` | `#f08b8b`, `#6ccb9c` |
| Warnung `--g-warnung` auf `--g-warnung-grund` | `#704b0b` auf `#fff2d8` | `#e6c27a` auf `#3a3121` |
| Hinweis `--g-hinweis-grund` | Tinte | `#39434f` (erhöht, kein heller Balken) |
| Gewähltes Segment `--g-segment-gewaehlt` | Fläche | `#3a4450` |
| Navigation `--nordic-nav` | `#082a3d` | gleich, dazu eine Haarlinie zur Arbeitsfläche |

**Kontrast.** Text mindestens 4,5:1, große Schrift und Bedienelemente 3:1 (WCAG AA), in beiden Modi; die Hauptpaare
rechnet der Test nach, die Seiten misst `kontrast.js` im Rundgang (Bericht V5).

**Sonderfälle.**

- *Landschaft im Kopf von Heute:* Der Verlauf läuft in den Grund des Modus aus (`--g-grund-rgb`); im Dunkeln liegt
  ein Schleier darüber (`filter: brightness(.5) saturate(.8)`), der Gruß steht in heller Tinte. Der Eisvogel bleibt.
- *Seitenleiste:* bleibt dunkel und unverändert; eine Haarlinie (`--nordic-nav-glanz`) trennt sie vom dunklen Grund.
- *Karte (Leaflet):* Die Kacheln bleiben, wie OpenStreetMap sie liefert, und werden im Dunkeln nur gedämpft; Knöpfe,
  Quellenzeile und Namensschild in den Flächen der App. Die Punkte (`--g-ort*`) stehen auf den hellen Kacheln und
  bleiben deshalb gleich.
- *Mailinhalt:* Kingfisher zeigt Mails als Text in den Flächen der App, nicht als HTML; im Dunkeln ist er helle Tinte
  auf dunkler Fläche. Sollte HTML je gezeigt werden, dann auf einer eigenen hellen Fläche.
- *Kalenderfarben:* sieben Rollen `--g-kal-farbe-1 … 7`, `calendarColor()` liefert `var(--g-kal-farbe-N)`; dunkel
  heller, mindestens 3:1 auf der Fläche.
- *Schalter:* grau aus, Akzent an, der Knopf bleibt weiß. *Fokus:* 2 px in der Auswahlkante. *Bilder* (Eisvogel,
  Landschaft, Logo, Symbole) bleiben, wie sie freigegeben sind.

**Ausnahmen** (in `tests/farbrollen.test.mjs`): Masken (`mask-image`) nutzen nur die Deckkraft; `leaflet.css` aus dem
Paket wird überschrieben, nicht geändert; die Fensterleiste (`theme-color` in `index.html`) trägt die Farbe der
Navigation.

## Wo der Grundsatz vorgeht

Diese Seite steht unter `CLAUDE.md`, nicht daneben. Wenn Eleganz und
Verständlichkeit sich widersprechen, gewinnt Verständlichkeit — aber dann ist
die Aufgabe, das Verständliche schön zu machen, nicht das Schöne aufzugeben.

Und keine dieser Regeln hebt eine Sicherheitszusage auf. Eine Freigabekarte
darf ruhig unschön sein, solange sie vollständig ist.
