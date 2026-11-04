# Rückmeldung und Skillprüfung verständlicher – 04.11.2026

## Problem und Änderung

Die aktuelle Bedienprüfung mit Product Design und Build Web Apps zeigte drei konkrete Lücken:

1. „Stimmt nicht?“ wurde auch unter einer bloßen Skill-Auswahl gezeigt. Die anschließende Meldung klang nach Lernen, obwohl der Rückkanal nur eine Fehlernotiz speichert.
2. Beim Öffnen wuchs das Korrekturformular unter die feste Chateingabe. Abbrechen per Tastatur hatte keinen gezielten Rückweg.
3. Versions- und Prüftechnik verdrängten die eigentlichen Skill-Schritte; die Gegenbeispiele waren vor einer Übernahme eingeklappt.

Die Korrektur blendet Feedback bei Skill-Rückfragen und Lernvorschlags-Hinweisen aus. Echte Antworten mit einem angewendeten Skill bleiben meldbar. Der Rückkanal sagt vor und nach dem Speichern ausdrücklich, dass Fakten und Abläufe unverändert bleiben. Das Formular wird beim Öffnen in den sichtbaren Bereich gescrollt, Escape schließt es mit Rückfokus und erhält den eingegebenen Text. Während eines laufenden Speicherns wird kein erfolgloses „Abbrechen“ angeboten.

Skill-Details zeigen zuerst Geltungsbereich, Auslöser und Schritte. Bei offenen Vorschlägen sind beide Beispiele von Anfang an offen, der Hinweis „Noch nicht aktiv“ steht vor der Übernahme. Erfolgreiche technische Prüfungen und seltenes Bearbeiten/Exportieren liegen darunter in aufklappbaren Bereichen. Fehlgeschlagene Prüfungen bleiben ausdrücklich sichtbar und verhindern weiterhin die Übernahme. Es gibt keine Änderung an Speicherung, Auswahl, Modellberechtigungen oder Aktivierungsregeln.

## Prüfungen

- Neue Verhaltenszusicherungen zunächst rot gesehen: unzulässiger Feedback-Eintrag; Escape/Rückweg; korrekte Speicherbestätigung; sichtbare Anwendungsgrenzen; Warnung bei fehlerhafter Prüfung.
- 31 betroffene UI-Tests bestanden.
- Gesamte UI-Suite mit begrenzter Parallelität: `node --experimental-strip-types --test --test-concurrency=1 tests/*.test.mjs` – **1.031/1.031 bestanden**, 55,54 Sekunden.
- Erster Gesamtlauf: 1.030/1.031; der alte Test `nach „Melden“ steht, was mit der Meldung geschieht (Befund 12)` verlangte noch das entfernte Lernversprechen. Nach Anpassung an die beabsichtigte Semantik erneut vollständig grün. Kein stillschweigend übergangener Fehler.
- Typprüfung und Vite-Build bestanden. Bestehender Hinweis auf große JS-Pakete bleibt offen; dieser Patch ändert die Bündelung nicht.
- Assetprüfung: 11 Dateien und 14 Icons bestanden; `git diff --check` bestanden.
- Unabhängiges Review der gesamten Änderung: genau der veraltete Texttest als wichtiger Befund, korrigiert. Keine weitere verifizierte Critical-/Important-Regression. Die komponentennahen Tests allein beweisen keine Layout- oder VoiceOver-Qualität.

## Frische Bedienprüfung

Ausschließlich getrennte künstliche Daten auf Port 8893; kein persönlicher Bestand, keine echte Mail, kein Modellaufruf und kein Versand.

| Schritt | Beobachtung |
|---|---|
| Antwort öffnen | Nur die tatsächliche Antwort bietet Feedback; zwei Skill-Rückfragen darüber nicht mehr. |
| Feedback öffnen, ausfüllen, Escape, Enter | Bei 1.280 und 900 Pixeln nach Öffnen vollständig erreichbar; Fokus auf erster Auswahl, Rückfokus auf Auslöser; Text und Art bleiben erhalten. |
| Feedback speichern | Sichtbare Bestätigung: Fehlermeldung gespeichert; keine Fakten-/Ablaufänderung behauptet. |
| Bibliothek öffnen und vorhandenen Ablauf lesen | Schritte vor erfolgreicher Prüftechnik; Herkunft und seltene Aktionen aufklappbar. |
| Neue Fassung eines künstlichen Ablaufs speichern und öffnen | Version 2 bleibt vorgeschlagen, bisherige Version 1 bleibt aktiv; positive/negative Beispiele offen; explizite Übernahme weiterhin nötig. |
| Native Mac-Test-App neu starten | Aktuelles UI geladen, Feedback sichtbar; Escape/Enter und Entwurferhalt im echten WKWebView geprüft. |

Keine Warnungen/Fehler im Browserprotokoll. Die erste DOM-Eingabe in ein noch unterhalb des sichtbaren Bereichs liegendes Schritte-Feld lief in ein Timeout; nach normalem Scrollen funktionierte die native Eingabe. Kein verdeckter Schreibzugriff als UI-Ersatz.

Grenzen: Kein vollständiger Produktaudit, keine Prüfung aller Farben/Kontraste, kein vollständiger VoiceOver-Durchgang und kein 200-Prozent-Zoomnachweis. Ein bereits geöffnetes Formular wird beim Verkleinern des Fensters nicht automatisch neu positioniert; Tastaturnavigation und erneutes Öffnen bleiben möglich. Das gehört zur verbleibenden adaptiven P4-Prüfung. Kein Nachweis echten automatischen Lernens aus drei Korrekturen: dieser P2-Schritt ist weiterhin offen.

## Auslieferung

Aufbauend auf der geprüften Konfliktauswahl aus PR #118. Dieses Paket ist eine eigene UI-Korrektur, keine Veröffentlichung oder Installation in der persönlichen Alltagsinstanz. Die Alltagsfassung bleibt 1.0.44, der Großimport pausiert. Screenshots und vollständige lokale Prüfprotokolle liegen im privaten Arbeitsnachweis `work/product-plan-20261104/bedienung/` beziehungsweise im temporären Prüfverzeichnis, ausschließlich mit künstlichem Inhalt.
