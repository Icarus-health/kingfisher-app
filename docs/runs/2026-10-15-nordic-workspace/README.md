# Variante 3: gemeinsame helle Arbeitsflächen

Der gewählte Bildentwurf ist auf die vorhandene Kingfisher-Anwendung übertragen. Dunkle Navigation, ruhiger Landschaftskopf, weiße Leseflächen und klarere Schrift gelten für Gedächtnis, Aufgaben/Projekte, Gespräche, Nachrichten, Kalender, Heute, Personenprofile und Einstellungen. Dokumente haben Ordner, eine kompakte Liste und genau einen Original-Lesebereich.

Die Prüfung verwendet einen getrennten synthetischen Bestand auf Port 8893 mit deterministischen Providern. Keine persönlichen Mailquellen oder Cloudverarbeitung; keine Fortsetzung des pausierten Großimports. Dateien mit PDF-Namen enthalten in diesem Bestand synthetischen extrahierten Text und behaupten keine echte PDF-Darstellung.

## Nachweise

- [Gestaltungskontrolle mit vollständigen Bedienwegen und Grenzen](../../../design-qa.md).
- [Dokumentarbeitsplatz](01-dokumente.png), [Aufgaben](02-aufgaben.png), [Einstellungen](03-einstellungen.png), [Personenprofil](04-personenprofil.png).
- [Originalansicht bei 390 px](05-dokument-390.jpg), [Mail bei 1280 × 360](06-mail-kurzes-fenster.jpg).
- [Gewählter Entwurf](00-vorlage-variante-3.png), [Gesamtvergleich](07-vergleich.jpg), [Detailvergleich](08-vergleich-detail.jpg).

## Automatisierte Prüfung

Ausgangspunkt 2805ee8: 701 UI-Tests bestanden. Abschließend 710/710 bestanden; `npm test`, `npm run build`, `python3 scripts/check_asset_manifest.py` und `git diff --check`. Der bestehende Hinweis auf einen großen Vite-Bundle bleibt; keine zusätzliche Abhängigkeit installiert. Backend unverändert, daher kein vollständiger Backend-Wiederholungslauf.

Neue Dokumentregressionen decken Auswahl/Rückweg, aktuelle Suchergebnisse, Quellenentzug, eingebettete reine Originalansicht, begrenzten History-Zustand und Ordnerpfad ab. Das unabhängige Review identifizierte zusätzlich zwei P2: ungebundene automatische Erstquelle und verlorene Importvorschau bei Tabwechsel. Die entsprechenden neuen Regressionen scheiterten vor der Korrektur und bestanden danach. Eine dritte Prüfung sichert den beabsichtigten Wechsel der Quelle beim Seitenwechsel.

Im Browser wurde eine künstliche Textdatei mit Projekt vorbereitet, über zwei Gedächtnis-Tabs hinweg erhalten, nach Schließwarnung weiterbearbeitet, ausdrücklich aufgenommen und mit gleicher Projektbindung wiedergefunden. Eine Aufgabennotiz wurde gespeichert; Chatentwürfe, Mail-Rückweg, Kalenderansicht und Profil-Rückwege wurden bedient. Keine Konto-, Cloud- oder Modellkonfiguration geändert.

## Status

Lokal implementiert und im Browser geprüft. Diese Nachweise behaupten weder Merge noch persönliche Mac-Installation noch Abnahme mit realen Konten. Normale Veröffentlichung und Datenprüfung vor einem persönlichen Update bleiben getrennte Schritte.
