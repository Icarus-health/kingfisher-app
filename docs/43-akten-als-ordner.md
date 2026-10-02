# Akten als Ordner (M2): nur lesend, für Obsidian oder jeden Editor

Stand: 30. September 2026 (Schema unverändert, keine Migration). Baut auf
[`30-akten.md`](30-akten.md) (Akten) und [`32-lage.md`](32-lage.md) (Lage) auf. Code:
`sidecar/icarus_memory/akten_markdown.py` (Inhalt und Dateien),
`akten_export_routes.py` (Einstellung, Schreiblauf, Übergabe), `atomic.ordner_tauschen`;
Mac-Helfer `scripts/mac_folder_worker.py` (Rolle `akten`); Oberfläche
`AktenOrdnerSettings.tsx`, `aktenOrdner.ts`. Tests: `test_akten_markdown.py`,
`test_akten_export_routes.py`, `test_mac_akten_worker.py`, `akten-ordner.test.mjs`;
Browserprobe `scripts/probe_akten_ordner_ui.py`.

## Was es ist und was nicht

Die Akten liegen in SQLite und sind nur in der Oberfläche sichtbar. Der Export legt sie als
lesbaren, verlinkten Markdown-Ordner ab, damit der Nutzer sie dort hat, wo er ohnehin schreibt.

**Das Gedächtnis ist Kingfisher. Der Ordner ist nur eine lesbare Ausgabe, damit die Akten ohne
Kingfisher lesbar bleiben; er ist kein Einschluss ins eigene Format.** Nichts fließt zurück:
Kingfisher liest aus dem Ordner nie etwas, weder Dateien noch Änderungen. Wer eine Akte
korrigieren will, tut es in Kingfisher; beim nächsten Schreiben steht es auch im Ordner.
Der Ordner wird bei jedem Schreiben überschrieben, auch eigene Änderungen darin.

**Der Ordner enthält Klartext** aus Mails, Terminen und Notizen. Er ist nicht verschlüsselt und
verlässt den Rechner nicht, solange der Nutzer ihn nicht selbst in einen synchronisierten oder
geteilten Ordner legt. Deshalb ist der Export aus, bis jemand einen Ordner wählt, und
„Quellen mitschreiben“ (der Rohtext der Quellen) ist zusätzlich aus.

## Wo in der Oberfläche

Bewusst nicht vorne. Die Karte **Akten als Ordner** steht unter **Einstellungen → Für Techniker** in
einem eingeklappten Abschnitt **Für Techniker** am Ende. Einen Bereich „Gedächtnis“ gibt es in den
Einstellungen noch nicht; ein späterer Umbau kann den Abschnitt dorthin nehmen. Weder die Startseite
noch der Erststart-Assistent verweisen darauf (die Browserprobe prüft das).

Die Karte: Ordner wählen (Vorgabeordner `Dokumente/Kingfisher/Akten` oder Auswahldialog des Mac,
nie ein getippter Pfad), Schalter „Akten in den Ordner schreiben“, Schalter „Quellen mitschreiben“,
„Jetzt schreiben“, „Ordner trennen“, dazu ein Satz zum letzten Stand („Zuletzt geschrieben: Di.,
29. Sept., 05:30, 102 Dateien.“) oder der Grund, warum nichts geschrieben wurde. Ein einziger
gefüllter Knopf, und nur, solange noch kein Ordner gewählt ist. Das Auswählen im Dialog ist die
Freigabe dieses einen Ordners und schaltet den Export ein. Trennen löscht nichts beim Nutzer.

## Der Ordner

```
Kingfisher Akten/
  index.md                 Katalog aller Akten nach Art, mit Stand-Datum
  _README.md               erzeugt von Kingfisher, wird überschrieben, nichts fließt zurück, Klartext
  .kingfisher-akten        Marke (nur ein Ordner mit ihr wird je ersetzt)
  Personen/Anna Keller.md
  Organisationen/…  Projekte/…  Themen/…  Orte/…
  Quellen/<id>.md          nur mit „Quellen mitschreiben“: der Rohtext
```

Je Akte eine Datei mit Frontmatter (für Obsidian-Dataview lesbar):

