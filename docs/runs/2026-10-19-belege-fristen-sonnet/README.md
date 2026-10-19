# Belegkorrektur und historische Quellenfristen

Korrekturcommit: `bfb5463`, Basis `1544d56`, Zielversion 1.0.25.

Ein Cloudmodell hatte einen tatsächlich vorhandenen Firmennamen dem falschen Originalblock zugeordnet. Die strikte Belegprüfung wies das korrekt ab. Ein ausdrücklich freigegebenes Cloudpaket darf nun bei einem fehlenden, mehrdeutigen oder ungültigen Entitätsanker genau einen vollständigen Korrekturversuch pro Kategorienabschnitt anfordern. Das Modell erhält dieselben Originalblöcke und dasselbe Schema; die vorherige Antwort bleibt ungeprüfte Eingabedaten. Keine automatische Suche nach einer anderen passenden Namensstelle, keine Namensnormalisierung und keine Teilübernahme. Alle Rollen- und Strukturprüfungen gehen der Ankerprüfung voraus; Rollenfehler, Transportfehler, unvollständige Antworten und andere Validierungsfehler lösen keine Korrektur aus. Kategorien und Entitäten werden erst nach vollständig gültiger Gesamtantwort gespeichert. Eine bereits erfolgreiche Aussageauswertung allein gilt weiterhin nicht als vollständige Quelle.

Jede Korrektursendung verwendet denselben Prüfpfad für Zugang, Quellenfassung, Zustimmung und Anfragebudget. Die Vorschau reserviert einen Zusatzaufruf pro Kategorienabschnitt; alte gespeicherte Anfragegrenzen bleiben unverändert. Gültige Erstantworten kosten keinen Zusatzaufruf, der lokale Qwen-Pfad bleibt unverändert.

Eine ausdrücklich genannte redaktionelle Frist stand in einem unsicher eingeordneten historischen Absatz. Zusätzlich war die Originalmail archiviert. `fristen.quellenangaben` erschließt nun ausschließlich ausdrücklich gebundene Datumsangaben aus fact/status/historical/uncertain als neutrale Quellenbelege. Diese stehen mit ursprünglicher Einordnung, ungeklärter Zuständigkeit und vollständigem Originalabsatz separat in der Akte. Ein später Vorbehalt oder eine Absage wird nicht durch die normale Kürzung von Aktenzeilen verdeckt. Es entstehen daraus keine eigenen Aufgaben, aktiven Briefingfristen oder bestätigten Zuständigkeiten. Der explizite Archivlesepfad gilt ausschließlich für Quellenfristen; Standardabfragen, Entzug, Elternquelle, aktuelle Fassung und Wissensbelege bleiben abgesichert. Cacheversion 9 verwirft alte leere Quellenfristenansichten.

## Gleiche Stichprobe

Die zehn eingefrorenen Originale entsprechen der vorherigen Stichprobe. Eine Werbemail bleibt vor jedem Modellaufruf ausgeschlossen. Die neun übrigen Mails wurden in einer getrennten Datenbankkopie mit dem vorbereiteten Anthropic-Zugang neu eingeordnet.

