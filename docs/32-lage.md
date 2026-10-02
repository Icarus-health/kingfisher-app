# Lage und Satzprüfung (Etappe D3)

Stand: 30. September 2026 (Migration 14, nach D1/D2 mit Schema 13). Umsetzung von D3 aus
[`27-schichten-und-fragen.md`](27-schichten-und-fragen.md), aufbauend auf den Akten
([`30-akten.md`](30-akten.md)). Code: `sidecar/icarus_memory/satzpruefung.py`, `lage.py`,
`lage_routes.py`; Zeitplan in `scheduler.py` (`_run_lage`) und `server.py` (`run_lage` in
`_wire_scheduler`); Anzeige in `akten_routes.py` und `app/kingfisher/src/AkteAbschnitte.tsx`;
Messung in `messlatte/akten.py`. Tests: `test_satzpruefung.py`, `test_lage.py`,
`test_lage_routes.py`, `messlatte/tests/test_akten_lage.py`.

## Was sich ändert

Die Akte einer Sache beginnt jetzt, wenn ein lokales Modell da ist, mit der **Lage**: zwei, drei
Sätze, was gerade gilt („Stuttgart = Bio-Fachtag am Klinikum X am 14.10., Vortrag 11 Uhr, Programm
liegt vor“). Jeder Satz trägt kleine Verweise auf seine Quellen; ein Klick öffnet das Original. Darunter
steht wie bisher die Akte (Stand, Offen, Fristen, Termine, Verlauf), auf Nachfrage geht es also
Lage → Akte → Quelle bis ins Original.

Oberstes Gebot ist, dass **keine falsche Information** entsteht. Deshalb schreibt das Modell nur, und
ein Programm ohne Modell, die **Satzprüfung**, entscheidet, was stehen bleibt.

## Die Satzprüfung (`satzpruefung.py`)

Eigenes Modul, ohne Modell, wiederverwendbar: E3 (Antworten) nutzt dieselbe Prüfung. Eingabe sind Sätze
mit Belegnummern und die belegten Textstellen (`Beleg`: Text, Kopf der Quelle, Zeitpunkt der Quelle).
Ergebnis je Satz: **bestanden** oder **verworfen mit allen Gründen**. Nichts wird still verbessert, der
Satz bleibt, wie das Modell ihn schrieb.

Ein Satz besteht nur, wenn

1. **jede Belegnummer existiert und gilt** (und mindestens eine genannt ist),
2. **alle harten Tokens in den zitierten Belegen stehen** (zusammen genommen, nicht je Beleg):

| Token | Regel |
|---|---|
| Daten | alle deutschen Formen („12.10.“, „12. Oktober“, „2026-10-12“, „12.10.26“, „12.-14. Oktober“) werden auf das Kalenderdatum normalisiert. Ein Datum ohne Jahr im Satz genügt mit Tag und Monat; nennt der Satz ein Jahr, muss es das Belegdatum tragen. Ein Beleg ohne Jahr löst mit dem Zeitpunkt der **Quelle** auf (`fristen.ohne_jahr`); ist das uneindeutig, ergänzt der Satz kein Jahr. |
| relative Angaben der Quelle | „bis Freitag“, „in zwei Wochen“ werden mit dem Zeitpunkt der Quelle aufgelöst (`fristen.fristen_in`, dieselbe Stelle wie die Akte), nie mit heute. |
| Uhrzeiten | „11 Uhr“ = „11:00“ = „11.00 Uhr“; Bereiche „11 bis 12 Uhr“. |
| Zahlen und Beträge | Tausenderpunkt, Dezimalkomma, „zwei“ = „2“; ein Betrag braucht dieselbe Währung, eine Summe („zusammen 250 Euro“) ist erfunden, wenn sie nicht dasteht; eine Jahreszahl muss aus dem Beleg stammen. |
| Adressen, Links, Kennungen | E-Mail, `https://…`, Aktenzeichen und Rechnungsnummern (Buchstaben und Ziffern gemischt) wörtlich. |
| Wochentage, Monate | im Beleg oder als Wochentag eines belegten Datums im Satz; „Anfang/Mitte/Ende Oktober“ wörtlich (oder „Ende“ mit einem Monatsletzten im Beleg). |
| Eigennamen, Orte | jedes großgeschriebene Wort, das kein Funktionswort, kein allgemeines Gattungswort („Termin“, „Frist“ …) und kein Wochentag oder Monat ist; Namensfolgen („Klinikum Stuttgart“) müssen als Folge dastehen. Tolerant gegen Beugung („Klinikums“) und Umlautschreibung („Mueller“ = „Müller“). |
| Statusaussagen | „bezahlt“, „bestätigt“, „erledigt“, „genehmigt“, „geliefert“, „unterschrieben“, „eingereicht“: dieselbe Wortgruppe muss im Beleg stehen. |
| relative Zeitangaben im Satz | „heute“, „morgen“, „nächste Woche“, „in zwei Wochen“ sind ohne festen Bezugstag nicht prüfbar und werden verworfen (`relative_zeit_erlaubt` für Aufrufer, die einen Bezugstag haben). |

