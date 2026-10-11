# Lokale Themenzuordnung: begrenzte Verbesserung, 11.10.2026

Das wiederhergestellte ausgewählte Modell `kingfisher-qwen3.5:9b-32k` ließ Werbung, Statusmeldung und Rechnung ohne Kategorie, obwohl die Kategorie-Beschreibungen diese Fälle abdecken. Der lokale Quote-Prompt enthält jetzt eine allgemeine Klarstellung: Themen unabhängig von erkannten Personen oder anderen Entitäten anhand der Taxonomie prüfen. Keine fallbezogenen Regeln oder angepassten Sollwerte. Remote-Prompt, JSON-Schema, Belegprüfung, Speicherung und Rollenwahl bleiben unverändert.

## Kontrollierter Vergleich und tatsächlicher Produktlauf

| Künstlicher Satz | Bisheriger Prompt | Allgemeine Klarstellung | Exakter geänderter Produktcode |
|---|---:|---:|---:|
| Acht vorhandene Entwicklungsfälle | 4/8 | 6/8 | 6/8 |
| Sechs unabhängig vor dem Versuch verfasste Gegenfälle | 2/6 | 5/6 | 5/6 |

Die Gegenfälle wurden vor Kenntnis der neuen Anweisung durch einen anderen Agenten verfasst und anschließend eingefroren. Spätere Experimente kannten diese Fälle; keine statistische oder dauerhaft blinde Testmenge. Die manuellen Sollmengen sind ein nachvollziehbarer Prüfmaßstab, keine allgemeine Wahrheit über jede mögliche Kategorisierung. Zwei Katalognotizen benennen ausdrücklich mehrdeutige zusätzliche Privat-Kategorien.

Der vollständige Vergleich nutzte 28 echte lokale Modellaufrufe in frischen temporären Stores. Der abschließende Produktlauf verwendet keinen Prompt-Wrapper: acht Aufrufe über `scripts/probe_category_quality.py`, sechs weitere über den beigefügten unabhängigen Treiber. Produkt-SHA-256 in beiden Berichten: `7fa1b14b9e3724800ac77d41e2fd22b5ecd3818347fd3ac48b5ca5f0b91985ed`. Alle Originale unverändert, alle erwarteten Personen in der geänderten Variante erkannt. Kein Cloudaufruf, keine persönlichen E-Mails und keine kostenpflichtige API.

**Bekannter Trade-off:** Der gemischte Newsletter erhält nach der Klarstellung zusätzlich `appointments` und verliert gegenüber dem bisherigen Prompt seinen exakten Sollmengentreffer. Der bedingte Lieferbericht enthält diese Zusatzkategorie in beiden Varianten. Beim privaten Zufallstreffen bleibt zusätzlich `unclear`. Die Verbesserung behebt Auslassungen, qualifiziert aber weder Termine noch Fakten, Identitäten, Aufgaben, Antworten oder persönliche Massenimporte. Kategorien bleiben überprüfbare Vorschläge; die zusätzliche Kategorie erzeugt keine Aufgabe oder Buchung.

## Nicht übernommene Versuche

- Eine allgemeine Datumsabgrenzung entfernt das zusätzliche Newsletter-Thema, lässt dafür die Statusmeldung wieder leer und verändert die zusätzliche Kategorie beim Zufallstreffen. Gleiche Gesamtzahlen, verschobene Fehler: nicht übernommen.
- Getrennte Personen- und Themen-Schemas erkennen in vier Fällen die Themen, erzeugen aber bei einer Rechnung die falsche Person „Ihre“. Nicht übernommen. Im bisherigen Prompt wurde bei einer Reservierung außerdem „Sie“ als Person ausgegeben. Ein exakter Textbeleg allein beweist keinen wirklichen Namen; dieser Befund ist offen, keine zusätzliche Pronomen-Sperrliste eingebaut.
- Ein erster unabhängiger Produktaufruf scheiterte an der lokalen Socket-Sandbox, nach einem Fall `provider_error`. Als unvollständiger Versuch erhalten; die anschließende autorisierte lokale Wiederholung führte alle sechs Fälle aus. Kein ausgefallener Fall wurde als Qualitätsmessung gezählt.

Keine neuen Sollwerte, Kategorien, Modellprofile oder zusätzlichen Cloudfreigaben. In einem Vergleichsfall dauerte der bisherige Aufruf 202 Sekunden; Ursache nicht geklärt. Daraus und aus den schnelleren Folgeaufrufen wird kein Geschwindigkeits- oder Akkunachweis abgeleitet.

## Prüfung, Betrieb und Grenzen

101 betroffene Tests bestanden (Kategorieverwaltung, lokale Quote-Belege, Diagnostik, Korrekturen, Personenerwähnungen und Qualitätsläufer); eine vorhandene Starlette/httpx-Warnung. Kein neuer vollständiger Backend- oder UI-Lauf für die kleine Backend-Promptänderung. Unabhängiger Review bestätigt die enge lokale Begrenzung und identische Übernahme des erfolgreichen Prototyps, akzeptiert den Vorschlags-Fix nur mit dem dokumentierten Trade-off.

Sieben persönliche Kerntabellen frisch vollständig über sortierte Zeileninhalte verglichen und unverändert: 344 Originalepisoden, 333 Quellenverweise, drei Gespräche/14 Nachrichten, keine Aufgaben/Projekte/Notizen. Globale Hintergrundpause lesend bestätigt. Das Modell war beim abschließenden Status bereits entladen; eigener eindeutig identifizierter Testdaemon beendet, Ausführungssitzung Exit 0. Modellgewichte bleiben erhalten.

Der neue Prompt ist **noch nicht auf dem Mac installiert**. Dort läuft weiter `1.0.6-preview.6979131`. Bestehende abgeschlossene Einordnungen werden durch eine Promptänderung nicht automatisch erneut bearbeitet. Wiederprüfung muss gezielt angefordert werden; gespeicherte eigene Korrekturen bleiben maßgeblich. Kein großer privater Mail-Rescan gestartet. Die native Fensterprüfung bleibt offen, da der Mac wieder gesperrt ist.

## Belege und Wiederholung

`guidance-full-contrast.json` enthält beide vollständigen Arme; `guidance-contrast.json` den ersten Drei-Fälle-Vergleich. `rejected-date-boundary.json` und `rejected-split-schema.json` dokumentieren die verworfenen Varianten. `product-development.json` und `product-independent.json` sind die abschließenden echten Produktberichte. `product-independent-sandbox-attempt.json` bewahrt den unvollständigen Socket-Versuch. `holdout-cases.json` bleibt unverändert.

Die Treiber bewahren den tatsächlich ausgeführten Code einschließlich der damaligen temporären Ausgabeziele. Für Wiederholungen neue Ausgabeziele verwenden; nicht vorhandene Berichte überschreiben. Den Kontrasttreiber ausschließlich am damaligen Basiscode `55b0a84` ausführen: Am geänderten Produkt würde sein Guidance-Arm die Anweisung doppelt hinzufügen. Der unabhängige Produkt-Treiber verwendet dagegen unmittelbar den aktuellen Produktcode.

Offizieller Entwicklungsbefehl: `PYTHONPATH=sidecar:scripts python scripts/probe_category_quality.py --model kingfisher-qwen3.5:9b-32k --output <neuer-Bericht.json>`. Die aktuelle 6/8-Messung beendet sich korrekt mit Exit 1, weil keine vollständige Erfüllung vorliegt.
