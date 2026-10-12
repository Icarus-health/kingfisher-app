# Statische Integrationsprüfung

Prüfer: bestehender lesender Agent `review_snapshot_relocation`, gegen `5f58289..26e2bda`. Keine Tests oder Laufzeit-/Datenzugriffe durch den Prüfer. Fokus: automatisch zusammengeführte api.ts/MemoryStatus.tsx, optionale Statusfelder, Sichtbarkeit und Authentifizierung.

Ein wichtiger Befund: Der Coverage-Poller prüfte Sichtbarkeit nur vor dem GET. Eine verspätete Antwort konnte während verborgener Ansicht weiterhin Zahlen und Automatikstatus ersetzen; bei schneller Rückkehr blieb der überholte Stand bis zum nächsten Poll sichtbar. Die neue Quellenübersicht verhinderte das bereits.

Sonst keine konkreten Blocker bei Authentifizierung, Query-Kompatibilität oder doppelten Quellenabrufen gemeldet. Das ist eine statische Aussage, keine Bedienfreigabe.

Korrektur im Integrationscode `173cef8`: Generation beim Sichtbarkeitswechsel und Verlassen der Ansicht ändern, laufenden Poll abbrechen, Antworten nur innerhalb der ursprünglichen sichtbaren Generation übernehmen. Nach Rückkehr unmittelbar frisch laden und überlappende Polls vermeiden. Derselbe Generationstest schützt Nachlese nach erfolgreichem oder unbestätigtem Umschalten der Automatik.

Nachweis: drei Pollfälle und zwei Automatik-Nachlesefälle reproduzieren den Fehler vor ihrer Korrektur. Sie bestehen danach; ein weiterer funktionaler Fall prüft Intervall, Erhalt der Timeline, Listener-/Timercleanup, Abbruch und ignorierte Antwort nach Unmount. Ein bisheriger Quelltext-Regextest verlangte wörtlich `if(active)`; die ersetzende Prüfung bedient die echten Effekte statt den Ausdruck festzuschreiben. Finale UI-Suite: 485 bestanden. Keine zweite unabhängige Laufzeitprüfung oder native Fensterprüfung behauptet.
