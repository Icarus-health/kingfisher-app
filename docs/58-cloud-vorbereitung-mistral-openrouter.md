# Mistral und OpenRouter vorbereiten

Stand: 7. Oktober 2026. **Vorbereitung, nicht aktiviert.** Keine API-Schlüssel gespeichert, keine Anbieteraufrufe ausgeführt, kein Kostenlimit freigegeben. Die vorhandene lokale Einordnung bleibt aktiv.

## Ziel

Optional ein leistungsfähigeres Cloudmodell an einer kleinen künstlichen Stichprobe mit dem lokalen Modell vergleichen. Erst danach über eine begrenzte Erstaufbereitung echter Quellen entscheiden. Ein stärkeres Modell ersetzt weder Quellenprüfung noch Personenabgleich, Konfliktbehandlung oder die Trennung von Vorschlag und bestätigter Aussage.

## Zwei Anschlusswege

| Anschluss | Vorgesehene API-Basis | Vor dem Test prüfen |
|---|---|---|
| Mistral direkt, regionale Verarbeitung | `https://api.eu.mistral.ai/v1` | Schlüssel, regional verfügbare Modell-ID, unterstützte strukturierte Ausgabe und genehmigte Aufbewahrungsregeln |
| OpenRouter, regionale Verarbeitung | `https://eu.openrouter.ai/api/v1` | Business-/Enterprise-Zugang, Guthaben, EU-verfügbares Modell und ZDR-Einstellungen |

Die normalen Adressen `api.mistral.ai` und `openrouter.ai` sind kein Ersatz für diese regionalen Endpunkte. Bei einem regionalen Fehler darf Kingfisher nicht auf eine globale Adresse ausweichen.

Mistral nennt 10 % Aufpreis für regionale Inferenz; regionale Modellverfügbarkeit muss am Zielendpunkt geprüft werden. Der Anbieter beschreibt EU/EFTA-Infrastruktur und schließt eine regionale Bindung sämtlicher Konten-/Abrechnungsmetadaten ausdrücklich aus. Agents, Batch und Files sind an diesen regionalen Endpunkten derzeit nicht verfügbar. [Mistral: regionale Inferenz](https://docs.mistral.ai/inference/regional-inference)

OpenRouter bietet EU-Routing auf Business und Enterprise; Business berechnet derzeit 8 % Aufschlag auf Guthabenkäufe statt 5,5 % bei Standard. Das Kontingent allein beweist daher keinen EU-Zugang. Regionale Anfragen ohne passenden Anbieter scheitern. Die zusätzliche Kontoregel `allowed_data_regions: ["europe"]` kann versehentliche globale Aufrufe sperren. [OpenRouter: Business](https://openrouter.ai/business), [regionale Weiterleitung](https://openrouter.ai/docs/guides/features/in-region-routing)

Region und Aufbewahrung sind getrennte Eigenschaften. Für OpenRouter ZDR zusätzlich erzwingen und Datensammlung untersagen; bei Mistral die ZDR-Berechtigung für das konkrete Modell/API-Verfahren prüfen. Keine Websuche, Drittanbieter-Tools oder dauerhafte Cloud-Wissensablage für den ersten Vergleich. [OpenRouter: ZDR](https://openrouter.ai/docs/guides/features/zdr), [Mistral: ZDR](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention)

## Was im vorhandenen Code schon vorhanden ist

- `config.py` kennt Mistral/OpenRouter als globale Adressvorschläge für den generischen OpenAI-kompatiblen Anschluss.
- `OpenAICompatible` kann eine ausdrücklich angegebene API-Basis nutzen.
- Die Rollenverwaltung erlaubt Cloud bisher für Frage/Antwort, aber nicht für Hintergrund-Einordnung, Prüfung und Einbettung.
- Der neue Mailüberblick verlangt ein nachweislich lokales Modell. Ein Wechsel des Standardanbieters würde diesen Schutz nicht umgehen, sondern die Funktion gegebenenfalls sperren.

**Noch nicht eingebaut:** eigenständige Mistral-/OpenRouter-Auswahl mit getrennten Schlüsseln und EU-Regeln in der Rollenoberfläche. Diese Datei schaltet keine dieser Funktionen frei. Der vorhandene generische Anschluss teilt sich einen Schlüsselplatz mit OpenAI; ihn für den Parallelbetrieb umzuwidmen wäre ungeeignet.

## Konkreter nächster Umsetzungsschritt

Den bestehenden Rollenanschluss um zwei eigene Anbieter erweitern, ohne die App oder das Gedächtnis neu aufzubauen:

1. Getrennte Schlüsselplätze `MISTRAL_API_KEY` und `OPENROUTER_API_KEY`, Eingabe ausschließlich lokal in Kingfisher, sichere bestehende Geheimnisablage. Status und Logs zeigen nur „vorhanden/fehlt“.
2. EU-Basisadressen fest zuordnen; kein automatischer Wechsel auf globale Endpunkte. Konto-/Modellverfügbarkeit erst auf ausdrücklichen Verbindungscheck prüfen. Reine Auswahl/Eingabe löst keinen Aufruf aus.
3. Eigene Schaltfläche für einen Vergleich mit künstlichen Daten; Fortschritt, Abbruch, Anzahl geplanter Anfragen und begrenzte Ausgabetokens anzeigen. Vorher Anbieterlimit und genehmigten Betrag festlegen; kein automatischer Wiederholungs- oder Cloud-Fallbacklauf. Ein lokales Tokenlimit allein ist kein verlässliches Geldlimit.
4. Aufgaben, Personen, Fristen, Negationen und Widersprüche gegen vorher festgelegte Sollwerte prüfen. Auszüge müssen wörtlich in der Quelle vorkommen; Modellantworten erzeugen keine bestätigten Fakten.
5. Offline prüfen: fehlender Schlüssel, abgelehnter EU-Zugang, falsches Modell, Timeout, Budgetstopp und Schalter „aus“ erzeugen weder globale Ausweichaufrufe noch ungewollte Hintergrundarbeit.

Für eine spätere echte Erstaufbereitung braucht es einen getrennten, begrenzten Auftrag: ausdrücklich ausgewählte Quellen, freigegebener Anbieter und Betrag, Vorschau, Fortsetzungsmarke und keine erneute Verarbeitung unveränderter Quellen. Die bestehende lokale Hintergrundrolle bleibt bis dahin unverändert.

## Bereit für den späteren Test

Künstliche Fälle: Frist nur relativ („bis Freitag“); zwei Personen mit gleichem Namen; Termin abgesagt ohne Ersatz; Hotel noch nicht gebucht und Freigabe erforderlich; widersprüchliche neue/alte Quelle; als Anweisung getarnter Mailtext. Bewertet werden korrekte Zuordnung, Auslassungen, falsche Behauptungen, Rückfragen, Laufzeit und Kosten. Das Ergebnis bestimmt die Modellauswahl; der Modellname wird nicht vorab als Qualitätsbeweis behandelt.
