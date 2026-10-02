# Schnell nutzbarer Prototyp mit vorhandenem Mac-Bestand

Stand: 7. September 2026. Priorität ist ein kleiner täglich nutzbarer Ablauf,
bevor der vollständige Icarus-Funktionsumfang abgenommen ist.

## Vorhandenes nutzen

1. **Gespräch:** Installierte Ollama-Modelle im Dropdown anzeigen. Ein bereits
   gespeichertes Modell erhalten; das im Prototyp geprüfte `qwen3.5:4b` nur dann
   vorauswählen, wenn es tatsächlich installiert ist. Ein Klick speichert und
   testet. Keine automatischen Downloads oder ungefragten Verbindungen.
2. **Sprache jetzt:** MacWhispers Diktierfunktion kann Text in ein fokussiertes
   Eingabefeld schreiben. Das ist der erste Weg für Spracheingabe in Kingfisher;
   eine eigene Mikrofonaufnahme ist dafür nicht erforderlich. Den tatsächlichen
   Diktiervorgang muss der Nutzer mit seinem Mikrofon testen.
3. **Kalender als nächster Adapter:** EventKit über einen kleinen lokalen
   macOS-Prozess, der erst nach Systemfreigabe Kalender anbietet. Anschließend
   wählt der Nutzer die freigegebenen Kalender. Vorhandene Konten werden über
   das Betriebssystem genutzt; Passwörter werden nicht kopiert.
4. **Eigene Spracherkennung später:** Derselbe macOS-Prozess kann eine geprüfte
   WhisperKit-Laufzeit anbinden und ausdrücklich ausgewählte vorhandene
   Core-ML-Modelle laden. Die Linux-Docker-App kann sie nicht direkt ausführen.
   Vor Wiederverwendung Vollständigkeit, Tokenizer und Modell-/Runtime-Lizenz
   prüfen. Ein vorhandener Ordner ist kein Transkriptionsnachweis.
5. **Mail:** Keine generelle Übernahme fremder App-Zugangsdaten. Entweder einen
   nachweislich unterstützten Mail-App-Zugriff mit Freigabe nutzen oder den
   bestehenden Kontoassistenten auf Mailadresse, Anbietererkennung und den
   nötigen OAuth-/App-Passwort-Schritt reduzieren.

## Begrenzte Erkennung

`scripts/discover_mac.py` läuft auf dem Mac und prüft ausschließlich Ollamas
Loopback-Modellliste sowie bekannte MacWhisper-App-/Modellordner. Es durchsucht
keine Mails, Termine, Transkripte oder beliebigen Benutzerordner und liest
keine Schlüssel. Das Ergebnis unterscheidet vorhanden, unvollständig und
noch benötigte Laufzeit. Es importiert nichts und verbindet nichts.

Dies ist ein erster prüfbarer Host-Baustein, noch kein in Docker integrierter
Mac-Connector. Die Einstellungen erkennen bislang Ollama direkt über den
bestehenden Host-Zugang. Der künftige Connector braucht eine lokal begrenzte,
authentifizierte Schnittstelle, explizite Freigaben und klare Entzugsmöglichkeiten.

## Gedächtnis und Oberfläche

Cognee ist im übernommenen Icarus-Code als optionaler semantischer Index
vorhanden. SQLite bleibt der verbindliche Bestand. Die Kingfisher-Graphansicht
ist eigener React-/SVG-Code; ein anderer Suchindex repariert deren Layout nicht.

Die erste visuelle Korrektur nutzt die vorhandenen Assets: Vogel und Beschriftung
überlagern sich nicht mehr; SVG-Kanten und Knoten verwenden denselben Koordinatenraum;
Knoten sind kompakte Kreise mit begrenzter Beschriftung. Nicht mehr nutzbare
Claim-Knoten werden nur in der Profilhistorie gezeigt, nicht als aktuelles Wissen. Die Navigation heißt
„Aufgaben“, die bisherigen URLs bleiben erreichbar. Eine umfassende Neugestaltung
und vollständige Profilakten bleiben separat zu prüfen.

## Kleine Prototyp-Abnahme

- Ein lokales Modell verbinden und ein Gespräch nach Neustart fortsetzen.
- Eine ausdrücklich genannte Information als Vorschlag prüfen, bestätigen und
  wieder widerrufen; keine automatische Faktbestätigung.
- Eine echte eigene Aufgabe anlegen und abschließen.
- MacWhisper-Diktat im Gesprächseingabefeld selbst testen.
- Danach einen freigegebenen echten Kalender ins Tagesbriefing aufnehmen.

Die ersten technischen Tests sind keine persönliche Alltagsabnahme. Kostenlose
Wetter-/Nachrichten-APIs und der übrige Vollumfang sind nachgelagert; die
bestehende 20-Punkte-Release-Roadmap bleibt erhalten.

## Primärquellen

- https://docs.macwhisper.com/article/14-how-to-use-the-dictation-feature
- https://github.com/argmaxinc/argmax-oss-swift
- https://app.argmaxinc.com/docs/guides/managing-models
- https://developer.apple.com/documentation/eventkit/accessing-the-event-store
