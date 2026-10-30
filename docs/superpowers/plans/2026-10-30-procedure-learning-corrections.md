# Dauerhafte Ablaufkorrekturen zuverlässig übernehmen

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Freigegebenes Abschlussziel; native Umsetzung, ein unabhängiges Schlussreview.

**Goal:** Bestehende Skill-Lernvorschläge aus klaren dauerhaften Ablaufanweisungen nutzbar machen und offene passende Vorschläge wiederverwenden.
**Architecture:** Bestehende Gesprächsroute, ProposalStore und SKILL.md-Darstellung beibehalten. Begrenzte Erkennung ausschließlich am Anfang der direkten Nutzerbitte; keine Modellrunde zur Auswahl. Lernvorschläge bleiben inaktiv.
**Tech Stack:** vorhandenes Python/FastAPI/SQLite, bestehende UI unverändert.
**Spec:** `docs/68-gedaechtnis-abschluss.md`, ausdrückliche Nutzerfreigabe vom 30.10.2026.

## Global Constraints

- Großimport bleibt pausiert; künstliche Daten in Tests und Git.
- Keine neuen Modelle, Cloudaufrufe, Werkzeuge, Datenbanken oder Oberflächen.
- Fakten, Kontaktstil und Verfahren getrennt halten; keine neue Berechtigung durch Lernen.
- Positive Eingabe: „Bei Zunftmails bitte künftig zuerst den Anlass prüfen, dann den Entwurf gegenlesen.“ oder „Merke dir für Zunftmails: zuerst Anlass prüfen, danach gegenlesen.“
- Bestehende Form „Lerne diesen Ablauf: …“ bleibt gültig.
- Reiner Stilwunsch, einmalige Arbeitsbitte, Frage, Zitat oder Mailtext erzeugt keinen neuen Lernaufruf.
- Passende offene und aktive Vorschläge anbieten, keine abgelehnten/entzogenen/überholten Fassungen; höchstens acht Metadaten, 2.400 Bytes, keine Ablaufkörper im Auswahlkatalog.
- Vollständige Modellqualität und Mac-Abnahme bleiben eigene offene Nachweise.

## Review Focus

- Ein zitiertes „künftig zuerst … dann …“ darf nicht zur eigenen Anweisung werden.
- „Schreib künftig kürzer“ ist Stil, keine Verfahrenskopie.
- Ein offener Vorschlag darf bei Wiederverwendung nicht vorzeitig aktiv werden.
- Quellenentzug/Versionen müssen auch wiedergefundene Lernvorschläge sperren.
- Erkennung darf keine beliebigen Gesprächsrunden in teure Modell-Lernarbeit verwandeln.

### Task 1: Klare dauerhafte Ablaufanweisung erkennen

Files: `sidecar/icarus_memory/procedure_routes.py`, `sidecar/tests/test_procedure_runtime.py`, `docs/67-bewaehrte-ablaeufe.md`.
Interfaces: `explicit_learning(message: str) -> bool` wird unverändert von `server.py` und `learn()` verwendet; der existierende Lernpfad bewahrt Quellenbindung, inaktiven Vorschlag und Bestätigung.

- [ ] Tests zuerst für beide positiven Formulierungen, reine Stilbitte, einmalige Aufgabe, Frage, Zitat/Weiterleitung und zweite Zeile. Echte HTTP-Probe: ein Modellaufruf, genau ein inaktiver Vorschlag, kein aktiver Skill vor Bestätigung; Quellenentzug blockiert Annahme.
- [ ] Run `TZ=UTC python -m pytest sidecar/tests/test_procedure_runtime.py -q --tb=short`; neue positive Fälle müssen vor Änderung fehlschlagen.
- [ ] Begrenzte direkte Daueranweisungen zusätzlich zum bestehenden Befehl erkennen; Dauerbezug und mindestens zwei erkennbare Verfahrensschritte erforderlich. Nicht nach Befehlen in Quellen suchen.
- [ ] Betroffene Tests grün, dokumentierte Benutzerbeispiele; Commit.

### Task 2: Bereits offene Vorschläge wiederfinden

Files: `sidecar/icarus_memory/procedures.py`, `sidecar/tests/test_procedures.py`, `docs/67-bewaehrte-ablaeufe.md`.
Interfaces: `ProcedureStore.learning_catalog(message: str) -> list[dict]`; bestehendes `propose()` dedupliziert identische bekannte Fassungen. Auswahl zur Ausführung bleibt ausschließlich active.

- [ ] Tests zuerst: passende pending-Metadaten finden, keine Körper/Quellen laden; zurückgewiesene/entzogene/ersetzte/ungültige Grundlagen ausschließen; gleiche Fassung wiederverwenden; acht/2.400-Grenze bewahren.
- [ ] Run `TZ=UTC python -m pytest sidecar/tests/test_procedures.py -q --tb=short`; fehlender offener Vorschlag muss rot werden.
- [ ] Vorhandene Auswahl um frische offene Vorschläge ergänzen und pro Name aktuelle Metadaten priorisieren; Bestätigung, Versionierung und Berechtigungen unverändert lassen.
- [ ] Pflichtprüfungen aus CONTRIBUTING plus betroffene Verfahrenstests; unabhängiges Review, konkrete Befunde einmal rot/grün beheben. Commit und Draft-PR. Keine Modellwiederholung bei unzureichender Speicherreserve.