```yaml
---
art: "projekt"
sache_id: "projekt:p-f16e7edecb1f"
name: "Mainz"
stand: 2026-09-30
kingfisher_version: "0.1.0"
quellen: 2
---
```

Darunter, soweit vorhanden: **Lage** (nur die geprüften Sätze, Ebene 3), **Stand**, **Offene
Punkte** (weiterhin „vermutlich“, samt „vermutlich erledigt“), **Fristen** (kommend, verstrichen,
überholt, Zeitangaben ohne Datum), **Termine**, **Aufgaben**, **Verlauf** und **Beziehungen**.
Beziehungen stehen doppelt: als `[[Personen/Anna Keller|Anna Keller]]` (Obsidian) und als
gewöhnlicher Link `[Anna Keller](../Personen/Anna%20Keller.md)` (jeder andere Editor).

**Jeder Satz trägt einen Belegverweis:** `Quelle: Titel, TT.MM.JJJJ · kingfisher://quelle/<id>`
und, wenn „Quellen mitschreiben“ an ist, zusätzlich `[[Quellen/<id>]]` und der Pfad
`Quellen/<id>.md`. `kingfisher://quelle/<id>` ist die Kennung für eine spätere Verknüpfung mit
dem Mac-Fenster; ein Schema-Handler dafür ist noch nicht registriert.

**Sichere Namen.** Keine Pfadtrennzeichen, keine Zeichen, die Obsidian in Links oder ein
Dateisystem ablehnt (`\ / : * ? " < > | # ^ [ ]`, Steuerzeichen), keine Punkte oder Leerzeichen am
Rand, höchstens 100 Byte, reservierte Windows-Namen mit Unterstrich. Kollisionen, auch solche nur in
der Groß-/Kleinschreibung (der Mac unterscheidet sie nicht), behalten beim ersten den schlichten
Namen; die übrigen bekommen ein festes Suffix aus ihrer Kennung (`Anna Keller (a1b2c3)`). Die
Vergabe folgt Art, Name und Kennung, nicht der Datenbank.

**Deterministisch.** Gleicher Bestand und gleicher Tag ergeben byte-gleiche Dateien: feste
Reihenfolge, keine Uhrzeit des Schreibens, kein Zufall. Das „Stand“-Datum ist der Tag des Schreibens
in der Zeit des Nutzers; kommend und verstrichen rechnet die Akte wie in der Oberfläche.

## Zwei Schritte, weil der Sidecar im Container läuft

Der Sidecar kann keinen Ordner auf dem Mac beschreiben und soll es auch nicht können. Darum:

1. Der Sidecar baut den Ordner **atomar** in seinem Datenbereich (`<Daten>/akten-export`): in einen
   Nachbarordner schreiben, dann tauschen (`atomic.ordner_tauschen`). Wer liest, sieht die alte oder
   die neue Fassung, nie eine halbe; bricht etwas ab, bleibt die alte Fassung, und ein Abbruch
   zwischen den zwei Umbenennungen wird beim nächsten Lauf geheilt.
2. Der **Mac-Helfer** (`mac_folder_worker.py --role akten`, startet mit der Kingfisher-App) holt ihn
   als ZIP ab (`GET /api/v1/akten/export/archiv`) und legt ihn im vom Nutzer gewählten Ordner als
   Unterordner **`Kingfisher Akten`** ab, ebenfalls atomar. Ersetzt wird nur ein Ordner mit der Marke
   `.kingfisher-akten`. Liegt dort schon etwas anderes (ein Ordner ohne Marke, eine Datei, ein
   Verweis), bleibt es unberührt, und die Karte nennt den Grund in einem Satz. Das Archiv wird vor dem
   Schreiben geprüft (keine absoluten oder aufwärts führenden Pfade, begrenzte Größe, Marke
   vorhanden). Wählt der Nutzer den Vault, bleiben alle anderen Dateien darin unberührt.

Der Helfer schreibt nur in den Ordner, den der Server als den freigegebenen kennt. Nach „Ordner
trennen“ vergisst er seinen gemerkten Ordner.

## Wann geschrieben wird

