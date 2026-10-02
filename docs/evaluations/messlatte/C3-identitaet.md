# Etappe C3: Identität über Anker statt Namensstrings

Stand: 29. September 2026. Vorher/Nachher mit der Messlatte (`messlatte/`), ohne Modell,
also nur die Stufe „Abruf“. Rohdaten: `2026-09-29-c3-ohne-rauschen.{md,json}` und
`2026-09-29-c3-10k-rauschen.{md,json}` in diesem Ordner, Basis in den `2026-09-29-basis-*`
Dateien.

## Befunde vor der Arbeit (am Code geprüft)

1. **Nur der Absender wurde Teilnehmer.** `mail_ingestion.remember` schrieb
   `participants=[message.sender]`; `To` und `Cc` wurden von `connectors/mail.py` nicht einmal
   gelesen. Eine eigene gesendete Mail an jemanden machte diesen nicht zum Kontakt, und der
   Absender „Lea Hartmann“ (der Nutzer selbst) stand in der Personenliste.
2. **Personen waren Namenstexte.** `personen.py` und `graph.py` schlüsselten auf
   `name.strip().casefold()` des *ganzen* Beteiligtentextes, bei Mails also „Anna Keller
   <anna@x.example>“. Damit waren „Keller, Anna <a@x>“, „Anna Keller <a@x>“ und „<a@x>“ drei
   Personen (die Prüfung `people_quality` schlug sie als „gleiche Mailbox“ vor). Zwei Menschen
   gleichen Namens mit verschiedenen Adressen waren ebenfalls zwei Knoten, aber nur weil der
   Beteiligtentext die Adresse enthielt; Namen ohne Adresse (Notiz, Transkript) verschmolzen
   mit jedem gleichlautenden.
3. **Die Fragen kannten keine Personen.** Die Wortsuche des Arbeitsstands fand „Frau
   Reinhardt“ nur über das Wort im Text; die Quellen unter ihrer Adresse waren keine
   Kandidaten. Bei zwei Alex Winter zeigte die Rückfrage (`bedeutungen.py`) zwei gleich
   beschriftete Zeilen ohne Unterscheidung; „Für welche Firma arbeitet Alex Winter?“ ging gar
   nicht in die Rückfrage.

## Aufbau

Nichts ist neu gespeichert: Es gibt keinen zweiten Personenbestand und keine Migration. Die
Rollen liegen als Feld `contacts` im JSON-Dokument der Episode (ältere Dokumente ohne das Feld
werden mit Vorgabe gelesen); die Person selbst ist wie bisher eine Ableitung.

| Baustein | Aufgabe |
|---|---|
| `kontakte.py` | Beteiligte einer Quelle mit Name, Adresse, Rolle (`von`/`an`/`cc`/`bcc`) und `ich`; Bcc nur in der eigenen Kopie |
| `connectors/mail.py` | liest `To`/`Cc`/`Bcc` (vor dem Dekodieren getrennt, „Keller, Anna“ bleibt ein Name) und die eigenen Adressen des Kontos |
| `mail_ingestion.py` | schreibt alle Beteiligten; eine früher ohne Rollen aufgenommene, gleichlautende Mail wird ergänzt statt verdoppelt |
| `episodes.py` | Feld `contacts`, `add_contacts` (Nachtrag), Abfragen nach Adresse und Namen |
| `identitaet.py` | Anker: Adresse; Namen sind Aliasse; Namen ohne Adresse nur bei genau einem Träger; eigene Adressen sind „ich“ |
| `personen.py` | Personenliste nach Anker, je Person alle Adressen und Namen, Unterscheidung nach Domäne, `Mehrdeutig` bei gleichnamigen |
| `graph.py`, `person_digest_context.py`, `person_merge_api.py` | Knoten über Adresse; Zusammenführung (`person_merges`) und ihr Rückgängigmachen unverändert |
| `personenfrage.py` | eine in der Frage genannte Person: alle ihre Quellen als Kandidaten; gleichnamige ohne Merkmal: Rückfrage mit beiden |
| `bedeutungen.py` | Anreden („Frau“, „Dr.“) fallen weg; gleichnamige Absender mit Domäne und den letzten Betreffen unterscheidbar |
| `teilnehmer_nachtrag.py` | holt Kopfzeilen erneut und ergänzt Bestandsmails (nicht angeschlossen, siehe unten) |

