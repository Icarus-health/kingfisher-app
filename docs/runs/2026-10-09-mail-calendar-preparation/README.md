# Mail → geprüfter Terminentwurf

Produkt-/Teststand `d431383b551c6a65254c93331819998f86a685eb`, Basis `9944ab3`. Draft PR32. Paketversion `1.0.6-local.d431383`; endgültiges Kompaktimage `sha256:930ef4d708d93668dcb79a54cbaac678444283e769addac1b9c3914fd511b858`.

## Verhalten

Die geöffnete Mail bietet eine lokale, dauerhaft gespeicherte Terminvorbereitung im vorhandenen Kalenderjournal. Titel, Beginn und Ende zeigen ihre Herkunft; unvollständige eigene Eingaben lassen sich speichern. Wiederöffnen derselben Quelle erhält den Entwurf. Zur Google-Vorschau sind vollständige, ausdrücklich geprüfte Angaben erforderlich. Verbindliches Schreiben bleibt eine gesonderte sichtbare Bestätigung.

Die Quellenbindung umfasst Volltext, relevante Konten-/Nachrichtenmetadaten, bekannten kontogebundenen Verlauf und Supportgeneration. Quellenänderung, Entzug, Ignore→Reopen und neue bekannte Antworten entwerten den alten Prüfstand. Jede öffentliche Ergebnisanzeige prüft erneut, auch bei schon ausgeführter Aktion oder einer Änderung während des Providerabrufs. Der Journalstatus done/uncertain bleibt beim Anzeigeverbot erhalten.

Zeitvorschläge sind unbestätigt und bewusst strikt: vollständige ISO-Intervalle oder unterstützte deutsche Vollangaben mit Jahr, Start, Ende und expliziter Zeitzone. Fehlende Angaben werden nicht erfunden. Absage im Betreff, Alternativen, gekürzte Quellen und andere vollständige Zeiten im bekannten Verlauf verhindern automatische Auswahl. Fehlende spätere Nachrichten außerhalb des gespeicherten Verlaufs können nicht ausgeschlossen werden. Keine Gäste werden aus Namen geraten.

Eine stabile Providerkennung schützt dieselbe Vorbereitung vor doppelter Kalenderanlage nach Neustart oder verlorener Antwort. Eine erneuerte Kalenderfreigabe erlaubt eine neue Prüfung eines sicher noch nicht geschriebenen Entwurfs; alte Bestätigungen werden ungültig. Ein unklarer oder bereits erfolgter Effekt wird dadurch nicht neu angelegt. Kalender-/Benachrichtigungswechsel verwirft die alte UI-Vorschau unmittelbar.

## Prüfungen

68 gezielte Backendtests und26 Subtests; unabhängiges Review mit eigenen HTTP-/Neustart-/Freigabe-/Entzugsproben. Rote Reproduktionen sind separat erhalten; sie sind keine Abnahme-Greens.416 UI-Tests und Produktionsbuild bestanden. Die UI-Handlerprüfung kompiliert tatsächliches TSX und führt Handler mit isoliertem Hookzustand aus; sie ersetzt keine native Bedienung.

Das endgültige Image besteht den exakten Satz von266 Python- und112 UI-Dateien sowie sechs künstliche API-Szenarien in netzlosen Containern ohne persönliche Volumes, Modelle oder App-Lifespan. Paketgrenzen und unabhängiger Installerreview sind separat dokumentiert. Die Verkleinerung kopiert nur geänderten JS-Code und index.html, keine unveränderten Bilder/Schriften. Der verworfene erste Build wurde als eigener unbenutzter Testbestand gezielt entfernt; kein globales Docker-Prune.

Breite lokale Regression: 6.398 bestanden,3 übersprungen,58 Subtests bestanden in875,85 Sekunden; zwei bestehende Warnungen. Mac-Installation erfolgreich: Backend `1.0.6-local.d431383`, Schema20 ohne Migration. Eine separate lesende Frischprüfung bestätigt266 Python-/112 UI-Dateien,344 unveränderte Originalkörper samt Dokumenten,17 Datenbanken, Einstellungen, Zugänge, Pause, Volume und native signierte Programmdateien. Beide Speicherreservephasen bestehen. Quelleaufnahme bleibt pausiert, Ollama aus. Dieser Zwischenstand ist keine Fertigmeldung für den gesamten CoS. Native Fenster-/Alltags-/Akkuabnahme, echte Gedächtnis-Gesamtqualität und große Quellenabdeckung bleiben offen. Keine Cloudkosten/private Testuploads/Modellbeschaffung ausgelöst. GitHub-CI bleibt übersprungen.

## Sicherung und echte Installation

Vor jeder Datenbanköffnung wurde die vollständige kalte Datenkopie einschließlich WAL/SHM byteweise geprüft. Privater Rückweg: `Kingfisher-Rueckweg/2026-10-09-vor-d431383-schema20`. Keine vollständige Datenkopie, Zugangsdaten oder privaten Originale sind Teil dieses Liefernachweises.

Zuvor wurde genau ein älteres Docker-Sicherungsduplikat nach Abgleich mit zwei erhaltenen Hostkopien ausgelagert;51.701.790Bytes freigegeben. Der gesamte übrige Dateibaum blieb bytegleich. Der erste Versuch hielt wegen einer fehlenden Prüfmodul-Abhängigkeit **vor** der Entfernung an; nach vollständigem Abgleich wurde derselbe alte Stand sicher wieder gestartet. Die Abhängigkeit wurde per roter Gegenprobe korrigiert, unabhängig nachgeprüft und erst der separate V2-Lauf ausgeführt. Erst danach erfolgte das neue Produktupdate. Alle Stopp-/Wiederanlauf-/Archiv-/Installationsnachweise bleiben getrennt. Keine globale Bereinigung und keine Großimport-Kapazitätsabnahme.

Die hier beigelegten Installer sind einmalige, versionsgebundene Ausführungsnachweise, keine allgemeine Nutzer-Updateanleitung. Nicht erneut ausführen. `native_ui_verified:false` gilt ausdrücklich weiter.
