# Abnahme der vertrauten Arbeitsflächen

Basis 1.0.8; Implementierung und Reviewkorrekturen bis 370599c. Persönliche Daten wurden nicht als Entwicklungsfixture verwendet.

## Automatisierte Prüfung

- Finale Backendprüfung: 6.518 bestanden, eine bestehende Prüfung übersprungen, 26 Unterprüfungen bestanden. Der Lauf nutzt künstliche Daten und lokale Testserver; Swift-/Clang-Modulcaches liegen in einem separaten temporären Ordner.
- UI: 652 bestanden; TypeScript und Produktionsbuild bestanden. Die bestehende Warnung zur Größe des Hauptbundles bleibt sichtbar.
- Vorheriger Sandboxlauf: lokale Server/Swift blockiert; zusätzlich zwei Integrationsbefunde korrigiert (gesicherter Modellprovider an Projektvorschläge, Wiederherstellungsfixture mit neuem Metadatenspeicher). Betroffene Prüfungen danach bestanden.
- Unabhängige Reviews reproduzierten und korrigierten Mail-Task-Projektabschluss-Race, entzogene Gesprächstreffer, falsche Kontaktdatierung, veralteten geöffneten Mailinhalt und Zeitumstellungsdarstellung. Das abschließende unabhängige Review von 370599c fand keine weitere konkrete Regression.

## Tatsächliche Bedienprüfung

Isolierter lokaler Dienst mit deterministischem künstlichem Antwortmodell, 35 Kontakten, Projekt, verschiedenen Aufgabenfristen, 85 gespeicherten Mails, Dokumentfassungen, Orten und vier überlappenden Terminen.

- Gespräche: mehrzeiliger Entwurf bleibt beim Wechsel erhalten; Shift+Enter sendet nicht; Enter erzeugt genau eine Eingabe und Antwort. Aufnahmeaktionen vervielfachen sich nicht nach Antworten. Eingabe und Datum/Uhr bleiben bei 900 Pixeln sichtbar.
- Aufgaben: Fristgruppen, Detailöffnung, Escape und Fokuszurückgabe geprüft. Aufgabe und Projekt mit einem Klick übernommen; Originalquelle angezeigt. Sammelvorschau mit zwei Einträgen übernommen und zwei Einzelergebnisse angezeigt. Projektabschluss mit neun offenen Aufgaben abgewiesen. Board verwendet dieselben Aufgaben und zeigt Offen/Wartend/Erledigt.
- Menschen: Suche erhalten beim Zurückgehen; Akte mit Kontakt, Aufgaben, Projekt und Originalquellen geöffnet. Aufgabe aus Akte geöffnet und zur vorherigen Akte zurückgekehrt.
- Bereiche: zwei Quellen gemeinsam um einen Bereich ergänzt; bestehende Bereiche und Einzelergebnisse blieben sichtbar.
- Dokumente: virtuellen Ordner mit Vorschau angelegt, aktuelle Dokumentfassung zugeordnet, gefiltert und Zuordnung rückgängig gemacht. Alte Originalfassung wird nicht als aktuelle Dokumentquelle angeboten.
- Organisationen: explizite Testgruppe mit zwei Einzelakten angelegt, Einzelakten erreichbar, Gruppierung rückgängig gemacht.
- Orte: Koordinaten geprüft und bestätigt. Karte ausschließlich im künstlichen Bestand eingeschaltet; Kacheln/Attribution/Marker und Ortsauswahl sichtbar geprüft; danach wieder ausgeschaltet.
- Eigenes Bild: künstliche lokale PNG-Datei ausgewählt, Vorschau gespeichert und Bildänderung rückgängig gemacht.
- Nachrichten: Kontofilter und Suche im Mailinhalt über mehrere Seiten des Bestands; historische Mail im Lesebereich. Ohne verbundenen Provider blieb sie lesbar. Quellenverwaltung/Ausschluss entfernte den Inhalt aus Lesebereich und Liste. Bei 900 Pixeln vollständiger Lesebereich mit Rückweg, kein horizontaler Seitenüberlauf.
- Kalender: Monats- und Wochenansicht, überlappende Zeitrastertermine, Detailöffnung und Escape/Fokus geprüft. Bei 900 und 1.280 Pixeln kein horizontaler Seitenüberlauf; das Raster scrollt innerhalb seiner Fläche.

