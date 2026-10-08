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

## Prüfung

- 291 betroffene Backendtests bestanden: OAuth/Provider/Cloudjobs, Kategorien,
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
- Keine vollständige grüne Gesamtsuite behauptet: ein abgebrochener breiter
  Zusatzlauf traf Sandbox-Socket-/Gerätemessungsfehler sowie einen bereits in
  HEAD vorhandenen Datumsparser-Vertrag. Der durch die neue Sicherungsdatei
  betroffene vollständige Wiederherstellungstest wurde ergänzt und besteht im
  oben genannten Abschlusslauf. Keine GitHub-CI-Wiederholung.

Eine echte Anmeldung, Kontoberechtigung und Verarbeitung persönlicher Mails
bleiben getrennte Prüfungen. Dieser technische Stand belegt keine fehlerfreie
Extraktion, Identitätsauflösung oder Antwortqualität im persönlichen Bestand.
Die 100-Mail-Probe muss diese Qualität erstmals sichtbar prüfen.

## Referenzen

- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
- https://developers.openai.com/siwc/ui-ux-guidelines

Die Preview-Schnittstelle unterstützt keinen `max_output_tokens`-Parameter.
Kingfisher begrenzt daher Anfragezahl, Quelldaten, gelesene Streambytes und
Antworttext lokal, nicht über ein zugesichertes serverseitiges Tokenbudget.
