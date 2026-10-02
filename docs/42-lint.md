# Lint über alle Akten (M2, Runde 2)

Stand: 30. September 2026. Code: `sidecar/icarus_memory/lint.py` (Prüfung, Befunde, Ablage, Zählung),
`lint_routes.py` (Hintergrundlauf, Routen, Entscheidung), Hook `akten_routes.nachlauf_anmelden`,
`lage.Lagen.ueberholte_saetze`; Oberfläche `app/kingfisher/src/Befunde.tsx`, `befunde.ts`; Messung
`messlatte/lint.py` und `messlatte/handlungen.py`. Tests: `sidecar/tests/test_lint.py`, `test_lint_routes.py`,
`messlatte/tests/test_lint.py`, `app/kingfisher/tests/befunde.test.mjs`; Browserprobe `scripts/probe_lint_ui.py`.

## Was er findet

Die Satzprüfung prüft jeden Satz gegen seine Quelle. Der Lint prüft die Akten gegeneinander, ohne Modell,
und legt **Befunde** an (Datenklasse `Befund`: Art, Sachen, Belege, ein Satz in Alltagssprache, Schwere):

| Art | Was | Folge |
|---|---|---|
| `widerspruch` | Eine Akte führt eine Frist oder einen Stand als aktuell, den eine andere Akte schon als überholt kennt (Person nennt noch den 15.01., die Projektakte kennt die Verschiebung auf den 29.01.). | zwei Vorschläge, „29.01.2027 gilt“ / „15.01.2027 gilt“ |
| `aussage_gegen_quelle` | Eine angenommene Aussage (`knowledge_claims`) widerspricht einer jüngeren Quelle derselben Sache: „Du hattest angenommen: Fabrikweg 3. Die Mail vom 15.09. nennt Hafenstraße 8. Was gilt?“ | ein Vorschlag, „„Hafenstraße 8“ übernehmen“ / „„Fabrikweg 3“ bleibt“ |
| `veralteter_satz` | Sätze der Lage, deren Belege alle älter sind als eine jüngere Änderung oder Standmeldung derselben Sache (dieselbe Regel, nach der die Akte solche Sätze ausblendet). | Hinweis; erledigt sich, wenn die Lage neu geschrieben ist |
| `waise`, `ohne_akte` | Ein Name in mindestens drei Quellen, den mehrere Adressen tragen: Diese Quellen hängen an keiner Akte. | Hinweis |
| `waise`, `ruhend` | Akte einer Person oder eines Projekts mit mindestens drei Quellen, die jüngste älter als zwölf Monate. Eine Organisation allein nicht (Rundschreiben ruhen oft jahrelang); mit gleichen Quellen steht sie im Befund der Person. | Hinweis, nie ein Vorschlag zum Löschen |
| `waise`, `verwaister_bezug` | Zuordnung des Nutzers zu einem Projekt, das es nicht mehr gibt; Zusammenführung mit einer Person, zu der keine Quelle mehr gehört. | Hinweis |
| `querverweis` | Eine Person nennt in mindestens drei Quellen ein Projekt beim Namen, keine dieser Quellen gehört zum Projekt, und die beiden Akten kennen sich nicht. | Hinweis |

Grundlage ist, was die Akten ohnehin wissen: `Akten.roh` (Fristen mit `ersetzt_durch`, Stand mit „vorher“),
`akten._gegenstand`/`_umfeld` für „gleicher Gegenstand“, die Bezüge (offene Erwähnungen, Zuordnungen des
Nutzers). Ein Widerspruch zählt nur, wenn beide Seiten einen **Wert derselben Sorte** tragen (Datum,
Anschrift, Postleitzahl, Mailadresse, Betrag) und sich diese Werte nicht überschneiden. Aktualität schlägt
Ähnlichkeit: Die jüngere Quelle ist „neu“.

## Was er nicht findet

* Widersprüche ohne vergleichbaren Wert: Zusage gegen Absage, zwei Meinungen, „läuft gut“ gegen „stockt“.
* Werte, die keine Akte als Frist oder Stand führt (ein Datum in einer bloßen Angabe zählt nur, wenn die Akte
  es als überholt kennt).