Regeln, die im Code stehen:

* Gleiche Adresse: dieselbe Person, unter jedem Namen. Kein Fuzzy-Matching.
* Gleicher Name, verschiedene Adressen: zwei Personen, bis der Nutzer sie zusammenführt.
* Ein Name ohne Adresse wird einer Adresse nur zugeordnet, wenn genau eine ihn als Alias trägt
  (akademische Titel und „Keller, Anna“ gegen „Anna Keller“ sind gleich; „Herr“ und „Frau“
  bleiben stehen). Sonst bleibt er eine eigene, als offen gekennzeichnete Person mit den
  Kandidatenadressen.
* Aufgaben („wartet auf“) und Aussagen hängen nur an einer Person, die ihren Namen allein
  trägt. Bei zwei Alex Winter bekommt keiner die Aufgabe.
* Frage: Ein vollständiger Name, der zwei Adressen trägt, und kein Wort der Frage passt nur zu
  einer (Domäne oder Betreff ihrer Quellen), ist eine Rückfrage mit beiden. Trägt die Frage ein
  Merkmal („Catering“, „Institut“), gilt nur diese Person. Ein Teilname, der verschiedene Namen
  trifft („Roth“), wird nicht geraten (bleibt bei der Wortsuche).
* Wirken die Adressen **nacheinander** (der Zeitraum der einen endet, bevor die andere beginnt:
  Arbeitgeberwechsel, Messlatte `adresse-geaendert`), wird keine Rückfrage erzwungen. Das ist ein
  Hinweis, kein Beweis: Die Personen bleiben getrennt, bis der Nutzer zusammenführt, und beide
  Quellenmengen sind Kandidaten.
* Nennt die Frage einen Zeitraum, zählen von der Person nur die Quellen aus diesem Zeitraum.

## Backfill: Lassen sich Teilnehmer aus dem Rohtext ergänzen?

**Nein.** Der gespeicherte Text einer Mail ist der Nachrichtenkörper (`message.body`); die
Kopfzeilen `To`, `Cc` und `Bcc` sind nicht mitgespeichert und stehen nur im Original auf dem
Server. Was im Text an Anreden oder zitierten „Von: …“-Zeilen vorkommt, ist keine belastbare
Herkunft. Ergebnis:

* Neue Mails tragen alle Beteiligten.
* Beim erneuten Lesen einer Bestandsmail (etwa nach einem UIDVALIDITY-Wechsel) ergänzt
  `mail_ingestion.remember` die Beteiligten in der vorhandenen Episode, ohne zweite Fassung.
* `teilnehmer_nachtrag.nachtragen` holt für Bestandsmails die Kopfzeilen in Paketen erneut
  (Paketgröße begrenzt, wiederholbar, Fehler lassen die Mail offen, ausgeschlossene Quellen
  bleiben unberührt). **Nicht angeschlossen:** Aufruf und Takt gehören zur Mailaufnahme (C4).
* Folge, die der Nutzer kennen muss: Die Beteiligten sind Teil des Belegs. Ein Nachtrag ändert
  den Fingerabdruck der Quelle, deshalb ordnet die Aufnahme ergänzte Mails neu ein (mit lokalem
  Modell, Zeit und Rechenlast).

## Messung (Messlatte, ohne Modell, Stufe „Abruf“)

Die Antwortqualität ist **nicht gemessen**: In der Entwicklungsumgebung läuft kein Modell.
Alle Zahlen: „x von 136 erwarteten Belegen“, „Fragen mit allen Belegen von 71“, „Fragen mit
verbotenem Beleg im Kontext von 77“, „Rückfragen mit allen Bedeutungen von 7“.

