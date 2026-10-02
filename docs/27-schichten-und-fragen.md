# Schichten, Bezüge und Frageverständnis (Etappen D und E)

Stand: 29. September 2026. Entwurf für die Umsetzung von D und E aus
[`26-plan-stabschef.md`](26-plan-stabschef.md). Er baut auf dem Bestand auf und
ersetzt nichts, was schon trägt. Maßstab ist die Messlatte (`messlatte/`).

## Was es schon gibt

| Baustein | Modul | Was es leistet | Was fehlt |
|---|---|---|---|
| Rohmaterial | `episodes.py` | Quellen mit Versionen, Entzug, Ausschluss | Termine (Etappe C1) |
| Auszug je Quelle (Ebene 1) | `working_memory_*` | Abschnitte mit Art (Bitte, Zusage, Änderung, Stand, Angabe), exakte Textstellen, Modell nur zur Einordnung | Fristen als Datum; Bezug zur Sache |
| Themen und Erwähnungen | `memory_categories.py` | Themen je Abschnitt, erwähnte Personen/Organisationen/Projekte mit Textstelle | Verknüpfung mit einer Identität; Orte |
| Identität | `claims.py` (`entity_registry`), `person_merges.py`, C3 | Personen über Adressen, umkehrbare Zusammenführung | Verknüpfung von Erwähnungen ohne Adresse |
| Akte (Ebene 2) | `mappe.py` | Bitten, Zusagen, Entwicklungen, Aufgaben, Termine je Projekt/Person, ohne Modell | andere Sachen (Organisation, Ort, Thema, Ereignis); Verlauf |
| Lage (Ebene 3) | — | — | ganz |
| Erste Suchstufe | `bedeutungen.py` | Bedeutungen eines Begriffs aus Bestand und Kalender | enge Fragemuster; Bedeutungen aus Erwähnungen gehen unter |

## Grundsätze

1. **Rohmaterial ist die Wahrheit.** Ebenen 1–3 sind abgeleitet, jederzeit neu
   erzeugbar, nie Fakten im Bestand. Fakten entstehen weiter nur über Vorschlag
   und Annahme (`10-verdichtung.md`).
2. **Jeder Satz hat einen Beleg.** Ein Satz der Lage oder einer Antwort nennt die
   Abschnitte, auf denen er beruht. Eine Prüfung ohne Modell verwirft ihn, wenn
   seine Zahlen, Daten und Namen nicht in diesen Abschnitten stehen.
3. **Aktualität schlägt Ähnlichkeit.** Wo eine neuere Quelle eine ältere ändert
   (Art `change`/`status`), zeigt jede Ebene den neuen Stand und nennt den alten
   nur als „vorher“.
4. **Nichts still begrenzen.** Wo gekürzt wird, steht die Gesamtzahl daneben.
5. **Eine Aufgabe je Modul.** Neue Teile kommen als eigene Module mit klaren
   Datenklassen; `server.py` bekommt nur Verdrahtung in eigenen `*_routes.py`.

## D1 – Bezüge

Eine Quelle verweist auf beliebig viele **Sachen**: Person, Organisation,
Projekt, Thema, Ort, Ereignis. Jede Verknüpfung trägt ihre Grundlage:

| Grundlage | Beispiel | Sicherheit |
|---|---|---|
| Anker | Absender-, Empfänger- oder Gastadresse einer Person | sicher, ohne Rückfrage |
| Modell | Erwähnung „Frau Becker“ im Text, eindeutig einer Identität zuordenbar | vorgeschlagen, korrigierbar |
| Nutzer | Zuordnung per Klick | maßgeblich |

Speicherung: eine Tabelle Verknüpfung (Quelle, Fingerabdruck, Sache, Grundlage,
Textstelle). Erwähnungen aus `memory_categories` werden aufgelöst gegen die
Aliasse der Registry; mehrdeutige Erwähnungen bleiben offen und erscheinen in
der Rückfrage, statt geraten zu werden. Orte kommen als neue Art dazu.

Die **Art** eines Abschnitts (Frist, Zusage, Bitte, Änderung, Termin) stammt aus
der Einordnung von Ebene 1; Fristen bekommen ein aufgelöstes Datum (vorhandene
Zeitauflösung in `time_scope.py`, mit Bezug auf den Zeitpunkt der Quelle).

## D2 – Akten (Ebene 2)

Eine Akte je Sache, verallgemeinert aus `mappe.py`:

- **Verlauf:** die verknüpften Quellen chronologisch, je eine Zeile aus Ebene 1.
- **Offen:** Bitten und Zusagen ohne spätere Erledigung oder Absage.
- **Fristen:** kommende und verstrichene Daten mit Quelle.
- **Beteiligte:** Sachen, die mit dieser Sache gemeinsam vorkommen.
- **Stand:** der jüngste `change`/`status`-Abschnitt je Gegenstand.

