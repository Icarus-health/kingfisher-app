# Folgeauftrag: Mac-Kalenderhelfer in der nativen App

Read-only Ursachenprüfung am 9. Oktober, Code `408df41695cb6a6c49fe5d3366d581c60f9bcfaf`; kein persönlicher Kalenderzugriff, kein neuer Build und keine Betriebssystemfreigabe durchgeführt.

## Nachgewiesene Lücke

`macos/App/AppDelegate.swift::finishStart(.ready)` startet nur `PowerReporter` und lädt die Oberfläche. `macos/build_dmg.sh` bündelt Compose und die Speicherprüfung, aber weder `CalendarReader` noch dessen Arbeiter/Laufzeit. Der separate Entwicklungsstarter `scripts/start_mac_app.py` startet die Arbeiter; sein Standardport 8891 passt außerdem nicht zum nativen App-Origin/Compose-Port 8890. Der Backend-Status braucht einen frischen Arbeiterkontakt und ist darum im nativen Paket offline.

## Begrenzte Umsetzung

- Einen expliziten Lifecycle-Besitzer in der nativen App ergänzen, der den Kalenderhelfer startet/beendet und an den einen geprüften App-Origin bindet. Keine neuen offenen Netzwerkports, kein dauerhaftes Startskript außerhalb des App-Lebenszyklus und kein stiller Netzwerk- oder Modellwechsel.
- Reader und notwendige Laufzeit verlässlich bündeln; kein vom Nutzer zu startender Entwicklungsprozess, keine spontane Laufzeitinstallation. Eine Swift-Lösung oder ein vollständig gebündelter Worker ist anhand der kleineren sicheren Wartungsfläche zu wählen. System-Python ist ohne Nachweis keine Produktvoraussetzung. Reader verlangt macOS 14+, Hülle unterstützt derzeit 11.3: ältere Systeme müssen den optionalen Helfer klar als nicht verfügbar behandeln.
- Kalenderfreigabe nur aus einer bewussten aktuellen Verbindungsaktion. Eine nach Neustart übriggebliebene Autorisierungsanforderung darf nicht ungefragt einen Systemdialog auslösen. Nach Freigabe Auswahl einzelner Kalender; leere Auswahl liest keinen Termin. Keine Aufweitung auf alle Kalender, Konten oder Quellen.
- Generations-/Auswahlprüfung und Quellenentzug im vorhandenen Backend erhalten. Helferfehler melden sich sichtbar; veraltete Termine sind nicht aktuell. Hintergrundaufnahme respektiert Pause und Leistungsbudget; der Helfer startet keine Modellverarbeitung. Fremde Inhalte sind Quelle, kein bestätigter Fakt.
- Native Signatur und sichere Bündelpfade, verständliche Bedienung ohne Zusatzschritte und Beenden/Neustart ohne verwaiste Helfer prüfen.

## Nachweise

Vor neuen Implementierungen die vorhandenen Tests für Mac-Kalender, App-Start, EventKit-Reader und Host-Power ergänzen. Paketinhalt und Lifecycle synthetisch prüfen: kein Berechtigungsdialog beim Start, kein Lesen ohne Auswahl, aktueller Origin, Generation/Disconnect, Abbruch/Fehler, Pause/Akku und keine hinterbliebenen Prozesse. Danach echter signierter Build und freigegebener Mac-Fensterablauf. Ein Code- oder Pakettest ersetzt nicht die reale EventKit-Freigabe- und Auswahlprüfung.

Die in dieser Lieferung erhaltene native Hülle ist nicht verändert; dieser Folgeauftrag ist noch nicht umgesetzt.