* Was die grobe Wortstammregel „gleicher Gegenstand“ nicht zusammenbringt; umgekehrt kann sie zwei Fristen
  zum selben Thema verwechseln. Das ist dieselbe Grenze wie in der Akte (`30-akten.md`).
* Zwei Akten, die beide nur den alten oder nur den neuen Wert kennen und keine gemeinsame Akte haben, die
  beide Quellen sieht: Dann weiß der Lint nicht, welche Seite überholt ist.
* Ohne Modell gibt es keine Lage und damit keine veralteten Sätze.

## Warum Vorschlag

Die Regel des Gedächtnisses gilt unverändert (`10-verdichtung.md`): Der Lint liest nur. Aus Widersprüchen
entstehen Wissenskandidaten über `KnowledgeService.propose` (`proposed_by = 'lint'`, Beleg: die Quelle mit
dem Zitat), nie direkt Aussagen. Erst der Klick in der Liste macht daraus Wissen
(`POST /api/v1/lint/befunde/{id}/entscheiden`). Wie bei einer Berichtigung steht die angenommene Aussage dann
auf einer eigenen Quelle „vom Nutzer entschieden“, nicht auf der Mail: Eine Quelle, die in bestätigtes Wissen
eingegangen ist, zeigt die Akte nicht mehr roh; die Mail mit der neuen Frist verschwände sonst gerade dort,
wo der Widerspruch auffiel. Der Vorschlag des Lint bleibt als Spur („abgelöst“), der andere Wert wird
zurückgestellt oder abgelehnt. „Ignorieren“ lehnt offene Vorschläge ab; nichts wird Wissen, was niemand
gewählt hat.

Kingfisher darf keinen der beiden Werte stillschweigend nehmen. Die Liste nimmt dem Nutzer trotzdem die
Arbeit ab: Sie findet den Widerspruch, nennt beide Werte mit Quelle und löst ihn mit einem Klick.

## Ablage und Lauf

* **Ablage** `lint.sqlite3` (eigene Datei, eigene Versionierung, in Sicherung und Schemaprüfung): Befunde mit
  Status `offen`, `erledigt`, `abgewiesen`. Der Schlüssel eines Befunds hängt an Art, Sachen und Belegen, nicht
  am Text: Ein abgewiesener Befund kommt nicht wieder, solange sich an den Quellen nichts ändert. Offene
  Befunde, die ein Lauf nicht mehr findet, entfallen; entschiedene bleiben als Spur. Die Liste zeigt keinen
  Befund, dessen Quelle entzogen ist (Entzug wirkt sofort).
* **Hintergrund:** nach dem Abgleich der Bezüge, im selben Faden (`akten-bezuege`), also nie parallel zu ihm
  und nie in einer Anfrage; höchstens alle zehn Minuten und nur, wenn sich seit dem letzten Lauf etwas
  geändert hat; der erste Lauf nach dem Start wartet die zehn Minuten ab.
* **Anstoß:** `POST /api/v1/lint` („Jetzt prüfen“). Läuft schon einer, sagt die Antwort das, statt zu warten.

| Route | Zweck |
|---|---|
| `POST /api/v1/lint` | Bezüge nachführen, prüfen, Befunde abgleichen, fehlende Vorschläge anlegen |
| `GET /api/v1/lint/befunde?status=offen` | Befunde mit Namen der Sachen, Titeln der Belege, Stand der Vorschläge, Zählung |
| `PATCH /api/v1/lint/befunde/{id}` | `{status: erledigt | abgewiesen | offen}` |
| `POST /api/v1/lint/befunde/{id}/entscheiden` | `{wahl: alt | neu}`, nur bei Widersprüchen mit offenem Vorschlag |

**Zählung für Briefing und Logbuch:** `lint.zusammenfassung(app)` (oder mit einer `Befunde`-Ablage) liefert
immer `{'offen', 'wichtig', 'je_art': {alle fünf Arten}, 'neu_seit_letztem_lauf', 'letzter_lauf'}`, liest nur
die Ablage und wirft nie. Die Signatur steht im Modulkopf von `lint.py` und ist stabil.

## Oberfläche

