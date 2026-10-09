# Vollständige Originalbindung bei erkannten Regeln

Produktstand `ce39f71046581567d9915d1b06a73e991072f1f3`, Basis `8394ff5169e28e0cc70bd48e818db123e2efb7f7` / zuvor installierter Produktcode `3ff842f`. Künstliche Kontrollen; keine persönlichen Quellen an ein Modell übergeben.

## Problem und Änderung

Der vorherige echte lokale Prüfmodelllauf akzeptierte zwei falsche Aussagen gemeinsam mit der zentralen Prüfung: „Druck eingestellt“ statt „Druck gemessen“ und eine auf den Glasrohling übertragene Erlaubnis für die Ofentür. Ein zweites Modell-Ja ist deshalb kein hinreichender Schutz.

Erkannte Erlaubnisse/Pflichten lösen nun eine vollständige Originalbindung aus, auch wenn erst der Antwortkandidat eine Erlaubnis erfindet. Im Formulierungsweg wählt das Modell serverseitig ausgegebene Originalstellen-IDs; der Code materialisiert den Wortlaut. Beide Prüftore, Aktualität und Quellenentzug bleiben aktiv. Freie Legacy-Ausgaben und alte gespeicherte Antworten unterliegen derselben zentralen Bindung.

Leerraum, Groß-/Kleinschreibung und ein abschließender Punkt dürfen variieren. Frage-/Ausrufezeichencluster und Zitate werden nicht entfernt. Innere Zeilenumbrüche, Semikolon und Doppelpunkt bleiben im Abschnitt; gewöhnliche deutsche Abkürzungen und Zahlpunkte erzeugen keine vorgetäuschten vollständigen Fragmente. Versteckter Volltext dient nur der Prüfung. Sichtbarkeit und erlaubter Quellenrahmen müssen für dieselbe Originalstelle in derselben tatsächlich zitierten Quelle gelten.

Normative Quellen mit Zitierzeichen fallen konservativ auf Originalkontext zurück; das kann auch bei einem harmlosen Zitat in derselben Quelle passieren. Bei relativen Regel-Daten oder programmatisch erzeugten Wandeltexten kann die strengere Bindung zusätzliche Zitat-Rückfälle auslösen. Wenn nach einer Verwerfung nur ein gewöhnlicher Fakt derselben Quelle bleibt, werden erkannte ausgelassene Regeln nicht verdeckt. Das ist ausdrücklich eine breitere, vorsichtige Reaktion.

## Feste Gegenproben und Review

Der unabhängige Katalog wurde vor Produktänderung eingefroren (Fixture SHA `a53217e6a52aa5a6c55728cc5ccc6d12ba21317a53538a391adbda970db4a361`). Alle 30 erforderlichen Bindungskontrollen bestehen; die acht bekannten falschen Kandidaten werden zentral abgelehnt. Das ist kein allgemeiner Genauigkeitswert.

69 neue dauerhafte Tests; 310 betroffene Tests bestanden. Auf einem isolierten unveränderten Basis-Snapshot scheitern 52 derselben 69 Tests, 17 Sicherheits-/Kompatibilitätsfälle bleiben grün. Darunter sind neben Bug-Reproduktionen auch neue ID-Vertragstests; die Zahl ist keine Zählung von 52 Produktfehlern.

Der unabhängige Review fand eine tatsächliche Kombination zweier unzureichender Quellen: eine Stelle war versteckt, eine andere sichtbar aber Teil eines verworfenen Zitats. Das gemeinsame Zitieren akzeptierte sie zunächst. Der permanente Test war vor Korrektur rot; nach der Korrektur werden beide Voraussetzungen in derselben Quelle verlangt. Der Reviewer bestätigte auch einen gültigen sichtbaren positiven Gegenversuch. Zusätzlich wurde die erfundene Erlaubnis aus einer bloßen Vorgangsbeschreibung rot reproduziert und korrigiert. Abschließend 88 Prüfungen durch den Reviewer bestanden.

## Grenzen und Abnahme

Der Vertrag beweist Originalwortlaut und Herkunft, keine Wahrheit, Verbindlichkeit oder vollständige Anwendung auf einen konkreten Vorgang. Die eingefrorenen Grenzen L01/L02 bleiben wichtig: Eine Einschränkung im Folgesatz oder ein historischer Entwurfsstatus kann durch einen wörtlichen Einzelsatz verloren gehen. Beide Kontrollkandidaten werden weiterhin akzeptiert, obwohl ihr uneingeschränkter Gebrauch sachlich falsch wäre. Sie bleiben ausdrücklich offene Produktarbeit; keine Fehlerfreiheits- oder CoS-Gesamtabnahme.

Der netzlose Pakettest bestätigt alle 264 Python- und 112 unveränderten UI-Dateien sowie Lizenz und konkrete Gegenproben. Zwei Python-Module geändert; native Oberfläche unverändert.

Der abschließende vollständige Backend-/Diagnostik-/Mac-Skriptlauf auf Teststand `fda6dc213a2c9183e92531940c137afc162b69a5` besteht mit **5986 Tests, 2 übersprungen, 32 Subtests**. Der Produktcode bleibt unverändert `ce39f71`. Ein früherer vollständiger Lauf hatte 5983 bestandene Tests und drei alte positive Umformulierungs-/Teilantwort-Erwartungen. Der unabhängige Reviewer bestätigte deren bewusst geänderten Vertrag; die Tests wurden mit negativen Paraphrasen und positiven vollständigen Originalen angepasst, ohne Produktlockerung. Danach 261 betroffene Tests und der vollständige Lauf grün. Die Testgruppen werden nicht addiert. Ein gestarteter erster Volltest des Zwischenstands 95a wurde nach dem neuen Gegenbefund abgebrochen und zählt nicht als Nachweis. Ein nativer 95a-Modelllauf wurde nicht begonnen; der Snapshot bleibt separat erhalten.

