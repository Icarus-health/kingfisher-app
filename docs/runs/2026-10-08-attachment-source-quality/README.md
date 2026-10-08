# Mailanlagen: belegbarer Inhalt, Lücken und Quellenentzug

## Reproduzierter Fehler

Ein bestätigter Fakt aus einer PDF-Anlage blieb im Antwortkontext verfügbar, nachdem die zugehörige Mail ausgeschlossen oder durch eine Fassung ohne Anlage ersetzt wurde. Anlagen hatten unabhängige Quellenzeiger ohne Bindung an die konkrete Mailfassung. Ein gemischtes PDF mit Text- und Scanseite hieß außerdem „gelesen“, obwohl die Scanseite fehlte. Bei einer langen einzelnen Textzeile ging der Anfang verloren; nach einer exakt ausgeschöpften ersten Seite konnte ein negatives Zeichenbudget fast die ganze Folgeseite übernehmen.

Die unabhängige Gegenprüfung fand weitere Abwesenheitsfehler: namenlose Anlagen und beschädigte MIME-Strukturen erschienen als „keine Anlagen gefunden“. Ein unvollständiger Wiederholungsabruf konnte eine zuvor vollständig gespeicherte Anlage durch einen ungelesenen Platzhalter ersetzen. Beim begründeten Entzug blieb der Metadatendigest hinter den neuen Tags zurück; der Quellen-Snapshot war danach inkonsistent.

## Änderung

Neue Anlagen tragen die exakte Eltern-ID zusätzlich zum bisherigen Mail-/Anlagen-Schlüssel. Gemeinsame SQL- und Snapshot-Prüfung verlangen eine aktuelle, zugelassene Elternfassung. Bei Altanlagen ohne Bindung wird nur eine einzige vorhandene Mailfassung akzeptiert; mehrdeutige Altbestände werden nicht auf eine neue Mail umgedeutet. Ausschluss, Quellenwechsel und Berichtigung entziehen auch Kinder, ihre Berichtigungen und davon abhängige bestätigte Aussagen. Wiederzulassung der Mail öffnet ihre Anlagen nicht automatisch.

Ein begrenzter Eltern-Fingerabdruck bindet Identität, Textdigest, Quellenzeiger und Ausschlussstatus. Reine Abrufberichte entwerten den unveränderten Inhalt einer Anlage nicht. Nicht betroffene Quellen behalten ihre bisherigen Fingerabdrücke. Begründete Zustandsänderungen führen den Metadatendigest korrekt nach.

Der vorhandene Parser behält höchstens fünf unterstützte Anlagen, 30 Seiten, 5 MiB und 60.000 Zeichen Inhalt je Anlage. Das nichtnegative Zeichenbudget umfasst Seitentrenner und erhält den Beginn langer Absätze. Fehlende Texte, Seiten- oder Zeichenlimits sowie ungelesene Anlagen erhalten `source:truncated`. OCR-erfolgreiche und weiterhin leere Seiten werden getrennt betrachtet.

Ein begrenzter Abrufbericht an der Mail zählt lesbare/teilweise/ungelesene Dateien, ausgelassene Anlagen, nicht unterstützte Formate, namenlose Teile und MIME-Fehler. Der Originaltext bleibt unverändert. Ein normaler Mailaufruf ohne Anlagenprüfung löscht diesen Bericht nicht. Nur ein vollständiger, eindeutig zugeordneter MIME-Abruf ohne Anlagenlimit darf Abwesenheit ableiten. Bei unvollständigen oder unbekannten Wiederholungsabrufen bleiben die vorherigen vollständigen Quellen erhalten; der Bericht nennt die Grenze.

Die Einrichtung beschreibt den Anlagenumfang je Leser: IMAP kann begrenzt PDFs/Dokumentbilder lesen; der bestehende Microsoft-Graph-Leser liest weiter nur Mailtext. „Unterstützt“ bezeichnet eine Fähigkeit, keinen nachgewiesenen vollständigen Bestand. Die Quellenansicht nennt unvollständige Erfassung oder fehlende Anlagenprüfung und öffnet gespeicherte Anlagen direkt. Ausgeschlossene historische Anlagen bleiben als solche einsehbar.

## Prüfung

Die neuen Regressionen verwenden echte temporäre Stores, ausdrücklich bestätigte künstliche Fakten, den realen PDF-Unterprozess, FTS-/Originalsuche und den Antwortkontext. Keine echten Konten, Cloudmodelle oder OCR-Modelle wurden aufgerufen. Sieben zunächst rote Parser-/Berichttests und die unabhängigen Vorher-Reproduktionen belegen den Ausgangsfehler; zusätzliche Kontrollfälle schützen vollständige Wiederholungen, Teilabrufe und gespeicherte Originale.

46 enge Parser-/Lifecycle-/Intakeprüfungen, 125 gesonderte Quellenregressionen, 391 Oberflächenprüfungen und der Produktionsbuild bestehen. Der erste breite Lauf wurde wegen fehlender Mac-/Loopback-Rechte abgebrochen; 112 isolierte Prüfungen bestehen mit den nötigen Rechten. Ein vollständiger Lauf des finalen Stands sowie Paket-/Installationsnachweise folgen vor der Übernahme.

## Grenzen

Das sind Textabdeckung und Quellenberechtigung, keine Garantie fehlerfreier OCR oder vollständiger Bildinterpretation. Eine Seite mit Text kann zusätzlich bedeutungstragende Bilder enthalten. Nicht unterstützte Formate und Anlagen über den Grenzen bleiben offen. Alte Mails ohne Abrufbericht werden nicht nachträglich als vollständig geprüft bezeichnet. Die gespeicherte Anlagenquelle ist die extrahierte Textfassung; eine unveränderte PDF-Binärablage mit Download ist hier nicht neu gebaut.

Alte Berichtigungen eines Anhangs enthalten einen früheren Ziel-Fingerabdruck ohne Elternbindung. Sie bleiben gespeichert, werden aber vorsichtig ungültig; diese Lieferung migriert oder bestätigt sie nicht automatisch. Korrektur-Ahnen werden auch im SQL-Suchgate begrenzt verfolgt; der finale Integritäts-Snapshot bleibt unabhängig Pflicht.

Die bestehende lokale OCR hat weiterhin eigene Laufzeit-/Ressourcenlimits; ein großer persönlicher Anlagenbestand ist hier weder als vollständig eingelesen noch als schnell abgenommen. Die Bedienung auf dem gesperrten Mac und die ausdrücklich nicht freigegebene Browserprüfung bleiben offen; die Sperre wird nicht durch einen anderen Zugriff umgangen. Keine neuen Cloudkosten, Modellaktivierung, Quellenfreigabe oder Wiederaufnahme des persönlichen Imports.

Diese Lieferung schließt konkret reproduzierte Quellenlücken. Sie beweist keinen fertigen CoS, keine allgemeine Suchvollständigkeit und keine fehlerfreie Gedächtnisqualität.