Zwei Vergleiche, weil der Hauptzweig zwischenzeitlich Etappe C1 (Termine als Episoden)
aufgenommen hat:

| Lauf | Belege | alle Belege | verbotene im Kontext | Rückfragen |
|---|---|---|---|---|
| A. Basis vor C1 und C3 (`4fb80b8`), ohne Rauschen | 95 | 42 | 15 | 0 |
| A. C3 auf dieser Basis, ohne Rauschen | 103 | 45 | 15 | 2 |
| A. Basis, 10.000 Rauschquellen | 85 | 37 | 15 | 0 |
| A. C3 auf dieser Basis, 10.000 Rauschquellen | 89 | 40 | 15 | 2 |
| B. Hauptzweig mit C1 und E4, vor C3, ohne Rauschen | 101 | 47 | 15 | 0 |
| B. C3 nach dem Merge, ohne Rauschen | 107 | 49 | 16 | 2 |
| B. Hauptzweig mit C1 und E4, vor C3, 10.000 Rauschquellen | 91 | 41 | 14 | 0 |
| B. C3 nach dem Merge, 10.000 Rauschquellen | 94 | 43 | 15 | 2 |

Lauf B ist der Stand dieser Lieferung; die Protokolle stehen in
`2026-09-29-c3-ohne-rauschen.*` und `2026-09-29-c3-10k-rauschen.*`, der Stand davor in
`2026-09-29-hauptzweig-vor-c3-*.md`. Lauf A (Basis und C3 ohne C1) ist nur in dieser Tabelle
festgehalten.

### Was sich in Lauf B ohne Rauschen geändert hat (Fragen-IDs)

Besser:

* **namensgleich-04** („Für welche Firma arbeitet Alex Winter?“) und **namensgleich-06**
  („Was ist mit Alex Winter?“): Das Produkt fragt mit beiden Personen zurück, mit Domäne und den
  letzten Betreffen („Mails von Alex Winter (winter-catering.example) · 5 Quellen · zuletzt: „Probeverkostung
  Winter Catering“, „Preisanpassung und Probeverkostung“ …“ und die Zeile für ifeh-hessen.example
  mit „Einladung Gastvortrag am Institut“, „Bitte um Feedback zum Fragebogen“ …). Rückfragen mit allen
  Bedeutungen: 0 von 7 auf 2 von 7. Die fünf übrigen Rückfragen (`mainz-01`, `mainz-06`,
  `meeting-protokoll-06`, `zeitraum-06`, `zusage-abgesagt-06`) betreffen keine gleichnamigen
  Personen und sind nicht Teil von C3.
* **profil-01** (Dr. Reinhardt, 1 von 5 auf 2 von 5) und **profil-03** (Frau Reinhardt, 1 von 3
  auf 2 von 3): Quellen unter der Adresse der Person, auch die eigenen Antworten an sie.
* **kontakt-vor-jahren-03** (Herr Weidner), **zusage-abgesagt-03**, **mainz-02**: je eine
  erwartete Quelle mehr im Kontext.
* **namensgleich-02**: die verbotene Quelle `namensgleich-004` (Catering) ist nicht mehr im
  Kontext (`namensgleich-005`, der Termin, bleibt). In Lauf A ist bei **namensgleich-01** außerdem
  `namensgleich-010` (Institut) aus dem Kontext verschwunden.

Unverändert: **identitaet** (7 von 8 Belegen gefunden, 4 von 5 Fragen vollständig). Die
gefragten Quellen waren dort schon Kandidaten; der Gewinn steckt in der Struktur (zwei Personen,
getrennte Knoten, Rückfrage), nicht in dieser Zahl.

Schlechter oder Preis der Änderung:

