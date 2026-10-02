# Welt und Wetter im Briefing (Etappe F4)

Stand: 29. September 2026. Umsetzung von „Wetter und Nachrichten“ aus [`26-plan-stabschef.md`](26-plan-stabschef.md)
und von Etappe 4 („Die Welt, soweit sie dich betrifft“) aus [`24-weg-zum-jarvis.md`](24-weg-zum-jarvis.md). Code
(`sidecar/icarus_memory/`): `wetter.py`, `wetter_routes.py`, `welt_feeds.py`, `welt_meldungen.py`,
`welt_briefing_routes.py`, Zeilen in `tagesbriefing.py`, Verdrahtung in `tag_routes.py`. Oberfläche:
`WeltSettings.tsx` (Einstellungen → Was Kingfisher darf), `TagesLage.tsx`. Tests: `test_wetter.py`,
`test_welt_feeds.py`, `test_welt_meldungen.py`, `test_tagesbriefing_welt.py`, `test_wetter_welt_routes.py`.

## Was sich ändert

Das Briefing (`docs/33`) hat zwei Zeilen dazu, beide nur, wenn es etwas zu sagen gibt:

| Zeile | Inhalt | Aktionen |
|---|---|---|
| Wetter | am Wohnort und, getrennt davon im selben Absatz, am Ort und zur Zeit des nächsten auswärtigen Termins: „Wetter in Wiesbaden: 14 °C, bewölkt. Mainz, 14 Uhr: 12 °C, Regen – Schirm einpacken?“ | keine |
| Welt | höchstens **eine** Meldung, mit Titel als Zitat, Quelle und Begründung: „Betrifft Klinikum Rheingau-Süd, weil dazu 4 Quellen in deinen Akten stehen (zuletzt „…“ vom 12. September).“ | Meldung lesen, Akte öffnen, Quelle abbestellen, Nicht mehr zu … |

Die Tageslage hat damit bis zu sechs Zeilen (`MAX_ZEILEN`); jede Zeile fehlt, wenn ihr Beleg fehlt.

## Wetter ohne Umgebungsvariablen

Einstellungen → **Was Kingfisher darf** → „Wetter im Briefing“. Vorgabe **aus**. Der Ort wird nie als Zahl getippt:
Man sucht einen Namen, Kingfisher zeigt Treffer („Mainz, Rheinland-Pfalz, Deutschland“), ein Klick wählt ihn und
schaltet das Wetter ein. Steht bei den Fahrzeiten ein Startort („Musterstraße 1, 65183 Wiesbaden“), bietet die Seite
den Ort daraus als Vorschlag an („Wiesbaden (dein Startort für Fahrzeiten)“); gesucht wird erst nach dem Klick.
Die Umgebungsvariablen `KINGFISHER_WEATHER_ENABLED`, `…_LOCATION`, `…_LATITUDE`, `…_LONGITUDE` gelten weiter als
Vorbelegung, solange in der Oberfläche nichts gespeichert wurde; was dort gespeichert wird, gilt vor ihnen (auch „aus“).
Das alte Briefing („Briefing öffnen“, `/api/v1/morning-briefing`) liest das Wetter ebenfalls aus dieser Einstellung.

### Datensparsamkeit

* Es geht nur der **Ortsname** hinaus (Geocoding-API von Open-Meteo, ohne Schlüssel, ohne Konto) und danach **zwei auf
  zwei Nachkommastellen gerundete Zahlen** (rund ein Kilometer) an die Vorhersage. Kein Titel, keine Teilnehmer, keine
  Straße, keine Uhrzeit des Termins: Aus einer Terminadresse wird durch `wetter.ortsname` nur der Ort („55116 Mainz“ →
  „Mainz“); ist keiner zu erkennen („Besprechungsraum 3“), geht nichts hinaus und die Zeile fehlt.
* **Ohne Einstellung keine Anfrage.** Eine einzige Stelle (`WetterDienst._anfragen`) sendet, prüft vorher die
  Einwilligung und erlaubt nur `https` und die beiden Open-Meteo-Hosts. Die Suche in den Einstellungen ist eine
  ausdrückliche Handlung des Nutzers und schickt nur den getippten Namen.