3. **keine Verneinungsumkehr offensichtlich ist**: Verneint der Beleg im selben Satzteil etwas, das der
   Satz aufgreift („nicht“, „kein“, „abgesagt“, „entfällt“, „storniert“ …), muss der Satz selbst
   verneinen. Verneint der Satz, muss ein Beleg verneinen. Konservativ: lieber verwerfen.

Der Titel der Quelle und ihr Datum zählen zum Beleg. Der Name der Sache darf im Satz stehen
(`zusatz_woerter`), weil er in keinem Zitat stehen muss.

**Bewusste Strenge.** Die Prüfung verwirft auch Richtiges, wenn ein Gattungswort nicht in der kurzen
Liste steht oder wenn der Satz „überwiesen“ sagt, der Beleg aber „überweisen Sie“. Ein fehlender Satz
kostet nichts, ein falscher schon. Tests gegen typische korrekte Umformulierungen halten dagegen
(`test_korrekte_umformulierung_besteht` und Verwandte).

**Grenzen.** Die Prüfung erkennt keine falsche Zuordnung (eine Zahl aus dem Beleg am falschen
Sachverhalt) und keine sinnverdrehende Umstellung ohne Verneinungswort, und sie prüft nicht, was der
Beleg selbst behauptet. Sie ist ein Sieb gegen Erfundenes, keine Wahrheitsprüfung. Was sie nicht
sieht, sieht der Nutzer am Beleg neben dem Satz.

## Die Lage (`lage.py`)

* **Eingabe ist die Akte, nicht das Rohmaterial.** `eingabe_aus_akte` wählt Zeilen der Akte und
  nummeriert sie, Aktualität zuerst: neuer Stand (mit einem „Vorher“), kommende Fristen, kommende
  Termine, vermutlich Offenes, letzter Termin, jüngster Verlauf. Jede Zeile ist ein Beleg mit Titel,
  Quelldatum und Zitat; eine Frist trägt zusätzlich ihr aufgelöstes Datum. Das Modell sieht genau die
  Zitate, die auch die Prüfung als Beleg kennt.
* **Akteninhalt ist Daten, keine Anweisung.** Der gesamte Inhalt steht in einem gekennzeichneten
  fremden Block (`security.wrap_untrusted`), das Modell bekommt keine Werkzeuge, ein Werkzeugaufruf in
  der Antwort ist ein Fehler, und Zeilen, die wie eine Anweisung an ein Modell klingen
  („Ignoriere alle bisherigen Anweisungen …“), kommen nicht hinein und sind nicht zitierbar (gezählt
  als `ausgelassen`).