## Abgebrochener echter Gesamtlauf

Der erste neue native Versuch hat 19/19 künstliche Quellen tatsächlich aufgenommen, eingeordnet und mit Themen-/Entitätenvorschlägen verarbeitet. Danach fehlten die BGE-M3-Modelldateien: kein Index, null geprüfte Fragen. Dieser Lauf ist **kein** neuer Abruf-/Antwortnachweis. Ursache und ausdrücklich angefragte Wiederherstellung stehen in [model-cache-incident.md](model-cache-incident.md); ein früherer eigener Testserver hatte durch einen gemeinsamen schreibbaren Cache die Dateien entfernt. Die früheren erfolgreichen Modellmessungen bleiben historische Ergebnisse, werden nicht als aktuelle Abnahme umgedeutet.

Ein zusätzlicher Volltest wurde zunächst in der Sandbox gestartet. Mehrere künstliche lokale Server konnten dort nicht binden. Der einzelne DNS-Test reproduziert `PermissionError: Operation not permitted`; mit freigegebenem lokalem Testserver besteht derselbe Test. Der eingeschränkte Gesamtlauf wurde abgebrochen und zählt nicht als vollständiger Produktnachweis. Der abschließende Lauf umfasst Backend und Diagnostik-/Mac-Skripte mit erlaubten künstlichen lokalen Servern.

## Ergänzender echter Formulierungsweg, ausdrücklich ohne Abruf

Ein eigener zusätzlicher Lauf prüft `satzantwort.formulieren` samt aktivem zweitem Modelltor mit bereits vorhandenen verifizierten Qwen-Gewichten. 16 Fragen mit fest eingefrorenen vorher ausgewählten Originalquellen, 15 Formulierungs- und 22 zweite Prüfaufrufe; kein Index, keine Suche, keine Aufnahme und kein neuer Gesamtabdeckungswert. W02 hat im früheren Auswahlstand keine Belege und erhält hier keinen Modellaufruf. W05 hatte vorher keine Satzformulierung; seine gespeicherte Ref-Reihenfolge S2,S1 wurde als neuer direkter Kontext verwendet.

Unabhängige Inhaltsprüfung: zehn ausreichende Satzantworten; W04 bleibt materiell unvollständig, weil der ausdrückliche Schluss „nicht zulässig“ fehlt. W05 enthält widersprüchliche Regeln und wird vorsichtig nicht als eindeutige Erlaubnis beantwortet. DE01–DE03 bleiben Quellenzitate nach weiterhin zu strenger Negations-/Anwendbarkeitsprüfung. Keine angezeigte unbelegte Behauptung in diesem begrenzten Lauf. IA05 fügt einen sachlich belegten, aber nicht benötigten Versand-Fakt hinzu – eine kleine Relevanzverschlechterung. Das ist kein belegter allgemeiner Qualitätsgewinn. Generator und zweites Tor verwenden dasselbe Modell; ein `ja` bleibt fehlbar.

Die Test-Blobs sind echte isolierte APFS-Dateiklone mit verschiedenen Inodes, keine Symlinks/Hardlinks. Vor Serverstart alle SHA256 geprüft, `OLLAMA_NOPRUNE=1` und Cloud aus. Ursprüngliche Qwen-Dateien einschließlich Prüfsummen und Metadaten unverändert vor/nach; eigener Server und Client enden mit Exit0. [Eingefrorener Bericht und unabhängiges Inhaltsreview](formulation-only/content-review-independent.json).

## Geprüfte Mac-Installation

Lokal installiert **1.0.6-local.ce39f71** nach kalter Sicherung. Alle 264 Python- und 112 UI-Dateien sowie die SQLite-Vec-Lizenz stimmen byteweise mit dem geprüften Paket überein. Alle 344 Originalkörper wurden frisch gegen ihre gespeicherten Digests und den kalten Bestand geprüft; 17 SQLite-Dateien bestehen quick_check. Konten/Einstellungen, Datenvolume, native signierte Anwendung und ausdrückliche Importpause bleiben erhalten. Produktives Ollama bleibt aus, Bedeutungssuche unavailable. Die native Fenster-/Tages-/Akkuprüfung ist weiterhin offen; ein gesunder Backendstart ist keine Bedienabnahme. Der Rückweg steht im Installationsbericht.

Die ergänzende Kategorisierungsdiagnose ist separat vorbereitet und unabhängig geprüft; sie gehört **nicht** zu dieser installierten Fassung. Vor großem Reimport braucht ihr bedarfsweiser Fehlerabgleich ein Gesamtbudget oder einen sichtbaren unvollständigen Status. Die Absatzbindung gegen die dokumentierten L01/L02-Restfälle wird ebenfalls getrennt vorbereitet. Keine neue private Verarbeitung, Cloudausgabe oder BGE-Wiederherstellung ohne die noch ausstehende Zustimmung.

Die kopierten Textlogs sind nur um nachgestellten Leerraum bereinigt; Roh- und Kopie-Prüfsummen stehen in `log-normalization.json`. Inhalte und Zeilenreihenfolge wurden nicht umgeschrieben.