* Antworten werden 30 Minuten (Vorhersage) und 24 Stunden (Ortssuche) gemerkt, ein Fehlschlag fünf Minuten lang nicht
  wiederholt. Fehlertexte enthalten weder Ort noch Adresse.

### Wetter am Termin

Der **nächste auswärtige Termin** (heute oder morgen, nicht ganztägig, mit einem Ort, der kein Videolink ist und nicht
der Wohnort) bekommt Temperatur, Wetterlage und, wenn es regnet oder die Regenwahrscheinlichkeit bei 50 Prozent oder
darüber liegt, die **Frage** „Schirm einpacken?“. Das ist ein Hinweis, keine Packliste: `einpacken.py` bleibt
belegpflichtig (Notiz oder Mail), und ein Wetterhinweis schafft keinen Eintrag dort. Mehrdeutige Ortsnamen sind ein
Restrisiko: Der erste Treffer der Suche zählt, das Briefing nennt den Ort, damit ein Irrtum auffällt.

## Nachrichten, die den Nutzer betreffen

**Einstellung**: „Eine Meldung aus der Welt im Briefing zeigen“, Vorgabe **aus**. Quellen wählt der Nutzer:

* **Feeds** (RSS, RDF, Atom): vier bekannte zum Anklicken (tagesschau, Deutschlandfunk, heise online, ZEIT ONLINE; `welt_vorgaben.py`, Stand 30.09.2026, Adressen nicht abgerufen, ein Klick fügt hinzu, der zweite entfernt; siehe [`47-einstellungen.md`](47-einstellungen.md)) oder eine eigene https-Adresse. Beim
  Hinzufügen wird der Feed einmal zur Probe gelesen; ein unbrauchbarer wird nicht eingetragen, der Grund steht in einem Satz.
* **Bereits eingerichtete öffentliche Quellen** (`world_sources`, Einstellungen → Für Techniker → Weitere öffentliche Quellen): ankreuzbar. Ihr schon
  geholter Text wird satzweise gelesen; es gibt dafür keinen neuen Abruf.

Ohne eingeschaltete Meldung und ohne gewählte Quelle wird **nichts abgerufen**. Abgerufen wird nie beim Öffnen der
Seite, sondern in einem Hintergrundlauf (`WeltDienst.anstossen`, höchstens alle 30 Minuten); das Briefing liest nur
die gespeicherte Wahl des Tages.

### Abgleich mit den Akten

`welt_meldungen.abgleichen` sucht in Titel und Text jeder Meldung die **Namen der Sachen aus den Akten**
(`bezuege.py`: Organisationen, Projekte, Orte, Themen), als ganze Wörter, ohne Rücksicht auf Groß und Klein,
Organisationen mit und ohne Rechtsform („Winter Catering GmbH“, „Winter Catering“). Personen werden nie abgeglichen.
Eine Sache braucht Rückhalt im Bestand (Organisation und Projekt mindestens eine Quelle, Ort und Thema mindestens
zwei), und Quellen der Art Web (geholte Seiten) zählen nicht: Eine Seite, die eine Sache erst hervorgebracht hat,
darf keine Meldungen zu ihr begründen. Gewicht: Organisation und Projekt vor Ort vor Thema, dazu Rückhalt, Nennung
im Titel, Frische der Sache. Meldungen älter als drei Tage und schon Gezeigtes zählen nicht.

**Optional** das Modell der Rolle `hintergrund`: Es bekommt den fremden Text in einem Block mit `wrap_untrusted`, darf
nur mit `{"betrifft": true|false}` antworten und nur **streichen** (`false`). Es läuft nur, wenn es lokal ist und die
Modellprüfung im Zeitplan freigegeben ist (wie bei der Einordnung). Jede andere Antwort, jeder Fehler und jeder
Werkzeugaufruf zählt nicht: Dann entscheidet der Namensabgleich allein.

### Regeln

* **Keine Meldung ohne Treffer.** „Wichtig für alle“ zählt nicht.
* **Höchstens eine am Tag.** Die Wahl wird für den Tag gespeichert und bleibt; wird sie abbestellt, folgt am selben Tag
  keine Ersatzmeldung.
* **Jede Meldung sagt warum**, mit Link auf die Akte.
* **Abbestellen mit einem Klick**, im Briefing selbst („Quelle abbestellen“, „Nicht mehr zu …“), sofort wirksam. Eine
  abbestellte Quelle bleibt in der Liste ausgeschaltet und wird nicht mehr abgerufen; eine abbestellte Sache steht
  unter „Abbestellt“ mit „Wieder zulassen“. Nichts davon ist endgültig.