Einstellungen → Für Techniker → Befunde der Prüfung über alle Akten: „Was Kingfisher aufgefallen ist“. Je Befund ein
Satz, die beteiligten Akten als Links, bei Widersprüchen der Hinweis „Ein Vorschlag: Erst dein Klick macht
daraus Wissen“ und zwei Knöpfe mit dem Wert darauf, sonst „Erledigt“; „Ignorieren“ bei allen. Nach jedem
Klick ein Satz, was passiert ist. Ruhende Akten stehen zugeklappt unten. Keine neue Hauptseite.

## Messung

**Messlatte, Stufe Lint** (`python -m messlatte lint --welt messlatte/welt [--rauschen N]`). Die Welt nennt
erwartete Befunde je Szenario (`lint` in `FORMAT.md`); neu sind Projekte des Arbeitsbereichs, Zuordnungen von
Quellen und angenommene Aussagen (`projekte`, `projekt`, `angenommen`), die `messlatte/handlungen.py` über die
Routen der Oberfläche einspielt. Szenario `widersprueche` (12 Quellen): Person gegen Projektfrist, angenommene
Lieferanschrift gegen jüngere Mail, ein Name zweier Personen in drei Gesprächen, ein Referent, der dreimal
über das Projekt schreibt. Namen und Betreffwörter stammen aus dem vorhandenen Wortschatz der Welt: Das
Rauschen, das die Messlatte aus diesem Wortschatz erzeugt, bleibt dadurch Quelle für Quelle gleich (geprüft).
Eine erste Fassung mit neuen Namen und Wörtern wie „Angebot“, „Mittagessen“, „Küche“ verschlechterte mit
10.000 Rauschquellen die Abrufkennzahlen (Rückfragen 7 → 6, Fragen vollständig 57 → 55) und wurde ersetzt. Dazu in `kontakt-vor-jahren` die ruhende Akte von Holger Weidner.

| Lauf | erwartete Befunde gefunden | Fehlalarme | Fakten unverändert | Dauer |
|---|---|---|---|---|
| ohne Rauschen (188 Quellen, 109 Sachen) | **5 von 5** | **0** | ja (1 angenommene Aussage vor und nach dem Lauf; 3 offene Vorschläge) | 2,2 s (Anstoß samt Nachführen) |
| 10.000 Rauschquellen (4.386 Sachen) | **5 von 5** | **0** | ja | 45 s (erster Lauf, Akten kalt) |

Vorher gab es keinen Lint (0 von 5 möglich). Abrufkennzahlen mit Regel-Einordnung vorher (`807bbc9`) → nachher:
124 → 124 von 136 (10k: 109 → 109), Fragen vollständig 64 → 64 (57 → 57), Rückfragen 7 → 7; die Fehlerlisten
sind gleich.

Im Rauschen meldet der Lint Hinweise „ruhend“; die Stufe prüft jeden (jüngste Quelle älter als ein Jahr) und
zählt sie getrennt, nicht als Fehlalarm. Jede andere Art im Rauschen wäre ein Fehlalarm. Berichte:
`docs/evaluations/messlatte/2026-09-30-lint-*`.

Die Zeile im Verlauf steht in `docs/evaluations/messlatte/README.md`.

## Sabotageproben

Jede Zusicherung wurde absichtlich gebrochen (ein Ausdruck ersetzt) und die zuständigen Tests laufen gelassen
(Skript im Arbeitsverzeichnis, nicht im Repository).

