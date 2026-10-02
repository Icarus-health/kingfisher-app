# Rückkanal für Fehler: „Stimmt nicht?“

Stand: 30. September 2026. Die erste Woche im Alltag ist der Test, den keine synthetische
Welt ersetzt ([`DEVELOPER-START.md`](DEVELOPER-START.md), „Eine Woche Alltag“). Was dabei
auffällt, darf nicht in einem Gefühl bleiben. Der Rückkanal macht aus „das war falsch“ mit
einem Klick eine Meldung, und aus der Meldung einen Fall für die Messlatte.

Das Gegenstück für Antworten, die stimmen, steht in [`45-uebernehmen.md`](45-uebernehmen.md) („In die Akte
übernehmen“, neben „Stimmt nicht?“; dort entsteht ein Vorschlag, hier nur eine Notiz).

Code: `rueckmeldung.py` (Ablage), `rueckmeldung_faelle.py` (Umwandlung), `rueckmeldung_routes.py`
(Routen), `messlatte/faelle.py` (Befehl). Oberfläche: `Rueckmeldung.tsx`, `rueckmeldung.ts`.
Tests: `sidecar/tests/test_rueckmeldung.py`, `messlatte/tests/test_faelle.py`,
`app/kingfisher/tests/rueckmeldung.test.mjs`. Browserprobe: `scripts/probe_rueckkanal_ui.py`.

## Was es tut

**Melden.** Unter jeder Antwort im Gespräch steht still „Stimmt nicht?“. Der Klick fragt in einem
Satz, was nicht stimmt, mit fünf Arten zur Auswahl (Falsch, Unvollständig, Veraltet, Zu langsam,
Etwas anderes) und einem freiwilligen Feld „Richtig wäre …“. Nach „Melden“ steht dort „Gemerkt.“.
Rückfragen und Auswahlfragen von Kingfisher sind keine Antworten und tragen den Link nicht.

**Was die Meldung festhält** (`rueckmeldungen.sqlite3`, Tabelle `rueckmeldung`): Zeitpunkt, Frage,
die Antwort so, wie der Nutzer sie las, ihre Satz- und Belegstruktur (Sätze mit Belegnummern,
Belege mit Kennung und Titel, kein Quellentext), die Kennungen der Quellen, auf die sie sich
stützte, der Modellstand (je Rolle Anbieter, Modell, lokal oder nicht, ohne Schlüssel und
Adressen), die Art, der Freitext und der Stand `offen` oder `erledigt`. Die Oberfläche schickt nur
Gespräch, Nachricht, Art und Freitext; alles andere liest der Server selbst aus der Gesprächsansicht
(`app.state.gespraech_ansicht`, dieselbe Ansicht wie `GET /api/v1/conversations/{id}`). Was gemeldet
wird, ist damit, was gesagt wurde, und nicht, was ein Browser behauptet. Wer dieselbe Antwort noch
einmal meldet, ersetzt die alte Meldung (Art, Freitext) und öffnet sie wieder.

**Liste.** Einstellungen, „Rückmeldungen“: Anzahl und offene, je Meldung Frage, Art, Datum und
„Richtig wäre“, dazu „Erledigt“. Erledigt löscht nichts.

**Routen** (alle mit Token): `POST /api/v1/rueckmeldungen`, `GET /api/v1/rueckmeldungen`
(`?status=offen|erledigt`), `PATCH /api/v1/rueckmeldungen/{id}/erledigt`,
`GET /api/v1/rueckmeldungen/faelle`.

**Sicherung.** Die Datei steht in `SQLITE_DATA_FILES` wie `gespraeche.sqlite3`, in der
Schema-Vorabprüfung vor Updates (`update_backup`) und wird nach einer Wiederherstellung neu
geöffnet. `test_every_backup_store…` legt eine Meldung an und prüft sie nach der Wiederherstellung.

## Was es nicht tut

* Es **schreibt nichts ins Gedächtnis**: kein Vorschlag, keine Aussage, keine Korrektur einer
  Quelle oder Akte, kein Widerruf. Eine Meldung ist eine Notiz an die Entwicklung. Das Gedächtnis
  korrigiert weiter nur über Vorschlag und Annahme (`10-verdichtung.md`).
* Es tut **nichts Außenwirksames**: nichts wird gesendet, geteilt oder hochgeladen.
* Es **behebt nichts** und ändert die Antwort nicht. Wer den Fehler behebt, ist die Entwicklung,
  und sie tut es, nachdem der Fall in der Messlatte steht.
* Es **misst nicht selbst**. Die Messung bleibt `python -m messlatte lokal`.

## Vom Klick zur Messlatte

Die Oberfläche nennt keinen Befehl (Fremdprobe, Befund 16). Unter „Für Techniker“ sagt sie in einem Satz, was aus
einer Meldung wird („Jede Meldung wird eine Prüffrage …“), und bietet die Datei zum Speichern an. Unter der Antwort
steht nach „Melden“ nur, was die Nutzerin wissen muss: „Gemerkt. Kingfisher soll diesen Fehler nicht wieder machen.“,
dass die Meldung auf dem Rechner bleibt, und wo sie steht; „Prüffrage“, „Messlatte“ und „wer Kingfisher verbessert“
stehen dort nicht (Fremdprobe 3, Befund 11). Die Befehle stehen nur hier:

```sh
# Einstellungen, Für Techniker, Rückmeldungen, „Als Prüffragen speichern“ (Datei rueckmeldungen-faelle.json)
# oder ohne Oberfläche, aus dem Datenordner (wird nur gelesen):
python -m messlatte faelle --aus <Datenordner>/rueckmeldungen.sqlite3 --ausgabe rueckmeldungen-faelle.json
python -m messlatte lokal --fragen rueckmeldungen-faelle.json
```

