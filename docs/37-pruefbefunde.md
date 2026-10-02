# Prüfbefunde vom 29.09. behoben

Eine unabhängige Prüfung fand vierzehn Befunde in den Etappen D3, F1 bis F3
(Akten, Lage, Satzprüfung, Briefing, Gespräche). Zu jedem gibt es einen Test, der den
Fehler zeigte (`sidecar/tests/test_pruefbefunde_0929.py`, bei Lage und Sicherung in
`test_lage.py` und `test_complete_recovery.py`), die kleinste Behebung und eine
Sabotageprobe: Behebung zurückgenommen, Test rot, Behebung wiederhergestellt, Test grün.

| Nr. | Befund | Behebung | Sabotageprobe |
|---|---|---|---|
| 1 | Die Packliste las `all_episodes` und zeigte entzogene, ignorierte und überholte Notizen (auch im Briefing). | `EpisodeStore.geltende_zuletzt` (nur aktuelle, nicht ignorierte Fassungen); `_aufnehmen` prüft `usable_ids`; die Lage zeigt keine Sätze mit nicht mehr geltenden Belegen. | Test `test_packliste_liest_keine_entzogene_notiz` und `…_ueberholte_fassung` rot ohne Behebung. |
| 2 | Das Wort „Frist“ ließ Jahresbericht (15.10.) und Steuererklärung (30.11.) einander „ersetzen“. | `_gegenstand`: Stämme des Umfelds ohne allgemeine Fristwörter, mindestens zwei gemeinsame. Ein Kompositum mit Gegenstand („Einreichfrist“) bleibt tragend; `frist-verschoben` der Messlatte bleibt grün. | `test_verschiedene_fristen_ersetzen_sich_nicht` rot; die Gegenrichtung (`…_bleibt_ersetzt`) schützt die Verschiebung. |
| 3 | Bei automatischer Zuordnung schrieb `_sprecher_uebernehmen` Namen, Adressen und Projekt unumkehrbar in die Quelle. | Nur nach Bestätigung (`bestaetigen`, Oberfläche „Stimmt so“). Was hinzukommt, merkt die Ablage in `uebernommen` (Migration 2); `loesen` und eine Bestätigung für einen anderen Termin nehmen genau das zurück (`EpisodeStore.remove_contacts`, `link_project(…, None)`). Begründung: `add_contacts` ist absichtlich additiv; ein Merkzettel je Mitschrift ist die kleinste Lösung, die nie fremde Einträge entfernt. | Vier Tests rot ohne Behebung (Auto schreibt nichts, Bestätigen übernimmt, Lösen nimmt zurück, Lösen entfernt nur Eigenes). |
| 4 und 7 | Der Register-Cache erkannte `ignore` und `add_contacts` nicht, las ignorierte Episoden und hielt beim Bau `episodes._lock` über den ganzen Bestand. | `EpisodeStore.geltender_stand` (Anzahl, Zeilennummern, Stützgeneration der geltenden Quellen) als Cache-Stand; `each_geltende` liest seitenweise; Bau ohne Speichersperre, Stand vor und nach dem Bau verglichen. | Drei Tests (Entzug, Nachtrag, Sperre) rot; mit dem alten Stand allein bleibt der Cache veraltet. |
| 5 | `gespraeche.sqlite3` fehlte in der Sicherung; Entscheidungen zu Mitschriften gingen bei der Wiederherstellung verloren. | In `SQLITE_DATA_FILES` und in die Schema-Vorabprüfung (`update_backup`); beim Wiederherstellen wird das Handle der Ablage mit den anderen geschlossen und neu geöffnet. | `test_every_backup_store…` (jetzt mit Ablage), Mitgliedschaft und Wiederherstellung über die Routen rot. |
| 6 | „Fertigung“ zählte als „fertig“; „offen“ und „noch nicht“ waren kein Gegenstatus. | Wortformen über Endungsliste statt Präfix; Gruppe „offen“ (offen, ausstehend, unerledigt, „noch nicht“); `_gegenstatus` weist einen Satz ab, wenn der Beleg dort, wo beide die meisten Sachwörter teilen, nur das Gegenteil sagt. | Die drei Beispiele aus dem Befund plus Gegenstatus und Verlauf rot; bestehende Umformulierungen bleiben grün. |
| 8 | Mailhilfen nutzten `agent.provider` (Rolle „antwort“). | `rollen_von(app).provider('hintergrund')` für Antwortentwurf und Aufgabenvorschläge; lokal-pflichtig bleibt. | Beide Tests rot ohne Behebung. |
| 9 | Die Wegezeit blockierte das Briefing (bis 12 s je Termin) und merkte nur Erfolge. | Zeitbudget von 3 s je Aufruf (`WegezeitDienst.frist`); der Rest erscheint als „wird berechnet“, die Anfrage läuft im Hintergrund weiter, die Oberfläche lädt nach. Fehlschläge gelten 60 s. Der Einwilligungstext nennt den Ort des vorherigen Termins als Startpunkt. `mac_antworten` prüft `aktiv`. | Drei Tests rot ohne Behebung. |
| 14 | Eine veraltete Lage zeigte Sätze weiter, die eine neuere Meldung überholen könnte. | Sätze ausgeblendet, wenn eine change/status-Quelle, die beim Schreiben der Lage noch nicht in der Eingabe war, jünger ist als alle Belege des Satzes; `stand_vom` und Hinweis in der Oberfläche; zeigt sie nichts mehr, meldet die Akte `lage_wird_aktualisiert`. | Fünf Tests rot ohne Behebung. |
| 15 | `a.zeit.date() <= tag` verglich das UTC-Datum mit dem Tag des Nutzers. | `bezugstag()` (Zeitzone des Nutzers). | Absage 00:30 Uhr Ortszeit nach dem Termintag: rot ohne Behebung. |
| 16 | Nachname als Teilstring („Braun“ in „Braunschweig“). | Ganzes Wort (`_als_wort`), auch für Organisationsnamen. | `test_nachname_nicht_als_teilstring` rot. |

