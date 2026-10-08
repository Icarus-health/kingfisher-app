# ChatGPT-Abo und begrenzte Gedächtnispakete

## Verhalten

Unter **Einstellungen → KI → ChatGPT für dein Gedächtnis** kann ein berechtigtes
ChatGPT-Konto über den öffentlichen OAuth-Weg verbunden werden. Anmeldung,
Modellwahl und Freigabe konkreter Mails sind getrennt. Der Modellkatalog kommt
vom angemeldeten Konto; kein kostenpflichtiger API-Ersatz und kein privater
ChatGPT-Endpunkt. Diese Vorschaufunktion verbraucht ChatGPT-Kontingent und ist
kein unbegrenzter Zugang. Die normale lokale Hintergrundautomatik bleibt separat.

- **100 Mails prüfen:** umfasst auch bereits lokal eingeordnete Originalmails.
  Eine vollständig verarbeitete Probe ist technische Voraussetzung für Bulk;
  zusätzlich soll der Nutzer die Ergebnisse gegen Originale prüfen.
- **Größeren Bestand vorbereiten:** höchstens 1.000 freigegebene Mails pro Paket.
  Anfragebudget: vier Aufrufe × erlaubte Paketgröße, keine automatische Fortsetzung
  nach Paketende. Bereits aktuell cloudbearbeitete Quellen werden übersprungen,
  wenn beide Einordnungsschichten vollständig sind.
- **Bestehende Einordnung nachprüfen:** ersetzt abgeleitete Einordnung gezielt.
  Originaltexte, Quelldaten und bestätigte Themenkorrekturen bleiben erhalten.
  Dies ist eine ausdrücklich gestartete Nachprüfung, keine neue periodische
  Cloud-Automatik.
- Große Bestände werden über stabile Speicherseiten mit höchstens 2.000
  untersuchten Quellen je Vorschauanfrage erreicht. Der Umfang ist sichtbar;
  die Oberfläche überspringt höchstens vier leere Bulk-Seiten pro Aktion und
  bietet danach die nächste Seite an. Eine Seite mit offenen Kandidaten bleibt
  erhalten, damit die noch nicht ausgewählten Quellen nicht verloren gehen.
- Pause, Widerruf, Kontowechsel, geänderte oder entzogene Quelle verhindern
  weitere Verarbeitung beziehungsweise das Speichern veralteter Ergebnisse.
  Eine bereits begonnene Übertragung kann nicht rückgängig gemacht werden.
  Kontingent-/Verbindungsunterbrechungen bleiben fortsetzbar; ein Dienstneustart
  setzt keinen Cloudlauf selbsttätig fort.

Service-, Abrechnungs- und Benachrichtigungspostfächer werden nicht mehr als
Menschen projiziert. Ausdrücklich bestätigte Gruppen bleiben erhalten und sind
rückgängig zu machen. **Gedächtnis → Menschen → Prüfen** zeigt zusätzlich
„Erwähnte Menschen · Quellenhinweise“ mit Originalzitaten. Diese Namen werden
nicht automatisch mit Identitäten verschmolzen. Der Ausschnitt ist auf 500
Quellen und höchstens 200 Hinweise begrenzt; fehlendes Quelldatum wird nicht als
aktuelles Ereignis ausgegeben.

## Ursprüngliche Funktionsprüfung

- Abschließender Lauf: 308 betroffene Backendtests bestanden: OAuth/Provider/Cloudjobs, Kategorien,
  Arbeitsgedächtnis, Personen, Mailintake, Sicherung und vollständige getrennte
  Wiederherstellung. Eine vorhandene Starlette-Abkündigungswarnung.
- Frontend-Build und 358 Frontendtests bestanden. Vorhandener Hinweis auf große
  JavaScript-Bündel, kein Buildfehler.
- Synthetischer Integrationstest verbindet signierte Anmeldung, öffentlichen
  Responses-Stream und beide Gedächtniseinordnungen; kein echter OpenAI-Aufruf.
- Unabhängiges Review fand einen Freigabe-Randfall bei verzögerter
  Anfragevorbereitung. Nachkorrektur: Prüfung direkt vor Anfragebeginn, während
  des Streams und vor Ergebnissen; gezielte Regression verhindert Übertragung
  nach einer Pause während der Tokenvorbereitung. Nachprüfung ohne weiteren
  konkreten Blocker in diesem Umfang.