* **meeting-protokoll-06** („Stand bei Roth“, 2 von 2 auf 1 von 2 Belegen) und, nur mit
  Rauschen, **zeitraum-02** (1 von 1 auf 0 von 1): Durch die Empfänger sind mehr Mails
  durchsuchbar, die den Namen tragen; die zwölf Plätze der Auswahl (gezählt in Textstellen, nicht
  in Quellen) reichen dann nicht mehr für alle. Ein Versuch, je Quelle nur zwei Textstellen
  zuzulassen, hat die Belege nicht verbessert und die Fragen mit verbotenem Beleg von 16 auf 18
  erhöht; er wurde verworfen.
* Mehr verbotene Belege im Kontext bei **falle-04** (`falle-007`), **frist-verschoben-02**
  (`frist-verschoben-001`), **zusage-abgesagt-01** (`zusage-abgesagt-002`): Wer „alle Quellen der
  Person“ als Kandidaten bringt, bringt auch ihre überholten. Gefragt ist hier D (Aktualität
  schlägt Ähnlichkeit), nicht C3.
* **adresse-geaendert-02/-03** (Jasmin Krüger schrieb nacheinander von zwei Adressen) bleiben
  eine Antwort, keine Rückfrage, wegen der Regel „nacheinander“ (siehe oben). Ohne sie wären beide
  Fragen in eine unnötige Rückfrage gekippt; das wurde in einem Zwischenlauf gemessen.

## Sabotageproben

Für jede Zusicherung wurde die Regel im Code absichtlich gebrochen und das Ergebnis der Tests
gelesen (`test_kontakte_identitaet.py`, `test_personenfrage.py`, `test_identitaet_graph.py`,
`test_teilnehmer_nachtrag.py`, `test_person_merges.py`, `test_menschen.py`, `test_graph.py`).

| Zusicherung | Bruch im Code | Fehlgeschlagen (Auswahl) |
|---|---|---|
| To und Cc werden Beteiligte | `kontakte.fuer_mail` verwirft alle Empfänger | `test_an_und_cc_werden_beteiligte_mit_rolle`, `test_bcc_nur_in_der_eigenen_gesendeten_mail`, `test_eigene_adresse_ist_ich_und_keine_fremde_person`, `test_beteiligte_werden_nachgetragen_und_der_text_bleibt` |
| Bcc nur in der eigenen gesendeten Mail | Bedingung in `fuer_mail` entfernt | `test_bcc_nur_in_der_eigenen_gesendeten_mail` |
| Eigene Adresse ist „ich“ | `kontakt()` setzt `ich` nie | 7 Tests, darunter `test_eigene_adresse_ist_ich_und_keine_fremde_person` |
| Eigene Adresse zählt nicht als Person | `personen._sammeln` überspringt „ich“ nicht mehr | 6 Tests, darunter `test_eigene_adresse_aus_den_einstellungen_gilt_auch_fuer_altbestand` |
| Eigene Adresse als Empfänger nicht in `participants` | Ausnahme in `teilnehmer_texte` entfernt | `test_an_und_cc_werden_beteiligte_mit_rolle` (und in der Messlatte `test_mails_kommen_ueber_den_mailweg_mit_kopfzeilen_an`) |
| Gleiche Adresse, eine Person („Keller, Anna“ = „Anna Keller“) | Anker enthält den Namen | 11 Tests, darunter `test_gleiche_adresse_mit_verschiedenen_namen_ist_eine_person` |
| Gleicher Name, verschiedene Adressen: zwei Personen | Anker ist der Name | 13 Tests, darunter `test_gleicher_name_mit_verschiedenen_adressen_sind_zwei_personen` |
| Name ohne Adresse nur bei Eindeutigkeit | `aufloesen` nimmt den ersten Kandidaten | `test_name_ohne_adresse_bleibt_bei_zwei_kandidaten_offen` |
| Nachtrag statt Verdopplung | `_ohne_beteiligte_gespeichert` findet nichts | `test_mail_ohne_rollen_wird_beim_erneuten_lesen_ergaenzt_nicht_verdoppelt` |
| Personenfrage findet Quellen über Alias | Alias-Abgleich in `erwaehnte` gebrochen | 14 Tests, darunter alle vier Formen „Frau/Dr./Claudia/Claudia Reinhardt“ |
| Gleichnamige ohne Merkmal: Rückfrage mit beiden | `unklare_person` verlangt Merkmal nie | `test_gleicher_name_ohne_merkmal_gehoert_in_die_rueckfrage` (beide Fragen), `test_gleichzeitige_gleichnamige_erzwingen_die_rueckfrage` |
| Ein Merkmal in der Frage entscheidet für eine Person | `unterscheidet` findet nie ein Merkmal | `test_mit_merkmal_gilt_nur_die_eine_person` (alle drei Fragen) |
| Aufgabe „wartet auf“ nicht dem Falschen zuschreiben | `eindeutig` immer wahr | `test_wartet_auf_gleichnamige_wird_keinem_zugeschrieben`, `test_api_meldet_mehrdeutigen_namen_als_409_mit_beiden_adressen` |
| Zusammenführung umkehrbar | `undo` ändert nichts | `test_zusammenfuehrung_der_gleichnamigen_ist_umkehrbar`, `test_confirm_persist_project_and_undo_without_changing_sources`, `test_api_preview_confirmation_staleness_and_undo` |
| Adresswechsel nacheinander erzwingt keine Rückfrage | `nacheinander` immer falsch | `test_adresswechsel_nacheinander_erzwingt_keine_rueckfrage` |
| Profil eines mehrdeutigen Namens mischt nicht | die Prüfung auf mehrere Kandidaten entfällt | `test_profil_eines_mehrdeutigen_namens_mischt_nicht`, `test_api_meldet_mehrdeutigen_namen_als_409_mit_beiden_adressen` |
| Kandidatenauswahl nimmt die Quellen der Person auf | `people` bleibt leer | `test_quellen_der_person_stehen_in_der_kandidatenauswahl`, `test_mit_zeitraum_zaehlen_nur_die_quellen_der_person_aus_dem_zeitraum` |

