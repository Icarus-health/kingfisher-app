# Informationsquellen und Aufnahmeumfang

Code: `5c99e0a731851f3480aeb561293153a3f0b51473`. Basis: `3667e4e18b9e255780c755889370b46368cf0a6d`. Eigenständige Implementierung, kein LifeOS-Code kopiert. Nicht auf dem Mac installiert; echte Fensterprüfung auf Nutzerwunsch verschoben.

## Ergebnis für den Nutzer

Unter **Gedächtnis → Verarbeitung & Verlauf** zeigt eine gemeinsame Übersicht Postfächer, eingetragene Kalenderkonten/-abos, ausgewählte Mac-Kalender sowie Dokument- und Mitschriftenordner. Sie erklärt die Grenzen und führt direkt zum passenden Zugang oder Kalender. Sie bleibt erreichbar, auch wenn die übergeordnete Gedächtnisabdeckung noch nicht geladen wurde.

Mailzählung, Aufnahme/Wiedererkennung und abgeschlossene Einordnung werden getrennt. Ein unbekannter Umfang ist keine vollständig gelesene Mailbox. Regelmäßiger Mailabgleich und historische Aufnahme haben unterschiedliche Nachweise. Fehler bleiben auch bei pausierter Aufnahme sichtbar. Externe Kalender werden ausschließlich als eingerichtet ausgewiesen, nicht als vollständig abgeglichen oder leer.

Ein bestätigter Mac-Abgleich erfordert bekannte ausgewählte Kalender, Freigabe, erreichbaren Helfer, einen höchstens fünf Minuten alten vollständigen Snapshot und ein Zeitfenster, das die aktuelle Zeit enthält. Ohne diese Nachweise wird keine leere Agenda behauptet. Ältere Server ohne Snapshot-Vollständigkeitsfeld bleiben ausdrücklich unbestätigt.

Fehlgeschlagene Statusabfragen behalten den letzten bekannten Stand und markieren ihn als veraltet. Abfragen laufen nur bei sichtbarer Seite, ohne überlappende Runden, mit Abbruch nach 15 Sekunden. Versteckte oder verlassene Ansichten veröffentlichen keine verspäteten Ergebnisse. Keine neue Dauerinferenz, kein Importstart und keine Änderung von Freigaben.

## Begrenzte Statusabfragen

Die Ansicht verwendet sechs lokale GET-Routen: Mailaufnahme, Integrationen, Zeitplan, Mac-Kalenderstatus sowie Dokument-/Mitschriftenstatus mit `?summary=true`. Die kompakte Ordnerantwort enthält Zähler und Fehleranzahl, keine Dateiliste, Originaltexte oder einzelnen Fehlermeldungen. Gespeicherte Dateiverweise einschließlich Mehrfachreferenzen werden korrekt gezählt; fehlende Original-IDs bleiben als unbekannt sichtbar. Zustände werden in SQL-Gruppen von höchstens 500 IDs gelesen. Der normale Ordnerstatus ohne Queryparameter bleibt kompatibel; die UI kann ältere volle Antworten ebenfalls lesen.

Das ist eine erste Übertragung der Atlas-Idee auf vorhandene Informationsquellen. Kein Geräte-/Serverinventar, kein Nachweis aller Quellen, keine Anbieter-Synchronisationshistorie und keine zweite Gedächtnisdatenbank. Metadatenrouten können bestehende Anbieter-Verfügbarkeitsinformationen enthalten; die neue Ansicht ruft keine Kalenderinhalte oder Modellinferenz direkt auf. Die HTTP-Prüfung verwendet ausschließlich künstliche Daten und blockiert externe Zugriffe.

## Nachweise

- 71/71 betroffene Backend-Tests, einschließlich bestehender Mail-, Kalender-, Authentifizierungs- und Ordnerfälle. Kein vollständiger Backend-Lauf behauptet.
- 452/452 Tests der gesamten UI-Testsammlung; 21/21 neue fokussierte Fälle.
- Aus sauberem Git-Archiv des genannten Code-Commits: 12/12 HTTP-Fälle, 21/21 UI-Fälle und TypeScript/Vite-Build bestanden. Abhängigkeiten aus der vorhandenen lokalen Installation geteilt; unversionierte Dateien ausgeschlossen.
- Reale geschützte HTTP-Routen: ohne Sitzung 401, unveränderte Originale/Einstellungen, keine Quellenaufnahme und keine Freigabeänderung. Kompaktabfragen erhalten den letzten erfolgreichen Zeitstempel bei Teilfehlern.
- 10.000 künstliche Dateiverweise auf **ein** Original werden ohne einzelne Textabfragen und mit höchstens einem Zustand-SELECT gezählt; Antwort unter 2 KiB. Zwei Ordnerfälle mit 10.000 künstlichen Fehlern bleiben ebenfalls unter 2 KiB. Das ist kein Lasttest für 10.000 unterschiedliche Originale oder die Modellverarbeitung.
- Vorher/Nachher-Belege für versteckte Übersicht bei fehlender Abdeckung, verdeckte Mailfehler, Fehler trotz Pause, volle statt kompakte Ordnerantwort und ausufernde Fehlerliste. Das frühe `compact-red.log` enthält neben drei fehlgeschlagenen Prüfungen zwei Fehler beim Test-Abbau, weil die künstliche Sperre für Originalzugriffe zu lange aktiv war. Die Sperre wurde auf den geprüften HTTP-Aufruf begrenzt; diese beiden Abbaufehler zählen nicht als Produktfehler. Auch Einrichtungsfehler bei Testpfaden/Imports sind keine Produktregressionsnachweise.
- Unabhängige statische Prüfung fand die Fehlerlisten-Lücke; Korrektur nochmals geprüft, keine weiteren konkreten Blocker. Siehe `independent-review.md`.

Die Rohprotokolle liegen komprimiert bei; Prüfsummen und eingefrorener Code stehen in `verification.json` und `freeze.json`. Bestehende Warnungen: Starlette/httpx-Veraltung und Vite-Bündelgröße. SSR-/Controller-/HTTP-Prüfungen ersetzen keine visuelle oder native Bedienprüfung.

## Offene Freigaben

Mac-App, persönliche Daten, pausierte Aufnahme und ausgeschaltetes Ollama wurden nicht verändert. Keine Cloudkosten, Modellaufrufe, CI-Wiederholungen oder Agenten-Check-ins gestartet. Die Arbeit basiert direkt auf main und enthält die anderen offenen Vorschauänderungen nicht. Vor einer gemeinsamen Installation müssen diese gezielt zusammengeführt und am echten Fenster geprüft werden. Persönliche Antwortqualität, Alltagstauglichkeit und tatsächlicher Ressourcenverbrauch bleiben eigenständige Abnahmen; dieser Statusbildschirm belegt sie nicht.
