# Die Ziellinie: wann Kingfisher nutzbar ist

Aktueller Abnahmestand: **30. Oktober 2026**. Der Plan wurde am 20. Oktober
beschlossen; seine damaligen Messungen bleiben unten erhalten.
Dieses Papier legt fest, was „nutzbar“ heißt, was dafür noch gebaut wird und was bis
dahin **nicht** mehr getan wird. Es ergänzt [`24-weg-zum-jarvis.md`](24-weg-zum-jarvis.md)
und ersetzt dessen offene Reihenfolge für die nächsten drei Pakete.

## Korrektur vom 30. Oktober 2026

Das Gedächtnis ist **noch nicht im Alltag abgenommen**. Die Aussage vom 20. Oktober,
es sei „fertig genug“ und weiteres Prüfen bringe keine neue Erkenntnis, war zu weitgehend:
Die Prüfung vom 30. Oktober fand automatische Erledigung allein aus Mailbezug,
Verwechslungen gleichnamiger Personen und bestätigte Personenadressen, die beim Abruf
getrennt blieben. Eine grüne Suite hatte diese falschen Verträge teilweise mitgetragen.

Die freigegebene Reparatur bleibt auf den bestehenden Kern begrenzt: Ausgehende Mail
schlägt Erledigung vor, bestätigt sie aber nicht; bekannte Gegenadressen begrenzen den
Warterückweg. Personenwahl erfolgt bei Mehrdeutigkeit vor Modell und breiter Suche;
bestätigte Zusammenführungen gelten gemeinsam in Akte und Abruf, Rücknahme und
Quellenentzug auch für gespeicherte Antworten. Getrennte Zeiträume beweisen keinen
Adresswechsel. Eine Weiterleitung belegt „an … geschrieben“, keine Antwort an diesen
Empfänger. [Prüfumfang und offene Grenzen](runs/2026-10-30-memory-core-repair/README.md).

Zusätzlich war eine ausdrücklich genannte Frist um 18 Uhr auf 23:59 Uhr verschoben
worden. Die Reparatur erhält eindeutig gebundene lokale Uhrzeiten und lässt erkannte,
aber unklare oder bereits verstrichene Fristen zur Prüfung als Vorschlag stehen.
Eine im Backend nicht aufgelöste Frist darf auch beim Übernehmen nicht aus einer
Modellangabe wiederkehren. Tagesfristen bleiben bis zum Tagesende aktiv.

Die gezielten synthetischen Regressionen und kleinen lokalen Modellproben ersetzen
keine repräsentative Qualitätsprüfung oder Mac-Abnahme. Der Großimport bleibt
pausiert. Bestehende automatische Aufgabenänderungen werden zunächst lesend geprüft,
nicht still zurückgesetzt. Weitere Funktionen sind bis zur Abnahme nicht vorgesehen.

## Planungsgrundlage vom 20. Oktober 2026

Ablage, Herkunft, Fristen, Personen, Akten, Briefing und Suche waren implementiert;
die damalige volle Suite war grün (Fassung 1.0.26,
[Protokoll](runs/2026-10-20-stabschef-pakete/README.md)). Das belegt diesen damaligen
Teststand, keine vollständige Qualität des Gedächtnisses. Damals wurden zwei Lücken benannt:

1. **Das lokale Modell schafft die vier Sprachschritte nicht**: Einordnung in die
   richtige Akte, Bitten und Zusagen aus freiem Text, Antwort in Sätzen mit den
   richtigen Belegen, Entwurf im eigenen Ton. Gemessen: Einordnung 4 bis 6 von 8,
   Antwortsätze 3 von 15, 51 bis 66 Sekunden je Frage
   ([Vergleich](runs/2026-10-12-hindsight-comparison/README.md)). Ein Cloudmodell
   ordnete 9 von 9 Mails vollständig ein
   ([19.10.](runs/2026-10-19-belege-fristen-sonnet/README.md)).
2. **Sechs Zubringer fehlen**, die kein Modell ersetzt: der Gesendet-Ordner (eigene
   Zusagen), Zeitangaben in die Zukunft („morgen“, „nächste Woche“), Aufgaben, die der
   Post folgen (heute: Erledigung nach Bestätigung statt allein wegen einer ausgehenden Mail), Mitteilungen auf dem Mac, der
   Vorschlag „neue Akte?“ und ein Stilprofil für Entwürfe.

Die damals beschlossenen drei Pakete bleiben als Planung dokumentiert. Prüfungen
konkreter Fehler und ihrer Gegenfälle sind bis zur Abnahme erforderlich.

## Was „nutzbar“ heißt

Eine normale Arbeitswoche mit dem echten Postfach. Am Ende stimmen fünf Sätze:

1. Jede Mail der Woche liegt in der richtigen Akte, oder Kingfisher hat gefragt.
2. „Was brauche ich morgen?“ und „Worauf warte ich?“ werden richtig beantwortet, mit
   Quelle.
