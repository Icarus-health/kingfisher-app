# Quellengebundene Personenakten und vorbereiteter Claude-Import

Stand: 19. Oktober 2026. Ausgangspunkt: `746ac048`.
Alle Beispiele und automatisierten Nachweise dieses Pakets sind künstlich.
Es wurden weder echte Anbieteranfragen gesendet noch persönliche Mails oder Schlüssel veröffentlicht.

## Getrennte Arbeitsweisen

- **Erstaufbau und Nachprüfung:** ausdrücklich ausgewählte Mailpakete dürfen mit dem bisherigen ChatGPT-Zugang oder der neu vorbereiteten Claude API eingeordnet werden. Eine Vorschau überträgt nichts. Ein Paket bindet Anbieter, Modell, Quellenfassung und Zugangsfassung; Änderungen verlangen eine neue Freigabe. Neustarts setzen laufende Aufträge auf Pause.
- **Alltag:** vorhandene lokale Modellrollen bleiben erhalten. Das Hinterlegen eines API-Schlüssels schaltet keine Rolle oder Hintergrundarbeit ein. Mailabruf und pausierter Großimport werden durch dieses Paket nicht fortgesetzt.
- **Qualität:** „verarbeitet“ heißt nicht „fachlich richtig“. Die Auswertung bleibt an Originalstellen gebunden; bestätigte Nutzerangaben werden nicht automatisch überschrieben. Eine Stichprobe gegen Originale bleibt vor der Erweiterung erforderlich. Die bestehende automatische Pflege prüft nicht unabhängig die Bedeutung sämtlicher Zuordnungen.

## Behobene Fehlzuordnung

Eine im alten Mailzitat oder in einer Signatur erwähnte Person bekam bisher sämtliche offenen Punkte und Fristen dieser Mail in ihrer Akte. Nun gelangen bei bloßen Modell-Erwähnungen nur Abschnitte mit passender Originalstelle in die abgeleitete Darstellung. Der Originalverweis bleibt sichtbar.

Allein aus einer Modell-Erwähnung werden auch angenommene Aufgaben dieser Quelle nicht mehr der Person zugewiesen. Ausdrückliches `wartet_auf` und bestätigte Quellenzuordnungen bleiben erhalten. Absender- und Teilnehmeranker bleiben Korrespondenzkontext; daraus folgt weiterhin keine bestätigte Aufgabenverantwortung.

Eine erfolgreiche erneute Einordnung verwirft alte automatische Quellenbezüge atomar. Veränderte Erwähnungsstellen gehen in den Akten-Fingerabdruck ein. Alte abgeleitete Zusammenfassungen dürfen fremde Aussagen aus reinen Erwähnungen nach dieser Änderung nicht erneut einblenden. Originale, gespeicherte Aufgaben und bestätigte Zuordnungen werden nicht gelöscht.

## Kurzer Mailüberblick und Zitate

Belegte datierte Mailhistorie kann den aktuellen Kurzüberblick nicht mehr verdrängen oder dessen Textbudget erschöpfen. Die ausgewählten Passagen bleiben unveränderte Ausschnitte des Originals. Getrennte Antworten werden nicht zusammengeklebt.

**Bewusste Grenze:** Wird zitierter Kontext ausgeblendet, gilt der Überblick als unvollständig und erzeugt keine neuen Aufgabenvorschläge. Auch eine vor dem Zitat stehende Antwort wie „Ja, bitte veröffentlichen“ kann von einer dort genannten Freigabebedingung abhängen. Das Original bleibt vollständig verfügbar. Die vollständige Gedächtnis-Einordnung wird durch diese Begrenzung des Kurzüberblicks nicht verändert.

## Anbieter, Kosten und Datenschutz

Unter Einstellungen → KI & Modelle → Cloud-Zugänge können Anthropic, OpenAI, Mistral und OpenRouter vorbereitet werden. Für den konkreten Mailimport sind ChatGPT und Claude API auswählbar; gespeicherte Zugänge sind kein Nachweis gültiger Konten, Modelle oder regionaler Berechtigung. Weitere Anbieter sind dadurch noch nicht angebunden.

Anthropic und OpenAI erhalten getrennte vorbereitete Schlüssel, damit die bisherige automatische Standardanbieterwahl nach einem Neustart nicht versehentlich Cloud aktiviert. Die Schlüssel liegen im vorhandenen verschlüsselten Speicher und werden nie zurückgegeben. Ein Austausch, eine Entfernung oder Modelländerung entwertet die frühere Importfreigabe. Bestehende manuelle Anbieter-Konfiguration bleibt erhalten.

Die direkte Claude API nutzt bezahltes API-Guthaben. Das Gesamtbudget beträgt vier gezählte Modellanfragen mal tatsächlich ausgewählter Mailzahl; einzelne Quellen teilen sich dieses Paketbudget. **Dies ist keine Euro-Obergrenze**. Es gibt weder automatische Wiederholungen noch Ausweichanbieter. Batch ist nicht implementiert. Für einen Großbestand sind gemessene Tokenkosten und ein gesondert freigegebenes Budget nötig.

Eine europäische Firma allein garantiert keine DSGVO-Konformität. Ausschlaggebend sind unter anderem konkreter Endpunkt, Verarbeitung und Aufbewahrung, Vertrag und mögliche internationale Übermittlungen. Die Oberfläche nennt offizielle Quellen und Prüfdatum und unterscheidet:

- Claude API: globaler Standardzugang; standardmäßig keine Trainingsnutzung, regulär Löschung innerhalb von 30 Tagen mit Ausnahmen.
- OpenAI API: globaler Standardzugang; EU-Optionen hängen von Berechtigung, Projekt und Endpunkt ab.
- Mistral: expliziter EU/EFTA-Inferenzendpunkt; Metadaten können anderen Regeln unterliegen.
- OpenRouter: regionaler Zugang für Business/Enterprise innerhalb der dokumentierten Europaregion einschließlich UK/Schweiz; BYOK kann die tatsächliche Ressourcenregion verändern. Kein globaler Fallback.

Quellen, am 19.10.2026 geprüft:

- [Anthropic API-Guthaben](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage)
- [Anthropic Trainingsverwendung](https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training)
- [Anthropic Aufbewahrung](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data)
- [OpenAI API-Datenkontrollen](https://developers.openai.com/api/docs/guides/your-data)
- [Mistral regionale Inferenz](https://docs.mistral.ai/inference/regional-inference)
- [OpenRouter regionale Weiterleitung](https://openrouter.ai/docs/guides/features/in-region-routing)
- [EU: Datenschutz und internationale Übermittlungen](https://europa.eu/youreurope/business/governance-and-sustainability/digital-and-data-compliance/data-protection-gdpr/index_en.htm)

## Prüfung

Neue Personen- und Zitatfälle wurden zuerst gegen den ungeänderten Code reproduziert; unabhängige Reviews fanden zusätzlich Aufgaben-Verwechslung, top-postierte Bedingungen, Vorschau-Wiederverwendung und gleichzeitiges Fortsetzen. Diese Fälle haben eigene Regressionstests.

Die Endergebnisse und die Grenze der Bedienprobe werden nach Abschluss unten ergänzt. Ein Test mit künstlichen Daten ersetzt weder die Modellgüteprobe an echten Mails noch die Abnahme einer installierten Mac-Fassung.
