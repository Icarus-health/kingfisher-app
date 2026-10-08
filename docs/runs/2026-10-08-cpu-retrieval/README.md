# Lokale CPU-Abrufmessung · 8. Oktober 2026

Die vorhandene Linux-arm64-Ollama-Umgebung 0.24.0 verwendet ausschließlich bereits installierte Gewichte. Modellcache nur lesend, internes Docker-Netz ohne Internet, Cloud abgeschaltet, zwei CPU-Kerne und sechs GiB als Testobergrenze. Die Modellgewichte und Modellrollen der installierten Kingfisher-App wurden nicht verändert. Der Mac hing am Netzteil.

## Erfolgreich gemessen: Bedeutungssuche

`original-semantic-ranks.json` enthält alle 36 Fragen des unveränderten alten Katalogs; `independent-semantic-ranks.json` die vorab eingefrorenen 23 Fragen der neuen Kontrollmenge. Gewichte: `bge-m3:latest`, Digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`. Der Originalkataloghash stimmt mit den historischen Messungen überein; der neue Kontrollhash ist `857965be8e845fde716e5d22d94d5310f5011058db68a4b7107abae1e10e465a`.

| Reine Bedeutungssuche | Fragen | Alle Goldquellen über 0,55 | Alle Goldquellen unter den ersten drei |
|---|---:|---:|---:|
| Original, direkt | 16 | 16 | 16 |
| Original, umformuliert | 16 | 11 | 16 |
| Unabhängig, direkt | 10 | 10 | 10 |
| Unabhängig, umformuliert | 9 | 8 | 9 |

Diese Kennzahlen messen Kandidatenpotential, **keine vollständigen Antworten**. Weitere ungeeignete Kandidaten können gleichzeitig über der Schwelle liegen. Die unbekannten Fragen haben keine Goldquelle; auf dem Originalkatalog bleiben alle vier unter der Schwelle, auf der unabhängigen Menge liefert eine von vier eine ungeeignete Quelle: „Wer prüft die Ware im Auftrag KL-24?“ erhält die Lieferantin von KL-24 mit 0,587457. Lieferung belegt keine Prüfung. Die PIN-Frage erreicht auf dem Originalkatalog 0,541009 zur Zugangskarte. Eine niedrigere Schwelle kann deshalb Antwortbarkeit nicht entscheiden.

Die fünf ursprünglichen Umschreibungen mit früher fehlender Spur stehen frisch gemessen weiterhin jeweils auf Rang 1, aber unter 0,55. Der unabhängige Zwei-Themenfall M-731/M-713 verliert eine seiner beiden nötigen Quellen an derselben Schwelle (0,538938). Das erklärt eine Kandidatenlücke, rechtfertigt aber **keine ungemessene Produkt-Schwellenänderung**. Wörter, Schwelle und Bestandsgrenze blieben unverändert.

## Fehlgeschlagener echter Antwortlauf

`answer-runtime-failed-attempt.json` ist der echte Agentenweg des geprüften Codes fc5f33e mit Quote-Modus und den ersten acht unveränderten Fragen. Alle 13 Antwortmodellaufrufe scheiterten; der Bericht registriert sie ausdrücklich als Fehler. Der Docker-Test erreichte 13 OOM-Kills; das Antwortmodell meldete 5,4 GiB Bedarf, während der gesamte Docker-VM-Pool rund 7,74 GiB umfasst und weitere bestehende Dienste laufen. Bedeutungssuche im echten Pfad scheiterte zusätzlich an ihrem 3-Sekunden-Limit beim Modellwechsel. Diese Rückfälle sind **keine neue 0/8-Antwortqualitätsmessung** und dürfen nicht mit der früheren erfolgreichen nativen Messung verglichen werden.

Die reine Rankingmessung lief dagegen mit ausdrücklichen CPU-Optionen, kleinen Batches und eigenem begrenztem Mess-Timeout erfolgreich. Das verändert nicht die produktiven Timeouts. Nach dem fehlgeschlagenen Antwortversuch wurde der eigene Testcontainer beendet und mitsamt internem Netzwerk entfernt. Keine fremden Dienste neu gestartet oder Ressourcenlimits erhöht. Der vollständige lokale Antwortvergleich bleibt offen.

## Reproduktion und Grenzen

`cpu-ranking.py` ist der exakt ausgeführte Standardbibliothek-Treiber. Er erwartet den Katalog als erstes Argument und einen lokalen Ollama-Dienst auf 127.0.0.1:11434; pro Batch höchstens acht Texte, num_gpu=0, num_thread=2, num_ctx=2048. Beispiel innerhalb der isolierten Netzwerk-Namensräume: `python /probe/ranking.py /probe/original-catalog.json`. Ergebnis geht als JSON nach stdout; Fortschritt nach stderr. Die Digest-/Dimensions-/Normprüfungen liefen vor der Auswertung.

Bei einer Wiederholung müssen Berichte auf ein dauerhaftes Ausgabeziel geschrieben werden. Der erste Antwortlauf nutzte irrtümlich ein temporäres Ziel im automatisch entfernten Clientcontainer; ein zusätzlicher Leser sicherte das vollständige JSON vor dessen Ende. Die gesicherte Datei ist parsebar und enthält alle acht Zeilen und 13 Modellereignisse. Keine Rohantwort eines privaten Nutzers wurde verarbeitet.

Die Goldwerte des unabhängigen Katalogs werden nach den Ergebnissen nicht angepasst. RQ11 wurde vor der ersten Messung präzisiert, damit ausdrücklich beide Notizen verlangt sind, statt zwei alternativ hinreichende Quellen fälschlich gemeinsam als Pflicht zu bewerten. Menschliche Inhaltsprüfung bleibt für tatsächliche Modellantworten nötig; diese Rankings enthalten keine solchen Antworten.

## Reproduzierter Produktfehler und Korrektur

Unabhängig vom Modellvergleich wurde der echte Antwortweg mit künstlichen Quellen geprüft: Bei zwei eingeordneten Quellen und Inventarlimit eins war die Bedeutungssuche `partial`, die Quellenantwort erschien aber als unbegrenzt. Ein leerer Rückfall konnte darüber hinaus „keine Information“ behaupten. Die Korrektur bindet Treffer und Abdeckungsstatus an denselben tatsächlichen Suchaufruf. Eine globale, zwischen parallelen Aufrufen veränderliche Statusvariable wird nicht als Nachweis gelesen. Die bisherige Listen-Schnittstelle bleibt kompatibel.

Begrenzter Bestand und ausgefallene Bedeutungssuche werden sowohl bei belegten Antworten als auch bei leerem Rückfall, abgelehnter Quellenauswahl und Satz-Abstention kenntlich gemacht. Bestätigte Belege bleiben erhalten. Gespeicherte Antworten werden beim Lesen weiterhin ohne Embedder gegen Originale und Quellenentzug geprüft. Die Diagnose erfasst den tatsächlich gebundenen Status; eine eingeschaltete, unvollständige oder unbeobachtete Bedeutungssuche zählt nicht mehr als vollständiger Erfolg. Das korrigiert einen falschen Vollständigkeitseindruck, nicht die weiterhin bestehende Grenze von 2048 flüchtig eingebetteten Abschnitten.

Der größere Suchindex, ein erfolgreich abgeschlossener frischer Modellvergleich und die native Alltagsprüfung bleiben erforderlich. Der Mac war beim erneuten Fensterzugriff weiterhin gesperrt; dieser Zugriff ist kein bestandener Bediennachweis.

## Prüfung des endgültigen Codes

359 betroffene Backend-/Diagnoseprüfungen bestehen (54,33 s). Darunter echte HTTP-Wege für begrenzte und ausgefallene Suche, leere Ergebnisse und Auswahl-Abstention sowie Offline-Wiederöffnung und Quellenentzug. Das unabhängige Review fand vier weitere Weitergabe-Lücken: fehlerhafter Statusadapter, eingeschränkte Anschlussfrage, nachgelagerter Originalstellen-Rückfall und angeklickter Bedeutungsrahmen. Acht zusätzliche Regressionen scheiterten vor deren Korrektur; danach bestehen sie. Zwei weitere RED/GREEN-Fälle sichern den Hinweis beim erneuten Anzeigen des Originalstellen-Rückfalls, ohne Einbettung oder Veränderung der gespeicherten Nachricht. Ein gezieltes unabhängiges Nachreview bestätigte die Korrekturen. Kein neuer vollständiger Backend-Lauf, keine CI-Wiederholung und keine Cloudanfrage.

## Lieferung

[PR 8](https://github.com/Icarus-health/kingfisher-app/pull/8) ist als `e9b7905843852dd73ef72e546a7e806daa3fdc80` zusammengeführt; sein Baum ist zum geprüften Code `66eb641e2b2be68c025401cdfaf14f27f1ac14f2` unverändert.

Am Mac installiert ist **1.0.6-local.66eb641**, Abbild `sha256:468dbdd0c650e4895af2a419f7c46d716ecc353668a65114e3e54014de273dc6`. Es wurde ohne Netzwerk aus dem vorhandenen Abbild `69d471…` gebaut; Oberfläche und Abhängigkeiten bleiben daraus erhalten, die 260 Paketdateien wurden aus sauberem Git-Archiv ersetzt und ihr gemeinsamer SHA-256 `21e3c74b68194168b6ac6e716a3ab445bde8d13470271efae145d04917b94712` im fertigen Abbild bytegleich geprüft. Ein netzloser Funktionstest bestätigt die neue callgebundene Schnittstelle.

Vor Austausch wurden App, private Konfiguration und kalter Datenbestand lokal unter `Kingfisher-Rueckweg/2026-10-08-vor-66eb641` gesichert. Alle 344 vorhandenen Eintragskennungen und Inhaltsprüfsummen sind erhalten; 17 SQLite-Dateien bestehen vorher und nachher die Integritätsprüfung. Mailkonten, Kalender, Cloudanbieter, Modellrollen und Zeitplan sind unverändert. Derselbe Datenvolume und Loopback-Port bleiben in Gebrauch. Der native Starter ist bytegleich; Bundle-Fassung und Signatur wurden angepasst. Fassung, Gesundheitsprüfung und World-API sind erreichbar. Die native Fensterprüfung bleibt wegen des gesperrten Macs offen. Kein öffentliches Stable-Release oder Container-Upload; der öffentliche Updater liefert diese lokale Vorschau nicht aus.
