# Morgenbriefing, Terminvorbereitung und Wegezeit (Etappe F1)

Stand: 30. September 2026. Umsetzung des ersten Teils von Etappe F aus
[`26-plan-stabschef.md`](26-plan-stabschef.md) und von „Termine vor und nach“ aus
[`24-weg-zum-jarvis.md`](24-weg-zum-jarvis.md). Code (`sidecar/icarus_memory/`): `terminvorbereitung.py`,
`fristlage.py`, `einpacken.py`, `tagesbriefing.py`, `wegezeit.py`, Routen in `tag_routes.py` und
`wegezeit_routes.py`; Mac: `macos/RouteReader.swift`, `scripts/mac_maps_worker.py`. Oberfläche:
`TagesLage.tsx`, `TerminVorbereitung.tsx`, `WegezeitSettings.tsx`. Tests: `test_terminvorbereitung.py`,
`test_fristlage.py`, `test_tagesbriefing.py`, `test_wegezeit.py`, `test_wegezeit_routes.py`,
`test_mac_maps_worker.py`, `messlatte/tests/test_terminvorbereitung.py`.

## Was sich ändert

Auf der Startseite steht über allem **eine Tageslage in drei bis fünf Zeilen**, ein Urteil statt einer Liste
(`briefing.py` bleibt die Rangfolge der Aufgaben darunter). Jede Zeile trägt eine Aktion:

| Zeile | Inhalt | Aktionen |
|---|---|---|
| Wohin | nächster Termin heute (sonst morgen), Ort, „Losfahren um …“ oder „Fahrzeit unbekannt“ | Vorbereitung öffnen, Fahrzeit berechnen / Startort eintragen |
| Wer kommt | die bekannten Teilnehmer und, mit Datum und im Wortlaut, was sie schrieben oder wollen | Vorbereitung öffnen, Quelle öffnen |
| Einpacken | nur, was in einer Notiz oder Mail steht | Quelle öffnen |
| Fristen | das Dringendste der nächsten sieben Tage oder eine verstrichene, vermutlich offene Zusage | Quelle öffnen |
| Wetter | eine Zeile, wenn Wetterdaten da sind (Open-Meteo), am Wohnort und am Ort des nächsten auswärtigen Termins, siehe [`36-welt-und-wetter.md`](36-welt-und-wetter.md) | keine |
| Welt | höchstens eine Meldung, die zu einer Sache aus den Akten passt, mit Begründung; abbestellbar ([`36`](36-welt-und-wetter.md)) | Meldung lesen, Akte öffnen, abbestellen |

Fehlt der Beleg, fehlt die Zeile: keine Packliste ohne Quelle, kein Wetter ohne Daten, keine Fahrzeit ohne Dienst.

## Terminvorbereitung ohne Klick

`GET /api/v1/tag/briefing` bereitet **jeden Termin von heute und morgen** vor, bevor jemand etwas öffnet. Je
Teilnehmer (über die Adresse, `person:a:<adresse>`, Etappe C3) aus der **Akte** (`akten.py`):

* **Was sie wollen**: als Vermutung gekennzeichnet. Die Akte führt Bitten und Zusagen als „vermutlich offen“
  (Rolle: sie bittet, du hattest zugesagt, sie sagte zu). Dazu **Wünsche und genannte Beträge** aus den eigenen
  Mails der Person: Sätze wie „hätte ich gern …“ und „bis zu 12.000 Euro einplanen“, wörtlich, mit Datum. Ein
  älterer Satz zum selben Gegenstand (mindestens zwei gemeinsame Wortstämme, Regel der Akte) tritt hinter den
  jüngeren zurück: Aktualität schlägt Ähnlichkeit.
* **Letzter Kontakt**, „Seit wann ihr euch kennt“ (älteste Quelle), **Aktueller Stand** (jüngste Änderung je
  Gegenstand), kommende Fristen der Person.
* **Hintergrund**: Stand der gemeinsamen Akte (Organisation oder Projekt, das alle bekannten Teilnehmer
  teilen; das Projekt des Termins, wenn zugeordnet, sonst als „vermutet“).
* Zeilen, die schon unter „Letzter Kontakt“ stehen, wiederholt der Hintergrund nicht.

**Nichts erfunden**: Jede Zeile ist ein wörtliches Zitat mit Quelle (Episode, Titel, Datum) und lässt sich mit
„Quelle öffnen“ ansehen (nur lesend). Teilnehmer ohne Adresse oder ohne Akte stehen unter „Nicht im Gedächtnis“
und werden nie über den Namen geraten. Was die Akte unter „vorher“ führt (ein neuerer Stand hat es abgelöst),
erscheint weder als Stand noch unter „Zuletzt“. Der Pfad liest nur und schreibt nichts in den Bestand.

