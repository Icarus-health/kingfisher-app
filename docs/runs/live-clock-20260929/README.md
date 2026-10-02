# Laufende Uhr auf allen Seiten

Die Heute-Uhr verwendete `briefing.generated_at` und blieb deshalb beim Briefing-Zeitpunkt stehen. Die gemeinsame Navigation hat jetzt eine eigene laufende Uhr (Datum und Sekunden); die Heute-Anzeige nutzt dieselbe Komponente ohne Sekunden. Der historische Zeitstempel im Briefing bleibt erhalten. Gerätezeitzone, sekündliche Aktualisierung, sofortiger Abgleich bei Fokus/Sichtbarkeit und Listener-Cleanup.

Prüfung: Frontend-Build und Docker-Build bestanden. Separater kompilierter Komponenten-Harness prüfte Berlin-Zeit, Mitternachtswechsel, Fokus/Sichtbarkeit, Formatierung und Cleanup. Codeprüfung durch Hauptagent. Keine Änderung am Backend; keine unnötige Wiederholung der vollständigen Backend-Suite.

Revision 2070565 als `kingfisher:live-clock-20260929` auf bestehendes Pilot-Volume ausgerollt, vorher Snapshot erstellt. Quellen-/Aufgaben-IDs, Integrationen und aktive Einordnung unverändert erhalten. Vorheriger Container bleibt gestoppt als Rückfalloption; niemals beide Container gleichzeitig auf dasselbe Volume starten.

Offen: tatsächliche visuelle Abnahme der neuen Uhr. Native App war lesbar, aber Interaktionen liefen in Timeout; Browserzugriff auf 8892 anschließend ausdrücklich durch gespeicherte Nutzerfreigabe verweigert. Kein Umgehen dieser Sperre. Nach manuellem Neuladen/Neustart sollte die neue Oberfläche geladen werden; dieser letzte Schritt wurde nicht als verifiziert gewertet.

Separat: Google-Projekt Kingfisher Local angelegt und OAuth-Branding vorbereitet. Richtlinienzustimmung steht aus. Keine OAuth-Anmeldedaten erstellt, keine Nutzerkonten verbunden, kein Zugriff auf persönliche Mails/Kalender freigegeben.
