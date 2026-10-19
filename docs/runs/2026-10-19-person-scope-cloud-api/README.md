# Quellengebundene Personenakten und vorbereiteter Claude-Import

Stand: 19. Oktober 2026. Ausgangspunkt: `746ac048`; geprüfter Produktcode: `1f2df0a` (nachfolgende Ergänzungen betreffen nur diesen Nachweis).
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

Bisher nachgewiesen:

- Die letzten 127 Cloud-/Kategorieprüfungen umfassen den endgültigen Claude-Pfad mit wörtlichem Namen, Block-ID und Vorkommensnummer. Zeichenpositionen werden vom vorhandenen Validator im Original bestimmt, nicht vom Modell gezählt.
- 78 Personen-/Mailprüfungen, 26 Sicherungs-/Wiederherstellungsprüfungen und 11 Diagnoseprüfungen im sauberen Checkout bestanden.
- 744 UI-Prüfungen unter dem vorgeschriebenen `TZ=UTC`; Build, Asset-Vertrag und Diff-Prüfung bestanden. Der bekannte zeitzonenabhängige Kalender-Test wurde nicht verändert.
- Unabhängige Reviews prüften Personenabgrenzung und Cloud-/Zugangsschutz; ein zusätzlicher synthetischer Alt-Schema-Test bestätigte den Erhalt alter ChatGPT-Aufträge mit pausierter Wiederaufnahme.
- Bedienprobe im In-App-Browser auf getrenntem lokalem Bestand: Zugang speichern und entfernen, Vorschau ohne Versand, ausdrückliche Paketfreigabe, simulierter Verbindungsabbruch, Widerruf und erneut entfernter Schlüssel. Nach Testserver-Neustart zeigte eine ausgewählte Mail höchstens vier Anfragen. Der Transport war technisch blockiert; kein echter Anbieteraufruf.
- Absenderakte und nur in der Signatur erwähnte Person durch die sichtbaren Verbindungen geöffnet: Anfrage und unbestimmte Frist bleiben beim Absender; bei der Erwähnung bleibt der Quellenverweis ohne fremde Bitte. Keine relevanten Browserwarnungen/-fehler. Die Zugänge bleiben bei 900 und 1.280 Pixeln erreichbar; bei 900 Pixeln kein horizontaler Seitenüberlauf.

Der vollständige Backend-Lauf bestand mit **6.875 Tests und 26 Subtests**, ein plattformspezifischer Fall wurde ausgelassen (Python 3.12, UTC). Er begann vor der letzten einzeiligen Umstellung auf den bestehenden Claude-Zitatmodus; dessen endgültiger Stand ist zusätzlich durch den oben genannten frischen 127er-Lauf geprüft. Ein Test mit künstlichen Daten ersetzt weder die Modellgüteprobe an echten Mails noch die Abnahme einer installierten Mac-Fassung. Noch kein Mac-Update oder Importstart.
