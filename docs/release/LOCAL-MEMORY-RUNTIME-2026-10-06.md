# Lokaler Alltagspilot: Speicher, Mailaufnahme und Modellgrenzen

Stand: 6. Oktober 2026. Dieser Nachweis trennt geprüfte Funktionen von noch offenen Qualitätsfragen. Er ist keine Zusage eines fehlerfreien Gedächtnisses.

## Gelieferte Korrekturen

- Die optionale lokale Mail-KI arbeitet jetzt auch vor der dauerhaften Ordneraufnahme. Regeln bleiben vorrangig; unsichere, unvollständige oder zu lange Nachrichten kommen in den Prüfbereich. Der KI-Schalter bleibt unabhängig von der Pause der Gedächtniseinordnung. Eine nachträgliche Änderung der Freigabe verhindert die automatische Aufnahme.
- Die Prüfung behält Ordner und Nachrichtenkennung bei. Eine ausdrücklich übernommene Mail aktualisiert denselben Importdatensatz; veränderte Originale werden abgewiesen. Manuelle Wiederholprüfung ist auch für ausgefilterte Einträge möglich. Die Anzeige erklärt, dass `overflow` volle Filterversuche zählt, einschließlich Wiederholungen.
- Der IMAP-Posteingang liest die ausgewählten UIDs in einem gebündelten `UID FETCH (UID FLAGS BODY.PEEK[])`. Inhalte werden anhand der vom Server gelieferten UID zugeordnet, nicht anhand der Antwortreihenfolge. Fremde, mehrdeutige und doppelte Kennungen werden verworfen. Die Ordnerauswahl bleibt lesend. [IMAP-Spezifikation](https://www.rfc-editor.org/rfc/rfc9051.html).
- Personenakten nennen gemeinsame Quellen als solche. Ihr gemeinsames Auftreten ist kein Nachweis einer tatsächlichen Beteiligung oder Beziehung.
- Lokale `kingfisher-*`-Ollama-Profile werden serialisiert. Vor einem Profilwechsel werden nur andere geladene Kingfisher-Profile entladen; fremde Modellnamen bleiben unangetastet. Nach dem Aufruf wird die Verweildauer auf 15 Sekunden verkürzt. Fehler beim Vorbereiten verhindern den Modellaufruf. Das ist keine allgemeine RAM-Obergrenze für den Mac.
- Decision-only-Modelle erhalten die native `/v1/systemone`-Schnittstelle. Positive Prüfung lokaler Gewichte und Fähigkeiten, begrenzte Eingaben/Antworten, keine Proxy-/Redirect-Weiterleitung und kein Chat-Fallback. Ungültige oder unzureichend sichere Entscheidungsantworten gelten als unklar.

## Gemessene lokale Modelle

Mac mit 32 GB gemeinsamem Speicher; Ollama 0.35.1. Die Profile wurden aus vorhandenen Gewichten erstellt, ohne neuen Modelldownload. [Ollama create](https://docs.ollama.com/api/create), [Verweildauer](https://docs.ollama.com/api/generate).

| Profil | Kontext | Befund mit künstlichen Daten |
|---|---:|---|
| `kingfisher-qwen3.5:9b-32k` | 32768 | Ollama meldete etwa 7,3 GB für das geladene Profil; einfache strukturierte Prüfungen etwa 0,6 s warm, 4,7–5,5 s mit Kaltstart/Wechsel. |
| `kingfisher-gemma4:12b-32k` | 32768 | Antwortrolle funktioniert; gemessener Wechsel etwa 8,1 s. Kein belastbarer Gesamt-RAM-Wert für diese Rolle aus der Probe. |
| `kingfisher-tev1:4b-8k` | 8192 | Native Entscheidungen funktionieren; etwa 5,0 GB und 5,3 s beim Kaltstart. Noch kein Standardprüfer. |

Das vorher gewählte Nemotron-30B-Profil belegte laut Ollama etwa 26,7 GB mit Kontext 262144. Es wurde entladen und nicht gelöscht. Für 32-GB-Geräte empfiehlt Kingfisher nun Qwen9B als Hintergrundstandard; das große Nemotron bleibt eine Alternative für größere Geräte.

TEV konnte bei den konservativen Entscheidungsschwellen sieben von acht einfachen Mailbeispielen nicht sicher entscheiden. Auch drei Aussageprüfungen einschließlich eines korrekt belegten positiven Beispiels blieben unklar. Die Schwellen wurden deshalb nicht abgesenkt. Modellwahrscheinlichkeiten sind keine kalibrierte Fehlerquote. Qwen bestand vier kleine Richtungs-/Negations-/Datumsprüfungen; das ersetzt keine breite Qualitätsmessung.

## End-to-End-Grenzen und Pilotkonfiguration

Eine künstliche Arbeitswoche mit drei Quellen und drei Fragen hat Aufnahme, unveränderte Originale und Integrität bestätigt. Der strenge Textgrader bestand 2/3 Antworten. Die dritte war inhaltlich korrekt („Das Hotel … ist nicht gebucht“), enthielt aber nicht die verlangte genaue Formulierung „keine Hotelbuchung“. Die Probe verwendete Qwen und keinen zweiten Prüfmodell-Durchlauf. Daraus folgt keine allgemeine Trefferquote.

Eine separate künstliche Richtungs-/Negationsfrage mit getrennten Rollen erhielt die richtige Originalquelle, ließ aber den korrekt belegten Satz „Lea gibt Tom den Schlüssel“ weg. Die bestehende deterministische Negationsprüfung wertete eine andere, verneinte Aussage derselben Quelle zu weitreichend aus. Die Antwort enthielt die richtige Aussage, dass die Übergabe noch nicht erfolgt sei. Der gesamte kalte Ablauf dauerte rund 35 Sekunden. Diese Übervorsicht und die komplexe Antwortlatenz bleiben gezielt zu verbessern; sie wurden nicht durch eine schwächere Wahrheitsprüfung verdeckt.

Der lokale Pilot wurde daher auf geprüfte Quellenausschnitte (`saetze=aus`) gestellt. Frage, Hintergrund und Prüfung nutzen das begrenzte Qwen-Profil, die allgemeine Antwortrolle das Gemma-Profil, Einbettungen weiterhin `bge-m3`. Automatische Einordnung und lokale Mail-KI sind aktiviert; die vor der Aktualisierung pausierte Hintergrundsteuerung wurde wieder gestartet. Das ist eine reversible Pilotkonfiguration, keine Änderung der allgemeinen Produktvorgabe. Der KI-Import prüft zunächst zwei Mails pro Hintergrundtakt; ein kompletter großer Altbestand wird nicht als bereits verarbeitet dargestellt.

## Reale lokale Installation

Vor der Aktualisierung wurden Einstellungen und das im gestoppten Zustand gesicherte Datenvolume außerhalb des Repositorys privat archiviert. Die laufende Installation verwendet weiterhin dasselbe Volume. Alle 232 ursprünglichen Quellen wurden nach der Aktualisierung anhand ihrer ID und Inhaltsdigest wiedergefunden. Keine produktiven Probequellen angelegt, keine privaten Quellen an ein Cloud-LLM geschickt, keine Mail versendet.

Backend 1.0.2 ist ein lokal gebautes Image. Die vorhandene native Mac-App 1.0.1 bleibt der Launcher. Dies ist noch kein veröffentlichter GHCR-/DMG-Release. Das alte Image und die Sicherung bleiben erhalten.

Vorher dauerte der direkte Abruf von 30 Mails rund 8,3 Sekunden und überschritt die sechs Sekunden des UI-Abrufs. Nach der Bündelung: direkte Probe 2,4 Sekunden, erfolgreicher UI-Endpunkt 3,9 Sekunden, 30 Nachrichten ohne Teilfehler. Eine zwischengespeicherte Fehlermeldung verschwand nach dem Wiederholungsabruf. Im nativen Fenster wurden alle 30 Mails und die Filterzählungen sichtbar; die Ortszeit aktualisierte sich weiter. Einzelmessungen sind keine Latenzgarantie für fremde Mailserver.

## Prüfstand

Die unabhängige Nachprüfung konzentrierte sich auf UID/Inhalt-Zuordnung, Freigabewechsel, lokale Modellgrenze und UI-Aussagen. Sie fand eine irreführende Überlaufanzeige; diese wurde korrigiert. Die vollständige erste Backend-Prüfung fand zudem eine Regression: Der Mail-KI-Schalter war versehentlich an die Gedächtnispause gekoppelt. Beide Aufnahmewege wurden korrigiert und gezielt nachgeprüft.

- Abschließende fokussierte Mail-/Scheduler-/Automatikprüfungen: 54 bestanden.
- Frontend: 277 bestanden; Typecheck und Produktionsbuild bestanden.
- Mac-Launcher: 26 bestanden, ein Skip; lokaler SDK-/Modulcache explizit gewählt.
- Docker-Produktionsbuild und Gesundheitsprüfung der aktualisierten Installation bestanden.
- Abschließende vollständige Backend-Suite: 4756 bestanden, ein Skip, zwei Warnungen; 753,08 Sekunden mit Python 3.12 und Freigabe für lokale Testserver.

Keine GitHub-Actions-Wiederholung ausgelöst. Der Commit verwendet `[skip ci]`. Lokale Tests belegen diesen Stand; sie ersetzen weder einen mehrtägigen Alltagstest noch eine unabhängige Abnahme großer persönlicher Datenbestände.
