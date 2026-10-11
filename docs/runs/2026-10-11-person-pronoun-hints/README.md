# Pronomen sind keine Personennamen

11. Oktober 2026, Code `45cb1c8272a1335a49b7a3adc1d59fa3c542e9c5`. Im bestehenden Draft #54, noch nicht persönlich installiert. Mac bleibt auf dem geprüften Speicherschutzpaket `1.0.6-preview.3690733`; große Aufnahme unverändert pausiert.

## Konkreter Fehler und Korrektur

Die [vorherigen echten lokalen Modellversuche](../2026-10-11-category-guidance/README.md) enthielten die falschen Personen „Ihre“ und „Sie“. Ein exaktes Originalzitat beweist nur eine Fundstelle. Bisher akzeptierte die Modell-Entitätsvalidierung diese Wörter als Namen, sofern sie nicht schon einem allgemeinen Postfach zugeordnet waren.

Ein geschlossenes Set einzelner deutscher Personal-, Reflexiv- und Possessivpronomen wird jetzt in allen bestehenden Kategorie-Entitätswegen und beim Lesen bereits gespeicherter Spans ausgefiltert. Vollständiger normalisierter Gleichheitsvergleich, keine Teilwort-/Stammregel: kurze Namen, „Siebert“, „Anne Sie“, andere Entitätsarten und sonstige Belege bleiben erhalten. Keine Prompt-/Modellwahländerung, Personenverschmelzung oder Faktenbestätigung.

Seltene Anzeigenamen wie „Sie“ bleiben als ungeprüfte Erwähnung verfügbar, wenn derselbe vollständige Name in aktuellen Mailkontakt-/Teilnehmermetadaten mit gültiger, nicht generischer Adresse steht. Rohtext und zitierte Von-Zeilen liefern keine Ausnahme; Sammelpostfächer bleiben gesperrt. Grenze: Ein solcher Kontakt beweist nicht, dass jedes gleichlautende Pronomen im Text den Kontakt meint. Diese Ausnahme ist keine Zuordnung von Aussagen oder Aufgaben zur Person. Die bestehende getrennte Identität aus Kopfmetadaten bleibt unverändert. Ohne Mailanker kann ein seltener wirklicher Einzelname mit gleicher Schreibweise als Körper-Erwähnung ausgefiltert werden; Original und vorhandene Kontakte bleiben erhalten. Die Regel löst nicht jede falsche Namenserkennung oder andere Sprachen.

## Tatsächliche Nachweise

- Erste 26 neue Gegen-/Kontrollfälle: auf altem Code 17 erwartete Fehler und neun bestandene Erhaltungskontrollen. Nach Korrektur bestanden.
- Unabhängiges lesendes Review bestätigte die enge Ausnahme und fand das fehlende Reflexivpronomen „sich“. Beide zusätzlichen Belegmodi erst fehlschlagend geprüft, anschließend ergänzt. Kein weiterer konkreter Befund im geprüften Diff; Reviewer führte keine Tests aus.
- Finale 32 neue Fälle: lokale Quote-/Absolutbelege, künstlicher ausdrücklich erlaubter Remote-Quote-Weg, gespeicherter Altspan nach Datenbank-Neustart, echte/kurze Namen, Organisationen, aktuelle Absender-/Empfängermetadaten, generische/ungültige Adresse sowie Roh-/Zitatkopf ohne Ausnahme. Alte gespeicherte Pronomenzeile bleibt nach Wiederöffnung tatsächlich in der Datenbank; nur die Anzeigeprojektion verbirgt sie. Originalquelle und andere Belege unverändert.
- 198 betroffene Tests und 44 zusätzliche, disjunkte Cloud-/Importtests bestanden (242 zusammen). Provider ausschließlich künstlich; keine neue Modellinferenz, kostenpflichtige Anfrage oder persönlichen Quellen. Vorhandene Starlette/httpx-Abkündigung. Keine neue gesamte Backend-Suite oder UI-Wiederholung für diesen reinen Backend-Diff.

`verification.json` bindet Code und Datei-Hashes; komprimierte Logs bewahren die roten und finalen Läufe. Die vorherigen echten Modell-Qualitätswerte werden dadurch nicht nachträglich geändert. Das beweist den deterministischen Filter, keine allgemeine Einordnungs- oder Identitätsgenauigkeit und keinen neuen nativen Bediennachweis. Auslieferung im nächsten geprüften Paket und persönliche Alltagsabnahme bleiben offen.
