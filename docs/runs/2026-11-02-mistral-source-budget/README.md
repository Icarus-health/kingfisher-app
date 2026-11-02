# Mistral EU: ausdrücklich freigegebene Quellenpakete

## Umfang

Die bestehende Paketvorschau und Quellenprüfung können optional `mistral-small-2603` über `https://api.eu.mistral.ai/v1` nutzen. Dies ändert weder die vier lokalen Alltagsrollen noch den pausierten Großimport oder die automatische Einordnung neuer Mails. Ein vorhandener Mistral-Schlüssel allein aktiviert keinen Lauf.

Der eigenständige Kostenstand startet bei **0 USD**. Eine authentifizierte, ausdrücklich bestätigte Änderung setzt ein kumulatives Gesamtlimit; sie setzt verbrauchte oder reservierte Beträge nicht zurück. Neue oder geänderte Limits erfordern eine neue Paketvorschau. Die Abrechnung verwendet ganzzahlige Mikro-USD und den fest eingebauten Preisstand, ohne Steuer- oder Wechselkurszusage.

Vor jeder Anfrage werden das ganze vom Anbieter bestätigte Kontextlimit und die vollständige Ausgabe reserviert. Gültige Nutzungszahlen werden auch bei anschließend abgelehnten oder zurückgezogenen Ergebnissen abgerechnet. Unbekannte Abrechnung, Zeitüberschreitung oder unklare Zustellung halten die Reservierung fest und blockieren weitere Mistral-Anfragen. Ein neuer Schlüssel, Neustart oder höheres Limit hebt diese Sperre nicht auf. Eine allgemeine Abrechnungsbereinigung gehört nicht zu dieser Lieferung.

Der Kostenstand liegt außerhalb der wiederherstellbaren Quelldateien. Eine Wiederherstellung lässt den aktuellen Kostenstand unverändert; ein fehlender Kostenstand beginnt ohne Ausgabefreigabe. Originale, genaue Belege, Quellenentzug und bestätigte Nutzerentscheidungen bleiben maßgeblich.

## Nachweise

- Unabhängiges Review der Abrechnung, des Transports, der Quellenjobs, Zugangsspeicherung, Wiederherstellung und UI-Freigaben: keine bestätigten Blocker; **200 betroffene Backendtests** und **7 Budget-Logiktests** bestanden.
- Implementierungsprüfung der Paket-/Zugangs-/Wiederherstellungswege: **263 Tests** bestanden. Transport und dauerhafte Reservierungen separat: **132 Tests** bestanden. Diese teilweise überlappenden Zahlen werden nicht addiert.
- Oberfläche: **985 Tests** bestanden. Produktionsbuild erfolgreich; die bereits vorhandene Warnung zur Größe des Hauptpakets bleibt.
- Getrennte Browserprobe mit künstlichen Daten, realen React-Komponenten und simulierten lokalen API-Antworten: **15 Ablaufprüfungen** bestanden. Geprüft wurden 0-USD-Sperre, ungültiger Betrag, Entwurfserhalt und Fokus nach Speicherfehler, neue Freigabe nach Limitänderung, verpflichtende Quellenzustimmung, verspätete Vorschau nach Zugangsänderung sowie 900/1.280 Pixel ohne horizontalen Überlauf. Heller und dunkler Systemmodus wurden angesehen. Dies ist keine native Mac-Abnahme und kein Anbieteraufruf.
- Die Bedienprobe fand einen echten Fokusfehler nach fehlgeschlagenem Speichern; dieselbe Probe besteht nach der Korrektur. Eine Designprüfung fand zwei feste Farben; diese verwenden jetzt die vorhandenen Stilwerte.
- Vorbereitete künstliche Quellenprobe: **39 Helper-/Diagnostiktests** bestanden. Die vollständig simulierte Route verwendete sieben unveränderte Originale, eine Metadatenabfrage und 14 Einordnungsaufrufe. Der echte lokale Kostenrechner verbuchte **1.204 Mikro-USD** aus simulierten Nutzungszahlen, ohne offene Reservierung. Dies sind keine angefallenen Anbieterkosten.
- Unabhängige Ergänzungsprüfung des neuen Prüfskripts, der Fokuskorrektur und der UI-Freigaben: **31 Helper-Tests** bestanden, keine zusätzlichen bestätigten Blocker.
- In einem parallelen betroffenen Testlauf überschritt ein Test seine 10-Sekunden-Wartezeit; die zwei isoliert wiederholten Varianten bestanden. Die Wartezeit wurde nicht erhöht; auch die vollständige integrierte Regression besteht.
- Vollständige integrierte Backend-Regression vor der unten beschriebenen Schlüssel-Leseoptimierung: **9.553 bestanden, 1 übersprungen und 26 Unterprüfungen bestanden** in 22:35 Minuten. Die einzige Warnung betrifft die vorhandene Starlette/httpx-Testabhängigkeit.

### Parallelprüfung: gemessene Schlüssel-Leseoptimierung

Die anschließende GitHub-Parallelprüfung fand vier zu frühe Zehn-Sekunden-Abfragen neuer Routentests. Ein Profil am eingefrorenen Stand zeigte: Der normale künstliche Auftrag entschlüsselte die unveränderte Schlüsseldatei **138-mal**, mit etwa **9,3 Sekunden CPU-Zeit** allein für die 600.000-Runden-Schlüsselableitung. Sperren und simulierte HTTP-Antworten verursachten zusammen weniger als 0,03 Sekunden. Mit nur 20 ms zusätzlicher Verzögerung je Entschlüsselung war der scheinbare Testfehler reproduzierbar; derselbe Auftrag endete anschließend mit richtigen Ergebnissen.

