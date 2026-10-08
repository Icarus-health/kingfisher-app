# Quellenänderungen öffnen den Fortschritt erneut

## Problem und Änderung

Eine über die normale API ergänzte Person verändert Generation und Fingerabdruck einer bereits eingeordneten Quelle. `source_state()` und die begrenzte Quellenprüfung erkannten danach offene Arbeit, während `progress()` weiterhin „erledigt“ zählte und die semantische Abdeckung keine offene Quelle meldete. Die semantische Indexansicht konnte sogar eine alte Einordnung erneut einbetten; die spätere Fingerabdruckprüfung verhinderte zwar deren Ausgabe, aber Fortschritt und Arbeitsplanung waren falsch.

Fortschritt, semantische Quellenlücke und Indexansicht verwenden jetzt denselben vorhandenen Generation-/Statusmarker. Fehlende oder veraltete Marker öffnen die Arbeit; solche Einordnungen werden nicht erneut eingebettet. Originale, bestehende Vektoren und Referenzen bleiben gespeichert. Unveränderte alte Marker werden nur nach tatsächlicher Fingerabdruckprüfung im bestehenden begrenzten Quellenscan ergänzt, ohne erneute Klassifizierung oder Einbettung. Expliziter Ausschluss bleibt bestehen; bei übergroßen Quellen kann die erneut geprüfte Größengrenze den deterministischen Zurückstellungsstatus erneuern. Keine Schemaänderung.

Der Fortschritt schließt Gesprächs-Nachschlagequellen außerdem nur anhand des wirklichen Tags aus. Die bloße Erwähnung dieses technischen Kennzeichens im Originaltext versteckt keine normale Quelle mehr.

## Nachweis

12 neue Regressionen; die ersten acht zeigten vorher sieben Fehler, zwei weitere Fehler wurden vor ihren jeweiligen Korrekturen einzeln reproduziert. 170 betroffene Tests bestanden (eine bestehende Starlette/httpx-Warnung). Abgedeckt: Metadatenänderung, fehlender Altmarker, unveränderte Vektorreparatur, veränderter Fingerabdruck, 503 Quellen bei Scanbudget 500, Ausschluss und Mailzähler, Größenbegrenzung, Originaltext mit Tagbegriff, erneute Einordnung und Quellenentzug. Ein unabhängiger günstiger Reviewer fand keine konkrete Regression; sein eigener synthetischer Check bestätigt Wiederverwendung vorhandener Vektoren ohne Embedder-Aufruf.

Der netzlose Smoke im fertigen Image prüft mit künstlichen Quellen den Ablauf Einordnung → Index → verlorener Altmarker → Prüfung → Vektorwiederverwendung → Metadatenänderung → offene Arbeit → neue Einordnung → Entzug. Kein Modellaufruf, 128MB Speicherlimit. 264 Paketdateien und 112 unveränderte UI-Dateien byteweise geprüft.

## Grenzen und wirklicher Quellenbestand

Der Marker ist ein struktureller Frischenachweis, kein Ersatz für die volle Fingerabdruck- und Sichtbarkeitsprüfung vor Ausgabe. Direkte Datenbankmanipulationen außerhalb der generationserhöhenden Quellen-APIs sind damit nicht allgemein erkennbar. Fehlende Altmarker werden bei pausierter oder ausgeschalteter Modellautomatik **nicht eigenständig** repariert: Sie bleiben vorsichtig offen bis zum nächsten autorisierten begrenzten `pending()`-Scan. Statusabfragen starten weder Scans noch Modelle. Keine zusätzliche Hintergrundautomatik und keine aufgehobene Importpause.

Die lokalen Zähler bleiben vor/nach dem Update gleich: 333 erfasste Rohquellen, Fortschritt 329/324 erledigt/4 zurückgestellt/1 Wiederholungsfall. Dieser Bestand hatte keinen mit der Änderung neu geöffneten Markerfall; der Fehlernachweis ist synthetisch. Der verbundene Postfachverlauf umfasst 122.399 inventarisierte Einträge, aber erst 304 aufgenommene Mails; 120.805 warten auf Abruf und sieben sind fehlgeschlagen. Inventarisierte Postfachnachrichten sind noch keine durchsuchbaren Originalquellen. Keine Qualitätsaussage über alle Mails und keine Vollständigkeitsbehauptung.

## GitHub und Mac

Produktcommit `46aeef58ff31b4c2210da277839d096bc22d07e0`, lokal **1.0.6-local.46aeef5**. Image `sha256:447f1e5bab161259930e91c54b77c331877f630e0318d5bc4a22dc9347bec92b`. Kalte Sicherung `Kingfisher-Rueckweg/2026-10-08-vor-46aeef5`; 344 Original-IDs/Inhaltsdigests und 17 SQLite-Dateien erhalten/geprüft, gleiches Datenvolume. Konten, Kalender, Anbieter, Modellrollen und Zeitpläne erhalten. Native Binärdatei unverändert, Signatur geprüft, Backend gesund. Importpause bleibt bestehen, Ollama aus und Bedeutungssuche deshalb `unavailable`.

Keine öffentliche Veröffentlichung, Cloudinferenz, Modellinstallation, CI-Wiederholung, Abonnements oder Check-ins. Native Bedien-/Tages-/Akkuabnahme weiterhin offen (zuletzt gesperrter Mac); insgesamt noch kein abgenommener CoS.
