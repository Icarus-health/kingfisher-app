# Aufgabenbedienung – 7. September 2026

Erledigte Aufgaben lassen sich wieder öffnen. Offene Aufgaben können lokal
mit einer wartenden Person versehen und wieder zurückgeholt werden.
Keine Nachrichten oder externen Delegationen. Fälligkeit aus dem Datumsfeld
wird mit lokaler Zeitzone nach UTC serialisiert. Verspätete Listenantworten
überschreiben keine neuere Aufgabenansicht mehr.

Read-only Prüfung durch Luna-Subagent fand die fehlenden Warteaktionen;
Implementierung und Abnahme durch Hauptagent. Kein gemessener Kostenvergleich.

20 gezielte Kingfisher-Backendtests, UI-Build und Asset-Vertrag bestanden.
Separater Container mit flüchtigem Datenverzeichnis auf Port 8892:
Browserablauf Anlegen → Erledigen → Wiederöffnen → Warten → Zurückholen →
Neuladen erfolgreich. Screenshot visuell geprüft. Testcontainer anschließend
entfernt, Nutzerdaten nicht verändert. Neues Image auf Port 8891 gestartet.