* **Nach jedem Nachführen der Akten** (`akten_routes.nachfuehren` ruft `akten_export_routes.anstossen`,
  ein Aufruf): nur bei eingeschaltetem Schalter und gewähltem Ordner, nur wenn sich im Bestand etwas
  geändert hat (Änderungsstand der Bezüge, nach dem eigenen Lauf neu gemerkt, damit das Schreiben sich
  nicht selbst anstößt), nur wenn alle Bezüge berechnet sind, **höchstens alle 120 Sekunden** und
  **nie zweimal gleichzeitig**. Ein wegen der Drossel übergangener Anstoß wird mit einem Zeitgeber
  nachgeholt (nie mehr als einer).
* **Auf Knopfdruck** (`POST /api/v1/akten/export`), sofort, auch wenn sich nichts geändert hat: Der
  Ordner wird dem Helfer neu angeboten. Die Antwort wartet bis zu 10 Sekunden; dauert es länger, meldet
  sie `laeuft`, und die Karte fragt nach.
* Bei Änderung von „Quellen mitschreiben“ und beim Einschalten, sofort.
* Bleibt der Inhalt gleich (gleiches Paket), wird nichts neu abgelegt und dem Helfer nichts Neues
  angeboten.

Ein Fehler beim Schreiben kippt nie eine Anfrage. Die Meldung nennt den Grund ohne Akteninhalt („Die
Akten konnten nicht als Ordner geschrieben werden. Ein neuer Versuch folgt.“), der alte Stand bleibt.

## Schnittstelle (`akten_export_routes.py`)

| Route | Zweck |
|---|---|
| `GET /api/v1/akten/export` | Stand: Schalter, Ordner, Dateizahl und Zeit des Schreibens, ob es auf dem Mac angekommen ist, ob der Helfer sich meldet, Grund eines Fehlers |
| `PUT /api/v1/akten/export` | `aktiv`, `quellen` |
| `POST /api/v1/akten/export` | „Jetzt schreiben“ (ohne Ordner: 409 mit einem Satz) |
| `POST /api/v1/akten/export/ordner`, `DELETE …/ordner/auswahl`, `DELETE …/ordner` | Auswahl anfordern (`vorgabe` oder `waehlen`), abbrechen, trennen |
| `POST …/worker`, `GET …/archiv`, `POST …/gespiegelt` | Protokoll des Mac-Helfers |

Gespeichert ist der Stand in den Einstellungen (`akten_export`: `aktiv`, `quellen`, `ordner`, Stand
des Schreibens, Stand der Übergabe); die Anfrage „Ordner wählen“ lebt nur im Speicher. Keine Route
nimmt Dateien oder Text aus dem Ordner an (ein Test prüft die Schnittstelle).

## Prüfungen

