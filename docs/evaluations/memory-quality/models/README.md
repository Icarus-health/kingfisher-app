# Modellvergleich für das Gedächtnis

Welches Modell erledigt die beiden Gedächtnisaufgaben gut? Das Skript
`scripts/probe_working_memory_models.py` misst es an einem eingefrorenen,
synthetischen Katalog (`catalog.json`), über den echten Produktcode:

* **Einordnung** (`working_memory_analysis.interpret`): Welche Art hat jeder
  Absatz (Bitte, Zusage, bedingte Aussage, Änderung, Stand, früher, unklar,
  bedeutungslos)? 8 Mails, 17 Absätze.
* **Auswahl** (`working_memory_answers.prepare`): Welche Quellen beantworten die
  Frage, und braucht es eine Rückfrage (Person, Vorgang, Zeit, Widerspruch)?
  10 Fragen. Gemessen wird das Ergebnis nach den festen Schutzregeln, also das,
  was der Nutzer sehen würde.

Beide Kataloge enthalten je eine eingeschleuste Anweisung im Quelltext; ein
gutes Modell folgt ihr nicht.

## Aufruf

Ein Arm je Modell, beliebig viele:

```sh
python scripts/probe_working_memory_models.py \
  --arm ollama:qwen3.5:4b \
  --arm ollama:qwen3.5:9b \
  --arm kompatibel:mistral-small@http://localhost:1234/v1 \
  --output docs/evaluations/memory-quality/models/vergleich-<commit>.json
```

Cloud-Modelle zum Vergleich, nur mit ausdrücklicher Freigabe:

```sh
ANTHROPIC_API_KEY=… python scripts/probe_working_memory_models.py \
  --arm anthropic:claude-sonnet-5 --arm openai:gpt-4.1-mini --cloud-erlaubt \
  --output docs/evaluations/memory-quality/models/cloud-<commit>.json
```

Ausgabe je Arm: richtig eingeordnete Absätze, ganz richtige Fälle, Auswahl mit
richtigem Status und richtigen Quellen, ungültige Antworten, Sekunden je Aufruf.
Das Ergebnis wird nie überschrieben.

## Was das Skript nicht ändert

Im Produkt bleibt der Arbeitsstand lokal: Einordnung und Auswahl laufen nur mit
einem lokalen Modell, Quellen verlassen den Rechner dafür nicht. Das Skript
sendet ausschließlich den synthetischen Katalog. Ob Cloud-Modelle für das
Gedächtnis je zugelassen werden sollen, ist eine eigene Entscheidung mit
eigener, ausdrücklicher Einwilligung; dieses Messwerkzeug liefert dafür nur die
Grundlage.

Die Chat-Antworten selbst sind davon unabhängig: Dort lassen sich schon heute
lokale Modelle und Anbieter wie Anthropic, OpenAI oder jeder
OpenAI-kompatible Dienst (OpenRouter, Mistral, LM Studio, llama.cpp, vLLM)
einstellen.

Eine Entscheidungsgrundlage, keine Produktabnahme.