* **Modell und Schema.** Rolle `hintergrund` (`model_roles`), `complete_json`, Schema
  `{saetze: [{text, belege: [Nummern]}]}`, höchstens drei Sätze (ein vierter zählt als verworfen),
  streng gelesen: jede Abweichung ist ein Fehler, der nichts ändert.
* **Jeder Satz läuft durch die Satzprüfung.** Bestandene Sätze werden gespeichert, verworfene fallen
  heraus und werden mit Grund gezählt (`verworfen`).
* **Ablage.** Tabelle `lagen` (Migration 14, abgeleitet, jederzeit neu erzeugbar): Fingerabdruck der
  Akte, Kennung des Modells, Sätze mit `(Nummer, Quelle, Fingerabdruck der Quelle)`, Zählung. Kein
  Quelltext und nie ein Fakt im Bestand (`knowledge_claims` bleibt unberührt).
* **Aktualität.** Der Fingerabdruck der Lage ist der der Akte (`eingabestand`: Quellen, Bezüge,
  Einordnung, Wissensstand) und dazu, **welche gezeigten Fristen und Termine noch kommen**. Rutscht eine
  Frist in die Vergangenheit, gilt die Lage als veraltet, auch ohne neue Quelle. Die Anzeige zeigt bei
  veralteter Lage nur Sätze, deren Quellen unverändert und gültig sind (Entzug wirkt sofort), und den
  Hinweis „Die Lage wird aktualisiert“.
* **Ohne Modell keine Lage.** Das Modell muss lokal sein (`is_local`) und JSON liefern; sonst passiert
  nichts, und die Oberfläche zeigt die Akte ohne Lage, ohne Fehler.

## Hintergrundlauf (`lage_routes.py`, Zeitplan)

Die Lage entsteht ausschließlich im Zeitplan; es gibt keine Route, die ein Modell aufruft.

* Der Schritt hängt an `Scheduler` (`_run_lage`): im regulären Durchgang nach der Einordnung und in den
  Pausen zwischen den Durchgängen (`_run_background_lage`), im selben Thread, unter derselben
  Ablaufsperre (`_run_lock`, nicht blockierend), und nur, wenn der Zeitplan an ist, die Modellprüfung
  erlaubt ist und keine neue Quelle auf Einordnung wartet. Kein eigener Thread.
* `run_lage` in `_wire_scheduler` nimmt den Anbieter der Rolle `hintergrund` über `scheduled_provider`,
  also als `VerifiedLocalProvider`, wo der Plan `local_model_only` verlangt (die Gewichte des lokalen
  Modells werden vor jeder Anfrage bestätigt), und `permitted` prüft den Agenten und den Plan wie bei den
  anderen Läufen. Die Rolle `hintergrund` ist nie Cloud; ein nicht lokaler Anbieter wird ausdrücklich
  abgewiesen.
* **Kleine Pakete, wichtigste Sachen zuerst.** Höchstens zwei Sachen je Schritt (ein Modellaufruf je
  Sache). Geprüft werden immer die 20 jüngsten Sachen und dazu reihum ein Fenster von 40 weiteren. Vorn
  stehen Sachen mit kommender Frist oder kommendem Termin, dann die mit jüngster Aktivität. Eine Lage,
  die jünger als zehn Minuten ist, wird nicht sofort wieder geschrieben; eine Sache, die eben
  scheiterte, pausiert 30 Minuten.
* Statusmeldungen nennen nur Zahlen, nie Inhalte („2 Lagen erstellt, 1 Satz ohne ausreichenden Beleg
  verworfen“).

## Oberfläche

