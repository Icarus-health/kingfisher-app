# Lokal sprechen im bestehenden Gespräch

Spec: docs/superpowers/specs/2026-10-09-local-voice-dialog.md. Basis 502e650d170ba8d477f04cd9df20150544e0adef, eigene Featurebranch. Kein Fenster-/Mikrofonzugriff in dieser Runde; spätere echte Abnahme unverändert erforderlich.

## Task 1: Native Aufnahme- und Wiedergabegrenze

Strikt validierte Nachrichten, Main-thread-Koordinator und echter Apple-Adapter mit zwingender Geräteerkennung. Künstliche Freigabe-/Recorder-/Stimmenfälle prüfen späte Freigabe, Start/Stop/Cancel, falsche Sitzungskennung, alte Resultate, 60-/5-Sekunden-Grenzen, lokale Fähigkeit und verstecktes Fenster. Nachweisen, dass keine Aufnahmen/Dateien/Cloudfallbacks entstehen. SDK-/ARM-Typprüfung ohne Gerätezugriff. Native Bridge an Mainframe, Origin und aktuelles sichtbares Gespräch binden; Freigabetexte im Bundle. Erwartet: Vertragstests und Kompilierung bestanden, kein realer Mikrofon-/Stimmenaufruf.

## Task 2: Bestehenden Gesprächsflow verbinden

Mikrofonschaltfläche nur bei bestätigter nativer lokaler Fähigkeit. Vorhandenen Entwurf erhalten, diktierte Teiltexte separat anzeigen, Ende als prüfbarer Entwurf übernehmen; Abbrechen verwirft Zusatz, nie automatisch senden. Verbergen/Navigation/Sendebusy beendet Aufnahme. Rückmeldungen nur für eigene aktuelle Kennung. Antworten auf Wunsch nach frischem GetConversation und identischer zugänglicher sichtbarer Fassung lokal vorlesen. Alle Quellen-/Beleg-/Abdeckungshinweise erhalten. Abbruch bei Wechsel. Browser ohne Bridge unverändert. Funktionsfälle vor Implementierung prüfen, vollständige UI-Suite/Build. Keine unsichtbare Textkopie oder neue KI-Verarbeitung.

## Task 3: Review und Lieferung

Unabhängige Prüfung von lokalen Datenschranken, fremden Frames/Docs, Lebensdauer/Timer/Taps, Entwurf und Quell-/Antwortrücknahme. Wichtige Befunde durch zuvor scheiternden Test korrigieren. Gepinnte Quellen und Artefakte dokumentieren; GitHub-Entwurf mit [skip ci]. Keine Installation vor späterer Fenstertestfreigabe und eigener Mikrofonaktion. Vollständiger Voice-Nachweis bleibt bis zur realen Bedien-/Hörprüfung offen.