## Umfang und Grenzen

Die Prüfungen belegen die genannten Arbeitsabläufe; sie sind kein vollständiges Barrierefreiheitszertifikat und kein Lasttest des gesamten persönlichen Mailarchivs. Modellvorschläge werden weiterhin geprüft und bestätigt; ohne vorhandenes Vergleichsprojekt wird kein automatischer Erstprojektvorschlag berechnet. Große Listen zeigen ausdrücklich geladene Seiten; Metadatenübersichten melden ihre Begrenzung. Aktivierung von Cloudmodellen und Fortsetzung des Großimports sind nicht Teil dieser Lieferung.

Mac-Sicherung, normaler Updateweg und abschließende Prüfung der installierten Fassung werden nach der Veröffentlichung separat dokumentiert.

## Veröffentlichungskorrektur

Der erste Release-Lauf für 1.0.9 wurde nach über 20 Minuten ohne Abschluss von `linux/arm64 ui-build npm ci` kontrolliert beendet. Es wurde keine unvollständige Fassung installiert. Der statische UI-Build verwendet in 1.0.10 `BUILDPLATFORM`; nur HTML/CSS/JavaScript werden in beide Zielbilder kopiert. Python-Build und Laufzeit bleiben auf ihrer jeweiligen Zielarchitektur. Grundlage: https://docs.docker.com/build/building/multi-platform/#cross-compilation.

## Korrektur aus dem echten Mac-Fenstertest

1.0.10 wurde über den normalen Knopf installiert: 18 Datenbanken intakt, 16 Bestandstabellen unverändert, Zugänge erhalten, Onlineansichten aus. Entwurf/Shift+Enter/Wechsel im nativen Fenster geprüft, Prüfentwurf anschließend entfernt. Die echte Kalenderansicht zeigte einen neuen Filterfehler: mehrere physische Mac-Kalender wurden durch die Elternkennung gemeinsam gefiltert. 1.0.11 ergänzt dafür eine separate Anzeigekennung und die Namen ausgewählter Kalender auch ohne aktuelle Termine; Provideridentität, Termin-UID und Kopienregeln bleiben unverändert. 20 gezielte UI- und 48 Backendprüfungen sowie Produktionsbuild bestanden. Die finale Filterprüfung folgt nach Installation von 1.0.11.

Finaler vollständiger UI-Lauf für die Kalenderkorrektur: 653 bestanden, keine fehlgeschlagen; TypeScript und Produktionsbuild bestanden. Die gezielte Backendprüfung umfasst weiterhin 48 bestandene Prüfungen.

## Zweite Korrektur aus dem Mac-Fenstertest

Die getrennten Mac-Kalenderfilter in 1.0.11 wurden mit den drei ausgewählten Mac-Kalendern und dem Google-Abo erfolgreich geprüft; eine Auswahl ohne Termine blieb sichtbar. Einzelne Filter beeinflussten die übrigen Kalender nicht. Alle Filter wurden wiederhergestellt, Termindetails geöffnet und per Escape geschlossen. 18 Datenbanken intakt, 16 maßgebliche Bestandstabellen unverändert; die wirksame globale Hintergrundpause blieb aktiv. Gespeicherte historische Mail weiterhin lesbar trotz bestehender Live-Gmail-Verbindungsstörung. Der Rückweg von einer Originalquelle über eine verknüpfte Personenakte verlor jedoch die Bereichsansicht. Diese Bedienlücke wird in 1.0.12 gezielt korrigiert; die erneute Abnahme folgt nach Veröffentlichung.

Finale Rückwegkorrektur: 665 vollständige UI-Prüfungen bestanden, darunter zwölf neue Regressionen für Quellenakte, Bereichsseiten/Auswahl, geänderte Quellen, Ordnerfilter, Organisationsentwürfe und Ortsauswahl. TypeScript und Produktionsbuild bestanden. Es werden nur kleine Ansichtskennungen im Verlauf dieses Fensters gespeichert; Quellenkörper, API-Antworten, Koordinaten und Bestätigungsvorschauen bleiben ausgeschlossen. Listen und Metadaten werden nach Rückkehr frisch geprüft.