Die Akte (`AkteAbschnitte.tsx`) zeigt oben, falls vorhanden, den Abschnitt **Lage**: die Sätze, je Satz
„Belege“ mit einem Link je Quelle (Titel; ein Klick öffnet die Quelle an Ort und Stelle), darunter
„Erstellt am … · aus N Quellen · von einem lokalen Modell geschrieben, Satz für Satz gegen die Quellen
geprüft (ein Satz ohne ausreichenden Beleg verworfen)“ und bei veralteter Lage „Die Akte hat sich
seitdem geändert. Die Lage wird aktualisiert.“ Ruhig nach `16-gestaltung.md`: eine Fläche, keine
Farbe, kein Knopf. Bei veralteter Lage lädt die Seite höchstens sechsmal im Abstand von 20 Sekunden
still nach. Ohne Lage fehlt der Abschnitt; die Akte ist vollständig.

## Messung

**Messlatte, Stufe Akten** (`python -m messlatte akten --welt messlatte/welt --modell-hintergrund
ollama:NAME`): Mit einem lokalen Modell der Rolle `hintergrund` erzeugt die Stufe die Lage der fünf
Fälle und prüft sie an den Aktualitätserwartungen: **Eine verbotene Aussage (der überholte Wert als
heutiger Stand, ohne „vorher“) ist falsch**; fehlt die erwartete Aussage, ist die Lage unvollständig,
aber nicht falsch. **Ohne Modell steht „Nicht gemessen“ im Bericht**, nie „bestanden“; ein nicht
lokales Modell ebenso. Die Mechanik ist mit Skriptmodellen getestet (`test_akten_lage.py`):

* sorgfältiges Skriptmodell (sagt den Stand): 0 falsche Aussagen, 5 von 5 Lagen, 4 von 5 vollständig
  (bei `frist-verschoben-klinik` steht der 29.10. nicht im Stand-Zitat);
* unaufmerksames Skriptmodell (gibt die als überholt gekennzeichnete Zeile als Stand aus): **1 falsche
  Aussage** in `adresse-geaendert-wechsel` (alte Anschrift „Klinikstraße 5“), obwohl die Satzprüfung den
  Satz durchlässt, denn er steht wörtlich in einem Beleg. Genau diesen Fehler kann nur die Messlatte
  finden.

**Die Qualität mit echtem Modell steht aus.** Hier lief kein Ollama; die Zahlen oben messen die
Mechanik, nicht ein Modell. Das misst der Nutzer auf dem Zielgerät mit `--modell-hintergrund`.

## Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck im Code ersetzt) und die zuständigen Tests
laufen gelassen.

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| S1 | Belegnummer muss existieren | `test_beleg_ohne_existenz_wird_verworfen` |
| S2 | Beleg muss gültig sein | `test_ungueltiger_beleg_wird_verworfen` |
| S3 | Mindestens ein Beleg | `test_satz_ohne_belegnummer_wird_verworfen` |
| S4 | Datum mit Jahr muss im Beleg stehen | `test_datum_ohne_jahr_im_beleg_erlaubt_kein_erfundenes_jahr` |
| S5 | Datum ohne Jahr muss im Beleg stehen | `test_satz_bleibt_unveraendert_und_reihenfolge_bleibt` |
| S6 | Relative Angaben mit dem Zeitpunkt der Quelle | `test_umformulierung_von_bitte_und_rechnung_besteht` |
| S7 | Uhrzeit muss im Beleg stehen | `test_erfundene_uhrzeit_und_zeitbereich` |
| S8 | Zahl muss im Beleg stehen | `test_erfundene_zahl_wird_verworfen` |
| S9 | Betrag braucht dieselbe Währung | `test_betrag_braucht_dieselbe_waehrung_und_summen_sind_erfunden` |
| S10 | Adresse, Link, Kennung müssen im Beleg stehen | `test_mailadresse_link_und_kennung_muessen_stehen` |
| S11 | Wochentag muss belegt sein | `test_wochentag_muss_belegt_oder_zum_datum_passend_sein` |
| S12 | Anfang/Mitte/Ende Monat muss belegt sein | `test_monat_und_monatsphrase_muessen_belegt_sein` |
| S13 | Namen und Orte müssen im Beleg stehen | `test_erfundener_name_oder_ort_wird_verworfen` |
| S14 | Namensfolge muss zusammen im Beleg stehen | `test_erfundener_name_oder_ort_wird_verworfen` |
| S15 | Statusaussage braucht dieselbe Wortgruppe | `test_statusaussage_braucht_dieselbe_wortgruppe_im_beleg` |
| S16 | Verneinung im Beleg, nicht im Satz | `test_verneinungsumkehr_des_belegs_wird_verworfen` |
| S17 | Verneinung im Satz, nicht im Beleg | `test_verneinung_die_der_beleg_nicht_traegt_wird_verworfen` |
| S18 | Relative Zeitangaben ohne Bezug | `test_relative_zeitangaben_ohne_bezug_werden_verworfen` |
| S19 | Umlautschreibung ist tolerant | `test_relative_zeitangaben_ohne_bezug_werden_verworfen` |
| S20 | Sachname darf im Satz stehen | `test_sachname_darf_im_satz_stehen_auch_wenn_er_nicht_im_beleg_steht` |
| S21 | Verneinung wird satzteilweise gelesen (Datum-Punkt) | `test_verneinungsumkehr_des_belegs_wird_verworfen` |
| L1 | Jeder Satz läuft durch die Satzprüfung | `test_bestandene_saetze_werden_gespeichert_erfundene_verworfen_und_gezaehlt` |
| L2 | Höchstens drei Sätze | `test_hoechstens_drei_saetze_der_rest_zaehlt_als_verworfen` |
| L3 | Lage veraltet bei Aktenänderung (Fingerabdruck) | `test_lage_veraltet_bei_aenderung_der_akte_und_wird_neu_erzeugt` |
| L4 | Entzug wirkt sofort (veraltete Lage zeigt nur unveränderte Quellen) | `test_veraltete_lage_zeigt_keinen_satz_einer_geaenderten_oder_entzogenen_quelle` |
| L5 | Nur mit lokalem Modell | `test_ohne_lokales_modell_entsteht_keine_lage_und_die_akte_bleibt_vollstaendig` |
| L6 | Freigabe nach dem Modellaufruf erneut prüfen | `test_freigabe_entzogen_vor_oder_waehrend_des_aufrufs_speichert_nichts` |
| L7 | Anweisungsartige Zeilen bleiben draußen | `test_anweisungsartige_zeilen_kommen_nicht_zum_modell_und_sind_nicht_zitierbar` |
| L8 | Akteninhalt steht als fremde Daten | `test_das_modell_bekommt_akteninhalt_als_fremde_daten_ohne_werkzeuge` |
| L9 | Was von der Uhrzeit abhängt, gehört zum Fingerabdruck | `test_fingerabdruck_aendert_sich_mit_akte_und_zeitlage` |
| L10 | Mindestabstand zwischen zwei Lagen | `test_mindestabstand_verhindert_dauerschreiben` |
| L11 | Fehlschlag pausiert die Sache | `test_fehlschlag_pausiert_die_sache` |
| L12 | Antwort streng gelesen (Format) | `test_unbrauchbare_antwort_ist_ein_fehler_und_aendert_nichts` |
| L13 | Modellwechsel macht die Lage zum Kandidaten | `test_modellwechsel_macht_die_lage_zum_kandidaten` |
| R1 | Ohne lokales Modell ruft der Lauf nichts auf | `test_zeitplanschritt_ohne_lokales_modell_lasst_die_quellen_zu_hause` |
| R2 | Lauf prüft die Freigabe vor dem Paket | `test_lauf_entzug_mitten_im_paket_stoppt` |
| R3 | Lauf prüft die Freigabe vor jeder Sache | `test_lauf_entzug_mitten_im_paket_stoppt` |
| R4 | Paket klein | `test_paketgroesse_ist_klein` |
| R5 | Zeitplan: Lage nur mit Modellprüfung | `test_zeitplanschritt_ist_verdrahtet_und_pausiert_ohne_modellpruefung` |
| R6 | Zeitplan: Lokalpflicht des Plans (geprüfter lokaler Anbieter) | `test_zeitplanschritt_mit_lokalpflicht_prueft_die_gewichte_und_faellt_bei_fehlen_zu` |
| R7 | Zeitplan: Freigabe des Plans | `test_zeitplanschritt_stoppt_bei_geaenderter_freigabe` |
| R8 | Hintergrund: nur mit Zeitplan und Modellprüfung | `test_hintergrundschritt_nur_mit_zeitplan_und_modellfreigabe_und_ohne_dringenderes` |
| R9 | Hintergrund: gleiche Sperre, kein Warten | Test hängt (Sperre wird blockierend genommen); Lauf abgebrochen |
| R10 | Lage im Durchgang fängt Fehler ab | `test_scheduler_ruft_lage_im_durchgang_und_faengt_fehler` |
| R11 | Akte zeigt die Lage | `test_neue_quelle_macht_die_lage_veraltet_und_der_naechste_lauf_schreibt_sie_neu` |
| R12 | Anzeige: veraltet gekennzeichnet | `test_neue_quelle_macht_die_lage_veraltet_und_der_naechste_lauf_schreibt_sie_neu` |
| M1 | Messlatte: verbotene Aussage ist falsch | `test_lage_pruefung_kennt_den_vorher_hinweis_und_fehlendes` |
| M2 | Messlatte: ohne Modell nicht gemessen | `test_lage_ohne_modell_ist_nicht_gemessen_nie_bestanden` |
| M3 | Messlatte: nicht lokal nicht gemessen | `test_lage_mit_nicht_lokalem_modell_ist_nicht_gemessen` |

