# Mac-Kalender in der nativen App

Ausgangspunkt: `e7033f5`, vorherige Lieferung am Mac `1.0.6-local.af8e791`.
Ziel bleibt ein im Alltag nutzbarer CoS; diese Lieferung schließt den fehlenden nativen Kalenderhelfer.

1. Den vorhandenen authentifizierten Kalendervertrag um eine aktuelle Hintergrundfreigabe ergänzen. Historischer Gedächtnisabgleich darf Pause, Akkusperre oder geänderte Auswahl nicht überholen. Live-Anzeige bleibt eine separate, begrenzte Lesefunktion.
2. Einen vollständig gebündelten Swift-Helfer im App-Prozess betreiben: derselbe Origin 8890, kurzlebige lokale Requests ohne Proxy/Redirect, feste Größen-/Zeitraumgrenzen, keine externe Laufzeit. Nach Ende/Update keine weiteren Aufnahmen.
3. EventKit ausschließlich lesend anbinden. Start fragt keine Berechtigung an. Nur die aktuelle bewusste Verbindungsaktion im Hauptfenster darf einen Systemdialog auslösen; Generation vor dem Dialog prüfen. Ältere Macs bekommen eine klare Nichtverfügbarkeit.
4. Vorhandene Kalenderauswahl und Quellengeneration erhalten; keine Auswahl heißt kein Event-Lesen. Livejahr stückweise, Gedächtnisfenster in begrenzten Abschnitten; vor jedem Abschnitt aktuelle Auswahl/Freigabe prüfen. Keine Kalendernotizen im Live-Snapshot.
5. Echte Verhaltensprüfungen mit synthetischem Reader/Backend, Build und Paketprüfung; unabhängiges Review. Erst danach gesicherten nativen Stand am Mac installieren und Connect/Auswahl/Trennen/Neustart prüfen. Private Kalenderauswahl und Betriebssystemdialog bleiben beim Nutzer.

## Fortschritt

- Ursachenprüfung bestätigt: `finishStart` startet nur PowerReporter; kein Kalenderhelfer im fertigen Bündel. Entwicklungsworker läuft außerhalb des App-Lebenszyklus und hat einen anderen Standardport.
- Entscheidung: Swift im App-Prozess vermeidet zusätzliche Python-Laufzeit, separate TCC-Identität und verwaiste Prozesse. Bestehender Entwicklungsreader bleibt erhalten.
- Grenzen: Bestehende konservative Behandlung leerer historischer Abschnitte bleibt zunächst bestehen; ein leeres Ergebnis gilt nicht automatisch als Löschbeweis. Kein Modell-/Cloudaufruf ist Teil des Kalenderhelfers.
- Implementiert: Swift-Koordinator, begrenzter authentifizierter Loopback-Client, EventKit-Leser im App-Prozess, Lebenszyklus/Update-Stop und Fensterbrücke. Keine Berechtigungsanfrage im Start/Poll; Main-Queue prüft aktuelle Generation nochmals (GET höchstens zwei Sekunden).
- Reviewkorrekturen: fehlgeschlagene Brücke sichtbar; aktive Connect-Anfrage wird nicht vom passiven Poll konsumiert; echte TCC-Sperre entzieht Quellen ohne Originalverlust; technische Transport-/Lesefehler täuschen keine TCC-Sperre vor. Historische Fehler stehen separat zur Live-Anzeige. Teilannahme eines Gedächtnisabschnitts gilt nicht als abgeschlossen.
- Vorläufige Prüfung: 99 betroffene Backendtests bestanden, native synthetische Verhaltensprobe bestanden, früher ARM64-Build bestanden; endgültiger eingefrorener Build und HTTP/Paketprüfungen folgen. Ein paralleler Compilerlauf wurde durch laufende Dateiänderungen ungültig und wird ausschließlich aus dem eingefrorenen Stand wiederholt.
- Noch offen: endgültiges unabhängiges Review, vollständiger nativer Paket-/Lifecycle-Nachweis und gesicherte Mac-Installation mit echter Verbindungs-/Auswahlprüfung. Der Mac arbeitet bis dahin weiter mit af8e791; Hintergrund bleibt pausiert.