- Sonnet 5.5: 9/9 vollständig, 26 API-Anfragen, 196,62 Sekunden, kein Ausweichmodell.
- 0,249040 USD aus tatsächlich gemeldeten Tokens zum [Anthropic-Standardtarif](https://platform.claude.com/docs/en/about-claude/pricing), vorab auf 0,60 USD begrenzt; ohne Steuern oder individuelle Abrechnung.
- Die betroffene Zahlungsbestätigung hatte bereits im ersten frischen Versuch korrekte Namensbelege. Der neue Korrekturpfad wurde im bezahlten Lauf nicht benötigt; seine Fehler- und Schutzpfade sind separat in 17 synthetischen Cloudtransport-Integrationen geprüft.
- Alle 26 gespeicherten Antworten wurden ohne API-Aufruf durch den endgültigen Stand abgespielt. Nachrichten, Schema und Ausgabebudget jedes Requests sind identisch mit dem bezahlten Lauf. Aussage- und Kategorienresultate sind identisch; 167 Originalspannen stimmen wörtlich überein.
- Die redaktionelle Frist ist jetzt als historische Quellenangabe auffindbar, bei unverändert unsicherer Einordnung. Nur die passenden Mailkopfpersonen erhalten diesen historischen Quellenbezug; bloß im benachbarten Absatz genannte Autorinnen erhalten weder die Frist noch eine Aufgabe.
- Ein unabhängiger Prüfer hat alle neun Fälle und Personenprofile gegen die Originale bewertet. Die zwei gezielten Korrekturen sind bestanden; es gibt keine Freigabe für einen Großimport.

Der bezahlte Lauf nutzte den vorläufigen Korrekturstand mit noch fehlender Archivsichtbarkeit. Die nachträglichen Änderungen betreffen die datengestützte Fristanzeige sowie die Priorität von Validierungsfehlern, nicht die Modellanfragen. Der abschließende kostenfreie Replay prüft exakt diese Grenze und den ausgelieferten Code. Es wurde kein zweiter bezahlter Lauf versteckt wiederholt.

Originale, Nutzerentscheidungen, bestätigte Aufgaben, Projekte, Notizen und Wissensaussagen bleiben zeilenweise unverändert. Ergebnisse liegen privat außerhalb des Repositorys; es wurden keine Testeinordnungen in den Produktivbestand übertragen. Der produktive Mailimport bleibt pausiert. Lokale Rollen bleiben Qwen9B und BGE-M3.

## Prüfungen und Grenzen

52 neue gezielte Regressionstests sichern Korrektur, Budget/Freigabe, Quellenfristen, Archivzugriff, Quellenentzug, Fassungswechsel, Personenabgrenzung, lange Vorbehalte und Cachewechsel. Ein unabhängiges finales Code-Review fand keine verbleibenden Befunde innerhalb dieses Umfangs; 91 gezielte Backendtests und 2 UI-Tests bestanden.

Die Oberfläche wurde mit künstlicher historischer Quelle im lokalen Browser geprüft: Fristenabschnitt beginnt geschlossen, zeigt Einordnung und Zuständigkeitsvorbehalt, erhält die späte Absage im vollständigen Absatz und öffnet die Originalquelle. Keine Konsolenfehler. Ein bestehender Kalender-UI-Test hing vom aktuellen Datum ab: In der Kalenderwoche 19.–25. Oktober ändert ein Wechsel zum 25. Oktober das Wochenfenster nicht. Der Test stellt nun seine Ausgangswoche ausdrücklich her; Produktverhalten und Erwartungen bleiben unverändert.

Vollständige Backendprüfung des endgültigen Codes: **7.257 bestanden, 1 übersprungen, 26 Unterfälle bestanden** (zwei niedrig priorisierte Prozesse; 553,25 Sekunden). 745 Oberflächentests, 235 Gedächtnisdiagnosen und 330 Messlatte-/Mac-Tests bestanden (1 übersprungen). Oberflächenbau, Asset-Vertrag, Versionsprüfung und Profil-Schema bestanden. Bestehende Starlette-/Escape- und Paketgrößenhinweise bleiben. Zwei frühere Vollprüfungen wurden für konkrete Review-/Archivkorrekturen abgebrochen; nur der abgeschlossene Lauf auf dem endgültigen Code zählt als Freigabelauf.

Vor und nach der Probe waren Originale und bestätigte Daten zeilenweise unverändert. Kein Ollama-Modell war geladen; der App-Container lag nach dem Lauf bei etwa 143 MiB, lokale Leseanfragen antworteten zu Beginn in 4–364 ms. Die echte Mac-Aktualisierung ist vom Code-/Stichprobenergebnis getrennt: Das Fenster ist derzeit gesperrt; die Freigabe zum Entsperren ist angefragt.

Themenkategorien bleiben modellabhängige Vorschläge; Unterschiede zwischen Läufen sind dokumentiert. Zahlungsplantermine, unverbindliche Seminarangebote und ausschließlich im Betreff genannte Einsatzdaten sind kein Beweis vollständiger Termin- oder Aufgabenerfassung. Die überwiegend historische Stichprobe ersetzt keinen Pilotlauf mit aktuellen handlungsrelevanten Mails und keine Prüfung des gesamten Postfachs. Die lokale automatische Aufgabenerkennung wurde durch diesen Cloudversuch nicht ersetzt.