Ohne Modell berechenbar, zwischengespeichert mit dem Fingerabdruck ihrer
Eingaben und neu berechnet, sobald eine verknüpfte Quelle sich ändert.

## D3 – Lage (Ebene 3)

**Stand: umgesetzt (30.09.2026)**, siehe [`32-lage.md`](32-lage.md): `satzpruefung.py` (ohne Modell,
wiederverwendbar für E3), `lage.py`, `lage_routes.py`, Zeitplanschritt, Anzeige in der Akte, Stufe Akten der
Messlatte mit `--modell-hintergrund`. Die Qualität mit echtem Modell steht aus.

Zwei bis drei Sätze je Sache, im Hintergrund vom Modell für Hintergrundarbeit
geschrieben. Eingabe ist die Akte, nicht das Rohmaterial. Ausgabe als JSON:
Sätze mit Belegnummern. Die Satzprüfung verwirft unbelegte Sätze. Fehlt ein
Modell, zeigt die Oberfläche die Akte ohne Lage.

## E1 – Frage verstehen

**Stand: umgesetzt (29.09.2026), Beschreibung und Messung in [`31-frageverstaendnis.md`](31-frageverstaendnis.md).**

Ein kleines, schnelles Modell übersetzt die Frage in eine strukturierte Anfrage:

```json
{"sachen": ["Mainz"], "zeitraum": "letzte_woche", "absicht": "ueberblick",
 "suchworte": ["Angebot", "Klinikum"], "umschreibungen": ["Verpflegung"]}
```

Die Sachen werden gegen die Registry, Aliasse, Projekte, Orte und Termine
aufgelöst. Ohne Modell greifen die heutigen Muster als Rückfall; sie werden
dabei weiter (etwa „Was ist **eigentlich** mit Mainz los?“).

**Mehrdeutigkeit:** Passt eine genannte Sache auf mehrere Einträge ähnlichen
Gewichts, fragt Kingfisher zurück und bietet **alle** Bedeutungen an, auch
private („Urlaub in Mainz“), mit je einer Zeile Kontext und einem Klick.

## E2 – Suchen von oben und unten

**Stand: umgesetzt (30.09.2026)**, Beschreibung, Messung und Sabotageproben in [`35-belegte-antworten.md`](35-belegte-antworten.md).

- **Von oben:** Lage und Akte der aufgelösten Sachen.
- **Von unten:** Volltextindex (C2) und, wo eingerichtet, Bedeutungssuche über
  das Rohmaterial, erweitert um die Umschreibungen aus E1.
- Zusammenführung per Rangfusion; Zeitraum und Aktualität filtern.

## E3 – Antworten

**Stand: umgesetzt (30.09.2026)**, siehe [`35-belegte-antworten.md`](35-belegte-antworten.md). Die Qualität mit echtem Modell steht aus.

Das Modell für Antworten formuliert kurz aus Akte und Belegen, jeder Satz mit
Belegnummern; die Satzprüfung aus D3 gilt auch hier. Scheitert sie, fällt die
Antwort auf den heutigen Weg zurück (Originalzitate). Die Antwort zeigt den
Weg nach unten: Lage → Akte → Quelle.

## E4 – Modelle nach Rolle und Geräte-Scan

**Stand: umgesetzt (30.09.2026).** Rollen `frage`/`antwort`/`hintergrund`/`einbettung`
(`model_roles.py`), Geräteempfehlung (`model_recommendation.py`), Laden über
Ollama (`model_pull.py`, `model_roles_routes.py`), Oberfläche unter
Einstellungen → Lokale KI; Beschreibung in `09-einrichtung.md`. Die Rolle
`frage` hat seit E1 einen Aufrufer (`frage.py`), gilt aber nur mit Zuweisung; Cloud gilt nur für `frage` und
`antwort`, `hintergrund` und `einbettung` bleiben lokal.

| Rolle | Aufgabe | Anforderung |
|---|---|---|
| `frage` | E1 | < 1 s, strukturierte Ausgabe |
| `antwort` | E3 | wenige Sekunden, belegt |
| `hintergrund` | Einordnung, Bezüge, Lage | gründlich, darf langsam sein |
| `einbettung` | Bedeutungssuche | lokal, dauerhaft |

Die Rollen erweitern das vorhandene Routing (`model_routing.py`,
`routing_runtime.py`, `local_model_guard.py`), statt ein zweites zu bauen. Je
Rolle ist ein lokales oder ein Cloud-Modell wählbar; Cloud nur mit
ausdrücklicher Einwilligung für diese Rolle. Der Geräte-Scan
(`device_profile.py`) schlägt je Rolle ein Modell vor, das zum Arbeitsspeicher
passt, und lädt es auf Klick.

## Reihenfolge und Messung

D1 → D2 → E1 → E2 → D3/E3 → E4. Nach jedem Schritt misst die Messlatte die
Stufe Abruf; die Stufe Antwort misst der Nutzer mit Modell auf dem Zielgerät.