- Weitere Regressionen: Tokenrotation/Widerruf, manipulierte OIDC-Identität,
  unvollständige/zu große Streams einschließlich fehlendem Zeilenende,
  Kontingentende auch bei der zweiten Einordnung, kein doppelter Worker nach
  Pause, Quellenänderung, manuelle Korrektur und Paging ohne ausgelassene Quellen.
- Damaliger Prüfstand ohne vollständige grüne Gesamtsuite: ein abgebrochener breiter
  Zusatzlauf traf Sandbox-Socket-/Gerätemessungsfehler sowie einen bereits in
  HEAD vorhandenen Datumsparser-Vertrag. Der durch die neue Sicherungsdatei
  betroffene vollständige Wiederherstellungstest wurde ergänzt und besteht im
  oben genannten Abschlusslauf. Keine GitHub-CI-Wiederholung.

Dieser technische Stand belegt keine fehlerfreie Extraktion, Identitätsauflösung
oder Antwortqualität im persönlichen Bestand. Die echte Anmeldung und die
begrenzte Mailprobe sind unten von den künstlichen Tests getrennt dokumentiert.

## Installierter Mac und echte Probe

**Aktueller Prüfstand:** Der unten beschriebene Lauf ist inzwischen beendet:
100 Quellen durchgesehen, 48 in beiden Schichten vollständig, 37 ungültige
Entitätsantworten und 15 Verarbeitungsgrenzen. Das Arbeitsgedächtnis ist bei
99 Quellen vollständig. Der große Lauf bleibt gesperrt. Die abschließende,
auch inhaltliche Prüfung steht in [pilot100-pruefung.md](pilot100-pruefung.md).
Die aktuelle Mac-Fassung ist **1.0.6-local.83da66f** mit vier Gedächtnisbereichen,
getrennter Absenderidentität, weniger Suchrauschen und modellfreier wörtlicher
Quellenanzeige. Die Offline-Abrufprüfung, ihre offenen Umschreibungsschwächen
und die tatsächlichen Mac-Bedienproben stehen in [abrufpruefung.md](abrufpruefung.md).
Die erneute Nachprüfung derselben sieben Mails mit der zuvor installierten
Fassung `160cfd7` bestand beide Schichten bei allen sieben Quellen, mit 22 Modellanfragen
und 145 geprüften Originalbereichen. Das ersetzt keine erfolgreiche 100-Mail-
Qualitätsprobe; der große Lauf bleibt gesperrt. Verhalten, Migration, Sicherung,
Bedienprüfung und Tests stehen in [bereiche-und-absender.md](bereiche-und-absender.md).
Die vorherige Fassung `0b56993` hatte bei sieben Quellen drei vollständige
Kategorienauswertungen und vier abgewiesene Absenderrollen bei 21 Anfragen.
Die folgenden Momentaufnahmen dokumentieren den früheren Zwischenstand.

Zuvor installiert war **1.0.6-local.e882740**, Code
`e8827400bf211152dff8b7ec98a1dd7a315cb308`. Das unveränderte native ausführbare
Programm wurde mit aktualisierten Versionsangaben wiederverwendet und das Bündel
erneut lokal signiert; kein neuer universeller Mac-Build wird behauptet. Der
Container wurde aus einem sauberen Git-Archiv gebaut, ohne private Daten im
Buildkontext. Datenvolume und ausschließlich lokale Portbindung bleiben gleich.

Vor dem Austausch sind App, private Konfiguration und vollständiges kaltes
Datenvolume außerhalb des Repositorys gesichert. Die 340 Originalquellen haben
unveränderte Digests; 0 Aufgaben und 2 Gespräche blieben erhalten. 17 SQLite-Dateien
bestanden `quick_check`. Private Einstellungen blieben bis auf die Bildfassung
gleich. Die lokale Modellauswertung war und bleibt ausgeschaltet; der Mailabruf
selbst ist **nicht** pausiert. Eine bestehende Importpause wird daher nicht
behauptet.

Im echten nativen Fenster geprüft: KI-Einstellungen, nicht vorangekreuzte
Datenfreigabe, Metadatenvorschau ohne Übertragung, Modellwahl und Arbeitsstand.
Die ChatGPT-Anmeldung wurde im Browser abgeschlossen; die App bestätigt
Abo-Nutzung und lädt den tatsächlichen Modellkatalog. Ein Ausleseversuch einer
unbeteiligten Safari-Sitzung wurde von der Freigabeprüfung abgewiesen und nicht
umgangen. Die Verbindung ist durch den App-/API-Status und echte Modellantworten
nachgewiesen, nicht durch Auslesen dieser Sitzung.