## Fristen

`fristlage.py` liest aus den Akten der zuletzt aktiven Personen, Organisationen und Projekte: kommende Fristen der
nächsten sieben Tage und **verstrichene Fristen in Bitten und Zusagen, zu denen die Akte keine Erledigung kennt**
(nicht älter als 45 Tage, immer „vermutlich noch offen“). **Überholte Fristen sind nie dabei**: Die Akte führt
sie unter „ersetzt“, `fristlage` liest nur `kommend` und `verstrichen` und prüft `ersetzt_durch` zusätzlich. Zitiert
wird der Satz um die Datumsangabe (die Akte liefert ihn seit F1 als `satz`; eine einzeilige Ergänzung in
`akten.py`). Reihenfolge: heute und morgen Fälliges, dann Verstrichenes (das Jüngste zuerst, denn je älter, desto
eher hat es sich still erledigt), dann Kommendes nach Datum. Dieselbe Quelle hängt an mehreren Akten und zählt einmal.

## Einpacken

`einpacken.py` sucht in der Notiz zum Termin (aus dem Gedächtnis, C1), in den Quellen der Teilnehmer und in eigenen
Notizen der letzten 45 Tage, die den Termin nennen (Name, Organisation oder Titelwort), Sätze mit „mitnehmen“,
„mitbringen“, „einpacken“, „bringe … mit“. Für den Nutzer gilt ein Satz, wenn er ihn selbst schrieb oder wenn ihn
jemand direkt anspricht („Bitte bringen Sie … mit“). „Ich bringe folgende Zahlen mit“ einer anderen Person steht
nicht in der Packliste. Ohne Beleg entfällt der Abschnitt. Anhänge stehen (noch) nicht im Bestand; was eine Mail
„anbei“ schickt, ist deshalb keine Packliste.

## Wegezeit

`wegezeit.py`: eine Anbieter-Schnittstelle (`Anbieter.fahrzeit(von, nach, verkehrsmittel, abfahrt)`) mit

1. **Apple Karten** (`MacKarten`): der Sidecar legt die Frage in einen Briefkasten im Speicher, der Mac-Arbeiter
   `scripts/mac_maps_worker.py` holt sie ab (`GET /api/v1/wegezeit/mac/anfragen`, alle fünf Sekunden), fragt den
   Swift-Helfer `build/kingfisher-route` (`MKDirections`, `calculateETA`) und liefert die Minuten
   (`POST …/antworten`). Ohne Lebenszeichen des Arbeiters (45 s) wartet der Sidecar nicht.
2. **OpenRouteService** (Auto, zu Fuß) und **Google Routen** (auch Bus und Bahn) mit eigenem Schlüssel. Der
   Schlüssel liegt im Schlüsselbund (`ICARUS_ORS_KEY`, `ICARUS_GOOGLE_ROUTES_KEY`), reist im Anfragekopf (nie in der
   Adresse), steht nie in Einstellungsdatei, Antwort oder Log (`Geheimnis`, Fehlertexte ohne URL, ein Log-Filter für
   die Anfragezeilen von httpx).
3. **Ohne Dienst**: kein Zeitwert, sondern „Ort: …. Fahrzeit unbekannt.“ mit dem Grund (aus, kein Startort, kein
   Dienst, Dienst nicht erreichbar).

**Einwilligung**: Einstellung „Fahrzeiten berechnen“ (Einstellungen → Kalender, oder ein Klick in der Zeile „Wohin“ mit
einem Satz Erklärung). **Vorgabe aus**; nur ein echtes `true` zählt. Ohne sie wird kein Anbieter gefragt
(`WegezeitDienst.auskunft`, eine einzige Stelle). Es verlassen zwei Adressen den Rechner, kein Titel, keine Teilnehmer,
keine Uhrzeit. Videokonferenzen und Termine ohne Ort werden nie gerechnet; die Antworten werden 20 Minuten gemerkt.

**Startpunkt** ist der Ort des Termins davor am selben Tag (wenn er endet, bevor der nächste beginnt), sonst die
Heimatadresse aus den Einstellungen; fehlt sie, fragt die Zeile einmal danach („Von wo fährst du meistens los?“).
**Losfahren** = Beginn minus Fahrzeit minus Puffer (10 Minuten, bei Bus und Bahn 15). Endet der Termin davor später,
sagt der Satz „Das wird knapp.“

## Messung