* **Fremder Inhalt ist Daten.** Feedtexte werden nie ausgeführt und nie als Anweisung gegeben. Sie werden **nicht in
  das Gedächtnis geschrieben**, weder als Episode noch als Fakt (`world_monitor.py` tut das für die von Hand
  aktualisierten Weltquellen weiter, als Rohquelle der Art Web; die Feeds hier nicht). Gespeichert wird höchstens die
  gewählte Meldung des Tages (Titel und Link, gekürzt) und ihre Begründung in den Einstellungen; die Zusammenfassung des
  Feeds nicht. Im Briefing steht der Titel als Zitat.

### Feeds sicher lesen (`welt_feeds.py`)

Dieselben Regeln wie `world_sources.py` (öffentliche https-Adresse, Prüfung gegen interne Ziele vor jeder Anfrage
und nach jeder Weiterleitung, drei Weiterleitungen, Zeitlimit) und für XML zusätzlich: Ein Feed mit `<!DOCTYPE` oder
`<!ENTITY` wird abgelehnt, **bevor** ein Parser ihn sieht; Kodierungen mit Nullbytes (UTF-16) ebenso; höchstens
256 KiB (auch beim Streamen ohne Längenangabe), 40 Einträge, Titel 200 und Text 600 Zeichen; HTML wird zu Text,
Skripte fallen weg; Links nur `https`. Nur Standardbibliothek (`xml.etree`), keine neue Abhängigkeit.

## Sabotageproben

Jede Zusicherung wurde durch Ersetzen eines Ausdrucks gebrochen und die Tests dieser Etappe liefen (`-x`). Alle
Proben wurden gefangen. Drei (S4, S5, S21) waren beim ersten Lauf **nicht** gefangen, weil eine zweite Sperre dahinter
dieselbe Zusicherung sicherte (Tiefenverteidigung) oder ein Test nur den einfachen Fall prüfte; dafür kamen drei Tests
dazu, und die Proben wurden mit allen Sperren zusammen wiederholt (S4a/b, S21a/b, S2b).

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| S1 | Nur der Ortsname verlässt den Rechner (Adresse statt Ort) | `test_nur_der_ortsname_und_gerundete_koordinaten_…`, `test_ortsname_ist_nur_der_ort_nie_die_strasse` |
| S2 | Ohne Einwilligung keine Wetteranfrage (Sperre in `_anfragen`; dazu alle drei Sperren) | `test_nur_die_beiden_open_meteo_adressen_…`, `test_ohne_einstellung_geht_keine_anfrage_hinaus` |
| S3 | Nur die beiden Open-Meteo-Adressen mit https | `test_nur_die_beiden_open_meteo_adressen_mit_https_werden_gefragt` |
| S4 | Höchstens eine Meldung am Tag (frühe Sperre; beide Sperren) | `test_die_gewaehlte_meldung_wird_am_selben_tag_nicht_neu_gesucht`, `test_hoechstens_eine_meldung_am_tag_…` |
| S5 | Keine Meldung ohne Treffer (Paarung ohne Namen) | `test_der_abgleich_paart_nur_meldungen_mit_dem_namen_der_sache` |
| S6 | Abbestellte Sache wird ignoriert | `test_abbestellen_je_sache_entfernt_die_meldung_…` |
| S7 | Abbestellen nimmt die Meldung des Tages weg | dasselbe |
| S8 | Am selben Tag keine Ersatzmeldung nach dem Abbestellen | dasselbe |
| S9 | Feed mit Entitäten oder Dokumenttyp abgelehnt, bevor ein Parser ihn sieht | `test_feed_mit_entitaeten_oder_dokumenttyp_wird_abgelehnt_…` |
| S10 | Feed über 256 KiB abgelehnt | `test_zu_grosse_feeds_werden_abgelehnt_…` |
| S11 | Zu große Antwort bricht beim Streamen ab, auch ohne Längenangabe | `test_zu_grosse_antworten_brechen_ab_…` |
| S12 | Höchstens 40 Einträge | `test_zu_grosse_feeds_werden_abgelehnt_…` |
| S13 | Weiterleitung auf interne Ziele wird vor der Anfrage gestoppt | `test_eine_weiterleitung_auf_ein_internes_ziel_…`, `test_abruf_lehnt_http_und_interne_ziele_ab_…` |
| S14 | Fremder Text steht dem Modell nur in einem markierten Block | `test_dem_modell_steht_der_fremde_text_nur_in_einem_markierten_block_…` |
| S15 | Das Modell darf nur streichen | dasselbe |
| S16 | Feedtext wird nie mit der Meldung gespeichert | `test_eingeschleuste_anweisungen_werden_nicht_befolgt_…`, `test_welt_ist_aus_bis_der_nutzer_sie_einschaltet_…` |
| S17 | Personen werden nie abgeglichen | `test_orte_und_themen_brauchen_mehr_rueckhalt_und_personen_…` |
| S18 | Orte und Themen brauchen Rückhalt im Bestand | dasselbe, `test_eine_sache_die_nur_aus_weltquellen_stammt_…` |
| S19 | Geholte Webseiten sind kein Rückhalt (Kreisschluss) | `test_eine_sache_die_nur_aus_weltquellen_stammt_hat_keinen_rueckhalt` |
| S20 | Vorgabe aus; nur ein echtes `true` mit Ort zählt | `test_vorgabe_ist_aus_und_nur_ein_echtes_true_mit_ort_zaehlt` |
| S21 | Ohne eingeschaltete Meldung wird nichts abgerufen (Lesen und Lauf) | `test_ohne_einwilligung_startet_das_lesen_…`, `test_ohne_einwilligung_oder_ohne_quelle_wird_nichts_abgerufen` |
| S22 | Zu alte Meldungen zählen nicht | `test_zu_alte_meldungen_zaehlen_nicht` |
| S23 | Schon Gezeigtes kommt nicht wieder | `test_am_naechsten_tag_kommt_eine_andere_…` |
| S24 | Keine Weltzeile ohne Begründung | `test_eine_meldung_ohne_begruendung_wird_nicht_gezeigt` |
| S25 | Der Schirm ist eine Frage, nie eine Tatsache; Wetterhinweis getrennt von der Packliste | `test_der_satz_zum_termin_nennt_den_schirm_nur_als_frage`, `test_wetter_daheim_und_am_termin_…` |
| S26 | Termine am Wohnort bekommen kein zweites Wetter | `test_termine_am_wohnort_oder_online_bekommen_kein_zweites_wetter` |