Das fokussierte unabhängige Rückweg-Review fand eine fehlende Ladebarriere bei verzögerten Dokumentordner-/Bereichsabfragen. Der korrigierte Stand wartet auch auf diese Antworten und auf Metadaten-Refreshes; terminale Fehler behalten ihre sichtbare Meldung. Zwei zusätzliche Regressionen belegen die Wartezeit und das spätere Wiederherstellen der Zielzeile. Finaler vollständiger UI-Lauf: 667 bestanden; TypeScript und Produktionsbuild bestanden. Im 900-Pixel-Testfenster blieb die ausdrücklich gewählte Quelle nach Quelle → Personenakte → Organisationsakte → Zurück ausgewählt.

Die direkte Browserprüfung fand außerdem einen Ankerfehler beim Scrollen des gesamten Fensters: eine bereits unsichtbare Zeile wurde gewählt. Die korrigierte Schnittmenge aus Fenster und innerer Scrollfläche behält auch teilweise sichtbare Zeilen mit ihrer tatsächlichen Position. Drei zusätzliche Regressionen für Fenster-, Seiten- und Verzeichnisscroll bestanden. Der finale UI-Lauf umfasst 670 bestandene Prüfungen; TypeScript und Produktionsbuild bestanden. Bei 900 Pixeln blieb nach Originalquelle → Personenakte → Zurück die Position exakt bei scrollY 1563 und derselben teilweise sichtbaren Zeile sowie der ursprünglichen Auswahl.

## Installierter Abschlussstand 1.0.12

Alle fünf Pakete sind in Main und Fassung 1.0.12 veröffentlicht. Die fokussierten Abschlussreviews der Dokument-Ladebarriere und der sichtbaren Scrollankerwahl fanden keine weitere konkrete Regression. 670 UI-Prüfungen und Produktionsbuild einschließlich TypeScript bestanden; die Backendprüfung umfasst den oben dokumentierten Lauf und die gezielten Kalenderprüfungen.

Der erste Release-Aufruf scheiterte ausschließlich bei GitHubs Release-Erstellung mit HTTP 500; Mac- und Docker-Builds waren bereits erfolgreich. Nur dieser Veröffentlichungsschritt und seine nachgelagerte Download-Seite wurden nachgeholt. Die erfolgreichen Builds und die CI-Tests wurden nicht erneut ausgeführt. Release und latest.json sind veröffentlicht; das veröffentlichte DMG stimmt im SHA-256 mit dem gebauten Artefakt überein.

Installation 1.0.12 erfolgte über denselben nativen Updater/UpdateMachine-Ablauf mit offiziellen Manifest- und Kompatibilitätsprüfungen, Speicherprüfung, vorgeschalteter Sicherung, exaktem Rückweg und Laufzeitkontrolle. Die zusätzliche kalte Sicherung wurde vorher vollständig wiederhergestellt und byteweise verglichen. Nach dem Wechsel: 18 Datenbanken intakt, 16 maßgebliche Bestandstabellen unverändert, Konfiguration außer Bildkennung unverändert, wirksame globale Hintergrundpause aktiv, Onlinekarte und Logos aus. Gespeicherte Mails blieben lokal lesbar.

**Noch offen:** Der Mac wurde während der abschließenden Arbeit gesperrt. Die Fensterprüfung des Rückwegs auf 1.0.12 und das Neuladen des bereits geöffneten Fensters konnten daher nicht erfolgen. Die fünf Arbeitsbereiche wurden zuvor im echten Fenster auf 1.0.10/1.0.11 geprüft; die abschließende Rückwegkorrektur ist im getrennten Browser bei 900 Pixeln samt genauer Scrollposition und Auswahl geprüft. Die bestehende Live-Gmail-Verbindungsstörung bleibt offen. Der pausierte Großimport wurde nicht fortgesetzt.