`messlatte/tests/test_terminvorbereitung.py` bereitet den Termin vom 30.09.2026 (Frau Engel, Herr Odenthal) gegen
die unveränderte Welt vor (Regel-Einordnung, kein Modell) und prüft die Fragen `terminvorbereitung-01`, `-02`, `-04`:
alle erwarteten Aussagen stehen darin, keine verbotene (15.000 statt 12.000), alle erwarteten Belege werden zitiert
(`-01`: 007, 005, 002, 008; `-02`: 008, 007; `-04`: 007) und der verbotene Beleg (Telefonnotiz 004) nicht. Zusätzlich:
Herr Odenthals Wunsch (Schulung) steht bei ihm, Frau Engels (Screening) bei ihr; die Packliste nennt Laptop und Handout
(Notiz 012) und Leas Kalkulation (011), nicht Frau Engels Zahlen (010). Grenze: Die Telefonnotiz vom 18.06. hat keine
Adresse und kommt erst mit der Modell-Einordnung in eine Akte; der neuere Betrag bliebe dann der Stand.

## Sabotageproben

Jede Zusicherung wurde durch Ersetzen eines Ausdrucks gebrochen und die Tests dieser Etappe liefen (`-x`, der erste
Fehlschlag steht da). Alle 13 Proben wurden gefangen.

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| S1 | Vorbereitung ohne Klick aus der Akte | `test_der_termin_ist_ohne_klick_vorbereitet_…` |
| S2 | Überholte Frist ist nie aktuell (zweite Prüfung in `fristlage`) | `test_aus_akte_prueft_die_ueberholung_selbst_noch_einmal` |
| S3 | Verstrichen zählt nur, wenn noch offen | `test_erledigte_zusage_steht_nicht_als_verstrichen_da` |
| S4 | Wegezeit nur mit Einwilligung | `test_ohne_einwilligung_wird_kein_anbieter_gefragt_…` |
| S5 | Ohne Dienst ein ehrlicher Satz, keine Zahl | dasselbe |
| S6 | Einpacken: „Ich bringe … mit“ anderer zählt nicht | `test_einpacken_nennt_nur_belegtes_…` |
| S7 | Schlüssel im Kopf, nie in der Adresse | `test_openrouteservice_schluessel_im_kopf_…` |
| S8 | Adressen der Kartendienste nicht im Log | `test_httpx_protokolliert_keine_adressen_…` |
| S9 | Fehlertexte ohne Schlüssel und Adresse | `test_google_routes_fehler_tragen_weder_…` |
| S10 | Überholter Wert steht nicht unter „Zuletzt“ | `test_ueberholte_werte_stehen_nicht_als_stand_…` |
| S11 | Startpunkt ist der vorherige Termin | `test_startpunkt_ist_der_ort_des_vorherigen_termins_…` |
| S12 | Notiz zum Termin zählt fürs Einpacken | `test_notiz_zum_termin_kommt_aus_dem_gedaechtnis` |
| S13 | Keine Zeile ohne Beleg | `test_ohne_einwilligung_steht_fahrzeit_unbekannt_…` (Absturz), dazu `test_ohne_beleg_fehlen_einpacken_und_wetter_…` |

## Ungeprüft und offen

* **Mac-Helfer ungeprüft.** `RouteReader.swift`, `build_route_reader.sh` und `mac_maps_worker.py` wurden auf Linux
  geschrieben. Geprüft ist nur der Python-Arbeiter (mit Attrappen-Helfer und -Sidecar) und die Syntax; der Swift-Code
  wurde nie übersetzt oder ausgeführt, ob `CLGeocoder` und `MKDirections.calculateETA` aus einem Kommandozeilenprogramm
  ohne App-Bündel liefern (und für Bus und Bahn), ist offen. Der Arbeiter ist in `start_mac_app.py` eingetragen und
  bleibt still, wenn der Helfer nicht gebaut ist.
* Die Kartendienste OpenRouteService und Google Routen sind nur gegen Attrappen-Antworten getestet, nicht gegen die
  echten Dienste (kein Netz, kein Schlüssel).
* Wünsche und Beträge sind Mustersuche (`hätte gern`, `wünsch…`, `… Euro`), keine Modellleistung; „was sie wollen“
  wird mit dem Modell der Einordnung besser (Bitten in Akten).
* Anhänge fehlen im Bestand; Nachrichten und Wetter am Termin kamen mit F4 ([`36-welt-und-wetter.md`](36-welt-und-wetter.md)).
* Die Tageslage ist auf heute und morgen begrenzt. Das Wetter kommt seit F4 aus der Einstellung „Wetter im Briefing“ (die Umgebungsvariablen `KINGFISHER_WEATHER_*` bleiben Vorbelegung); ohne beides fehlt die Zeile.
* Die Oberfläche der Startseite ist nicht für Telefonbreite gebaut (bestehend); die Tageslage bricht bei schmaler
  Breite um.
