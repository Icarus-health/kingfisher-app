# Kernablauf: Quellen, Gedächtnis und Alltag

Stand: 7. Oktober 2026. Ausbau des bestehenden Produkts, kein Neuaufbau. Ziel ist ein persönlicher Chief of Staff, der Informationen nachvollziehbar aufnimmt, im richtigen zeitlichen Zusammenhang wiederfindet und daraus übersichtliche, überprüfbare Arbeit vorbereitet. Ein Modellvorschlag ist keine bestätigte Tatsache oder ausgeführte Aktion.

## Drei zusammenhängende Bereiche

| Bereich | Bestehender Kern | Diese Lieferung | Nächster Nachweis |
|---|---|---|---|
| Informationen hinein und pflegen | Freigegebene Mail-/Kalenderzugänge, Dateiimport, Originalquellen, lokale Einordnung, Ausschluss/Korrektur | Sichtbarer KI-Bereich mit getrennten Cloud-Zugängen; Verarbeitungsstatus direkt erreichbar und bei sichtbarer Seite alle 15 Sekunden aktualisiert | Tatsächlich erfasste Konten, Ordner, Zeiträume und Anlagen mit dem Ausgangsbestand vergleichen |
| Gedächtnis wiederfinden | Quellenbelege, Personen-/Projektbezug, Suche, Aussagehistorie | Quellengeschichte nach Originaldatum zusätzlich zum Änderungsverlauf; undatierte Quellen werden nicht auf den Importtag datiert | Unabhängige Fragen zu Personen, Fristen, Absagen und widersprüchlichen Quellen gegen bekannte Sollwerte prüfen |
| Alltag organisieren | Heute, Mailüberblick, Kalender, bestätigte Aufgaben, Aufgabenvorschläge | Quelldatum und Erfassung sichtbar; Aufgabenprüfung in Seiten mit Zeitfilter, ohne erste-100-Grenze; geänderte Listen laden sich ausdrücklich neu | Ein echter Tagesablauf vom Eingang über die Prüfung bis zur Aufgabe; Kalender und Mail daneben gegenprüfen |

## Bedienwege

- **Einstellungen → Zugänge:** Quellen verbinden und deren Umfang auswählen. Ein verbundenes Konto bedeutet noch nicht, dass alle Ordner, Anlagen oder historischen Nachrichten erfasst sind.
- **Einstellungen → KI & Modelle:** API-Schlüssel für Mistral/OpenRouter und konkrete Modell-ID hinterlegen; danach lokale Modelle prüfen. Alte Verweise `#model` und `#technik-modelle` führen hierher.
- **Gedächtnis → Verarbeitung & Verlauf:** Aufnahmestand, lokale automatische Einordnung, Quellengeschichte und Änderungen am Gedächtnis. Direktlink: `/memory?view=status`.
- **Aufgaben → Zur Prüfung:** Alle, zeitnahe oder zeitlich zu prüfende Vorschläge; 25 je Seite. Erst die ausdrückliche Übernahme macht daraus eine Aufgabe.

## Zeit und Quellenrechte

Die Quellengeschichte verwendet ausschließlich vorhandene, zeitzonenbezogene Originaldaten. Erfassung und Entscheidungen haben eine eigene Zeitachse. Quellen ohne verlässliches Datum sind gezählt, aber keinem Quellmonat zugeordnet. Der Quellenentzug gilt weiterhin bei jeder Seite und jedem Belegabruf. Bereits bestätigte Aufgaben werden durch das Alter ihrer Quelle nicht gelöscht.

Auch unbestätigte Vorschläge aus undatierten oder alten Dokumenten müssen zeitlich geprüft werden. Ein heutiger Dateiimport ist kein Nachweis einer heutigen Verpflichtung. Die Aufgabenliste verwendet für Folgeseiten eine Kennung des gültigen Bestands; Änderungen führen zur sichtbaren Rückkehr auf Seite eins. Das ist Navigation im aktuellen Bestand, keine unveränderliche historische Momentaufnahme.

## Cloud-Vorbereitung

Schlüssel werden nur schreibbar eingegeben und über die bestehende sichere Geheimnisablage gespeichert. API-Antworten und Validierungsfehler enthalten keinen Schlüssel. Speicherung ruft keinen Anbieter auf und schaltet keine Rolle frei. Mistral und OpenRouter haben getrennte Schlüsselplätze und feste regionale Adressen. Schlüssel-/Modelländerungen widerrufen bestehende Freigaben dieses Anbieters. Ein anderer Cloud-Standard oder ein nicht nachweislich lokales Ollama-Modell darf dann nicht übernehmen. Auch nach einem fehlgeschlagenen Agent-Neuaufbau bleibt ein entzogener Anbieter gesperrt.

Fragen/Antworten können später nach ausdrücklicher Rollenfreigabe Cloud nutzen. Hintergrund-Einordnung, Prüfung und Einbettung bleiben lokal. Ein begrenzter Cloud-Vergleich, echtes Kostenlimit und freigegebene Erstaufbereitung echter Daten sind **noch nicht geliefert**; siehe [Cloud-Vorbereitung](58-cloud-vorbereitung-mistral-openrouter.md). Kein echter Schlüssel oder Anbieteraufruf gehört zur Prüfung dieser Lieferung.

## Grenzen und Abschlusskriterien

Die Verarbeitungskarte zeigt bei mehr als 2.000 Quellen eine ausdrücklich begrenzte Aufschlüsselung. Die genaue Gesamtzahl der gültigen Aufgabenvorschläge benötigt je Seite weiterhin einen Durchlauf durch die Warteschlange; die Antwort selbst bleibt begrenzt. Ein sehr großer Bestand ist damit noch kein nachgewiesener schneller Alltagseinsatz. Die Quellendatumsübersicht liest nur Metadaten, keine Volltexte.

Vor der Freigabe: fokussierte Regressionen, breitere Tests, UI-Build und unabhängiges Review. Danach Bedienprüfung auf dem entsperrten Mac mit getrennten künstlichen Daten; Installation erst mit Sicherung und anschließendem Erhaltungsnachweis. Bestehende Quellen, bestätigte Aufgaben und Zugangsdaten werden nicht als Testbereinigung gelöscht.

Der persönliche Pilot ist erst dann alltagstauglich belegt, wenn die tatsächlich gewünschten Postfächer und Kalender angebunden sind und die unabhängige Prüfung besteht. Weder die Anzahl grüner Tests noch ein stärkerer Modellname beweist ein fehlerfreies Gedächtnis.