Alle 17 Brüche wurden von mindestens einem Test gefangen; danach wurde jeder Bruch zurückgenommen
(Arbeitsbaum sauber). Die Proben liegen als Skript nicht im Repository; jede ist im Code der
Tabellenzeile in einer Zeile nachzustellen.

### Sabotageproben der Nacharbeiten (Nachtrag im Takt, Übersetzung alter Zusammenführungen)

Tests: `test_teilnehmer_nachtrag_takt.py`, `test_teilnehmer_nachtrag_zeitplan.py`,
`test_person_merges_altkennung.py`. Alle 22 Brüche wurden gefangen und zurückgenommen.

| Zusicherung | Bruch im Code | Fehlgeschlagen |
|---|---|---|
| Rückstau der Einordnung bremst den Nachtrag | Prüfung `rueckstau(...)` entfernt | `test_rueckstau_der_einordnung_bremst_und_danach_geht_es_weiter` |
| Ohne Freigabe kein Abruf | `permitted()` im Schritt entfernt | `test_ohne_freigabe_wird_weder_geholt_noch_geschrieben` |
| Freigabe nach dem Abruf erneut geprüft | Prüfung unter der Sperre entfernt | `test_freigabe_zurueckgenommen_nach_dem_abruf_schreibt_nichts` |
| Schreiben unter `conversation_lock` | Sperre durch `nullcontext` ersetzt | `test_geschrieben_wird_unter_der_gemeinsamen_sperre` |
| Mail ohne Kopfzeilen blockiert nicht | wird nicht zurückgestellt | `test_mail_ohne_kopfzeilen_blockiert_die_uebrigen_nicht_…` |
| Lauf endet | `fertig` wird nie gesetzt | `test_takt_arbeitet_in_kleinen_paketen_mit_fortschritt_und_endet` |
| Gescheiterte Mail ruht, kommt wieder | Ruhezeit nicht vermerkt | `test_gescheiterte_mail_ruht_und_kommt_nach_der_pause_wieder` |
| Eine Mail in zwei Ordnern zählt einmal | `COUNT(DISTINCT …)` ohne DISTINCT | `test_eine_mail_in_zwei_ordnern_zaehlt_und_wird_einmal_geholt` |
| Nachtrag hängt im Mailtakt | Aufruf in `run_mail_intake` entfernt | `test_zeitplan_hat_den_nachtrag_im_mailtakt` |
| Pausierte Aufnahme stoppt den Nachtrag | nur `allowed` statt `store.aktiv` | `test_zeitplan_ruht_bei_pausierter_aufnahme` |
| Fortschritt im Status | Feld im Status entfernt | `test_status_zeigt_fortschritt_des_nachtrags` |
| Alte Zusammenführung findet Mitglieder | Aufruf in `graph.build` entfernt | `test_alte_zusammenfuehrung_zeigt_nach_der_umstellung_ihre_mitglieder`, `test_api_zeigt_uebersetzte_zusammenfuehrung` |
| Alte Kennung bleibt gespeichert | `alt_ids` bleibt leer | `test_alte_kennung_bleibt_am_mitglied_gespeichert` |
| Idempotent | Gültiges Mitglied wird verändert | `test_uebertragung_ist_idempotent` |
| Zwei alte Formen einer Adresse: ein Mitglied | Zusammenlegen entfällt | `test_zwei_alte_namensformen_derselben_adresse_werden_ein_mitglied` |
| Nicht Abbildbares wird markiert | Markierung entfällt | `test_nicht_abbildbares_mitglied_bleibt_sichtbar_…` |
| Mehrdeutiges wird nicht geraten | `>= 1` statt `== 1` | `test_mehrdeutige_alte_kennung_wird_nicht_geraten` |
| Gruppe nennt Nicht-Zuordenbares | `unassigned_members` leer | `test_nicht_abbildbares_mitglied_bleibt_sichtbar_…` |
| Gruppe ohne zuordenbare Mitglieder bleibt | `if not present: continue` wie zuvor | `test_gruppe_ganz_ohne_zuordenbare_mitglieder_bleibt_als_gruppe_sichtbar` |
| Eigene Adresse ist keine Person | Ausnahme entfernt | `test_eigene_adresse_gilt_auch_ohne_vorgegebene_kennungen_nicht_als_person` |
| Kein Scan bei gültigen Kennungen | Früher Ausstieg entfernt | `test_neuer_bestand_mit_heutigen_kennungen_wird_nicht_veraendert` |
| Aufgehobenes bleibt unberührt | Filter in `nachziehen` und `uebersetzen` und SQL-Bedingung in `mitglieder_ersetzen` entfernt | `test_aufgehobene_zusammenfuehrung_wird_nicht_angefasst` |

