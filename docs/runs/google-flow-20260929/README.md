# Google-Anmeldung: automatische Rückmeldung

Die Callback-Seite bestätigte die Anmeldung, aber die Oberfläche fragte den Status nur nach einem manuellen Klick ab. Das führte zu einer scheinbar stehengebliebenen Einrichtung.

Die Oberfläche prüft nun alle 2,5 Sekunden und bei Fokus/Sichtbarkeit erneut; maximal zehn Minuten pro aktivem Beobachter. Terminale Zustände stoppen die Abfrage. Anfragen überlappen nicht, veraltete Antworten nach Bereinigung bleiben wirkungslos. Konto- und Kalenderbestätigung bleiben ausdrücklich beim Nutzer. Mail und Kalender haben getrennte, ausschließlich aus der Sitzungskennung bestehende sessionStorage-Einträge. Google-Tokens und Autorisierungs-URLs werden dort nicht gespeichert. Bestehende Versuche aus der alten Oberfläche sind nach einem Neuladen nicht rekonstruierbar.

Die Oberfläche benennt die Schritte Anmeldung und Verbindung bestätigen. Erfolgstexte unterscheiden Mail und Kalender. Die Kontenübersicht wird auch aktualisiert, wenn die Verbindung während eines Tabwechsels abgeschlossen wurde.

Validierung: `node --experimental-strip-types --test tests/google-signin-progress.test.mjs` im UI-Verzeichnis: 8/8 bestanden. Produktionsbuild bestanden. Hauptagent hat Code und Tests geprüft. Tests betreffen den Statuscontroller, keine echte Google-Anmeldung oder visuelle Abnahme. Die bestehende Computersteuerungssperre für die lokale Browseroberfläche wurde nicht umgangen.

UI-Revision 5a6f106 wurde nach Sicherung der vorherigen statischen Oberfläche in den bestehenden Pilotcontainer kopiert. Neue Assets zuerst, HTML atomar zuletzt; alte Assets bleiben für offene Fenster erhalten. Container-Startzeit blieb unverändert, kein Backend-Neustart, keine Datenmigration, keine Änderung der Konten oder Freigaben. SHA-256 des ausgelieferten HTML gegen Build verglichen. Das laufende Basisabbild bleibt live-clock-20260929 mit aktualisierter UI; künftige Neuerstellung muss das Abbild google-flow-20260929 verwenden.
