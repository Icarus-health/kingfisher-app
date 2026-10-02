# Kalenderliste – lokale Abnahme am 7. September 2026

Die bisher deaktivierte Kalendernavigation öffnet `/calendar`. Die Ansicht
zeigt die nächsten sieben Tage aus den vorhandenen Kalenderkonnektoren.
Sie unterstützt Aktualisierung, Quellenverwaltung, Ganztagstermine, Leerzustand
und Fehler einzelner Quellen bei weiterhin sichtbaren erfolgreichen Ergebnissen.

## Prüfungen

- UI-Build und Asset-Vertrag erfolgreich.
- 25 gezielte bestehende Backendtests erfolgreich; nach zusätzlichem
  Endpunkttest alle sechs Tests im Kalender-Testmodul erfolgreich.
- Neuer Endpunkt: Authentifizierung, begrenzte Tageszahl und Teilfehler geprüft.
- Playwright, Chromium, 1440 × 1000: Einstellungen → Kalender → Terminanzeige
  mit Quelle und Ganztag → Aktualisieren → Leerzustand → Quellenverwaltung.
- Seitentitel und Inhalt vorhanden, keine Runtimefehler oder Vite-Fehleranzeige.
- Screenshot visuell geprüft: keine Überlappung oder abgeschnittenen Termintexte.

Die Browserantworten enthielten ausschließlich synthetische Termine und eine
absichtlich nicht erreichbare Testquelle. Persönliche Kalender wurden nicht
verändert. Backendtests verwenden temporäre Datenverzeichnisse.
Browser-Plugin nicht verfügbar; vorhandene Playwright-Laufzeit verwendet.

Nicht geprüft: mobile Darstellung und persönliche Kalenderdaten. Die Liste
ist lesend; Termine anlegen oder verändern ist nicht Teil dieses Schritts.

## Korrektur nach Nutzerrückmeldung

Direktes Öffnen von `/calendar` lieferte 404, obwohl clientseitige Navigation
funktionierte. Serverroute ergänzt; Container-Routingtest umfasst jetzt den
Direktaufruf mit HTML-Antwort. Alle 21 Containertests bestanden. Neu gebautes
Image lokal gestartet und den vorhandenen Nutzer-Tab neu geladen: echte
Kalenderansicht mit 12 Terminen sichtbar. Keine persönlichen Termininhalte
in Prüfdokumentation oder Screenshots gespeichert.

## Woche, Monat und Jahr

Vier umschaltbare Ansichten, persistierte Ansicht, Monats-/Wochennavigation
innerhalb des laufenden Jahres, Heute-Sprung, Tagesauswahl und Jahresraster.
Mac-Jahresdaten werden in höchstens 31 Tage langen Abfragen gelesen und per UID
zusammengeführt. Die API kennzeichnet fehlende Jahresabdeckung als Fehler.
Der Synchronspeicher enthält nun das laufende Jahr mit zwei Tagen Randpuffer.

28 gezielte Backendtests und UI-/Asset-Build bestanden. Im echten Nutzer-Tab
Monat → Jahr (12 Monate) → Neuladen (Ansicht bleibt) → Woche (7 Tage) → Monat
geprüft. Monatsraster visuell geprüft. Echter Jahresabruf: 519 Termine,
keine Quellenfehler. Keine persönlichen Termintexte in diesen Nachweis kopiert.
Andere Jahre und eine stundenbasierte Wochen-Zeitleiste sind nicht enthalten.
