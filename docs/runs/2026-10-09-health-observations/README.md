# Eigene datierte Gesundheitsangaben

Code: `8d5971b5fb98229a50deb0f002b4d0f1da9e3be7`, Basis `3667e4e18b9e255780c755889370b46368cf0a6d`. [Design](../../superpowers/specs/2026-10-09-health-observations-design.md), [Plan](../../superpowers/plans/2026-10-09-health-observations.md), [Prüfmanifest](verification.json).

## Nutzbarer Codeumfang

`/wellbeing` ist über Heute und Entwicklung erreichbar. Eigene Messgröße, wörtlicher Dezimalwert, Einheit, Messzeit mit sichtbarem UTC-Versatz und optionale Notiz werden ausdrücklich geprüft und anschließend als Originalquelle gespeichert. Keine zweite Datenbank, kein Schemawechsel, kein Modellaufruf. Der technische `/health`-Endpunkt bleibt erhalten; Datenrouten verwenden die bestehende Authentifizierung.

Aktuelle eigene Angaben werden nach exakten UTC-Mikrosekunden und rowid sortiert, je Seite höchstens 25 (API maximal 50). Höchstens 100 Originaldokumente werden pro Anfrage validiert. Das ist eine Grenze für geladene/validierte Originale, **keine Obergrenze der SQL-Sortierarbeit** und kein Gesamtbestandszähler. Bei unprüfbaren Kandidaten kann eine leere Seite eine Fortsetzung enthalten. Cursors binden Abfrage, Grenzzeile und deren unveränderte Identität; Rechte werden pro Abruf erneut geprüft. Der Verlauf ist eine lebende, begrenzte Navigation, kein unveränderlicher Snapshot über mehrere Anfragen.

Korrekturen prüfen den Originalfingerabdruck, erzeugen neue Fassungen und sperren frühere Belege samt abhängigen Claims. Alte Originale bleiben erhalten. Eine unveränderte Korrektur schreibt nichts. UUID-Wiederholungen erhalten das Ergebnis desselben bestätigten Vorgangs; andere Eingaben oder entzogene Fassungen werden nicht durch Wiederholung zugelassen. Die UI behält dieselbe Kennung für einen erneut gesendeten, unveränderten Formularvorgang. Das beweist keine Wiederherstellung eines ungespeicherten Formulars nach Browserabsturz.

Die Quellen-/Kategorietransaktion rollt bei Speicherfehlern zurück. Claim-Invalidierung ist wie im vorhandenen Quellenwechsel zuerst in der separaten Claims-Datenbank: Ein Fehler kann konservativ strittige Claims hinterlassen, er darf kein überholtes Wissen wieder zulassen. Kategorien werden vor Aufnahme auf Verfügbarkeit geprüft. Rohwerte bleiben auch nach Verdichtungsbuchhaltung sichtbar.

## Nachweis

- 33 neue Backendfälle gegen reale SQLite-Stores/HTTP: Datum und Aufnahme getrennt, Textwert/Einheit/Offset erhalten, Selbstaussage verpflichtend, fremde Personen/mehrdeutige Zahlen/offsetlose Zeiten abgelehnt, Serverneustart mit erhaltener Vorgangskennung, identische Messungen mit getrennten Kennungen, Korrektur/Replays/alte Originale, echte Claim-Invalidierung samt Abhängigkeit, Stale/Entzug, unveränderte Korrektur, malformed sources, Leerseite mit Fortsetzung, Historien-Cursor, Speicher-Rollback und Mikrosekundenreihenfolge.
- 239 betroffene Backendtests bestanden (11 Dateien, einschließlich Quellenfassungen, Episoden, Claims, Kategorien, Bereiche und Zeitachse). **Kein vollständiger Backendlauf behauptet.** Ein anfänglicher Auswahlaufruf nannte zwei nicht existierende englische Testdateien und lief nicht; die gültige finale Auswahl nutzt die tatsächlichen Dateien.
- Alle 446 Frontendtests bestanden, darunter 15 neue Formular-/Handlerprüfungen: explizite Vorschau vor Schreiben, Doppelklick, verlorene Antwort, Stale-Korrektur mit erhaltenem Entwurf, Fortsetzung, späte Anfrage, sichtbarer Historien-Abrufstand und erneute Prüfung, DST-Lücke/-Doppelstunde, ursprüngliches Z und Mikrosekunden. Komponenten werden für diese Handlerprüfungen kompiliert und mit kontrollierten Hooks/Transport ausgeführt; **das ersetzt keine echte React-/DOM- oder native Bedienprüfung**.
- TypeScript/Vite-Build bestanden. Vite meldet das Hauptbundle über 500 kB; Starlette meldet die vorhandene Testclient-Deprecation. Keine Laufzeit-/Darstellungsfreigabe daraus abgeleitet.
- Aus sauberem Git-Archiv des Codecommits erneut: 33 HTTP-Fälle, alle 446 UI-Tests und Build bestanden. Bestehende lokale UI-Abhängigkeiten nur lesend eingebunden; Synchronisationsduplikate ausgeschlossen. Gebaute Dateien im Manifest per SHA-256 belegt.
- Vor Umsetzung fehlten die Endpunkte und Editor-/Seitenfunktionen nachweislich (25 HTTP-/4 Formular-/4 Editor-/4 Seitenfälle rot). Präzisionsfehler und No-op-Fehler vor ihrer Korrektur separat rot. Der korrigierte Historientest erkennt das temporäre Entfernen seiner Prüfaktion; Datei anschließend bytegleich wiederhergestellt und Tests grün.
- Unabhängiger Read-only-Review fand vier konkrete Design-/Implementierungsfehler; diese wurden korrigiert. Abschließender begrenzter Recheck meldete keine weiteren konkreten Blocker. Der Reviewer hat keine Tests oder persönlichen Daten geöffnet.

## Offene Lieferung

**Draft, nicht gemergt, nicht installiert.** Der Nutzer hat den Fenstertest verschoben; weder Browser- noch Headless-Ausweichzugriff erfolgte. Offen bleiben echte Desktop-/schmale Darstellung, Tastatur/Fokus, native Öffnen → Eingabe → Original → Korrektur → Ausschluss, Paket-/Mac-Auslieferung und größere Messreihen. Dateien/HealthKit, andere Menschen und medizinische Interpretation sind nicht enthalten. Der vollständige CoS-Auftrag bleibt offen; dieses Modul erklärt das Gesamtprodukt nicht für fertig.

Produktiver Import, bestehende persönliche Originale und Modell-/Cloudkonfiguration wurden in dieser Runde nicht bedient. Keine CI-Neustarts, neuen Abonnements oder Check-ins.
