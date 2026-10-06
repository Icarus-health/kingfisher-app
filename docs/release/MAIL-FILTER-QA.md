# Mailfilter vor automatischer Quellenaufnahme

Stand: 2026-10-06. Die historischen Prüfungen unten stammen vom 8. September. Aktuelle Korrekturen und Modellgrenzen stehen im [lokalen Betriebsnachweis](LOCAL-MEMORY-RUNTIME-2026-10-06.md); daraus folgt keine neue Gesamtquote oder Fehlerfreiheitszusage.

## Verhalten

- Einstellungen → Automatik → Mailfilter: Spam-Markierungen, Newsletter und ausdrücklich gesperrte Absender werden vor der automatischen Quellenaufnahme zurückgehalten. Erlaubte Absender umgehen Newsletter/KI, aber keine Sperr- oder Spam-Markierung.
- Optional prüft das kleine lokale Entscheidungsmodell der Prüfrolle sonstige Mails; ohne Decision-Modell nutzt der Filter die lokale Fragerolle. Auch die dauerhafte Ordneraufnahme verwendet diesen Filter. Der Mailfilter-Schalter bleibt unabhängig von der Pause der Gedächtniseinordnung. Keine Cloud-Ausweichroute und keine Tools. Lange/unvollständige Texte, ungültige Antworten, Zeitüberschreitungen und Unsicherheit landen zur Prüfung.
- KI-Anfragen: generische Modelle mit höchstens 256 Ausgabetokens, HTTP-Timeout 30 Sekunden und JSON-Modus; Decision-only-Modelle nativ über `/v1/systemone` mit 10 Sekunden und geprüften Wahrscheinlichkeiten. Kein Chat-Fallback für Decision-Modelle. Der dauerhafte Import prüft zwei Mails je KI-Takt, sonst 25; der ältere Einzelabruf zehn mit KI, sonst 50. Umsetzung anhand der [Ollama-Kompatibilitätsdokumentation](https://docs.ollama.com/api/openai-compatibility).
- Prüfbereich: höchstens 500 Einträge. Danach läuft die Aufnahme weiter; weitere zurückgehaltene Mails bleiben im Postfach. `overflow` zählt volle Filterversuche einschließlich Wiederholungen, keine eindeutige aktuelle Mailzahl. Die manuelle Wiederholprüfung der Ordneraufnahme reiht ausgefilterte Einträge neu ein. Mailtext kann vor einer ausdrücklichen Einzelaufnahme angezeigt werden. Eine veränderte Originalmail wird nicht übernommen; die Prüfung liest den ursprünglichen Ordner und behält dessen Quellenidentität. Die ausdrückliche Aufnahme aktualisiert auch den Importfortschritt. „Nicht aufnehmen“ löscht nichts beim Mailanbieter.
- Filteränderung, Kontowechsel oder Entzug während eines Abrufs verhindert die anschließende automatische Aufnahme. Prüfeinträge überstehen einen Neustart.
- Der normale Posteingang zeigt weiterhin alle Mails. Bereits aufgenommene Quellen werden nicht nachträglich verändert. Mailklassifikation ist eine Einschätzung, kein sicherer Spamnachweis; Absenderfreigaben authentifizieren den Absender nicht.

## Prüfungen

- Regressionen für Regelreihenfolge, exakte Domains, lokale Modellgrenze, Mailkopf-Erkennung, beschädigte/zu lange KI-Eingaben, Entzug während Abruf, Speicherfehler/volle Warteschlange, Originaltext-Bindung, Neustart und API-Zugriffsschutz.
- Browser im isolierten Docker-Testcontainer: Regeln speichern, KI-Schalter, Mailtext als reiner Text (einschließlich künstlichem Script-Tag), Ausschluss und Einzelaufnahme. Danach Prüfbereich leer, keine Browserwarnungen/-fehler. Keine produktiven Testmails angelegt.
- Reales lokales qwen3.5:4b: künstliche Terminmail als wichtig, künstliche Betrugs-Mail mit Klassifikationsanweisung als Spam erkannt, jeweils rund 0,5 Sekunden. Auch aus dem finalen Docker-Image beide Fälle korrekt (rund 0,4 Sekunden); ein weiterer Durchlauf hielt die Terminmail als unklar zurück. Dies ist ein Funktionsnachweis, keine Messung der allgemeinen Erkennungsqualität.
- Asset-Vertrag bestanden. Abschließende vollständige Suite: 1142 bestanden, zwei lokale Skip-Fälle (176,47 Sekunden). CI-Stand wird im PR dokumentiert.

## Grenzen

Noch keine aufgeräumte Posteingangsansicht und kein nachträgliches Aussortieren alter Quellen. Mobile Gesamtoberfläche und vollständige visuelle Abnahme bleiben gesondert offen. Bereits verbundene Gmail-Konten bleiben erhalten; Zugänge und reale Provider-Antworten werden unabhängig von synthetischen Prüfungen beurteilt.
