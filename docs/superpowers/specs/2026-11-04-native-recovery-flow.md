# Wiederherstellung im Mac-Produktweg

Anschluss an die geprüfte Arbeitskopie `93698ef`. Kein neuer Datenspeicher und
keine automatische Zusammenführung historischer Stände.

## Bedienung

App-Menü „Sicherung wiederherstellen …“: Datei auswählen, Sicherungspasswort in
einem sicheren Eingabefeld eingeben, getrennten Zielordner wählen. Die laufende
persönliche App bleibt geöffnet und unverändert. Lokale passende App-Version
verwenden; kein Download im Hintergrund.

Ein eigenes Fenster zeigt nach der Entschlüsselung den Prüfbericht: vorhandene
Daten, ungeklärte Bereiche und auswählbare Sicherungs-/Vergleichsstände. Details
sind aufklappbar. Keine Vorauswahl eines vermeintlich neuesten Vergleichsstands.
Vor „Arbeitskopie öffnen“: gewählten Stand nennen, fehlende Bereiche sichtbar
lassen, frische Verbindungen erklären und unbekannte spätere Änderungen
ausdrücklich bestätigen. Ungeklärte vorhandene Dateien sperren den Schritt.

Die Arbeitskopie öffnet dieselbe gebaute Kingfisher-Weboberfläche in einem eigenen
nativen Fenster. „Arbeitskopie öffnen …“ im App-Menü öffnet sie später erneut.
Ein Fehlschlag lässt die entschlüsselte Sicherung und vorbereitete Arbeitskopie
erhalten und bietet einen verständlichen erneuten Versuch. Keine generelle
App-Freigabe oder unbemerkte Umstellung des persönlichen Bestands.

## Technischer Anschluss

Ein gebündelter Hosthelfer `recovery_native.py` arbeitet per geschlossenem
JSON-Auftrag auf stdin. Passwort steht niemals in Argumenten, Logs oder
Ergebnistext. Operationen: `extract`, `inspect`, `prepare`, `open`. Alle
Dateipfade stammen ausschließlich aus nativen Dateidialogen und den daraus
erzeugten Zuständen, nicht aus fremden Webnachrichten.

- Docker und das lokal installierte, auf sha256 gepinnte App-Image werden von
  der nativen App übergeben. Fähigkeitenprüfung vor Extraktion/Arbeitskopie.
- Datenarbeit in kurzlebigen Containern ohne Netzwerk, nur explizite Mounts.
  Originale readonly; neues Ziel außerhalb der historischen Daten. App-Image
  enthält die vorhandenen `recovery_bundle`/`recovery_preflight`/`recovery_workspace`
  Funktionen; keine zweite Implementierung von Datenmigration oder Rechte-Reset.
- Arbeitskopienpfade bleiben zwischen Vorbereitung und Start identisch. Neue
  Container erhalten nur die eigene Arbeitskopie als schreibbaren Bind-Mount,
  keinen Docker-Socket, fremde Konten oder persönlichen Bestand.
- Der normale Server startet über den sauberen Arbeitskopien-Launcher. Ein
  ausdrücklicher Container-Modus bindet intern an 0.0.0.0; der Host veröffentlicht
  ausschließlich einen gewählten Loopback-Port. UI stammt aus dem festen
  Image-Assetpfad, nicht aus geerbten UI-Umgebungsvariablen.
- Wiederöffnen validiert Besitzer, Image, Mount und Port statt irgendeinen
  gespeicherten Containernamen blind zu starten. Fehlerbereinigung entfernt nur
  nachweislich neu erzeugte Container; niemals Quellen, Arbeitskopien oder
  vorhandene Container. Keine externen Modell-/OAuthaufrufe bei der Vorbereitung.

## Prüfung und Grenzen

Geschlossene Aufträge, Pfad-/Zielkonflikte, Passwortschutz, veränderte Berichte,
Wiederöffnen und Fehlerbereinigung mit simulierten Dockergrenzen prüfen. Native
Zustands-/Auswahllogik separat testen und vollständige App kompilieren. Danach
isolierter Containerablauf mit künstlichen Daten, sofern verfügbar. Echte
Fensterprüfung erst nach der noch ausstehenden konkreten Test-App-Freigabe;
kein Browserwechsel als Umweg. Bis dahin keine visuelle Abnahme behaupten.

Lokale Kalender-/Updatebrücken der separaten Arbeitskopie werden nur dann
angeboten, wenn sie an genau diese Instanz gebunden sind. Kein Rückfall auf
den persönlichen Hauptdienst. Neue OAuth-/Modellverbindungen benötigen wie
bisher die sichtbare Einrichtung. P5/Nutzungswoche bleiben bis zur tatsächlichen
Mac-Abnahme offen.

## Getrennte Fenster und Entwürfe

Ein eigener persistenter WebKit-Datenspeicher ab macOS 14 trennt Cookies und
Website-Daten von der Haupt-App. Ältere Systeme verwenden einen nichtpersistenten
Speicher. Der bestehende Gesprächsentwurf liegt in sessionStorage und bleibt
auch mit persistentem Datenspeicher nicht zuverlässig über ein neues Fenster
erhalten. Deshalb gibt es auf allen unterstützten macOS-Versionen vor Schließen
oder Beenden einen ausdrücklichen Entwurfshinweis; gespeicherte Daten bleiben.

„Neu laden“ folgt ausschließlich dem aktiven Fenster. Während einer nativen
Auswahl oder noch laufenden Vorbereitung ist die Aktion deaktiviert. Es gibt
keinen Rückfall auf die persönliche Haupt-App. Die Auswahl des lokalen
Docker-Sockets wird vor jedem Ablauf geprüft und für alle Schritte fest gebunden.
