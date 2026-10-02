# Ausgewählte Textdateien aufnehmen

Der Browser liest nur die ausdrücklich ausgewählte UTF-8-Textdatei. Vorschau und optionale Projektzuordnung erfolgen vor dem ausdrücklichen Aufnahmebefehl. Unterstützt: Markdown, TXT, Org, RST und CSV bis 512 KiB. PDF, Word und fortlaufende Ordnersynchronisation sind damit noch nicht abgedeckt.

Der Server prüft Dateiname, Endung, Textgröße, Inhalt und Projekt. Dokumentinhalt wird als fremde Dokumentquelle aufgenommen, nicht als Nutzerwahrheit oder bestätigtes Wissen. Digest-Dubletten behalten ursprüngliche Herkunft und Projektzuordnung. Die Rückmeldung nennt diesen Unterschied ausdrücklich. Originaldateien werden weder geändert noch gelöscht.

Browserprüfung auf isoliertem Port 8892 mit synthetischem Markdown: keine Übertragung bei Auswahl/Vorschau, ausdrückliche Aufnahme, inerte HTML-Darstellung, anschließender Quellenleser, Wiederholung ohne Dublette und Sichtbarkeit in der Projektakte. Die neue UI verwendet vorhandene Formular-/Quellenkomponenten; vollständige kanonische Abnahme bleibt offen.

Ergebnis: Browserablauf bestanden, zwölf gezielte Backend-Tests bestanden, TypeScript/Vite-Build und Assetmanifest bestanden. Die erste visuelle Prüfung führte zu angepassten Innenabständen und Überschriftengröße im Dateibereich.

## Dauerhafte Dateiliste und Ausschluss

Importierte Dokumente werden aus der bestehenden Episodenablage in Seiten zu 50 Einträgen angezeigt, auch ohne Projekt. Der Dateikörper wird erst beim Öffnen geladen. Die Liste zeigt Zeitpunkt, Projektlink und Ausschlussstatus; sie ist nach Reload weiter verfügbar.

Quellenausschluss markiert direkt belegte aktive Wissensaussagen und ihre aktiven Abhängigkeiten atomar als fraglich. Revision und Verlauf ändern sich gemeinsam. Die Quelle bleibt lesbar, wird aber nicht weiter für neue Wissensannahmen verwendet. API-Annahme und Ausschluss teilen die Gesprächssperre. Ausgeschlossene Quellen bleiben auch bei der Archivierung ausgeschlossen.

Browserprüfung: gespeicherte Quelle nach Reload öffnen, Ausschluss abbrechen, dann bestätigen; bestätigtes Wissen verschwindet aus dem aktuellen Profil und bleibt fraglich im Verlauf. Ausschlussstatus bleibt nach Reload sichtbar. Getrennte Testdaten, keine Benutzerquelle ausgeschlossen. Paginationvertrag mit 52 Dateien und fremder Episode geprüft.

Der Dateilisten-/Ausschlussablauf wurde auch im gebauten Docker-Image geprüft. Die Gesprächssperre serialisiert innerhalb des ausgelieferten einzelnen App-Prozesses; sie stellt keine prozessübergreifende Transaktion zwischen Episoden- und Wissensdatenbank dar. Bei einem Fehler nach der Wissenssperre bleibt Wissen vorsorglich fraglich.

Gesamtprüfung dieses Stands: 842 Backend-Tests bestanden (eine bestehende Starlette-Warnung), 131,29 Sekunden; Docker-Browserablauf bestanden. Nach lokaler Installation Health und echter Mac-Kalender-Browserlauf bestanden.
