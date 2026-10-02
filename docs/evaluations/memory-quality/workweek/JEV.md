# JEV / TypeSafe: Eignung für Kingfisher

Recherche 28.09.2026, ausschließlich offizielle Quellen. Kein SDK installiert, kein Account angelegt, keine Daten an JEV gesendet.

## Entscheidung

JEV derzeit nicht als verpflichtenden Gedächtnisbestandteil integrieren. Eng abgegrenzte Entscheidungen mit festen Ergebnistypen sind als Architekturprinzip nützlich; Verfügbarkeit einer API und formal gültige Antworten beweisen keine zuverlässige Personen- oder Zeitzuordnung.

## Dienst und Datenfluss

Die [offizielle Dokumentation](https://docs.typesafe.ai/introduction) beschreibt API-Aufrufe mit Zustand und typisierten Fragen: Choice, Score und Noul. In den geprüften offiziellen Repositories und Modellunterlagen wurde kein herunterladbares JEV-Modell und kein öffentlich dokumentierter lokaler Betriebsweg gefunden. SDK-Quellcode ist kein Modellgewicht.

Die [Datenschutzerklärung](https://typesafe.ai/legal/privacy-policy), datiert 19.11.2025, sagt zu, Eingaben nicht für Training/Fine-Tuning zu verwenden. Sie nennt zugleich Hosting sowie Speicherung/Verarbeitung in den USA, Dienstleister als mögliche Empfänger und eine allgemein formulierte Aufbewahrungsdauer. Daraus folgt kein pauschales Urteil „rechtswidrig“; ein für Kingfisher passendes EU-/AVV-/Löschkonzept ist damit aber nicht nachgewiesen. Eine einfache lokale Anonymisierung garantiert ebenfalls keine Entfernung aller personenbezogenen Zusammenhänge.

## Was übertragbar ist

Der offizielle MIT-lizenzierte [System One Adapter](https://github.com/typesafe-ai/system-one-adapter-python) bildet die API mit anderen LLMs nach und unterstützt eigene OpenAI-kompatible Endpunkte. Damit ist ein lokaler Modellendpunkt ein möglicher Integrationsweg, dessen tatsächliche Kompatibilität noch getestet werden muss. Es wird dann das gewählte LLM verwendet, nicht JEV. Dessen Güte und Kalibrierung werden nicht durch dieselbe Antwortstruktur geerbt. Kein Anlass, diese zusätzliche Abhängigkeit vor einem nachgewiesenen Nutzen einzubauen; Kingfisher besitzt bereits begrenzte Auswahlantworten.

Sinnvolle isolierte Fragen wären: Enthält diese Quelle eine Zusage oder nur eine Bitte? Ist eine genannte Bedingung ausdrücklich erfüllt? Ist unter den Personenbezügen eine eindeutige Auswahl möglich? Belegt dieser Ausschnitt die verlangte Buchungsart? Jede Auswahl benötigt auch „nicht belegt / unklar“; Quellen und Identitäten bleiben durch Programmregeln überprüfbar.

## Zuverlässigkeitsgrenze

[TypeSafes dokumentierte Fehlerfälle](https://docs.typesafe.ai/model-jaggedness/jev-1.13) nennen insbesondere Zahlen, Datum/Zeit, komplexe indirekte Zusammenhänge, irrelevanten Kontext und adversarielle Eingaben. Keine Garantie fehlerfreier Entscheidungen oder sicherer Prompt-Injection-Abwehr.

[Confidence](https://docs.typesafe.ai/confidence) wird aus der Verteilung über Antwortoptionen berechnet. Ein hoher Wert ist kein unabhängiger Quellenbeweis und keine zugesicherte individuelle Fehlerwahrscheinlichkeit für unsere deutschen CoS-Fälle. Schwellen müssen anhand eigener Fälle samt Kosten falscher Entscheidungen bewertet werden.

## Konsequenz für die Abnahme

Erst Fehler in der fortlaufenden Arbeitswoche einem Schritt zuordnen: Aufnahme, Routing, Kandidatensuche, Auswahl, Aktualität oder Ausführung. Dann einen Spezialisten auf demselben festgeschriebenen Fallbestand vergleichen. Ein möglicher späterer JEV-/Mistral-Test beginnt mit synthetischen Daten und explizitem Kostenlimit. Persönliche Quellen bleiben bis zu einer separaten Entscheidung lokal.
