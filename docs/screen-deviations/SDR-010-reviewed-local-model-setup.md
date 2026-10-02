# Umsetzungsfreigabe: lokale Modelleinrichtung

Datum: 8. September 2026. Entscheidung durch Codex im Rahmen der vom Nutzer
übertragenen Entwicklungs- und Reviewentscheidung („enscheide selber wie“ und
Freigabe, selbst geprüfte PRs zusammenzuführen). Dies dokumentiert die
Umsetzungsprüfung durch den beauftragten Agenten, keine nachträglich erfundene
persönliche Einzelabnahme eines Screenshots durch den Nutzer.

## Bezug zur Vorlage

Screen 14 der kanonischen Systemübersicht bleibt die Grundlage: dunkle
Seitennavigation, helle Arbeitsfläche, Integrationen links und Dateninformation
rechts. Die Vorlage definiert keinen lokalen Ollama-Einrichtungsdialog.
Entsprechend dem Prinzip aus SDR-007 wird der zusätzliche Ablauf als reduzierter
Inline-Bereich in dieser bestehenden Einstellungsstruktur umgesetzt.

## Freigegebener Umfang

- Kompakte Zeile „Lokale KI“ mit gespeicherter Auswahl und „Modell verwalten“.
- Bei fehlender Einrichtung geöffnet; vorhandene lokale Modelle in einer Auswahl.
- Manuelle Modellnameneingabe nur als ausdrücklich gewählte Ausweichmöglichkeit.
- Speichern und tatsächliche Verbindungsprüfung; keine Erfolgsmeldung allein aufgrund eines HTTP-Status.
- Lade-, Leer-, Fehler- und Erfolgszustände innerhalb desselben Bereichs.
- Nach erfolgreicher Verbindung direkter Einstieg „Zum Gespräch“.
- Keine neuen Bilder, Providerlogos, Dialogfenster oder abweichende Designsprache.

Die Freigabe gilt nur für diesen Einrichtungsablauf. Sie ersetzt weder die
Gesamtabnahme aller Einstellungsbereiche noch den vollständigen Desktopvergleich
von Roadmap-Punkt 16. Nachweise: VISUAL-CHECK-local-model-v1.md.
