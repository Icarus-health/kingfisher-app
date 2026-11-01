# Native Rawrecords als streng geprüfte Literal-Kandidaten

Basis: `8d065d1ddd3ca3bef115a9786338a720e081d435`. Dieser freigegebene
Nachtrag enthält 14 Produkt-Ergänzungen und zwei Entfernungen in
`satzantwort.py` und `satzpruefung_modell.py`. Keine neue Promptvariante,
Parser-/Persistenzstruktur, Sourceänderung oder Modellrolle. Alle Quellen,
MIME-Nachrichten und Prüfantworten sind synthetisch; keine privaten Dateien,
echten Modelle, Root-Dateien oder Netzprovider verwendet.

## RED und exakt begrenzte Kandidatenbildung

Auf der Basis führen zwei korrekt gelesene leere Original-ID-Auswahlen trotz
vollständiger geeigneter nativer Rows zum Zitatmodus. Die neuen MIME→Store→
`prepare`→Prüfung→`render`-Positivfälle für eine bzw. zwei Quellen waren RED.

Nur innerhalb der bestehenden einmaligen Nachprüfung kann nach **zwei**
korrekt validierten `nichts_vorliegend`-Ausgaben ohne Stellen eine Kopie der
Rawrecords als Kandidaten entstehen. Dafür muss jede Bedingung zutreffen:

- internes Flag standardmäßig `False`; `erzeugen` erlaubt es ausschließlich
  bei identischer Source-ID-Menge ausgewählter Refs und angebotener Belege
  sowie `ausgelassen == 0`;
- insgesamt ein oder zwei angebotene Belege, **jeder** mit genau einer aktuell
  validierten vollständig sichtbaren Native-Row;
- aktives Prüftor; anschließend bestehen dieselben ersten Gates und die
  getrennte zwingende Full-Raw-Frage-/Vorbehaltsprüfung je Quelle.

`unklar`, ungültiges Schema, fremde IDs, Fehler oder ein widersprüchliches
`nichts_vorliegend` mit ausgegebenen Stellen erzeugen keine Kandidaten.
Kein Teilbestand wird verwendet, wenn ein Beleg die Grenze verfehlt.
Normale gültige Generierung und die Begrenzung auf zwei Selektoraufrufe
bleiben unverändert. Eine weiterhin unbeantwortbare Frage wird nicht zur
globalen Abwesenheitsbehauptung.

## Herkunft und unveränderte Autoritätsgrenze

Jeder Kandidat ist exakt `Satz(ganzeNativeRow, eigeneBelegnummer)` aus dem
bereits frischen `_beleg_aus`→`docx_native_rows.read`-Ergebnis. Dessen Raw-
Offsets, Body-/Haupttextdigest, Quellversion, WMA-Fingerprint und aktuelle
Elternbindung bleiben maßgeblich. Keine Labels werden semantisch gedeutet,
keine Wörter, Datumsrollen, Personen oder Handlungen ergänzt.

Die Ausgabe bleibt immer der wörtliche unbestätigte Quellenbericht. Das
aktive Prüftor erhält separat Frage, ganze Row und unveränderten vollständigen
Rawbeleg. Ein Ja ist weiterhin notwendig; Nein/Unklar/Timeout bei **einer**
Quelle erzwingt den gesamten Zitat-/Unsicherheitsrückfall. Zwei identische
Rows aus verschiedenen Quellen bleiben getrennt und erzeugen keine gemeinsame
Vertrauensfreigabe.

Gespeichert werden dieselben nativen Reviewbezüge. Wiederlesen validiert
erneut den aktuellen Proof und bindet Frage/Row/Ref/Prüfmodell; ein gespeichertes
Ja allein genügt nicht. Der Legacyweg `vom_programm=True` für abgeleitete
Aktensätze bleibt beim Wiederlesen gesperrt. Eine Rawcopy nutzt den bereits
bestehenden nativen Originalvertrag und erzeugt keine bestätigten Claims.

## Enges Budget

Nur bei `gesamt_budget is None`, vorhandenem Kingfisher-Profil und exakt zwei
nativen Fragen gilt ein Standardgesamtbudget von höchstens **16 Sekunden**.
Das Einzelbudget bleibt **8 Sekunden**. Explizite kleinere Satz-/Gesamtbudgets
werden unverändert verwendet. Die vorhandene engere JSON-Anfragefrist begrenzt
auch das neue Paarbudget; bei bereits abgelaufener Frist gibt es keine Aufrufe.
Normale, gemischte, einzelne, drei oder mehr native Aufträge sowie andere
Profile behalten ihre vorherigen Budgets. Serialität, Modell-RAM und
Wire-/Rawlimits bleiben unverändert.

Die Fakeclock reproduziert RED: Zwei synthetische Prüfungen mit jeweils sieben
Sekunden benötigen zuvor `8 + 5` Sekunden Aufrufbudget, also scheitert die
zweite. Jetzt erhalten genau die zugelassenen Paare `8 + 8`; alle anderen
Budgetfälle bleiben unverändert. Keine neuen Sleeps oder tatsächlichen
Zeitverzögerungen werden dafür verwendet.

## Gezielter Nachweis

44 neue Kontrollen: ein/zwei Kandidaten nach zwei leeren Antworten; echte
MIME-/Provenienzkomposition; Schema-/Status-/ID-Ausschlussfälle in beiden
Selektorstufen; internes Default-False-Flag, fehlende/zusätzliche/ausgelassene
Belege; drei Quellen, mehrere Rows, Quelle ohne Row, Rawbudget, inaktives oder
nicht unterstütztes Tor; falsche Datumsrolle; native Review-/Row-/Frage-
Manipulation, Elternentzug, Sourceänderung und Legacy-Inferenzsperre.

Pflichtgegenfall: zwei Quellen mit identischer Row, davon eine mit dem echten
synthetischen Haupttextvorbehalt „Die folgenden Termine gelten nur nach
schriftlicher Freigabe.“. Die Testreihenfolge ist ausdrücklich **zuerst Ja
zur unbedingten Quelle, danach Nein/Unklar/Timeout zur vorbehaltenen Quelle**.
Der zweite unveränderte Full-Rawbeleg enthält den Vorbehalt; es bleibt kein
Teilrest oder gültige Satzstruktur. Keine Claims entstehen.

Der Abschlusslauf der gezielten Native-/Original-/Zitat-/Absatz-/Satztests und
sechs Pflichtkernmodule: **742 bestanden in 39,17 Sekunden**, eine vorhandene
Starlette/httpx-Deprecation-Warnung. Ein anschließender enger Nachlauf prüft
die ausdrücklich geordnete Pflichtgegenprobe: **44 bestanden in 3,25
Sekunden**. Keine komplette Suite. Der breite Prüfauftrag entspricht dem
Kommando in [Native-Auswahl](docx-native-selection.md) mit zusätzlich
`sidecar/tests/test_docx_native_candidates.py`. Der enge Nachlauf:

```sh
PYTHONPATH=sidecar:. python -m pytest -q sidecar/tests/test_docx_native_candidates.py
```

Die bestehende Native-Teilmengekontrolle erwartet jetzt nach aktivem Ja einen
wörtlichen Quellenbericht statt einer globalen Abwesenheit; leere Auswahlen
mit negativem Prüfurteil bleiben Zitate.

Die Modellattrappen belegen Gateführung und Budgets, keine reale Modellqualität.
Kein Push, PR, Release oder persönliche Nachklassifikation. Root übernimmt
erst nach unabhängigem Review und eigener begrenzter Probe.