| Probe | Gebrochene Zusicherung | Gefangen von |
|---|---|---|
| L1 | Widerspruch übersehen (veraltete Akte falsch bestimmt) | `test_person_nennt_noch_die_alte_frist…`, `test_anstoss_findet_den_widerspruch…`, Messlatte `test_alle_erwarteten_befunde_ohne_fehlalarm` |
| L2 | Fehlalarm Stand: gleiche Anschrift gilt als Widerspruch | `test_stand_mit_anderer_anschrift_ist_ein_widerspruch_gleiche_anschrift_nicht` |
| L3 | Fehlalarm Aussage: gleicher Wert in jüngerer Quelle | `test_aussage_ohne_widerspruch_bleibt_ohne_befund` |
| L4 | Fehlalarm Aussage: ältere Quelle zählt wie eine jüngere | `test_aeltere_quelle_mit_anderem_wert_widerspricht_der_aussage_nicht` (kam durch diese Probe dazu) |
| L5 | Aussage gegen Quelle übersehen (Anschrift nie verglichen) | `test_angenommene_aussage_gegen_juengere_mail…`, `test_alt_gilt_behaelt…`, Messlatte |
| L6 | Querverweis trotz Bezug | `test_kennen_sich_die_akten_gibt_es_keinen_querverweis` (Test durch diese Probe geschärft, doppelte Prüfung entfernt) |
| L7 | Waise ohne Akte schon ab einer Quelle | `test_name_zweier_personen_in_drei_quellen_ist_eine_waise` |
| L8 | Ruhend schon ab einer Quelle | `test_zwei_alte_quellen_sind_keine_ruhende_akte` |
| L9 | Ruhende Organisation allein ist ein Befund | `test_eine_ruhende_organisation_allein_ist_kein_befund` |
| L10 | Ruhend ohne Stichtag (Grenze falsch herum) | `test_stand_mit_anderer_anschrift…` (zusätzliche Befunde) |
| L11 | Veralteter Satz übersehen | `test_lage_mit_saetzen_auf_aelteren_belegen…` |
| L12 | Schlüssel hängt am Text | `test_befund_prueft_art_und_nur_widersprueche_tragen_entwuerfe` |
| V1 | **Direktes Schreiben statt Vorschlag** (der Lauf nimmt selbst an) | `test_angenommene_aussage_gegen_juengere_mail_wird_ein_vorschlag_nie_ein_fakt`, `test_anstoss_findet_den_widerspruch_und_legt_nur_vorschlaege_an`, Messlatte `test_der_lint_schreibt_keinen_fakt…` |
| V2 | Annahme auf der Mail statt auf eigener Quelle | `test_neu_gilt_macht_den_neuen_wert_zu_wissen_und_die_mail_bleibt_in_der_akte` |
| V3 | Ignorieren lehnt die Vorschläge nicht ab | `test_ignorieren_lehnt_die_vorschlaege_ab…` |
| A1 | Ein Lauf öffnet Ignoriertes wieder | `test_ablage_behaelt_entscheidungen…`, `test_ignorieren_lehnt…` |
| A2 | Entzug wirkt nicht sofort | `test_entzogene_quelle_nimmt_den_befund_sofort_aus_der_liste` |
| D1 | Drosselung fehlt | `test_hintergrund_laeuft_nach_dem_abgleich_im_selben_faden_und_gedrosselt` |
| M1 | Messlatte: Befund mit nur einem Teil der Quellen zählt als gefunden | `test_zuordnung_zaehlt_fehlalarme_und_verfehltes_streng` |
| M2 | Messlatte: Fehlalarme werden nicht gezählt | `test_zuordnung_zaehlt_fehlalarme_und_verfehltes_streng` |

20 Proben, alle gefangen; zwei (L4, L6) erst, nachdem die Probe einen schwachen Test zeigte.

## Offene Punkte

* **Wert statt Bedeutung.** Die Sorten sind Datum, Anschrift, Postleitzahl, Mailadresse und Betrag. Status
  („zugesagt“ gegen „abgesagt“) prüft der Lint nicht; das tut die Akte selbst (erledigt, abgesagt).
* **Gegenstand eines Vorschlags.** Aus einem Widerspruch zweier Akten wird ein Wissenskandidat zur
  wichtigsten beteiligten Sache (Projekt vor Organisation vor Person) mit dem Prädikat „Frist Belegungsplan“
  oder „Anschrift“. Das ist grob; eine Aussage über eine Person folgt der Namensprojektion der Gesprächsvorschläge.
* **Dauer.** Der erste Lauf über 10.000 Rauschquellen rechnet alle Akten (Zwischenspeicher) und braucht rund
  45 Sekunden; danach wenige Sekunden. Der Anstoß über die Route wartet so lange.
* **Logbuch.** Die Zählung steht bereit (`zusammenfassung`); die Zeile im Briefing baut das Logbuch.
