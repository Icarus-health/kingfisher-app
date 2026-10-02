# Roadmap: Docker auf dem Mac

Stand: 13. September 2026. Ziel ist der Icarus-Funktionsumfang mit Kingfisher-UI;
das korrigierbare Graphengedächtnis ist der gemeinsame Kern. Mobile und native
Mac-Paketierung sind gemäß Produktentscheidung zurückgestellt.

## Neue Priorität: Gedächtnisfreigabe vor Funktionsquote

Seit 13. September gilt die [Memory-first-Roadmap](MEMORY-FIRST-ROADMAP.md) als
aktuelle Entwicklungsreihenfolge. Der Nutzer priorisiert richtige Erinnerung,
wenige Fehler und angemessene Antwortzeiten. **Die Produkt-/Gedächtnisfreigabe
ist noch offen.** Die folgenden 80 % dokumentieren ausschließlich die bisherige
Funktionsabnahme und werden nicht als Reifegrad der erweiterten Vision verwendet.
Neue Qualitätsziele werden getrennt gemessen; kein stilles Umzählen dieser Liste.

## Zählweise und aktueller Stand

**16 von 20 Abnahmepunkten erfüllt = 80 %.** Jeder Punkt zählt gleich, obwohl
sein Restaufwand unterschiedlich groß ist. Die Zahl misst abgeschlossene
Prüfpunkte, keine Codezeilen, Zeitprognose oder Prozent der Produktqualität.
Angefangene Punkte bekommen keinen Teilkredit. Vorhandene Icarus-Funktionen
zählen erst mit dem hier benannten Nachweis. Backend-Punkte sind ausdrücklich
als solche bezeichnet; ihre Bedienbarkeit ist ein eigener Punkt.

| ID | Abnahmepunkt | Stand / Nachweis |
| --- | --- | --- |
| 01 / K0 | Gebauter Container liefert Kingfisher, Originalassets, aktive Routen und geschützte API | Erfüllt: PR #2, Container-/Browserlauf |
| 02 / K0 | Gespräch und bestätigtes Wissen bleiben nach Containerneustart verwendbar | Erfüllt: PR #2 und #3, echte Neustarts |
| 03 / K0 | Modelleinrichtung in freigegebener UI, echter unterstützter Provider, verständliche Verbindungsfehler | Erfüllt: echtes Ollama, fehlendes Modell, Wiederholen, neues Gespräch, Neuladen und Containerneustart geprüft; visuelle Zustandsprüfung und begrenzte Umsetzungsfreigabe unter delegierter Reviewentscheidung in SDR-010 / VISUAL-CHECK-local-model-v1.md dokumentiert |
| 04 / K1 | Backend: stabile Identitäten, Mehrfachbeziehungen, Zeitbezug und gleichnamige Personen | Erfüllt: PR #1, gezielte Gedächtnistests |
| 05 / K1 | Backend: belegte Korrekturen entwerten abhängiges Wissen und veralteten Modellkontext | Erfüllt: PR #1; Laufzeitnachweise ergänzt in #2/#3 |
| 06 / K2 | Gespräch: Quelle öffnen, bestätigen, widerrufen, nächsten Kontext und Neustart prüfen | Erfüllt: PR #3, tatsächlicher Browserablauf |
| 07 / K2 | Personen- und Projektprofile mit allen belegten Beziehungen bedienen | Erfüllt: suchbares Aktenverzeichnis, echte Mailquelle in Personenakte, getrennte Gleichnamige und mehrere Projektbeziehungen im isolierten Docker vor/nach Neustart geprüft. Befüllte Profile mit Referenz verglichen; begrenzte delegierte Umsetzungsfreigabe SDR-013. Nutzerinstanz aktualisiert. Nachweis: [ACCEPTANCE-PROFILES-80.md](ACCEPTANCE-PROFILES-80.md) |
| 08 / K2 | Identitäten klären und Beziehungen zeitlich/bezüglich ihres Kontexts korrigieren | Erfüllt: gemeinsamer geschützter Docker-Browserablauf, 19 gezielte Backendtests und visuelle Verwaltungszustände geprüft; eng begrenzte Umsetzungsfreigabe unter delegierter Reviewentscheidung in SDR-011 / VISUAL-CHECK-profile-management-v1.md |
| 09 / K3 | Opt-in Mail, Kalender und Dateien fortlaufend und ohne Dubletten aufnehmen | Erfüllt: ausgewählte Mac-Kalender, aktivierter Eingangsordner und echtes ALL-INKL-Postfach geprüft. 100 echte Mails in zwei begrenzten Läufen, identische Wiederaufnahme ohne Dubletten, gespeicherter 15-Minuten-Zeitplan und Containerneustart. Dateiänderungen, Entzug und Teilausfälle im isolierten Docker geprüft. Nachweis: [ACCEPTANCE-CONTINUOUS-SOURCES.md](ACCEPTANCE-CONTINUOUS-SOURCES.md) |
| 10 / K3 | Quellenänderung, Entzug, Teilausfall und Wiederholung nachvollziehbar behandeln | Erfüllt: identifizierte Datei-/Mailfassungen, Kalender-Snapshots, sichtbarer Entzug/Wiederzulassung, unabhängige Belege, Fehlversuche, Wiederholung und Neustart geprüft. Gemeinsame Abnahme: ACCEPTANCE-SOURCES.md; 137 gezielte Tests, vorherige Gesamtsuite und Docker-Browser bestanden |
| 11 / K4 | Tagesbriefing und Terminvorbereitung aus demselben aktuellen Gedächtnis | Erfüllt: gemeinsame Aufgaben-/Entscheidungsänderungen, expliziter Personen-/Projektkontext, Quellenentzug, Ortszeit, Kalender-Teilausfall und Wiederholung geprüft; Docker-Browser und echter Mac-Kalender. Gemeinsame Abnahme: ACCEPTANCE-50-PERCENT.md |
| 12 / K4 | Projekte, Aufgaben, Zusagen, Entscheidungen und Aktionsfreigaben gemeinsam bedienen | Erfüllt: fortlaufende lokale Zusagenerkennung, ausdrückliche Übernahme mit Quellenbeleg und Wartezustand, gemeinsamer Docker-Browserlauf mit Projekt, Tagesüberblick, Terminvorbereitung, Entscheidungsgrundlage und einmaliger Aktionsfreigabe; Neustart und lokale Auslieferung geprüft. Nachweis: ACCEPTANCE-COS.md |
| 13 / K5 | Modellrouting, Agenten und Werkzeugrechte mit nachvollziehbaren Übergaben | Erfüllt: lokale Modellprüfung und Auswahl, begrenzte Recherche-Rolle, gemeinsame Freigaben, nachvollziehbare Übergaben; echter Ollama-/Docker-/Neustartlauf. Nachweis: ACCEPTANCE-70-PERCENT.md |
| 14 / K5 | Ziele, Gewohnheiten, Lernen und aktuelle Außenwelt mit belegten Hypothesen | Erfüllt: bestehende Ziele, ausdrückliche Gewohnheiten und korrigierbare Tagesbelege, ausschließlich bestätigbare Lernbeobachtungen, opt-in öffentliche Quellen mit Alter/Entzug und expliziter Zielzuordnung; Browser, echte Quelle und Neustart geprüft. Nachweis: ACCEPTANCE-70-PERCENT.md |
| 15 / K5 | Automationen, Browsersteuerung und Sprache samt Fehler-/Neustartverhalten | In Arbeit: lokales Audio-Briefing mit macOS-Stimme, echtem Browser-Player, Abbruch und Neustart geprüft. Sprachinput, Browsersteuerung und gemeinsame Automationsabnahme bleiben offen. Nachweis: [LOCAL-AUDIO-QA.md](LOCAL-AUDIO-QA.md) |
| 16 / K6 | Alle Desktop-Zustände mit Originalreferenzen vergleichen und Abweichungen klären | Offen: Screenshots vorhanden, vollständige visuelle Abnahme fehlt |
| 17 / K7 | Neuinstallation mit Docker Desktop auf echtem Mac und eigenem Modell | In Arbeit: frischer Compose-Bestand auf dem echten Mac gestartet, eigenes Ollama-Modell in der Oberfläche verbunden, echte Antworten vor und nach Neustart sowie erhaltene Modellwahl und Gespräch geprüft. Laufzeit ist Colima, nicht Docker Desktop; der ausdrücklich benannte Docker-Desktop-Nachweis bleibt offen. Startfreigaben mit fünf isolierten Tests geprüft |
| 18 / K7 | Vollständiges Backup inklusive Schlüsselmaterial sichern und zurückspielen | Erfüllt: verschlüsseltes Paket mit Daten und Schlüsselkonfiguration am echten Bestand geprüft; Sicherung aus geschützter UI, Mac-Wiederherstellungsstarter mit eigener App, erhaltene Modellwahl/Gespräche/Ziele und neue echte Ollama-Antwort nach Restore im Browser geprüft. Nachweis: RECOVERY-BUNDLE-QA.md. Externe Modelle und macOS-Freigaben gehören nicht zum App-Datenpaket |
| 19 / K7 | Docker-Update eines bestehenden Bestands und Rückkehrweg ohne Datenverlust | Erfüllt: korrigierte Versionen hin/zurück mit allen zehn befüllten Stores und neuer Aufgabe geprüft; separate verschlüsselte Wiederherstellung mit gespeicherter App-Version, neuere Arbeit erhalten; beide Apps mit echter Ollama-Antwort im Browser geprüft. Konkreter Schema-Rückweg und Anleitung: ACCEPTANCE-50-PERCENT.md / UPDATE-AND-RETURN.md |
| 20 / K7 | PC-Stand abgleichen, PRs integrieren und vollständigen Alltagstest durchführen | In Arbeit: PR #5/#6 inklusive ursprünglicher PR-Kette nach main integriert; vollständiger lokaler CoS-Stand über PR #7 nach main integriert, vollständiger Alltagstest offen |