## Befund 1: geprüfte Fundstellen

Jede Stelle in `terminvorbereitung.py`, `einpacken.py`, `tagesbriefing.py`, `fristlage.py`,
`transkript_*.py`, `lage.py`, `akten.py` und `bezuege.py`, die `all_episodes`, `each_episode`
oder `get` nutzt und das Ergebnis zeigt:

* `terminvorbereitung._packquellen`: behoben (`geltende_zuletzt`).
* `terminvorbereitung._aufnehmen`: behoben (`usable_ids`).
* `terminvorbereitung._Arten`, `_wuensche`: lesen Quellen, die aus `quellen_von` stammen; diese Abfrage
  verlangt geltende Quellen (`GUELTIG`). Unverändert.
* `lage.lage`: behoben (`usable_ids` statt `get`).
* `akten._verlauf_zeigen`, `_termine_zeigen`, `bezuege._schreibweise`, `zitat`, `fristlage.quellenart`:
  bekommen ihre Episoden aus `quellen_von` beziehungsweise aus Bezügen, die `entziehen` und `GUELTIG`
  bereinigen; `get` liest dort nur Titel oder Art. Unverändert.
* `transkript_zuordnung`: `tagged` filtert ignorierte; `fuer_termin` prüft den Zustand. Unverändert.
* `bezuege.register`: siehe Befund 4.
* `einpacken.py` und `tagesbriefing.py` lesen keine Episoden selbst.

## Offene Punkte

* `agent.provider` wird außerhalb der Mailhilfen weiter direkt genutzt (`person_digest_api.py`,
  `person_digests.py`, `routing_runtime.py`, `server.py`); ob dort ebenfalls eine Hintergrundrolle
  gemeint ist, ist nicht geprüft.
* Das Wegezeit-Budget gilt je Briefing-Aufruf; die Oberfläche lädt „wird berechnet“ nach vier Sekunden
  nach, ein Push vom Sidecar gibt es nicht.