Zwei Proben waren beim ersten Versuch grün und haben die Tests verbessert: Die eigene Adresse fing nur
zufällig der Abgleich mit den heutigen Kennungen (jetzt eigener Test ohne vorgegebene Kennungen), und
„Aufgehobenes bleibt unberührt“ ist dreifach gesichert; einzeln gebrochen bleibt jede Sicherung grün,
erst alle drei zusammen lassen den Test rot werden.

## Offene Punkte

* **Bestandsmails ohne Empfänger (erledigt):** `teilnehmer_nachtrag.Lauf` hängt im Mailtakt
  (`server._wire_scheduler`, `run_mail_intake`), nur bei verbundenem Konto und laufender Aufnahme
  (dieselbe Freigabe wie die Aufnahme, geschrieben unter `conversation_lock`, nach dem Abruf
  erneut geprüft). Pakete zu 10 Mails je Takt (30 s). Weil jeder Nachtrag den Fingerabdruck ändert
  und die Mail neu einordnen lässt, ruht der Lauf, sobald mehr als 50 Mails des Kontos auf ihre
  (Neu-)Einordnung warten (Vergleich von `mail_intake_analysis.generation` mit der Stützgeneration
  der Episode; ohne Modell entfällt die Bremse). Mails, zu denen der Server keine Kopfzeilen mehr
  liefert, werden einmal versucht und dann übergangen; gescheiterte Abrufe ruhen eine Stunde. Der
  Fortschritt steht im Aufnahmestatus (`GET /api/v1/mail/intake`, je Konto `empfaengernachtrag`:
  `offen`, `ergaenzt`, `ohne_kopfzeilen`, `gedrosselt`, `fertig`); ist nichts mehr offen, endet der
  Lauf ohne weitere Abfragen. Der Zählstand liegt nur im Speicher: Nach einem Neustart wird einmal neu
  gezählt (was ergänzt ist, kommt nicht wieder vor). Die Oberfläche zeigt das Feld noch nicht an.
