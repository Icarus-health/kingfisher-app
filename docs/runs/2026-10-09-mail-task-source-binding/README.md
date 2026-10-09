# Mail-Aufgaben bleiben an die tatsächlich gelesene Quelle gebunden

Produkt-/Teststand: `e21193d3eefb772ff4cf6b80da5d8c16800b9ebb`, Basis `1af3037`. Lokales Paket `1.0.6-local.e21193d`, Image `sha256:c6bc20a9a39f8759dc7f987462378e41c109afb6b87d754555c14dc3d557176b`.

## Reproduzierter Fehler und Verhalten

Beim manuellen Anlegen einer Aufgabe sandte das Mailformular keinen Fingerabdruck der geöffneten Nachricht. Änderte sich die Quelle zwischen Öffnen und Speichern, konnte eine alte Bitte mit dem neuen, etwa widerrufenen Originaltext verknüpft werden. Die unabhängige künstliche Reproduktion lieferte vor der Korrektur HTTP201; dieselbe Anfrage mit dem alten Fingerabdruck bereits korrekt409.

Jetzt senden manuelle Aufgaben stets den Fingerabdruck der geöffneten Mailfassung. Fehlt er oder passt er nach einer Aktualisierung nicht mehr, blockiert bereits das Formular und erhält die Eingaben. Der Server verlangt ihn ebenfalls und prüft die aktuelle Mail vor Quellenaufnahme und Aufgabenanlage. Eine Änderung nur des Quellenzeitpunkts oder des Vollständigkeitsstatus zählt ebenfalls als Quellenänderung. Unveränderte Quellen lassen manuelle Aufgaben ohne Modellzitat zu.

Die bereits veröffentlichte Einmal-Kennung direkt übernommener Vorschläge bleibt kompatibel: Eine bereits vorhandene identische Aufgabe wird nach diesem Update nicht allein durch die erweiterte Fingerabdruckformel dupliziert. Diese Kennung wird ausschließlich nach der neuen Aktualitätsprüfung und dem bestehenden Zeit-/Zitatvertrag benutzt.

## Prüfungen

- Die roten Gegenproben reproduzierten fehlende Bindung, Datums-/Vollständigkeitsänderung und den zunächst entstehenden Kompatibilitätsfehler. Die endgültigen Tests bestehen; Details im unabhängigen Review. Die Gruppen sind nicht additiv.
- 401 Oberflächenprüfungen und Produktionsbuild bestanden. Drei neue Tests kompilieren den tatsächlichen TSX-Handler mit dem vorhandenen Buildwerkzeug und führen ihn mit isoliertem Hookzustand aus. Das ist keine gerenderte Browser- oder native Fensterabnahme.
- Das fertige Image wurde ohne Netzwerk, persönliche Daten, Modelle oder App-Lifespan geprüft. Exakte264 Python-Dateien und112 UI-Dateien; keine alten UI-Assets. Die künstlichen API-Fälle Körper/Datum/Vollständigkeit blockieren mit409 ohne Quellen-/Aufgabenwrite; eine frische manuelle Aufgabe liefert201 mit korrekter Originalquelle.
- Breite lokale Regression: **6.364 bestanden,3 übersprungen,32 Subtests bestanden**,858,72 Sekunden. Der erste Gesamtlauf wurde wegen vom Sandboxmodus gesperrter künstlicher lokaler UDP-/HTTP-Dienste abgebrochen. Der unveränderte Lauf wird mit erlaubten Testverbindungen ausgeführt; keine gelockerten Produkttests.

## Mac und Speicher

Das Update ist zunächst vorbereitet, noch nicht als installiert behauptet. Ein eng geprüftes Archivwerkzeug hat genau drei ältere Sicherungsduplikate aus Docker entfernt, nachdem jede Datei mit dem vollständigen bestehenden Mac-Archiv bytegleich abgeglichen wurde. Das Hostarchiv und die jüngste Live-Sicherung bleiben erhalten. 110.966.385 Bytes wurden frei, beide nativen Update-Reserveprüfungen bestehen;344 Originale,17 Datenbanken, Einstellungen und Pause bleiben unverändert. Das ist keine Kapazitätsfreigabe für den großen Mailimport.

Die persönliche Aufnahme bleibt pausiert; produktives Ollama bleibt aus. Keine Cloudfreigabe, Kosten, Modellbeschaffung oder private Testuploads. Der noch ausstehende BGE-Cache-Ersatz und die native Bedien-/Akkuabnahme sind davon getrennt. Keine Aussage, dass der gesamte CoS fertig oder fehlerfrei ist. GitHub-Actions werden wegen des bekannten Minutenlimits nicht gestartet.
