# Elternbasis: tatsächlicher Docker-/Ollama-Ablauf

14.09.2026; eigenes synthetisches Testvolume, Loopback-Port und vorhandenes lokales
Qwen2.5:14b. Image `f0ee5fc97098`, Quellcommit `7964241`, geprüfte Produktion
`504c845`. Keine privaten Konten, Daten, Modellumstellung oder Downloads. Alle fünf
Gesprächsanfragen und der zusätzliche Kartenabruf sind unverändert samt Prüfsummen
erhalten. Eigene Test-Authentisierung bleibt außerhalb des Repositorys.

Eine Budgetfreigabe wurde über die reguläre API angelegt; davon abhängig eine
Finanzierungsaussage und eine historische Entscheidung. Die erste Frage wählte
die Finanzierungsaussage aus, ohne die Elternaussage selbst in den Kontext zu nehmen.
Nach Widerruf der Elternaussage verschwand das Kind aus aktuellen Kontextkarten
und Modell-Inputs. Die nächste Antwort setzte den alten Modellverlauf zurück;
sichtbare Nachrichten blieben erhalten. Auch nach Neustart blieb das Kind ausgeschlossen.

Die historische Entscheidung blieb mit `basis.state=review` verfügbar. Ihre stabile
Qualifizierung blieb nach Neustart erhalten, ohne wiederholten Profil-Reset. Keine
der fünf Anfragen erzeugte Action Requests. Vollständige Provideranfragen wurden in
diesem HTTP-Lauf nicht abgefangen; die separaten RecordingProvider-Tests prüfen diese
Grenze. Daraus wird keine allgemeine semantische Modellfreigabe abgeleitet.

**Konkreter Antwortfehler:** Das Modell beschrieb den Beschluss, Vela zu starten,
zunächst als schon begonnenes Projekt. Die anschließende vorsichtige Formulierung
heilt diese unberechtigte Verstärkung nicht. Nach Neustart fragte es lediglich
allgemein zurück. Die Datenqualifizierung funktioniert in diesem Ablauf, die
sprachliche Unterscheidung von Beschluss und Ausführung ist weiter zu verbessern.

Die echte Kingfisher-Oberfläche wurde mit Playwright über die Gesprächsliste geöffnet.
Bei 1440 × 1000 ist „Ich habe den Start von Vela beschlossen. — Grundlage prüfen“
sichtbar und nicht verdeckt; Konsole ohne Fehler oder Warnungen. Screenshots bleiben
als temporäre QA-Artefakte außerhalb des Repos. Bei 1200 Pixeln zeigte sich die bereits
vorhandene Mindestbreite von 1280 Pixeln mit horizontalem Überlauf; eine allgemeine
responsive UI-Abnahme oder Neugestaltung wurde nicht vorgenommen.

PR #47 ist mit grüner CI integriert. Dieser Test belegt keine Aktualisierung der
privaten App, keine vollständige Quellenprüfung und keine sichere Wiederherstellung
alter Backups; diese bleiben separate Arbeitspakete.