* **Zusammenführung in der Oberfläche:** `PeopleReview` schlägt gleichnamige Personen mit
  verschiedenen Adressen als „Gleicher Name“ vor; der Nutzer führt sie wie bisher zusammen. Zwei
  Adressen einer Person nacheinander (Arbeitgeberwechsel) bleiben bis dahin zwei Personen. Ein
  Hinweis „gleicher Name, nacheinander, gleicher Postfachname“ als Vorschlag wäre der nächste
  einfache Schritt.
* **Ältere Zusammenführungen (erledigt):** Zusammenführungen auf Namens-Kennungen (`person:<hash>`
  aus dem Text „Name <adresse>“) werden übersetzt (`person_merge_altkennung.py`). Beim Bau des
  Graphen (`graph.build`, also beim ersten Lesen der Personenansicht) werden die alten Kennungen
  aus den Teilnehmertexten der Episoden und den „wartet auf“-Namen neu berechnet und auf die
  Adress-Kennungen abgebildet. Das Mitglied behält die alte Kennung (`alt_ids`) und die alte
  Beschriftung (`alt_label`); zwei alte Formen derselben Adresse werden ein Mitglied. Was keine oder
  mehrere heutige Personen trifft (Quelle zurückgezogen, eigene Adresse, mehrdeutig), bleibt
  gespeichert mit `nicht_zuordenbar` und Grund; die Gruppe im Graphen nennt es in
  `unassigned_members` („Nicht mehr zuordenbar“), auch wenn gar kein Mitglied mehr zuzuordnen ist.
  Die Übertragung ist idempotent, scannt den Bestand nur, wenn ein Mitglied heute unbekannt ist,
  fasst Aufgehobenes nicht an, und Aufheben stellt die Einzelpersonen wieder her. Namen ohne Adresse
  behalten ihre Kennung. Offen: Die Oberfläche (`PeopleReview`) zeigt `unassigned_members` noch nicht;
  ein als nicht zuordenbar markiertes Mitglied wird nur erneut versucht, wenn seine Kennung im Bestand
  wieder auftaucht oder `nachziehen(..., erneut=True)` gerufen wird (bisher nirgends).
* **Anrede und Organisationsnamen:** „Herr“ und „Frau“ gelten nicht als Alias, akademische Titel
  schon. Ein Absender wie „Akademie Taunus“ ist für die Zuordnung eine Person; die Domäne
  unterscheidet, mehr nicht. Ein Teilname („Roth“), der zwei verschiedene Namen trifft, erzwingt
  keine Rückfrage: Organisationsnamen als Absender machten sie sonst zu häufig.
* **Telefonnummern** als zweiter Anker: nicht gebaut; die Stelle ist `identitaet.Nennung`
  (Feld `adresse`) und `Verzeichnis.aufloesen`.
* **Verknüpfung mit `entity_registry`:** Ausdrücklich angelegte Entitäten (`entities.py`)
  bleiben, wo sie sind; ihre Verknüpfung mit einer Adresse über `link_source` ist möglich,
  aber noch nicht Teil der abgeleiteten Personenansicht.