Die native Menschenansicht zeigte zunächst noch zusammengesetzte Serviceadressen.
Eine gemeinsame, begrenzte Regel nimmt diese aus Personen und Duplikatvorschlägen
heraus; persönliche Namenbestandteile und ausdrücklich bestätigte Gruppen bleiben
erhalten. Die Standardansicht änderte sich im bestehenden Bestand von 119 auf 112
Einträge, ohne Originale zu löschen. Das bereinigt bekannte Postfachmuster, nicht
alle möglichen Organisationen oder falsch beschrifteten Absender.

Der erste echte 100-Mail-Lauf stoppte nach zwei Modellaufrufen bei Quelle 1:
Arbeitsgedächtnis vollständig, Kategorienphase fehlgeschlagen. Der ursprüngliche
Fehler wurde nicht gespeichert, daher ist seine genaue Ursache nicht nachgewiesen.
Eine zusätzliche, ausdrücklich begrenzte Diagnoseanfrage für dieselbe freigegebene
Quelle bestand (zwei Themen- und zwei Entitätsbelege); sie schrieb keine Ableitungen.

Die Korrektur verlangt bei ChatGPT keine berechneten Zeichenpositionen mehr:
Modell liefert Block-ID und exakten Namen, Code bestimmt nur bei eindeutigem
Originalvorkommen die Position. Fehlende, erfundene oder mehrdeutige Belege werden
verworfen. Einzelne ungültige Kategorienantworten und zu umfangreiche Quellen
erzeugen dauerhafte, begrenzte Prüfhinweise mit Originalquellenzugriff; sie stoppen
nicht alle weiteren Quellen. Konto-, Kontingent- und Transportfehler bleiben davon
getrennt. Auch Überschneidungen, Unicode-Positionen, Wiederherstellung und die
Begrenzung auf zehn ausgegebene Hinweise sind geprüft. Vorhandene gültige
Kategorieergebnisse werden bei einem Fehlversuch nicht überschrieben.

Der korrigierte 100-Mail-Lauf mit `gpt-6.1-sol` wurde am 08.10.2026 um 10:57 Uhr
Ortszeit ausdrücklich über den geprüften Freigabefluss gestartet. Die erste Quelle
bestand beide Einordnungsschritte. Eine Momentaufnahme währenddessen zeigte
135,9 MiB für den Kingfisher-Container und 0,37 % CPU; das misst weder Docker-VM
noch andere Anwendungen und ist kein ganztägiger Akkuvergleich. Der größere
Cloudlauf ist nicht freigegeben oder gestartet.

Zwischenstand vor Übergabe: **16/100 durchgesehen, 10 vollständig, 6 offene
Prüffälle, 35/400 Modellaufrufe**. Der Arbeitsgang läuft auf dem Mac weiter und
endet am Paket-/Anfragebudget oder pausiert bei einem Kontingentproblem. Kein
vollständiger oder inhaltlich bestandener 100-Mail-Test wird behauptet. Eine
Kontrolle der ersten acht vollständig eingeordneten Quellen fand 28 Entitäts-
und 13 Themenbelege im jeweiligen Original wieder. Auch dieser Belegabgleich
prüft nicht, ob das Modell jede Aussage semantisch richtig verstanden hat.
Die offene Liste einschließlich Originalquellen-Schaltflächen ist im nativen
Fenster sichtbar geprüft. Der temporäre Agent-Monitor wurde beendet; es gibt
keine neue Codex-Automation oder spätere automatische Qualitätsabnahme.

Vor einem großen Lauf fehlen die vollständige Auswertung dieser Probe und die
Prüfung der offenen Fälle. Regelmäßige unbeaufsichtigte Gedächtnispflege und
ChatGPT als allgemeiner Gesprächsanbieter sind durch diesen Ausbau nicht
aktiviert. Die neue Cloudanbindung ist auf ausdrücklich gestartete
Gedächtnisarbeit begrenzt; Ollama war bei der Prüfung nicht erreichbar.

## Referenzen

- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
- https://developers.openai.com/siwc/ui-ux-guidelines

Die Preview-Schnittstelle unterstützt keinen `max_output_tokens`-Parameter.
Kingfisher begrenzt daher Anfragezahl, Quelldaten, gelesene Streambytes und
Antworttext lokal, nicht über ein zugesichertes serverseitiges Tokenbudget.
