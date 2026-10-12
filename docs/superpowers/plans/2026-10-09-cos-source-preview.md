# Gemeinsame CoS-Vorschau mit Quellen- und Fortschrittsanzeige

Die vollständige Produktvision und offenen Abnahmen in `docs/63-cos-produktabschluss.md` und `docs/64-cos-abnahme-status-2026-10-09.md` bleiben erhalten. Vorheriger geprüfter Vorschaucode: `5f5828932c721d06d18137574d092de2f8a40212`. Zwei bestehende, geprüfte Entwürfe integrieren: PR #41 `e6cb3f1b71b2073e04577837d1cb87b0025d8521`, PR #42 `eba7cccd3abe90b015799cc07588a511d500fb10`. Es wird keine neue Funktion entworfen.

## Grenzen

Fenstertest auf Nutzerwunsch verschoben. Keine native Bedienung, Kalenderfreigabe, Installation, produktive Datenanbindung, Modell-/Cloudanfrage, Abhängigkeitsdownload oder Importwiederaufnahme. main, offene Drafts und öffentlicher Updater bleiben unverändert. Nur eigene Integrationsbranch sichern. [skip ci] in allen Commits. Vorheriges Paket behalten.

## Task 1: Gemeinsame Schnittstellen und Quellstand prüfen

Auf vorhandener Integrationsbranch beide gepinnten Heads zusammenführen, automatisch aufgelöste api.ts/MemoryStatus.tsx überprüfen. Sauberes Git-Archiv einfrieren. Betroffene Backendtests für Fortschritt/Frische, Quellenstatus, Auth, Mail, Ordner, Kalender, Gesundheit, Pausen/Energie und RAM-Reserve ausführen; vollständige UI-Suite und TypeScript/Vite. Unabhängige statische Prüfung des gemeinsamen Verhaltens. Erwartet: keine verbleibenden Regressionen oder wichtigen Integrationsblocker. Keine neuen Produktionsänderungen ohne vorher scheiternden Regressionstest.

## Task 2: Gemeinsames lokales Updatepaket prüfen und sichern

ARM-App mit vorhandener Baukette und neuer Vorschauversion bauen. Backend gegen gepinnte bereits vorhandene lokale Basis-ID ohne Netzwerk/Pull erzeugen, gesamte Python/UI-Paketinhalte ersetzen und Versionspaarung prüfen. Bestehendes synthetisches Paketprüfskript um die zusammengeführten Statusrouten ergänzen. In kurzlebigem Container ohne Netzwerk, Ports, Host-/Produktivvolume prüfen: Auth, Originalerhalt, Gesundheitskorrektur/Entzug, künstliche Kalenderauswahl, RAM-Ablehnung vor Modell-I/O, Live-Pause im Gedächtnisstatus, kompakte Ordnerreferenzen und Metadaten-Endpunkte. Inhaltsmanifeste/Version/Base-Schichten/Signatur/DMG prüfen. Pakete und Logs dauerhaft ablegen, Prüfnachweise und offene Mac-Abnahmen dokumentieren. Erwartet: paketierter Stand entspricht exakt dem geprüften Code; keine Behauptung über persönliche Qualität, Ressourcenverbrauch oder echten Kalenderfluss.

## Review-Fokus

Automatische api.ts/MemoryStatus.tsx-Zusammenführung, optionale AbortSignal-Parameter, gemeinsame Authentifizierung und kompakte Queryantworten; widersprüchliche Pause-/Freshnessanzeige, parallele oder verborgene Statusarbeit, Paketinhalt/-Version. Risiken realer Modelle, RSS/Akku und privater Kalender bleiben ausdrücklich ungemessen.