`--aus` nimmt auch die Antwort von `GET /api/v1/rueckmeldungen` als JSON-Datei. Beide Wege
benutzen dieselbe Umwandlung (`rueckmeldung_faelle.py`); der Test vergleicht sie. Die Datei hat
das Format von `messlatte/beispiel-eigene-fragen.json` (Kategorie `eigene`) und wird mit
demselben Prüfer geladen wie bei `lokal`; `messlatte faelle` liest sie danach probeweise und
meldet Fehler sofort.

| Aus der Meldung | im Fall |
|---|---|
| Frage | `frage` |
| „Richtig wäre …“ | `erwartet.aussagen`: der Text als Pflichtaussage (`[["…"]]`) |
| Art `falsch`, `veraltet` | `schwere: kritisch`, `verboten.aussagen`: die gemeldete Antwort (bei genau einem Satz dieser Satz) |
| Belege der Antwort | bei `falsch`, `veraltet` als `verboten.belege` (in `lokal` ohne Wirkung) |
| andere Arten | `schwere: normal` |
| Art, Datum, erledigt | `notiz` |

**Grenzen, ehrlich.** Die Messlatte sucht Aussagen als Teilstück im Antworttext. „Richtig
wäre …“ trifft deshalb zuverlässig, wenn dort etwas Kurzes steht („15. November“), und schlecht,
wenn ein ganzer Satz steht. Die verbotene Aussage ist die gemeldete Antwort im Ganzen; sie
schlägt an, wenn Kingfisher genau dies wiederholt. Wer es gezielter will, kürzt die Zeile in der
Datei auf die falsche Stelle. Meldungen ohne beides (etwa `zu_langsam`) lassen sich am Text nicht
messen; sie stehen in der Datei unter `nicht_messbar`, damit nichts verloren geht. `lokal` nimmt
dafür eine Frage mit nur verbotenen Aussagen an („sag das nicht wieder“); ohne erwartete und ohne
verbotene Aussage bleibt sie unmessbar und wird abgelehnt.

## Die Schleife schließt sich

Ein Fall entsteht bei der Meldung und **bleibt**. „Erledigt“ heißt: Der Fehler ist behoben oder
entschieden, nicht: Der Fall ist weg. Die erledigte Meldung steht weiter in der Datei (`notiz`:
„Erledigt, bleibt als Regressionstest“), und `lokal` fragt sie weiter. Kommt der Fehler zurück,
zeigt die Messlatte eine falsche Aussage. Der Weg für die Entwicklung: Meldung lesen, Fall
exportieren und messen (rot), beheben, messen (grün), erst dann „Erledigt“.

## Datenschutz

Die Ablage und die Fälle-Datei enthalten **Frage- und Antworttexte** des Nutzers. Beide bleiben
auf dem Rechner: Die Ablage im Datenordner (und in der Sicherung, die der Nutzer selbst anlegt),
die Datei dort, wohin der Browser Downloads legt oder wohin `--ausgabe` zeigt. Sie gehören nicht
ins Repository, nicht in einen Pull Request, nicht in ein Testprotokoll und nicht in einen
Cloud-Agenten. Die Berichte von `python -m messlatte lokal` enthalten weiterhin nur IDs, Klassen,
Zähler und Zeiten, auch mit dieser Datei. `messlatte faelle` schreibt auf das Terminal nur Zähler.
Tests und Browserprobe arbeiten mit erfundenen Texten.

## Nachweis

Sabotageproben (Zusicherung gebrochen, richtige Tests rot, zurückgestellt):

| Gebrochen | Rot |
|---|---|
| Datei aus `SQLITE_DATA_FILES` genommen | 3: Sicherung/Schemaprüfung, Wiederherstellung, `test_every_backup_store…` |
| „Erledigt“ löscht die Meldung | 3: Ablage, Liste, Export |
| Export lässt Erledigtes weg | 1: Export über die Route |
| Export ohne verbotene Aussage | 2: Fall und Einzelsatz |
| Server liest die Belege nicht selbst | 1: Meldung liest Belege und Modellstand selbst |
| `POST` ohne Token | 1: Routen brauchen das Token |
| `lokal` verlangt wieder Pflichtaussagen | 2: Wiederholung fällt auf, Format |
| CLI schreibt Fragetext aufs Terminal | 1 |
| CLI-Export ohne verbotene Aussage | 1: CLI und Route liefern dasselbe |
| UI: `meldbar` immer wahr / Zählsatz ohne Leerfall | je 1 |

Browserprobe im echten Chromium (`scripts/probe_rueckkanal_ui.py`): still, offen, Art wählen,
Freitext, „Gemerkt.“, Liste, „Erledigt“, Export als Datei, die `messlatte.lokal` liest; Konsole leer.

## Offen

* Ob „Stimmt nicht?“ unter jeder Antwort im Alltag zu laut ist, zeigt erst die Woche.
* Die verbotene Aussage ist die ganze Antwort. Ein Klick auf den falschen Satz statt einer Art
  wäre genauer, aber ein weiterer Schritt für den Nutzer; nur bei Bedarf.
* Die Fälle-Datei wird angestoßen, nicht automatisch nachgeführt. Wer sie regelmäßig braucht,
  exportiert neu; die Fall-IDs bleiben gleich (`rueckmeldung-` und die ersten zwölf Zeichen der Kennung).
