# Icon-Prüfung ohne Verwechslung mit Statuslisten

Unverändertes main `3667e4e18b9e255780c755889370b46368cf0a6d` scheiterte an `expired`: Die Grafikprüfung behandelte jedes Textpaar wie eine Navigationszeile. Damit wurden legitime Statuslisten aus ChatGPTAccess als nicht erlaubte Icons bewertet.

Die Prüfung sammelt jetzt ausdrückliche `icon(...)`-Textargumente und genau eine geschlossene `export const NAV = [...] as const`-Liste in `ui.ts`. Ein unbekanntes Icon, eine fehlende Variante und eine nicht prüfbare NAV-Liste bleiben Fehler. Einfache Anführungszeichen und Zeilenwechsel bei direkten Icon-Aufrufen sind mit erfasst. Grafikdateien, Manifest, Oberfläche und Laufzeitverhalten sind unverändert.

## Nachweis

- Ursprünglicher Prüfer: vier relevante Fehler bei sieben bestandenen Fällen.
- Zusätzliche Kommentar-/Textbeispiele fanden zwei Fehler in der ersten Korrektur; die Deklarationssuche wurde daraufhin zeilenverankert.
- Abschließende betroffene Tests: **13 bestanden**. Echte Grafikprüfung: **pass, 16 Dateiverweise, 15 Icons**.
- Abgeschaltete Referenzsammlung in einem getrennten Archiv: **7 gezielte Tests schlagen fehl**, 6 bestehen. Arbeitskopie wurde dafür nicht geändert.
- Enges unabhängiges Read-only-Review: kein aktueller Fehler gefunden; statische Grenzen ausdrücklich benannt.

## Grenzen

Das Werkzeug ist ein begrenzter statischer Vertragsprüfer, kein JavaScript-Parser. Dynamische `icon(iconName)`-Werte werden nicht allgemein aufgelöst. Der bestehende SourceRow-Vertrag erlaubt nur `mail`/`calendar-days`, die bereits über NAV geprüft werden. Änderungen an dynamischen Wertemengen brauchen eine explizite Prüfung. Deklarationsbeispiele in mehrzeiligen Blockkommentaren können konservativ eine zusätzliche NAV-Deklaration ergeben und den Lauf ablehnen. Direkte Icon-Aufrufe in Kommentaren/Text werden wie bisher konservativ mit erfasst.

Keine Modelle, persönlichen Daten oder native Fenster verwendet. Diese Werkzeugkorrektur ersetzt keine visuelle Abnahme. Der gewünschte Fenstertest bleibt verschoben. Rohprotokolle sind komprimiert beigefügt; kein GitHub-CI-Lauf oder Neustart angefordert.