Alle 49 Proben wurden gefangen (S = Satzprüfung, L = Lage, R = Lauf, Zeitplan und Anzeige, M = Messlatte). Bei R9 hängt der Test statt zu scheitern, weil die Sperre blockierend genommen wird; der Lauf wurde von Hand beendet.

Die Proben liegen nicht im Repository; wer sie wiederholen will, ersetzt die genannten Ausdrücke in
`satzpruefung.py`, `lage.py`, `lage_routes.py`, `scheduler.py`, `server.py`, `akten_routes.py` oder
`messlatte/akten.py`.

## Offene Punkte

* **Eingabe ist ein Ausschnitt der Akte.** Die Lage sieht je Quelle nur den einen Abschnitt, den die
  Akte im Verlauf zeigt, und höchstens 3 bis 4 Zeilen je Rolle. Ein Detail, das nur in einem anderen
  Abschnitt derselben Quelle steht (etwa „Vortrag 11 Uhr“ neben einer Einladung), kommt nicht vor, und
  die Lage kann es nicht nennen. Das ist die Grenze „Eingabe ist die Akte“, kein Fehler.
* **Streng.** Die Satzprüfung verwirft im Zweifel; wie oft ein echtes Modell dadurch Sätze verliert,
  ist ungemessen. Die Zahl der verworfenen Sätze steht in der Ablage und im Bericht.
* **Gattungswörter** sind eine kurze Liste. Ein Substantiv, das weder im Beleg noch in der Liste steht,
  wird wie ein Name behandelt und verworfen.
* **Sinnverdrehung** ohne Verneinungswort und falsche Zuordnung von Zahlen erkennt nur der Mensch am Beleg.
* **Veraltet heißt nicht „wird gerade neu geschrieben“.** Ist der Zeitplan aus oder fehlt ein lokales
  Modell, bleibt der Hinweis stehen, bis wieder eine Lage entsteht; die Sätze bleiben nur sichtbar,
  solange ihre Quellen unverändert sind.
* **E3** nutzt die Satzprüfung später für Antworten; die Bezugstage für „heute“ und „morgen“
  (`relative_zeit_erlaubt`) muss der Aufrufer dann selbst auflösen.
