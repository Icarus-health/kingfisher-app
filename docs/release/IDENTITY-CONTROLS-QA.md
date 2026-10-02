# Identitätsklärung – 7. September 2026

Explizite Registry-Profile zeigen ihre Quellenkennungen und gleichnamige Identitäten derselben Art. Namen lassen sich ändern; die stabile ID bleibt erhalten. Quellenkennungen werden erst nach ausdrücklicher Bestätigung gelöst. Bestehende Aussagen werden dadurch nicht widerrufen; der Dialog weist darauf hin.

Geprüft: TypeScript/Vite-Build, Docker-Build, Assetmanifest. Isolierter Playwright-Browserlauf mit zwei synthetischen Personen: Vergleichslink, Umbenennen und Neuladen, Abbruch und Bestätigung einer Quellenlösung, unveränderte zweite Identität, keine Browserfehler. Screenshot visuell geprüft. Keine Testdaten im Benutzerbestand.

Backend-Vertragstest umfasst Quellentrennung nach Konto, falsche Identität (409), unveränderte Claim-Referenzen und Persistenz nach erneutem Öffnen der Datenbank.

Offen: zeitliche und kontextuelle Beziehungskorrekturen sowie vollständige visuelle Produktabnahme. Die Roadmap bleibt bei 5 von 20 vollständig erfüllten Kriterien.

## Aussagen widerrufen

Registry-Profile bieten jetzt einen ausdrücklichen Widerruf mit Pflichtbegründung. Belege, Gültigkeitsintervall und Kontext sind aufklappbar. Nicht aktuell nutzbare Aussagen heißen „Weitere und frühere Aussagen“, da die Liste auch zukünftige Gültigkeitszeiträume umfasst. Widerrufene Aussagen bleiben mit Status sichtbar.

18 bestehende Backend-Tests bestanden, darunter Ausschluss widerrufenen Wissens aus dem Modellkontext. Isolierter Browserlauf prüft Belegdetails, Pflichtbegründung, Abbruch, bestätigten Widerruf, Neuladen und erhaltenen Verlauf. TypeScript-/Vite-Build und Assetmanifest bestanden. Kein Benutzerwissen wurde für diesen Test geändert.

Das Bearbeiten und Ersetzen von Beziehungen samt Zeitraum und Kontext ist weiterhin offen; dieser Schritt ergänzt deren nachvollziehbaren Widerruf.

## Beziehungen ausdrücklich ersetzen

Neue Korrektur im Registry-Profil: Wert, Aussage, Bezugsidentität, Kontext und Gültigkeitsintervall bearbeiten, mit Begründung prüfen und anschließend bestätigen. Die Prüfung schreibt noch nichts. Die bestätigte Korrektur erzeugt eine neue strukturierte Nutzerquelle; Originalbelege bleiben beim alten Stand. Subjekt und Beziehungsart bleiben erhalten.

Die Claim-Transaktion ersetzt ausschließlich die gewählte aktive Aussage und entwertet abhängige Aussagen. Ein Konflikt mit weiterem Wissen liefert 409 ohne stilles Überschreiben. Die normale Kandidatenannahme erlaubt weiterhin keinen Kontextwechsel. Episoden- und Vorschlagsaudit liegen in separaten Datenbanken; fehlgeschlagene Konfliktversuche können dort als abgelehnte Korrekturen erhalten bleiben.

Browser plugin not available: regulärer Playwright-Test auf isoliertem Port 8892 mit synthetischen Daten. Geprüft: ungültiges Intervall blockiert, Prüfseite ohne Schreibwirkung, explizite Bestätigung, geänderter Bezug/Kontext/Zeitraum, lokaler Zeitpunkt korrekt gespeichert, neuer Stand und ersetzter Verlauf nach Reload. Screenshot der Prüfseite visuell geprüft. Die vollständige Abnahme am kanonischen Design bleibt separat offen.

Abschließende Prüfung: gesamte Backend-Suite 822 bestanden (eine bestehende Starlette-Warnung), 129,51 Sekunden. Korrekturablauf zusätzlich im gebauten Docker-Image bestanden. Lokale Installation auf Port 8891 mit unverändertem Datenvolume; Health und echter Mac-Kalender-Browserlauf nach Neustart bestanden.

Belegbedienung: Registry-Aussagen sowie aktuelle/frühere Aussagen in abgeleiteten Profilen verwenden einen gemeinsamen Belegleser. Zitate führen über „Originalquelle öffnen“ zur gespeicherten Episode statt nur eine interne ID anzuzeigen. Isolierter Browserlauf: Quellenfehler simuliert, Wiederholung liest die echte Testepisode, Schließen funktioniert; keine Browserfehler. Screenshot visuell geprüft, Build/Assetmanifest bestanden.