Sabotageproben: jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck im Code ersetzt) und
geprüft, dass ein Test fehlschlägt. Das Ergebnis steht unten. Die Proben liegen nicht im
Repository; wer sie wiederholen will, ersetzt die genannten Ausdrücke.

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| N1 | Kollisionen werden ohne Groß-/Kleinschreibung verglichen | `test_akten_markdown` (Kollisionen) |
| N2 | Pfadtrennzeichen fallen aus Dateinamen | `test_akten_markdown` (Dateinamen sind sicher) |
| N3 | Die Reihenfolge der Eingabe ändert die Dateien nicht | `test_akten_markdown` (Determinismus) |
| N4 | Ohne Schalter keine Quellen und keine Verweise darauf (die erste Fassung des Tests prüfte nur den Rohtext, nicht die Verweise; die Probe führte zur Ergänzung) | `test_akten_markdown` (Quellen nur mit Schalter) |
| N5 | Frontmatter trägt `sache_id` | `test_akten_markdown` (Frontmatter) |
| N6 | Jeder Satz trägt `kingfisher://quelle/<id>` | `test_akten_markdown` (Belegverweis) |
| N7 | Schreiben tauscht atomar, statt ins Ziel zu kopieren | `test_akten_markdown` (ersetzt vollständig) |
| N8 | Unsichere Pfade im Export werden abgelehnt | `test_akten_markdown` (unsichere Pfade) |
| N9 | Bricht das Einsetzen ab, kommt die alte Fassung zurück | `test_akten_markdown`, `test_mac_akten_worker` (Tausch in Helfer und Sidecar gleich) |
| N10 | Ein `\|` im Namen zerreißt keinen Wiki-Link (ein echter Fehler, den der Test beim Schreiben fand) | `test_akten_markdown` (Linkzeichen) |
| N11 | Ist der Schalter aus, wird nichts selbsttätig geschrieben (die erste Fassung des Tests war wirkungslos: die Drossel war der Grund; Gegenprobe mit Schalter an ergänzt) | `test_akten_export_routes` (Schalter aus) |
| N12 | Die Drossel hält Läufe zurück und holt genau einmal nach | `test_akten_export_routes` (Drossel) |
| N13 | Nie zwei Läufe gleichzeitig | `test_akten_export_routes` (nie zwei Läufe) |
| N14 | Eine Ordnerwahl ohne passende Anfrage wird nicht übernommen | `test_akten_export_routes` (fremde Wahl) |
| N15 | Eine veraltete Rückmeldung des Helfers wird nicht einmal vorgemerkt (die erste Fassung des Tests sah nur die Anzeige; Prüfung des gespeicherten Stands ergänzt) | `test_akten_export_routes` (veraltete Meldung) |
| N16 | Trennen räumt den Ordner im Sidecar weg | `test_akten_export_routes` (Trennen) |
| N17 | Fehlermeldungen enthalten keinen Akteninhalt | `test_akten_export_routes` (Fehler beim Schreiben) |
| N18 | Der Helfer ersetzt keinen fremden Ordner gleichen Namens | `test_mac_akten_worker` (fremder Ordner) |
| N19 | Der Helfer prüft die Pfade im Archiv | `test_mac_akten_worker` (unsichere Pfade) |
| N20 | Der Helfer schreibt nur in den Ordner, den der Server als freigegeben kennt | `test_mac_akten_worker` (nur in den Ordner des Servers) |
| N21 | Der Helfer vergisst seinen Ordner nach dem Trennen | `test_mac_akten_worker` (Abbruch und Trennen) |
| N22 | Bei gemeldetem Grund wird dasselbe Paket nicht endlos neu angeboten | `test_akten_export_routes` (veraltete Meldung, Fehler) |

Alle 22 Proben wurden von mindestens einem Test gefangen; drei waren in der ersten Fassung
wirkungslos (N4, N11, N15) und führten zu je einer Ergänzung des Tests.

Browserprobe (`python scripts/probe_akten_ordner_ui.py --ausgabe DIR`, PYTHONPATH: `sidecar` und
Wurzel): echte Oberfläche in Chromium, echter Server mit der synthetischen Welt der Messlatte, der
Mac-Helfer als echter Code per HTTP, der Auswahldialog durch einen temporären Ordner ersetzt.
Bestanden: Abschnitt eingeklappt, ohne Ordner nichts zu tippen und ein gefüllter Knopf, Wahl,
Stand „zuletzt geschrieben“ (102 Dateien), Vorgabe „Quellen“ aus und dann Rohtext im Ordner erst
mit Schalter, „Jetzt schreiben“ stellt geänderte Dateien wieder her, Ausschalten und Trennen
löschen nichts, der Helfer vergisst den Ordner, keine Spur auf Startseite und im Assistenten, leere
Konsole. Bilder liegen bei der Lieferung im Arbeitsbereich, nicht im Repository.

## Offene Punkte

* **Nicht in Obsidian selbst geprüft.** Geprüft ist, dass Wiki-Links, Frontmatter und Namen den
  Regeln von Obsidian und Dataview folgen, nicht der Ordner in der Anwendung.
* **Helfer nur als Code getestet.** Der Dialog (`osascript`) und der Zugriff auf `Dokumente` (Freigabe
  des Mac) laufen nur auf dem Mac und sind hier nicht erprobt.
* **Jedes Schreiben baut alles neu** (alle Akten mit `alle`), bei sehr großem Bestand in einigen
  Sekunden bis Minuten im Hintergrund; gemessen ist das hier nur an der Welt der Messlatte.
* **`kingfisher://quelle/<id>`** ist noch kein registrierter Verweis; die Kennung steht bereit.
* **Die Einstellungsseite ist auf dem Handy breiter als der Schirm** (Bestand, nicht diese Karte);
  die Karte bleibt in ihrem Bereich.
* Der Export wird nicht gesichert oder wiederhergestellt (abgeleitet, jederzeit neu erzeugbar).