Die Korrektur behält jede echte Dateilesung und jede Zugangs-/Widerrufsprüfung bei. Ein privater, einzelner Cache je Schlüsselspeicher darf nur bereits erfolgreich geprüfte **identische verschlüsselte Bytes unter derselben aktuellen Passphrase** wiederverwenden. Änderungen, fehlende oder unlesbare Dateien, andere Passphrase, ungültige Daten sowie Schreib-/Löschversuche verwerfen den Eintrag. Rückgaben sind Kopien; native Betriebssystem-Schlüsselbunde bleiben unverändert. Die Kryptografie, Dateiformate und 600.000 KDF-Runden sind unverändert. Der zusätzliche Eintrag existiert nur im vertrauenswürdigen Hauptprozess, nicht als Datei, Umgebungsvariable oder Worker-Datum.

Unabhängige Prüfung fand zunächst eine Blockade bei einer als FIFO ausgetauschten Datei. Die korrigierte Fassung verwirft nichtreguläre Pfade und prüft den nichtblockierend geöffneten Dateideskriptor vor dem Lesen; reguläre Symlinks bleiben wie zuvor zulässig. Direkter FIFO, FIFO-Symlink und Austausch während der Prüfung wurden unabhängig erneut geprüft.

**110 fokussierte Tests** bestanden, darunter 29 Fälle mit tatsächlicher Verschlüsselung. Die vier ursprünglichen Routentests behalten ihre Zehn-Sekunden-Grenzen und vollständigen Assertions; sie bestehen in 2,44 Sekunden. Der normale künstliche Auftrag sank auf etwa **0,054 Sekunden** bei derselben Anzahl echter Schlüssel-/Salt-Lesungen. Das ist ein Transport-/Berechtigungstest mit simulierten Modellantworten, keine gemessene Mistral-Inferenzlatenz. Die ursprüngliche Sicherheitseinschränkung und der Fix wurden unabhängig nachgeprüft; keine bestätigten Befunde bleiben in diesem Zweidateien-Umfang offen.

## Reproduzierbare Prüfung ohne Anbieter

```sh
PYTHONPATH=sidecar:.:scripts python -m pytest scripts/test_probe_mistral_source_package.py scripts/test_probe_intake_precision.py -q
PYTHONPATH=sidecar:.:scripts python -m pytest sidecar/tests/test_cloud_import_budget.py sidecar/tests/test_mistral_import_provider.py sidecar/tests/test_mistral_source_credentials.py sidecar/tests/test_mistral_source_jobs.py sidecar/tests/test_mistral_source_routes.py sidecar/tests/test_cloud_memory.py sidecar/tests/test_restore_boundary.py -q
cd app/kingfisher
npm test
npm run build
```

## Offene tatsächliche Abnahme

Es wurde **kein echter Mistral-Aufruf** ausgeführt und kein persönliches Kostenlimit freigegeben. Das tatsächliche Konto, die regionale Modellverfügbarkeit und die realen Nutzungs-/Rechnungswerte bleiben ungeprüft. Das getrennte Prüfskript verlangt eine konkrete Freigabe, ein ausdrücklich angegebenes Limit bis 1 USD und einen eigenen Schlüssel nur für diese künstliche Probe. Es liest keinen persönlichen Kingfisher-Bestand oder gespeicherten Hauptschlüssel.

Das Skript prüft Personen und Kategorien über echte Quellenjobs und Belegvalidatoren. **Aufgaben und Fristen sind dort ausdrücklich `not_evaluated`**. Selbst bei vollständiger technischer Verarbeitung bleibt das Gesamturteil unvollständig und der Rückgabecode ungleich null. Es kann den Großimport nicht freigeben. Eine spätere gemischte Qualitätsprüfung muss auch Aufgaben, Fristen, Identitätsklärung und Abruf unabhängig an Originalen prüfen.

## Primärquellen des Preis- und Transportstands

Geprüft am 02.11.2026; Preisstand gültig bis 02.12.2026, danach blockiert die Anbindung bis zu einem neu geprüften Preisstand.

- [Small 4: Modell und Standardpreise](https://docs.mistral.ai/models/mistral-small-4-0-26-03): Standard 0,15/0,60 USD je Million Ein-/Ausgabetokens.
- [Regionale Inferenz](https://docs.mistral.ai/inference/regional-inference): EU-Endpunkt und 1,1-facher Regionalpreis, hier 0,165/0,66 USD. EU/EFTA-Inferenz und getrennte Konto-/Verwaltungsmetadaten sind keine pauschale Datenschutz- oder ZDR-Zusage.
- [Chat API](https://docs.mistral.ai/api/endpoint/chat): feste Standardkapazität mit `service_tier=standard_only`, striktes Antwortschema und begrenzte Ausgabe.
- [Offizielles Antwortmodell](https://raw.githubusercontent.com/mistralai/client-python/main/src/mistralai/client/models/chatcompletionresponse.py): kein erforderliches Antwortfeld `service_tier`. Fehlt es, gilt der ausdrücklich angeforderte Standardtarif; ein dennoch geliefertes abweichendes Feld wird abgelehnt.
- [Modellmetadaten](https://docs.mistral.ai/api/endpoint/models): das tatsächliche numerische Kontextlimit wird erst innerhalb eines freigegebenen Laufs geprüft. Speichern, Status und Vorschau haben keine solche Nebenwirkung.
