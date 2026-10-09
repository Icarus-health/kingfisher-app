# Getrennter CoS-Prüfstand aus Kalender, RAM-Reserve und Gesundheit

Die vorhandenen Spezifikationen und Abnahmegrenzen von PR #37, #38 und #40 gelten unverändert. Dies ist eine Integration und Paketprüfung, keine neue Produktfunktion. Ausgangspunkt: `63664cde52591d030b1de8d85d61c13edda70b01`; lokale Zusammenführung: `5f5828932c721d06d18137574d092de2f8a40212`.

## Grenzen

- Persönliche App, Dienst, Datenvolume, Einstellungen und Kalenderfreigabe bleiben unangetastet. Der Nutzer hat den Fenstertest verschoben.
- Keine Modelle, Downloads, Cloudanfragen, Wiederaufnahme des Imports oder CI-Wiederholung.
- Nur gepinnte Git-Quellen; ungetrackte Synchronisationskopien bleiben erhalten und gelangen nicht ins Paket.
- Lokales ARM-Paket, kein öffentlicher Release, keine Behauptung über Intel oder Notarisierung.
- Die offenen Drafts bleiben getrennt; `main` und der öffentliche Updater bleiben unverändert.

## Task 1: Gemeinsame Quellen und Regressionen prüfen

Git-Archiv einfrieren; betroffene Gesundheits-/Quellen-, RAM-/Modellrollen-, Kalender-/Vorbereitungs- und Paketvertragstests, vollständige UI-Tests und synthetische Swift-Tests aus genau diesem Archiv ausführen. TypeScript und Vite bauen. Automatisch zusammengeführte Schnittstellen unabhängig lesen lassen. Erwartet: keine neuen Regressionen. Warnungen, übersprungene Prüfungen und tatsächlich ungetestete Flows dokumentieren.

## Task 2: Gepaarte lokale Testpakete bauen

Die native ARM-App aus dem Archiv mit dem vorhandenen produktiven Bauweg erstellen, Signatur und Version prüfen. Backend vom vorhandenen, per Image-ID gepinnten lokalen Abbild ableiten: unveränderte Abhängigkeiten verifizieren, vollständiges Python-Paket und vollständige gebaute UI ersetzen, alte Paket-/UI-Reste entfernen. Kein Basisimage herunterladen.

Erwartet: gleiche Versionskennung in App und Backend; Image-ID, Inhaltsmanifest und native Prüfsummen festhalten. Das Paket in einem namenlosen, kurzlebigen Container ohne Netzwerk, produktives Volume oder Port prüfen. Synthetisch: Authentifizierung, eigene Messung/Korrektur/Verlauf/Entzug, RAM-Ablehnung vor Modellaufruf, vorhandene Kalenderroute, technische `/health` und UI `/wellbeing`. Keine reale Kalenderleseprüfung.

## Task 3: Ergebnis und nächste Mac-Abnahme festhalten

Paketstand, Eingangs-PRs, reproduzierbare Befehle, Testergebnisse, Prüfsummen und offene native/persönliche Abnahme dokumentieren. Nur die eigene Integrationsbranch mit `[skip ci]` sichern, ohne die Drafts oder `main` zu mergen und ohne Abonnement anzulegen.

## Review-Fokus

Registrierung und Authentifizierung der zusammengeführten Routen; Setup-Umgebungspriorität; Kalenderentzug und Quellenfassungen neben Gesundheitskorrekturen; Paketversion und keine veralteten UI-/Python-Dateien. Reale Modellqualität, RSS und Kalenderfreigabe bleiben gesonderte Abnahmen.