## Offen und ungeprüft

* **Kein Netz hier.** Open-Meteo (Geocoding und Vorhersage) und die Feeds sind nur gegen Attrappen getestet, die dem
  dokumentierten Antwortformat folgen (`results[].name/latitude/longitude/admin1/country`, `hourly.time/...`). Ob die
  echten Dienste genau so antworten, ist ungeprüft; ebenso die beiden vorgeschlagenen Feed-Adressen (tagesschau, heise).
* Der Namensabgleich kennt nur die **Schreibweise** der Sache und ihre Form ohne Rechtsform; echte Aliasse (Kürzel,
  Umbenennungen) kommen erst mit den Verzeichniseinträgen der Akten. Ein Ort oder Thema mit Allerweltsnamen kann zu
  Fehltreffern führen; die Mindestzahl an Quellen und das Abbestellen je Sache sind die Bremse. Das lokale Modell
  ist nur dann eine zweite Stufe, wenn eins freigegeben ist; ohne Modell steht der Namensabgleich allein.
* Die Regenhinweis-Schwelle (50 Prozent) ist eine Annahme, keine Messung.
* Es gibt keine Relevanzmessung über eine Woche Alltag: „Höchstens eine Meldung, und sie ist einschlägig“ ist
  gebaut, aber nicht am echten Bestand gezählt (Etappe 4 „Fertig heißt“).
* Die Karte „Relevantes aus der Welt“ der alten Übersicht zeigt weiter nur Beispielbilder, wenn Beispieldaten aktiv
  sind; ohne sie verweist sie auf die Einstellungen. Die eine echte Meldung steht in der Tageslage.
* Das lokale Modell wurde nur mit einer Attrappe getestet (Format, Markierung des fremden Textes, „nur streichen“),
  nicht mit einem echten Modell.