3. Jede Bitte an dich und jede eigene Zusage steht als Aufgabenvorschlag da.
4. Morgens eine Mitteilung auf dem Mac mit dem, was heute zählt. Nichts davon
   überflüssig.
5. Kein einziges Mal wurde etwas von Hand nachgetragen, das in einer Mail stand.

Das ist die Abnahme. Nichts wird dazugenommen, bis sie bestanden ist.

## Die drei Pakete

| Paket | Inhalt | Fertig heißt |
|---|---|---|
| **A. Cloud für die Sprachschritte** | Die Einordnung neuer Mails samt Bitten und Zusagen darf mit eigener Einwilligung an Anthropic (Claude API); Fragen und Antworten konnten das schon. Ein Schalter, ein Satz, ein Tagesbudget. Prüfung, Einbettung, Lage, Verdichtung und Entwürfe bleiben lokal. | Schalter im echten Browser geprüft; kein Aufruf ohne Einwilligung, über dem Budget, bei Pause oder für Nicht-Mails; Sabotageproben gefangen. |
| **B. Die Zubringer** | B1 Gesendet-Ordner (#86), B2 Zukunftsangaben (#87), B6 Aufgaben folgen der Post (eigene Mail → Erledigungsvorschlag; eindeutige bekannte Gegenseite mit Bezug → Warten aufgelöst; mit Rückgängig), B4 Projektvorschlag „neue Akte?“, B5 Stilprofil aus gesendeten Mails für Entwürfe, B3 Mac-Mitteilungen (braucht einen echten Mac). | Jeder Zubringer mit synthetischen Daten und im Browser geprüft; Messlatte nicht schlechter. |
| **C. Abnahmelauf** | Einmal das Postfach mit Budget einordnen, dann eine Woche Alltag. Was in der Woche falsch war, wird behoben, sonst nichts. | Die fünf Sätze oben stimmen. |

Danach ist 1.1 fertig. Lokal übernimmt Schritt für Schritt wieder, sobald ein Modell
es in der Messprobe schafft (erst Einordnung, dann Bitten und Zusagen, zuletzt
Antworten und Entwürfe). Das ist dann Pflege, kein Projekt.

## Was bis zur Abnahme nicht mehr passiert

- Keine Modellvergleiche, bis A und B stehen. Die Frage ist beantwortet: Lokal reicht
  heute nicht, Cloud reicht.
- Keine neuen Ansichten, keine Messlatte-Erweiterungen, keine Konzeptprüfungen.
- Gezielte Fehlernachweise und Regressionen während der Reparatur; danach eine
  repräsentative Abnahme mit den fünf Sätzen. Eine kleine Modellprobe gibt den
  Großimport nicht frei.

## Was dabei nicht verhandelbar bleibt

- **Einwilligung je Schritt.** Cloud nur mit einem Satz, dem der Nutzer zugestimmt hat,
  und mit einem Klick wieder aus. Die Einwilligung für Antworten gilt nicht für die
  Einordnung.
- **Daten anderer Menschen.** In Mails stehen Dritte. Beruflich braucht Cloud einen
  Auftragsverarbeitungsvertrag; Gesundheitsdaten verlangen besondere Vorsicht. Ein
  EU-Zugang (Mistral) ist vorbereitet, aber ungemessen.
- **Verdichtung schlägt vor, sie schreibt nicht.** Ein Cloudmodell ändert daran
  nichts: Fakt wird nur, was ein Mensch annimmt.
- **Nichts Außenwirksames ohne Freigabe.**

## Rollen

- **Der Nutzer:** entscheidet den Anbieter (beschlossen: Anthropic, da vorbereitet und
  gemessen), nutzt in Paket C eine Woche lang normal. Sonst nichts.
- **Claude Code:** baut A und B als Entwurfs-PRs mit Merge-Reihenfolge, selbst
  geprüft (Tests, Sabotageproben, echter Browser), und wertet Paket C aus.

## Für nach der Abnahme vorgemerkt

- **Strata als lokale Laufzeit prüfen** (vorgemerkt am 26.10.2026 auf Wunsch des Nutzers).
  [Strata](https://github.com/Niko1221/Strata) führt Modelle lokal aus, auch auf Apple
  Silicon, und bietet wie Ollama eine OpenAI-kompatible Schnittstelle. Bisher nur die
  Beschreibung gelesen, nichts installiert. Die Geschwindigkeiten dort sind auf NVIDIA- und
  AMD-Karten gemessen; für den Mac gibt es keine Zahlen. Bei 12.000 Eingabe-Token je Frage
  sind die genannten 110 bis 400 Token je Sekunde nicht schneller als heute.
  Eine Messprobe auf dem Mac des Nutzers: dieselben Fragen wie im
  [Protokoll vom 12.10.](runs/2026-10-12-personal-core-flow/README.md), Zeit je Frage und
  Güte der Antwort gegen Ollama. Nur wenn klar besser, anbinden. Dabei bedenken:
  `ollama_memory.managed_model`, Vorwärmen und die Einbettung mit `bge-m3` sind auf Ollama
  gebaut.