Nachweise: [PR #1](https://github.com/Icarus-health/Kingfisher/pull/1),
[PR #2](https://github.com/Icarus-health/Kingfisher/pull/2),
[PR #3](https://github.com/Icarus-health/Kingfisher/pull/3).
Verbindlicher Umfang und alle zwölf Icarus-Bereiche: [Produktplan](PRODUCT-PLAN.md).

## Laufendes Paket

Docker-Ersteinrichtung: Der Modellbefehl darf erst nach einer erfolgreichen
Antwort aus dem tatsächlichen Container „verbunden“ melden. HTTP 200 mit
`ok: false`, eine abweichende aktive Konfiguration und nicht erreichbare
Anbieter müssen sichtbar fehlschlagen. CI startet ohne Modell-Umgebungsvariablen
und verwendet nach dem Neustart ausschließlich die gespeicherte Einrichtung.
Die lokale Integration ergänzt die UI und prüft sie mit echtem Ollama.
Die begrenzte Umsetzungsfreigabe dieses ergänzten Zustands ist in SDR-010 dokumentiert.
Nachweise und Integrationsgrenzen: [Integrationsreview](INTEGRATION-REVIEW-20260907.md).

Jeder Folge-PR aktualisiert diese Liste mit seinem tatsächlichen Nachweis.
Die Zahl steigt erst bei vollständig erfülltem Punkt. Neue Anforderungen oder
geänderte Kriterien werden ausdrücklich dokumentiert, nicht still umgezählt.

## Lokaler Nutzungsstand

GitHub-Abgleich über PR #7: Die vollständige lokale Suite des übernommenen
Stands bestand mit 920 Tests. UI, Desktop und Container bestanden auch in
GitHub. Die dortige Python-3.10-Prüfung deckte vier Kalenderfehler auf:
Persistierte UTC-Zeiten mit Zulu-Suffix wurden nicht gelesen. Der gemeinsame
Zeitparser normalisiert dieses Suffix jetzt ausdrücklich; ein zusätzlicher
Test prüft gespeicherte Zulu-/Offset-Zeiten und den Helferstatus nach erneutem
Öffnen. Die erneute GitHub-Prüfung bestand mit 921 Tests unter Python 3.10 und 3.12 sowie UI-, Desktop- und Containerprüfung. PR #7 ist zusammengeführt.

Aus einem Mailvorschlag übernommene Aufgaben behalten jetzt die ausgewählte
Textstelle in ihrer Herkunft. Beim Speichern werden Digest und Wortlaut gegen
die aktuelle Nachricht geprüft; erfundene oder unbelegte Textstellen erzeugen
weder Aufgabe noch Episode. Die Aufgabenquelle zeigt den Beleg nach Neuladen
und kennzeichnet einen Quellenausschluss. 15 gezielte Mail-/Kalenderkontexttests
und ein geschützter Docker-Browserlauf mit synthetischem Postfach und
kontrolliertem lokalem Testmodell bestanden. Build und Assetmanifest geprüft,
lokal ausgerollt. Fortlaufende Zusagenerkennung bleibt offen; diese Änderung
verbessert den vorhandenen ausdrücklichen Übernahmeweg.

Modelleinrichtung erneut als vollständigen Nutzerweg geprüft: Ein nicht
installiertes Modell meldet einen Fehler, das vorhandene Ollama-Modell lässt
sich danach verbinden; „Zum Gespräch“ führt zur ersten echten Antwort. Die
Modellwahl und diese neue Unterhaltung blieben nach einem echten
Containerneustart erhalten. Ein zusätzlicher UI-Fehler wurde reproduziert
und behoben: Bei nicht erreichbarer Einstellungsabfrage erscheint „Status
gerade nicht erreichbar“ statt der falschen Behauptung, kein Modell sei
eingerichtet. Wiederholen lädt die gespeicherte Auswahl. Fehlerabfrage per
Browserroute simuliert, übriger Ablauf mit echtem geschütztem Docker/Ollama.
Build, Desktopdarstellung und Assetprüfung bestanden; lokal ausgerollt und
echte Kalenderteilnehmer anschließend geprüft. Die vollständige formale
visuelle Abnahme der Einrichtung bleibt separat offen.

Der lokale Doppelklick-Starter verwendet jetzt `scripts/start_mac_app.py`.
Er erkennt den lokalen Docker-Kontext, weckt bei Bedarf Colima bzw. eine
vorhandene Docker-Desktop-Installation, startet den vorhandenen Container und
wartet auf Erreichbarkeit vor der Browseröffnung. Entfernte Kontexte werden
nicht gestartet oder umgeschaltet. Kalender- und Sicherungshelfer werden mit
ihren bestehenden Einzelsperren gestartet. Vier neue Tests und vier
Wiederherstellungsstartertests bestanden; echter Warmstart, Heute-Ansicht,
Sicherungshelferstatus, Kalenderteilnehmer sowie genau ein Prozess pro Helfer
geprüft. Ein vollständiger Colima-Kaltstart wurde nur mit simulierten
Prozessantworten getestet, damit andere laufende Anwendungen weiterlaufen.
Docker Desktop ist auf diesem Mac nicht installiert; Punkt 17 bleibt offen.

Registry-Akten verknüpfen Aussagen jetzt anhand stabiler Identitäten mit den
zugehörigen Personen und dem ausdrücklich benannten Kontext. Namen werden aus
der aktuellen Registry gelesen; Gleichnamige bleiben getrennte Links. Eine
Lücke bei reinem Kontextbezug wurde reproduziert und behoben: Die Aussage
erscheint auch in der Akte ihres ausdrücklich zugeordneten Projektkontexts.
Nach Widerruf bleibt sie nur im Verlauf, mit weiterhin öffnenden Verbindungen.
35 gezielte Tests und der geschützte Docker-Browserlauf prüfen Gleichnamige,
Originalquelle, Ziel-/Kontextnavigation und Widerruf. Desktopdarstellung,
Build und Originalassets geprüft; auf Port 8891 ausgerollt und echte
Kalenderteilnehmer danach geprüft. Vollständige Profilabnahme bleibt offen.

Einstellungen vereinfacht: Dateien und vollständige Sicherung erscheinen als
kompakte Zeilen mit ausdrücklich geöffneten Inline-Bereichen. Die vorhandene
zweispaltige Hierarchie aus Referenzbild 14 bleibt erhalten; der Mailbereich
ist in der Desktopübersicht früher sichtbar. Beim erneuten Sicherungsstart
wird der alte Erfolg während der neuen Anfrage ausgeblendet. Im geschützten
Docker-Browser geprüft: Dateiimport, Quelle öffnen/ausschließen, gespeicherter
Zeitplan, vollständige Sicherung samt Neustart und geleerte Passwortfelder
auch beim Schließen. Desktop 1440 × 1000, Build und Originalassetprüfung
bestanden. Auf Port 8891 ausgerollt; echte Kalenderteilnehmer und kompakte
Einstellungen danach geprüft. Die vollständige visuelle Abnahme bleibt offen.

Die vollständige Sicherung ist als aufklappbarer Bereich in den Einstellungen
umgesetzt. Ein ausschließlich ausgehend verbundener Mac-Helfer holt den
expliziten Auftrag mit Zugriffstoken ab; Browser-Cookies dürfen das Passwort
nicht abholen. Das Passwort bleibt im Arbeitsspeicher, der Ergebnisstatus
übersteht den notwendigen App-Neustart. 15 gezielte Tests sowie der geschützte
Docker-Browserlauf auf Port 8892 prüfen Passwortabweichung, echte verschlüsselte
Sicherung mit Wiederherstellungsprüfung, geleerte Eingabefelder und erhaltenen
Ergebnisstatus nach Neuladen. Vollständige Backendtestsuite: 910 Tests bestanden.
Auf die Alltagsinstanz auf Port 8891 ausgerollt; der Mac-Starter startet den
Sicherungshelfer mit. Geschützter Browserstatus meldet ihn online, echte
Kalenderteilnehmer nach dem Update geprüft. Das über die Oberfläche erzeugte
Testpaket wurde zusätzlich in eine getrennte App auf Port 8893 zurückgespielt:
Modellwahl, beide ursprünglichen Gesprächsantworten, Ziele und Neuladen geprüft.
Eine neue echte Ollama-Antwort nach der Wiederherstellung blieb nach Neuladen erhalten.
Der Mac-Wiederherstellungsstarter öffnet jetzt eine eigene App und hinterlässt
einen Doppelklick-Starter im Ergebnisordner. Erneutes Öffnen verwendet denselben
Container und Datenbestand; die App läuft als normaler Kingfisher-Benutzer.
Vier Startertests und der vollständige Docker-/Browserablauf bestanden.
Damit ist Abnahmepunkt 18 abgeschlossen: 6 von 20 Punkten = 30 %.
Desktop bei 1440 × 1000 geprüft. Bei 390 Pixeln überlagert die bestehende
Seitenleiste den Bereich; die zurückgestellte mobile Ansicht ist nicht abgenommen.

Die vollständige Sicherung prüft vor dem Anhalten, ob die private
Docker-Konfiguration einschließlich Zugriffstoken und Schlüssel-Passphrase zur
gewählten Instanz passt. Fehlende, doppelte oder abweichende Werte werden
abgewiesen, ohne Geheimnisse auszugeben. Exportiert wird eine temporäre private
Kopie der geprüften Konfiguration, damit nachträgliche Änderungen das Paket
nicht verfälschen. Elf Tests und ein echter verschlüsselter Sicherungs- und
Wiederherstellungsprüflauf am getrennten Docker-Bestand erfolgreich.
Die aktuelle echte Instanzkonfiguration wurde nur lesend abgeglichen.
Die Sicherungsbedienung in den Einstellungen ist inzwischen ergänzt und geprüft.

Quellenausschluss in der Terminvorbereitung nachgeschärft: Ein offener
Aufgabenverweis konnte ausgeschlossenes Rohmaterial erneut aufnehmen.
Die abschließende Quellenauswahl respektiert jetzt den Ausschluss unabhängig
vom Verweisweg. Der Regressionstest reproduzierte den Fehler; 20 gezielte
Tests und der geschützte Docker-Browserablauf bestanden. Die Aufgabe und
andere Projektquellen bleiben erhalten.

Tageskarte und geöffnetes Briefing führen jetzt über die tatsächliche Termin-ID
direkt zur Kalender-Vorbereitung. Die Auswahl übersteht Neuladen, ist auch in
der Jahresansicht sichtbar und wird beim Schließen aus der URL entfernt.
Fehlende oder entzogene Termine zeigen einen Hinweis statt einer anderen
Vorbereitung. Der geschützte Docker-Browserlauf prüft beide Einstiege,
Sonderzeichen in IDs, Neuladen, Jahresansicht, Schließen und Kalenderentzug.
Build und Assetmanifest bestanden; die unveränderten Originalassets bleiben
die gestalterische Grundlage.

Gemeinsamer Aufgabenstand von Tagesbriefing und Terminvorbereitung geprüft:
Erledigen, Wiederöffnen, Projektwechsel, Warten und Zurückholen wirken auf beide
Ansichten. Ein reproduzierter Fehler bei 50 älteren Wartezuständen wurde
behoben: Das Briefing bewertet alle offenen Aufgaben, bevor es seine Auswahl
begrenzt. Die kompakte Karte nennt den Aufgabentitel, die ausführliche
Begründung bleibt im geöffneten und vorgelesenen Briefing. Vollständige Suite
mit 899 Tests erfolgreich; nach der Titelanpassung zusätzlich 41 gezielte Tests.
Docker-Browserlauf mit geschützter Sitzung und 50 Wartezuständen prüft den Weg
vom Briefing zur Erledigung und das Verschwinden aus beiden Ansichten.

Nachprüfung mit aktivem Browser-Zugangsschutz: Ziele, Zielverlauf,
Quelleninhalt/-ausschluss und Zeitplaneinstellungen verwendeten zunächst
Legacy-Adressen außerhalb des auf `/api` begrenzten Sitzungscookies. Die
bisherigen Fixtures ohne Token belegten diese Abläufe daher nicht ausreichend.
Die Oberfläche verwendet jetzt geschützte `/api/v1`-Aliase bei unverändertem
Cookie-Geltungsbereich. 13 neue Tests prüfen Sitzung und verweigerten Zugriff;
der tatsächliche Docker-Browserlauf prüft Zielanlage, Korrektur, Abschluss,
Wiederaufnahme, Verlauf, Widerruf, Quellenöffnung/-ausschluss und gespeicherten
Zeitplan. Vollständige Backendtestsuite: 896 erfolgreich. Das Image
`kingfisher:browser-session-fix` ist lokal auf Port 8891 ausgerollt; echte
Kalenderteilnehmer und lesender Zugriff auf Ziele/Zeitplan danach geprüft.
Die vollständige Update-/Rollback-Abnahme bleibt offen.

Kalender mit echten ausgewählten Mac-Quellen, Tagesbriefing sowie Listen-, Wochen-,
Monats- und Jahresansicht des laufenden Jahres. Direktaufrufe und Neuladen geprüft.
Nachweis: [Kalenderprüfung](CALENDAR-PAGE-QA.md). Diese Teilfortschritte schließen
die breiteren Abnahmepunkte 09–12 noch nicht vollständig ab.

Entscheidungen mit ausgewählten Originalgrundlagen und Korrekturhinweisen sind lokal bedienbar. Vollständige Backendtestsuite: 790 Tests erfolgreich. Nachweis: [Entscheidungsprüfung](DECISION-BASIS-QA.md). Visuelle und vollständige CoS-Abnahme bleiben offen.

Nachrichten sind lesbar; ausdrückliche Quellenaufnahme und Antworten mit kontoabhängiger Freigabe sind angeschlossen. Nachweis mit isolierten Testpostfächern: [Mailprüfung](MAIL-REPLY-FLOW-QA.md). Ein echter Anbieter-/Versandlauf bleibt separat offen.

## Projektbeziehungen in der Terminvorbereitung

Die Auswahl berücksichtigt jetzt auch Aussagen, deren Beziehungsziel die
konkrete Projektkennung ist. Ein gezielter Regressionstest prüft zwei
gleichnamige Projekte, die getrennte Auswahl ihrer Belege und den Wegfall
nach Widerruf. 19 Kalender-/Korrekturtests bestanden; Docker-Image
`kingfisher:project-target-preparation` gebaut. Geschützter Docker-Browserlauf
bei 1440 × 1000 bestanden: Projekt auswählen, Originalbeleg öffnen,
gleichnamiges Projekt getrennt halten, widerrufen und aktualisieren.
Keine JavaScript- oder Konsolenfehler. Desktopausschnitt visuell geprüft;
Browser plugin nicht verfügbar, bestehendes Playwright verwendet. Nach
Bestandssicherung lokal auf Port 8891 ausgerollt. Punkt 11 bleibt offen;
die Gesamtzählung bleibt 6/20 (30 %).

Gedächtnisdarstellung: Beschriftungen entsprechend Referenz 05 unter den
Knoten statt als winziger Text im Kreis; vorhandene Typ-Symbole verwendet.
Desktop bei 1521 × 1034, Tastaturnavigation, Profil-Neuladen, Build und
Assetmanifest geprüft. Lokal ausgerollt. Dicht belegte Graphen und vollständiger
Referenzvergleich bleiben offen; Gesamtzählung unverändert 6/20.

Rückweg nach Updates: Der Wiederherstellungsstarter kann über `--image` eine
ausdrücklich gewählte lokale Version verwenden, auch ohne bestehenden
Container. Die Auswahl wird vorab auf eine unveränderliche Image-ID aufgelöst
und für Entschlüsselung und separate App beibehalten. Fehlende lokale Images
führen ohne Download oder App-Start zum Fehler. Elf gezielte Wiederherstellungs-
und Pakettests bestanden. Ein echtes verschlüsseltes Testpaket wurde mit
`kingfisher:github-sync` separat geöffnet: gespeicherte Gespräche, neue echte
Ollama-Antwort und Neuladen geprüft; tatsächliche Container-Image-ID abgeglichen.
Anleitung: UPDATE-AND-RETURN.md. Automatische Versionszuordnung und vollständige
Schema-Rückwege bleiben offen; Punkt 19 und Gesamtzählung unverändert.

Versionszuordnung der Sicherung ergänzt: Neue Pakete führen die aktuelle
Image-ID verschlüsselt mit. Die Wiederherstellung schreibt sie erst nach
vollständiger Paketprüfung und verwendet sie für die separate App, sofern
keine Version ausdrücklich vorgegeben wurde. Ältere Pakete bleiben lesbar;
fehlende lokale Images starten keine Ersatzversion. 31 gezielte Tests
bestanden, einschließlich ungültiger Metadaten, Vorrang expliziter Auswahl
und erhaltener Daten bei fehlender Version. Echter Docker-Sicherungs-/Restorelauf
mit gespeicherter Image-ID, Gesprächen, neuer Ollama-Antwort und Neuladen
bestanden. Lokal ausgerollt und Sicherungshelfer neu gestartet. Ein vollständiges
Docker-Image ist nicht Teil des Pakets; Schema-Rückwege bleiben offen.

Schema-Rückweg konkret geprüft: Verschlüsselte Sicherung eines alten
Aufgabenschemas und Gesprächs, echte Migration durch TaskStore, neue Aufgabe,
Restore in separaten Ordner mit ursprünglichem Schema und unveränderter
Schlüsselkonfiguration. Neuerer Bestand bleibt erhalten. 69 gezielte Tests
bestanden. Vollständige übrige Store-/Updateabnahme weiterhin offen.

Vollständig befülltes Wiederherstellungspaket geprüft: Alle zehn gesicherten
SQLite-Stores mit fachlichen Einträgen, Einstellungen und echter verschlüsselter
Test-Schlüsseldatei. Vollständige SQL-Dumps/Schema-Versionen stimmen nach Restore
überein; Beziehungen und Quellenbelege bleiben lesbar, neuerer Ausgangsbestand
bleibt erhalten. Lokal und im ausgelieferten Docker-Image ohne Netzwerk
bestanden. Nachweis: RECOVERY-BUNDLE-QA.md. Punkt 19 bleibt bis zur vollständigen
Versionswechselabnahme offen.

Vollständiger befüllter Docker-Versionswechsel ergänzt (UPDATE-RUNTIME-QA.md):
Alle zehn Datenbanken über alt → neu → alt → neu erhalten. Der echte
Browserlauf deckte eine Zeitzonen-Sortierungslücke bei Mac-/Container-Nachrichten
auf. Korrigierte Reihenfolge, Vorschau und letztes Gespräch ohne Datenumschreiben;
Regression, Mikrosekundenfall und gleicher Browserablauf mit echter neuer
Ollama-Antwort bestanden. Lokal ausgerollt. Ältere Images enthalten die Korrektur
nicht; abschließende Versionswechselabnahme bleibt offen.

## Abschluss Modelleinrichtung am 8. September

Abnahmepunkt 03 abgeschlossen: Tatsächliche Modellverbindung einschließlich
fehlgeschlagenem Modell, Wiederholen, erster neuer Antwort und Erhalt nach
Containerneustart erneut geprüft. Desktop-Zustände bei 1521 × 1034 visuell
geprüft; falscher Fehlerhinweis während des Ladens behoben. Die Ergänzung zur
Einstellungsreferenz ist durch Codex im Rahmen der ausdrücklichen delegierten
Reviewentscheidung eng begrenzt freigegeben (SDR-010). Dies ist keine behauptete
persönliche Screenshot-Einzelabnahme durch den Nutzer. Frühere Hinweise auf
die offene Modelleinrichtungsabnahme sind durch diesen Nachweis überholt.
Gesamtstand jetzt 7/20 = 35 %. Die vollständige Desktopabnahme bleibt Punkt 16.

Projektakten vervollständigt: Belegte Beziehungen werden nun auch über Ziel-
und Kontextkennung berücksichtigt. Die gezielte Claim-Abfrage hat kein globales
Listenlimit; Registry-Akten verwenden denselben Zugriff. Gleichnamige Projekte
bleiben getrennt und Widerrufe erscheinen nur im Verlauf mit erhaltenem Beleg.
28 gezielte Graph-/Korrektur-/Kalendertests, UI-Build und Assetmanifest bestanden.
Geschützter Docker-Browserlauf bei 1521 × 1034: Projektbeziehung, Originalquelle,
Gleichnamige und Verlauf nach Widerruf geprüft. Technische Projektstatuswerte
in verständliche deutsche Beschriftungen übersetzt. Lokal ausgerollt; echte
Kalenderanzeige danach geprüft. Vollständige Profilabnahme bleibt offen.


Terminvorbereitung und Akten verwenden jetzt denselben gezielten Beziehungszugriff.
Ein älterer gültiger Beleg verschwindet dadurch nicht mehr hinter dem globalen
Listenlimit; gemeinsame Personen-/Projektbelege werden nur einmal gezeigt.
29 gezielte Tests und die vollständige Backend-Suite (940 bestanden, 145 s)
sind grün. Der neue Regressionstest scheitert im bisherigen Image
`kingfisher:profile-references` an der fehlenden Beziehung und besteht im neuen
Image `kingfisher:shared-context`.
Geschützter Docker-Browserlauf: dieselbe Beziehung in Projektakte und
Terminvorbereitung, Originalbeleg, Trennung gleichnamiger Projekte, Widerruf,
Aktualisieren und erhaltene Historie geprüft. Nach Sicherung lokal ausgerollt;
echte Mac-Kalenderteilnehmer in der Terminvorbereitung danach geprüft.
Image: `sha256:c7563e555f451ce39cd96300399964ea04886aae5042dccea0288269c49cccc6`.
Vollständige gemeinsame Profil-/Briefingabnahme bleibt offen; unverändert 7/20.


Personenakten: Der vorhandene Dokumentreiter zeigt zugeordnete Dokumentepisoden
mit lesbarem Originalinhalt statt eines festen Leerhinweises. Dokumente stehen
nicht mehr gleichzeitig unter Gespräche; aufgeführte Projekte öffnen ihre
ID-basierte Akte. UI-Build, Assetmanifest und geschützter Docker-Browserlauf
bei 1521 × 1034 bestanden: Dokument öffnen, Quelleninhalt lesen, Gespräche
wechseln, Projekt öffnen und neu laden. Screenshot im Aufgabenordner:
`outputs/person-documents-desktop.png`. Bestehende Reiter/Karten bleiben erhalten;
Referenz 06 geprüft, vollständige Profilabnahme weiterhin offen. Browser plugin
nicht verfügbar, vorhandenes Playwright verwendet. Lokal mit vorheriger
Datensicherung ausgerollt; echter Kalenderablauf danach bestanden.


Quellenentzug in Akten und Graph korrigiert: Ausgeschlossene Episoden zählen
nicht mehr als Kontakte, Themen, Projektbezüge oder aktuelle Dokumente.
Unabhängige Quellen bleiben sichtbar; Originalinhalt bleibt im Episodenspeicher
zur Nachprüfung erhalten. Regression vor der Änderung reproduziert (zwei statt
einem Kontakt), danach 71 gezielte Graph-/Personen-/Kalender-/Korrekturtests
grün. Docker-Browserlauf bei 1521 × 1034 prüft Quellenentzug über die geschützte
API, Neuladen der Personenakte, Kontaktzahl, leeren Dokumentreiter, erhaltene
andere Projektquelle und Entfernung des Quellknotens im Graphen. Lokal nach
Sicherung ausgerollt; echte Mac-Kalenderteilnehmer danach geprüft.
Der vollständige Abnahmeumfang bleibt offen, unverändert 7/20.


Gemeinsamer Identitäts-/Korrekturablauf erneut am geschützten Docker-Image
geprüft (1521 × 1034): Gleichnamige über Link vergleichen, Name ändern und
neu laden, Quellenkennung lösen abbrechen/bestätigen, andere Identität erhalten,
Bezug/Kontext/Zeitraum korrigieren, ungültigen Zeitraum abfangen, vor Bestätigung
keine Änderung schreiben, ersetzten Stand nach Neuladen anzeigen, Widerruf
abbrechen/bestätigen, Originalquelle im ersetzten Verlauf lesen. 19 gezielte
Backendtests sowie UI-Build/Assetmanifest bestanden.
Dabei behoben: Die abschließende Korrekturprüfung unterscheidet gleichnamige
Ziel-/Kontextidentitäten jetzt ebenso eindeutig wie die Auswahl. Eintragstypen
sind deutsch beschriftet; unterscheidende Kennung nur bei Gleichnamigen.
Screenshot: outputs/correction-identity-review.png im Aufgabenordner.
Lokal nach Sicherung ausgerollt und echter Kalenderablauf danach geprüft.
Punkt 08 bleibt bis zum vollständigen visuellen Abgleich der Verwaltungszustände
offen; diese Prüfung belegt den Bedienablauf, keine vollständige Referenztreue.


## Abschluss Identitäts- und Beziehungskorrekturen am 8. September

Punkt 08 ist nach gemeinsamer funktionaler und visueller Prüfung abgeschlossen.
Die Prüfzustände für Identitätsverwaltung und Korrektur wurden gegen Screen 06
abgeglichen und unter SDR-011 eng begrenzt als eingebettete Ergänzung freigegeben.
Vorherige Aussagen zur offenen Verwaltungsabnahme sind damit überholt.
Gesamtstand: 8/20 = 40 %. Punkte 07 und 16 bleiben ausdrücklich offen.


Aktenverbindungen ergänzt: Arbeitsprojekte werden in Beziehungen anhand ihrer
exakten Kennung aufgelöst und mit Namen zur richtigen Projektakte verlinkt.
Keine zweite Projektablage und kein Namensabgleich; Registry-Identitäten behalten
Vorrang. Regression vor Änderung reproduziert, danach 31 gezielte Tests grün.
Docker-Browser bei 1521 × 1034: Projektname, Zielroute, getrennte Gleichnamige,
Neuladen und erhaltener Verweis im widerrufenen Verlauf geprüft. UI-Build und
Assetmanifest bestanden. Lokal nach Sicherung ausgerollt, echter Kalenderlauf
danach bestanden. Vollständige Aktenabnahme bleibt offen.


Projektakten zeigen unter Team nun auch Personen aus ausdrücklich bestätigten
Projektbeziehungen, nicht nur Namen aus Projektquellen. Stabile Registry-IDs
bleiben getrennt; kein Namensabgleich. Die Oberfläche unterscheidet bestätigten
Projektbezug von Quellenkontakt und öffnet die jeweils passende Akte.
Regression vor Änderung reproduziert; 31 gezielte Tests bestanden, zusätzlicher
Gleichnamigenfall geprüft. UI-Build und Assetmanifest grün. Docker-Browser bei
1521 × 1034: beide Aktenwege, passende Beziehung statt gleichnamiger anderer,
Neuladen und Widerruf ohne Verlust unabhängiger Quellenkontakte bestanden.
Lokal nach Sicherung ausgerollt, echter Kalenderlauf danach bestanden.
Punkt 07 bleibt für die vollständige Aktenabnahme offen; unverändert 8/20.


Gemeinsame technische Aktenprüfung am 8. September: Personenreiter für Projekte,
Gespräche, Dokumente und ehrlichen leeren Notizstand; Projektreiter für Aufgaben,
Quellen/Arbeitsnotizen, Entscheidungen und getrennte Quellenkontakte/Identitäten
im geschützten Docker-Browser bestanden. Projektentscheidung erstellen/neuladen,
Aufgabenquelle öffnen und gefilterte Aufgabenliste erreichen, Originale als
inerten Text lesen, Namensgleichheit trennen, Fehlerzustand wiederholen geprüft.
Sichtprüfung bei 1521 × 1034. Technische Quellen-/Notiztypen deutsch beschriftet;
Einzahl von Kontakt und Beleg korrigiert. UI-Build/Assetmanifest bestanden.
Lokaler Nutzerbestand nur aggregiert geprüft: eine Episode, keine Teilnehmer-
und keine Projektzuordnung. Der ausdrücklich dokumentierte Nachweis befüllter
Akten aus echten Nutzerquellen (VISUAL-CHECK-memory-profiles-v1.md) fehlt daher
weiterhin. Isolierte Testdaten ersetzen diesen Nachweis nicht. Punkt 07 bleibt
offen, unverändert 8/20. Lokal nach Sicherung ausgerollt, echter Kalenderlauf grün.


Entscheidungsgrundlagen im Tagesbriefing mit Projektkontext verbunden: Die Karte
nennt die Entscheidung und ihr Projekt, die ausführliche Begründung bleibt im
Briefing. Der Link öffnet direkt die gefilterten Projektentscheidungen.
Regression vor Änderung reproduziert; 43 gezielte Briefing-/Kalender-/UI-API-Tests
bestanden. Docker-Browser bei 1521 × 1034 prüft denselben geänderten Wissensstand
in Briefing und Terminvorbereitung, direkten Projektlink und Rücknahme der
Entscheidung über die Oberfläche: Danach verschwindet sie aus beiden aktuellen
Ansichten. UI-Build und Assetmanifest grün, lokal nach Sicherung ausgerollt;
echter Mac-Kalenderablauf danach bestanden. Punkt 11 bleibt für die gemeinsame
Gesamtabnahme offen, unverändert 8/20.


Ortszeit im Briefing korrigiert: Die UI übermittelt automatisch die Browserzeitzone;
der Server berechnet Begrüßung, Tagesauswahl und Terminzeiten darin statt in der
Docker-Zeitzone. Alte API-Aufrufe ohne Parameter behalten ihre bisherige Vorgabe.
Ungültige Zeitzonen werden verständlich abgelehnt. Regression vor Änderung
reproduziert; Sommer-/Winterzeit und Tageswechsel geprüft. 44 gezielte Tests,
UI-Build und Assetmanifest grün. Docker-Browserlauf mit Europe/Berlin und
America/Los_Angeles bestätigt lokale Tageszuordnung und gleiche Terminzeit wie
im Browser. Lokal nach Sicherung ausgerollt, echte Mac-Kalenderanzeige danach
geprüft. Punkt 11 bleibt bis zum Abschluss der gemeinsamen Abnahme offen.


Gesamtprüfung nach der Ortszeitkorrektur (Code-Stand 81ecc23): alle 944
Backendtests bestanden in 149,84 Sekunden, eine Warnung. Protokoll:
`outputs/briefing-current-full-tests.txt` im lokalen Aufgabenordner. Der
Browsercheck an der laufenden App auf Port 8891 bestätigt weiterhin echte
Mac-Kalenderteilnehmer in der Terminvorbereitung. Die Übersicht zu Punkten
07 und 11 ist an die bereits vorliegenden Nachweise angepasst; keine neue
Abnahme und keine Änderung der Zählweise. Gesamtstand bleibt 8/20 = 40 %.

## Abschluss des 50-Prozent-Stands am 8. September

Punkte 11 und 19 sind gemäß ACCEPTANCE-50-PERCENT.md abgeschlossen. Frühere
Offen-Vermerke zu diesen beiden Abnahmen sind damit überholt. 945 Backendtests
bestanden (eine bestehende Starlette-Abkündigungswarnung), Docker-UI-Build und
Assetmanifest bestanden. Nach Sicherung lokal ausgerollt und echter
Mac-Kalender im Browser erneut geprüft. Gesamtstand: 10/20 = 50 %.
Die verbleibenden Punkte 07, 09, 10, 12–17 und 20 bleiben offen.

Datei-Teilausfälle am 8. September verbessert: Ein vorübergehend nicht lesbares
Markdown-/Obsidian-/Notion-/Textdokument wird mit Dateiname und Wiederholhinweis
im bestehenden Aufnahmebericht übersprungen; übrige Dateien werden aufgenommen.
Fehlerhaft codierte Notion-CSV-Dateien brechen den gesamten Lauf ebenfalls
nicht mehr ab. Regression vor Änderung für alle vier Adapter reproduziert;
38 Importtests bestanden. Im fertigen Docker-Image unter dem normalen
App-Benutzer echte Dateirechte entzogen: übrige Aufnahme und erneuter Versuch
nach Freigabe ohne Dublette für alle Adapter bestanden. Nach Sicherung lokal
ausgerollt und echter Mac-Kalender im Browser erneut geprüft. Keine neue
Quellenfreigabe, keine Testdaten im Alltagsbestand. Punkt 10 bleibt offen,
Gesamtstand unverändert 10/20 = 50 %.

Nächstes Ziel: 12/20 = 60 %, vorrangig Quellenverhalten (10) und gemeinsamer
Aufgaben-/Zusagenablauf (12). Noch keine neue Abnahme. Fehlertrennung im
Briefing ergänzt: Ein fehlgeschlagener Gedächtnisabruf lässt gesunde Termine
und Aufgaben sichtbar; fehlende Lese-/Priorisierungsbereiche werden ausdrücklich
und ohne interne Fehlerdetails benannt. Regression reproduziert, 46 gezielte
Tests plus zusätzlicher Bereichsfehlertest bestanden. Geschützter Docker-Browser
bei 1521 × 1034: Fehlerhinweis, sichtbarer Termin, Wiederherstellung nach Neuladen
und Terminvorbereitung geprüft; Screenshot visuell geprüft, keine Seitenfehler.
Browser plugin nicht verfügbar, reguläres Playwright verwendet. Lokal nach
Sicherung ausgerollt und echte Mac-Kalenderteilnehmer erneut geprüft.
Automatische Quellenänderungen und Zusagenerkennung bleiben die offenen
Arbeitspakete; Gesamtstand weiterhin 10/20 = 50 %.

Automatische Datei-Aufnahme meldet Teilausfälle jetzt ehrlich: Lesefehler tragen
neben der Überspring-Begründung einen Fehlerstatus; der Zeitplan benennt bis
zu drei Fehler im vorhandenen Ergebnistext. Nicht unterstützte Formate bleiben
normales Überspringen. Vorher fälschlich erfolgreicher Zeitplan als Regression
reproduziert; 62 Import-/Zeitplantests bestanden. Fertiges Docker-Image als
normaler App-Benutzer mit echten gesperrten Dateien und Wiederholung geprüft:
Fehlerstatus zunächst gesetzt, nach Freigabe erfolgreich, keine Dubletten.
Lokal nach Sicherung ausgerollt und echter Mac-Kalender im Browser geprüft.
Quellenversionierung bleibt offen, keine neue Abnahme; weiterhin 10/20 = 50 %.

Dateiversionen ergänzt: Ein dauerhafter Versionszeiger je freigegebenem Ordner
und Adapterreferenz erkennt veränderte Inhalte bei erneuter Aufnahme. Vor dem
Wechsel werden alter Beleg und abhängige Claims gesperrt; Originaltext bleibt
erhalten, neue Fassung bleibt unbestätigt. API und Zeitplan verwenden denselben
Weg. Schema 3, konkurrierende Schreiboperationen, Neustart und verschlüsselte
Wiederherstellung des Zeigers geprüft. 955 Tests bestanden, Docker-Browser mit
Aussagenverlauf und geöffneter alter Quelle bestanden, Assetmanifest unverändert.
Nach Sicherung lokal ausgerollt, echte Mac-Kalenderteilnehmer und Datenbankintegrität
geprüft. Grenzen einschließlich Altbeständen, Löschungen und identischen Kopien
stehen in SOURCE-VERSIONS-QA.md. Punkt 10 bleibt offen; weiterhin 10/20 = 50 %.

Identische Dateikopien bei neuer Aufnahme getrennt: Inhaltsdigest bleibt korrekt,
Entdopplung gilt je Quelle. Änderung von A sperrt nur ihren Beleg; die bestätigte
Aussage aus B bleibt gültig. Schema-4-Migration erhält eindeutige Altbelege;
mehrdeutige Altzuordnungen werden nicht automatisch umgedeutet. 957 Gesamttests,
gezielt erweiterter Claim-Test und Docker-Browser mit beiden Akten/Originalquellen
bestanden. Lokal nach Sicherung ausgerollt, echter Kalender und DB-Integrität
geprüft. Grenzen und Nachweise in SOURCE-VERSIONS-QA.md. Weiterhin 10/20 = 50 %.

Fehlende Dateiquellen: Nach vollständigem fehlerfreiem Import wird bestätigte
Dateiabwesenheit als Quellenentzug behandelt; Rohtext bleibt im Verlauf,
abhängiges Wissen wird gesperrt. Lesefehler, unvollständiger Lauf und nicht
verfügbarer Quellenordner werden nicht als Löschungen ausgelegt. 71 gezielte
Tests und Docker-Browserprüfung mit unabhängig gültiger Kopie bestanden.
Lokal nach Sicherung ausgerollt, echter Mac-Kalender danach geprüft.
Weitere Fälle sind in SOURCE-VERSIONS-QA.md benannt. Weiterhin 10/20 = 50 %.

Geleerte Dateien und entfernte Notion-CSV-Zeilen werden nach vollständiger
fehlerfreier Aufnahme als entfallene Belege behandelt. Nicht lesbare und zu
große Dateien gelten nicht als geleert. Sechs neue Regressionen zuerst rot,
danach 968 Tests des Projektbestands bestanden; lokale zusätzliche Kopien mit
Suffix „2“ waren vom abschließenden Lauf ausgeschlossen und bleiben unangetastet.
Docker-Browser mit bestätigter Aussage, Leerung, Quellenverlauf, Wiederholung
und unabhängiger Kopie bestanden. Assetmanifest bestanden, lokal nach Sicherung
ausgerollt und echter Mac-Kalender erneut geprüft. Punkt 10 bleibt offen,
Gesamtstand unverändert 10/20 = 50 %.

Metadatenänderungen bei gleichem Text sind jetzt eigene Quellenversionen:
Titel, Teilnehmer, Datum und Schlagworte werden getrennt vom Originaltext-Digest
berücksichtigt. Schema 5 erhält vorhandene IDs und normalisiert gleichwertige
Zeit-/Mengenangaben. Vier Regressionen zuerst rot; 973 Gesamttests bestanden,
inklusive direkter Schema-4-Migration, Neustart und Wiederherstellung. Im
Docker-Browser geänderten Teilnehmer, alten Beleg, fragliche Aussage und
unabhängig gültige Kopie geprüft. Nach Sicherung lokal ausgerollt, Schema 5,
DB-Integrität und echter Mac-Kalender geprüft. Gesamtstand weiterhin 10/20.

Ausgeschlossene Quellen können in ihrer Originalansicht ausdrücklich wieder
zugelassen werden. Rohtext wird erneut prüfbar, altes Wissen bleibt fraglich;
ersetzte Fassungen bleiben gesperrt. 977 Tests, UI-Build, Assetmanifest und
Docker-Browser bei zwei Desktop-Größen bestanden, einschließlich Abbrechen,
Fehler/Wiederholen und aktualisierter Dateiliste. Vorhandene mobile Mindestbreite
als Einschränkung dokumentiert. Lokal nach Sicherung ausgerollt, echter
Mac-Kalender geprüft. Mail und gemeinsame Quellenabnahme bleiben offen; 10/20.

Mailquellen sind nun anhand von Konto und serverseitiger Nachrichtenkennung
getrennt. Gleicher Text/Message-ID vereinigt keine unabhängigen Belege mehr.
Erneute Aufnahme geänderter Mails sperrt frühere Aussagen, die Oberfläche
unterscheidet geänderte, bekannte und ausgeschlossene Fassungen. Quellenentzug
während manueller Aufnahme verhindert Schreiben. 980 Tests, UI-Build,
Assetmanifest und Docker-Browser bestanden. Nach Sicherung lokal ausgerollt,
echter Mac-Kalender und DB-Integrität geprüft. Gemeinsame Quellenabnahme bleibt
offen, Gesamtstand weiterhin 10/20 = 50 %.

Gemeinsame Quellenabnahme abgeschlossen: Ausschluss ist jetzt direkt in jeder
Originalansicht einer Episode erreichbar, ohne doppelte Aktion in der Dateiliste.
Nach Bestätigung wird die Akte aktualisiert. Abbrechen, Fehler/Wiederholen,
Wiederzulassung ohne alte Wissensbestätigung, erneuter Ausschluss und unabhängiger
Beleg im Docker-Browser bestanden. 137 gezielte Abnahmetests inklusive expliziter
Kalenderänderung/-löschung bestanden; der Backend-Gesamtstand zuvor 980 Tests grün.
UI-Build und Assetmanifest bestanden, nach Sicherung lokal ausgerollt und echter
Mac-Kalender erneut geprüft. Punkt 10 erfüllt: **11/20 = 55 %**.
Nächstes Ziel für 60 % bleibt die vollständige gemeinsame Abnahme von Punkt 12.

8. September: Punkt 12 gemeinsam abgenommen; **12/20 = 60 %**. Nachweis und verbleibende acht Punkte: [ACCEPTANCE-COS.md](ACCEPTANCE-COS.md).
