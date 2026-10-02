# Dateiversionen – Zwischenstand zum Quellenverhalten

8. September 2026. Punkt 10 bleibt offen.

Wiederholt aufgenommene Dateien erhalten eine dauerhafte Zuordnung zum zuletzt
beobachteten Episodenstand. Der Schlüssel enthält den aufgelösten freigegebenen
Ordner und die Adapterreferenz; gleich benannte Dateien aus unterschiedlichen
Ordnern bleiben getrennt. Episode-Schema 3 ergänzt dafür source_heads. Die
vorhandenen Episoden werden nicht überschrieben.

Bei einer neuen Fassung sperrt Kingfisher zunächst Claims und abhängiges Wissen
mit dem alten Beleg, schließt dann die alte Episode aus der aktuellen Nutzung
aus und aktualisiert zuletzt den Versionszeiger. Ein Abbruch lässt den alten
Zeiger für Wiederholung bestehen. Der Compare-and-swap-Schritt verhindert das
Überschreiben eines inzwischen veränderten Zeigers. API- und Zeitplan-Aufnahme
verwenden die gemeinsame Gesprächs-/Wissenssperre.

Die neue Fassung bleibt Rohmaterial. Kopieren einer bereits ausgeschlossenen
alten Fassung reaktiviert weder Episode noch Wissen. Der Aufnahmebericht und
der Zeitplan zählen erkannte Änderungen. Originalquellen bleiben lesbar.

## Geprüft

- Zwei Datenbankverbindungen: erhaltener Versionszeiger, zurückgewiesene veraltete
  Schreiboperation, getrennte Dateischlüssel, keine Zuordnung unbekannter Episode.
- Datei aufnehmen, belegten Claim bestätigen, Datenbank erneut öffnen, Datei ändern,
  erneut aufnehmen: alter Claim nicht nutzbar, Original erhalten, neuer Rohtext
  unbestätigt, erneuter Lauf ohne Dublette; Rückkopieren reaktiviert nichts.
- Verschlüsseltes Paket mit befülltem source_heads-Eintrag wiederhergestellt;
  Versionszuordnung und alle ursprünglichen Store-Inhalte erhalten.
- Geschützter Docker-Browser, Chromium bei 1521 × 1034: vorher aktuelle Aussage,
  nach authentifizierter API-Aufnahme nur im Verlauf „Grundlage fraglich“, alte
  Originalquelle geöffnet und Ausschlusshinweis sichtbar, Wiederholung ohne
  weitere Änderung. Keine Seitenfehler. Screenshot source-version-history.png
  im lokalen Aufgabenordner visuell geprüft; bestehende Profilkomponenten.

Browser plugin nicht verfügbar, reguläres Playwright verwendet. Die Aufnahme
wurde im QA-Ablauf über den geschützten API-Endpunkt ausgelöst; kein neuer
Dateiverwaltungsdialog wird damit als abgenommen behauptet.

## Noch offen

Die erste Beobachtung legt den Ausgangsstand fest. Nicht eindeutig einem Ordner
zuordenbare Altbestände werden nicht durch Namensvermutung automatisch ersetzt.
Löschungen/Umbenennungen, Metadatenänderungen bei unverändertem Text und direkte
Upload-Ersetzungen benötigen weitere Arbeit. Die globale Inhaltsentdopplung
kann Belege mehrerer identischer Dateien zusammenführen; deren Sperre ist
konservativ und kann auch unabhängige Kopien betreffen. Mail-/Kalenderänderungen
haben eigene Quellidentitäten und werden nicht durch Dateinamen behandelt.
Keiner dieser offenen Punkte wird als abgeschlossen gezählt.

Die neue Schema-Version darf nicht direkt mit einem alten Image geöffnet
werden. Der Rückweg bleibt die separate Wiederherstellung einer dazu passenden
Sicherung und ihrer gespeicherten App-Version (UPDATE-AND-RETURN.md).

Finale Gesamtsuite: 955 Tests bestanden, eine bestehende Starlette-Warnung.
Nach Sicherung auf Port 8891 ausgerollt; echte Mac-Kalenderteilnehmer im Browser,
Episode-Schema 3 und SQLite-Integrität geprüft. Originalassets unverändert.

## Getrennte Belege identischer Dateien – Schema 4

Neu aufgenommene Dateien werden innerhalb ihrer stabilen Quellenkennung
entdoppelt. Zwei verschiedene Dateien mit identischem Inhalt haben getrennte
Episoden und Belege, aber denselben unveränderten SHA-256-Inhaltsdigest. Eine
Änderung von Datei A sperrt den Claim aus A; der Claim aus B bleibt nutzbar.
Wiederholte Aufnahme derselben Datei erzeugt weiterhin keine Dublette.

Schema 4 ergänzt den Quellenschlüssel an Episoden und erweitert den eindeutigen
Digest-Index um diesen Schlüssel. Eindeutige bestehende Versionszeiger werden
migriert, ohne Episoden-IDs oder Belege zu ändern. Mehrdeutige bereits gemeinsam
gespeicherte Altbelege bleiben konservativ: Eine unveränderte Wiederaufnahme
legt keine neue Fassung an und deutet keine alte Herkunft um. Diese Altbelege
brauchen weiterhin eine ausdrückliche Klärung.

957 Gesamttests bestanden. Zusätzlich wurde der Kopientest um zwei tatsächlich
bestätigte Claims erweitert und gezielt erneut ausgeführt: nur der betroffene
Claim gesperrt. Docker-Browser bei 1521 × 1034 bestätigt beide Aktenzustände,
alte Originalquelle ausgeschlossen, unabhängige Quelle weiter nutzbar,
Wiederholung ohne Dublette. Bild independent-file-still-valid.png visuell
geprüft. Keine Seitenfehler; Browser plugin nicht verfügbar, reguläres Playwright.
Nach Sicherung lokal ausgerollt; echte Mac-Kalenderteilnehmer sowie Schema 4
und SQLite-Integrität geprüft. Der vollständige Quellenpunkt bleibt offen.

## Nachweislich entfernte Dateien

Nach einer vollständigen fehlerfreien Ordneraufnahme prüft Kingfisher die
zu diesem Ordner und Adapter passenden bekannten Belege auf tatsächliche
Dateiabwesenheit. Nur FileNotFoundError gilt als fehlende Datei. Lesefehler,
unvollständige Läufe, ein nicht erreichbarer oder während des Abgleichs
ersetzter Quellenordner führen nicht zur Annahme einer Löschung. Zunächst
werden Dateistatus und Ordner geprüft, danach Belege und abhängige Claims
gesperrt. Originaltexte und Versionszeiger bleiben für den Verlauf erhalten.
Der Aufnahmebericht und Zeitplan nennen die Zahl entfernter Belege.

71 Quellen-/Import-/Zeitplantests bestanden. Die Prüfung läuft für Markdown,
Obsidian, Notion und Textdateien, einschließlich Begrenzung, Lesefehler,
fehlgeschlagener Statusabfrage, erneutem Lauf und Wiederauftauchen alter Inhalte.
Docker-Browser bei 1521 × 1034: Datei im isolierten Testbestand entfernen,
authentifizierte Aufnahme auslösen, alte Aussage nur im fraglichen Verlauf,
Originalquelle mit Ausschlusshinweis, unabhängige Kopie unverändert gültig.
Keine Seitenfehler, Screenshot removed-file-history.png visuell geprüft.
Nach Sicherung lokal ausgerollt, echter Mac-Kalender im Browser erneut geprüft.

Der damalige Stand betraf fehlende ganze Dateien. Geleerte Inhalte und entfernte
CSV-Zeilen sind im folgenden Abschnitt ergänzt. Metadatenänderungen bei gleichem
Text und explizite Wiederzulassung ausgeschlossener Quellen bleiben offen. Es gibt keine automatische
Reaktivierung alter Aussagen und keine automatische Übertragung einer Beziehung
auf einen umbenannten Dateipfad. Punkt 10 bleibt in Arbeit.


## Geleerte Dateien und entfernte Tabellenzeilen

Die Adapter melden erfolgreich gelesene Dateien mit ihren vorhandenen
Quellenreferenzen. Der vollständige Abgleich entzieht auch Belege, deren Datei
noch existiert, deren Inhalt aber entfernt wurde. Nicht lesbare, nicht
unterstützte und zu große Dateien liefern keinen solchen Abwesenheitsbeweis.
Notion-CSV-Zeilen bleiben über die bisherige Zeilenreferenz adressiert; beim
Verschieben einer Zeile greift zusätzlich die bestehende Inhaltsversionierung.

Sechs Regressionen zunächst rot: leeres Markdown, Obsidian nur mit Frontmatter,
leerer Text, Notion nur mit Überschrift, entfernte letzte CSV-Zeile und leere
CSV-Tabelle mit Kopfzeile. Danach bestanden; abhängige bestätigte Aussagen
werden unbrauchbar, Originaltext bleibt erhalten, Wiederholung zählt keinen
weiteren Entzug, unveränderte Tabellenzeile bleibt aktiv. Größenlimit wird
explizit nicht als Entfernung behandelt.

Docker-Browserlauf mit synthetischen Daten: bestätigte Aussage, Quelldatei
leeren, erneut aufnehmen, Aussage im Verlauf als Grundlage fraglich,
Originalquelle öffnen, Ausschlusshinweis und Rohtext sichtbar; unabhängige
Kopie weiterhin bestätigt. Screenshot bei 1521 × 1034 visuell geprüft.
Diese Ergänzung schließt Punkt 10 noch nicht vollständig ab; insbesondere
Metadatenänderungen und explizite Wiederzulassung bleiben zu prüfen.

Abschließender Gesamtlauf: 968 Tests bestanden, eine bekannte Starlette-Warnung.
Aufruf: `pytest sidecar/tests -q --ignore-glob='* 2.py'` mit PDF-Testabhängigkeiten.
Der erste Lauf enthielt zusätzlich lokale alte Testkopien; vier davon scheiterten
an der überholten Callback-Signatur. Diese Kopien wurden nicht geändert oder
in Git aufgenommen. Neuer Container nach Sicherung des Alltagsbestands gestartet;
echte Mac-Kalenderteilnehmer in der Terminvorbereitung erneut erfolgreich geprüft.


## Metadaten bei unverändertem Text

Schema 5 ergänzt einen separaten Metadaten-Digest für Quellen mit stabiler
Identität. Der Originaltext-Digest bleibt unverändert. Titel, Teilnehmer,
Quellendatum, Schlagworte und Episodenart bestimmen die Fassung mit; der
Aufnahmezeitpunkt und nachträgliche Projektzuordnungen tun dies nicht.
Reihenfolge und doppelte Einträge in Teilnehmer-/Schlagwortmengen sowie andere
Zeitzonenschreibweisen desselben Zeitpunkts erzeugen keine zusätzliche Fassung.

Vier Regressionen zunächst reproduziert: Titel, Teilnehmer, Datum und Tags
geändert, Text gleich. Danach entsteht eine neue unbestätigte Episode;
Originaltext und bisherige Metadaten bleiben erhalten, die frühere Episode
und abhängige bestätigte Aussagen werden gesperrt. Wiederholung nach Neustart
erzeugt keine Dublette, Rückkehr zur alten Fassung bestätigt kein altes Wissen.
Schema-4-Migration ergänzt den Fingerabdruck bei bestehenden eindeutigen Quellen
und erhält ihre IDs, Digests und Versionszeiger. Mehrdeutige Altzuordnungen
werden weiterhin nicht automatisch auseinandergeteilt.

Docker-Browser: Teilnehmer einer Notiz von Alex auf Bea ändern, erneut aufnehmen,
neue Episode mit gleichem Text-Digest prüfen; frühere bestätigte Aussage im
fraglichen Verlauf und alte Quelle mit Ausschlusshinweis öffnen. Unabhängige
Kopie bleibt gültig, Wiederholung erzeugt keine neue Episode. Screenshot bei
1521 × 1034 visuell geprüft; keine Seitenfehler. Keine Layoutänderung.

Die zuvor genannten Metadatenlücken für identifizierte Ordnerquellen sind damit
abgedeckt. Explizite Wiederzulassung und die vollständige Prüfung der anderen
Quellenwege bleiben für die gemeinsame Abnahme offen.

Abschluss dieses Schritts: 973 Tests des Projektbestands bestanden, bekannte
Starlette-Warnung. Assetmanifest unverändert bestanden. Nach Sicherung lokal
ausgerollt; Episoden-Schema 5 und SQLite-Integrität bestätigt. Echter Mac-Kalender
mit Teilnehmern in der Terminvorbereitung erneut erfolgreich geprüft.


## Ausgeschlossene Quelle ausdrücklich wieder zulassen

In der geöffneten Originalquelle gibt es „Quelle wieder zulassen“ mit einer
kurzen Erklärung und Bestätigung. Der gespeicherte Rohtext wechselt zurück auf
`new`; bestehende Aussagen und transitive Abhängigkeiten bleiben fraglich.
Die Anforderung wird vor dem Schreiben protokolliert. Ein Protokollfehler lässt
die Quelle ausgeschlossen. Wiederholung verändert bereits zugelassene Quellen
nicht; eine inzwischen durch einen anderen Versionszeiger ersetzte Fassung
wird mit Konflikthinweis abgewiesen. Die nicht ausführbare Aktion verschwindet
danach aus dem geöffneten Bereich. Die Dateiliste aktualisiert ihren Status.

Zwei Regressionen zuerst rot, anschließend 977 Gesamttests bestanden. Geprüft:
Neustart, leerer Modellkontext für das frühere Wissen, fehlende Anmeldung,
Protokollausfall, aktuelle gegenüber ersetzter Fassung, idempotente Wiederholung.
UI-Build und Assetmanifest bestanden. React-Prüfung: bestehende Komponenten,
keine neue Abhängigkeit, beschriftete native Buttons, gesperrte Doppelbetätigung,
Fetch-Abbruchschutz und Aktualisierung der übergeordneten Dateiliste.

Browser plugin nicht verfügbar; reguläres Playwright gegen den geschützten
Docker-Testcontainer auf 127.0.0.1:8892. Ablauf: Personenakte mit fraglicher
Aussage → Originalquelle → Wiederzulassung → Abbrechen → simulierter 503-Fehler
→ Wiederholen → Quelle `new`, Aussage weiter fraglich. Danach neue Quelldaten
aufnehmen → Wiederzulassung der früheren Fassung mit 409 abgewiesen. Abschließend
hochgeladene Quelle unter Einstellungen wieder zulassen und Listenstatus prüfen.
Titel/Inhalt, keine leere Seite oder Fehlerüberlagerung, tatsächliche Interaktionen
und Screenshots bei 1521 × 1034 und 1280 × 900 geprüft. Keine Seitenfehler;
Konsolenfehler nur für die absichtlich ausgelösten HTTP 503 und 409.

Zusätzlicher 390 × 844-Versuch zeigt die bestehende globale Mindestbreite von
1280 px (styles.css). Mobile Darstellung bleibt außerhalb dieser Desktop-Abnahme
und ist nicht als bestanden dargestellt. Es wurden keine neuen Assets oder
Änderungen am Layout der App eingeführt. Nach Sicherung lokal ausgerollt und
echter Mac-Kalender erneut im Browser geprüft.

Gemeinsame Quellenabnahme bleibt offen: Mail-Identität/erneute Aufnahme sowie
unterschiedliche Quellenwege zusammen prüfen. Die Wiederzulassung ist kein
Beleg dafür, dass sämtliche Quellenfälle bereits abgenommen sind.


## Mail: Identität, erneute Aufnahme und Quellenentzug beim Lesen

Neu aufgenommene Mails werden mit Konto und serverseitiger UID identifiziert.
Die vom Absender gelieferte Message-ID ist nur Herkunftsangabe, kein Schlüssel
zum Ersetzen anderer Nachrichten. Gleicher Text in unterschiedlichen Nachrichten
oder Konten bleibt unabhängig. Qualifizierte und unqualifizierte UID desselben
Kontos werden normalisiert. Die gemeinsame Versionsfunktion sperrt bei erneuter
Aufnahme einer geänderten Mail frühere Belege und abhängige Aussagen; neue
Fassungen bleiben unbestätigt. Wiederholung und Neustart erzeugen keine Dublette;
eine zurückgekehrte ausgeschlossene Fassung wird nicht reaktiviert.

Manuelle Aufnahme und Aufgabe aus Mail prüfen nach dem Netzabruf unter der
Sperre noch einmal die Quelle und Nachrichtenkennung. Postfachentzug während
des Abrufs erzeugt keine Episode. Der Zeitplan verwendet dieselbe Quellenlogik
und seine bestehende Prüfung des Entzugs samt gespeichertem Fortschritt.
Fehlt bei einer Änderung der Wissensspeicher, bricht die Versionsumschaltung ab.
Alte Mailaufnahmen ohne gespeicherte Serveridentität werden nicht anhand von
Textgleichheit oder fremden Headern nachträglich einem Postfach zugeordnet.
Im lokalen Alltagsbestand wurden nach dem Update null solche Mailaltbelege
gezählt; keine privaten Inhalte ausgegeben.

Regression: zwei Nachrichten mit gleichem Text und gleicher Message-ID wurden
zunächst fälschlich dieselbe Episode. Danach getrennte IDs bei gleichem korrektem
Text-Digest; nur die geänderte Nachricht entwertet ihren Claim. 980 Gesamttests
bestanden, darunter Quelle während manuellem Abruf/Task-Abruf entzogen, Neustart,
Kontentrennung, Wiederholung und Rückkehr zur alten Fassung. UI-Build und
Assetmanifest bestanden.

Browser plugin nicht verfügbar; reguläres Playwright gegen geschützten
Docker-Testcontainer, 1521 × 1034. `/nachrichten` → Mail A öffnen → als Quelle
merken → sichtbarer Hinweis auf geänderte Fassung → Akte mit fraglicher Aussage
und Originalbeleg öffnen → Akte B weiterhin bestätigt → erneute Aufnahme als
bekannt → alte Fassung erneut gelesen bleibt ausgeschlossen. Keine Konsolen-
oder Seitenfehler; Screenshots mail-version-notice.png und
mail-version-history.png visuell geprüft. Der erste Prüfversuch verwendete
irrtümlich `/messages`; nach Abgleich mit der tatsächlichen Route korrigiert.
Keine Layoutänderung. Nach Sicherung lokal ausgerollt; echter Mac-Kalender und
Datenbankintegrität erneut geprüft.

Die gemeinsame Abnahme von Punkt 10 ist noch offen. Als nächstes sind die
bereits geprüften Anbieterfälle und die sichtbare Bedienung des Quellenentzugs
über alle Originalansichten zusammenzuführen, statt weitere Teilpunkte zu zählen.


## Gemeinsamer Quellenabschluss

Ausschluss ist in der gemeinsamen Originalansicht jeder Episode bedienbar;
die Dateiliste behält ihre vorhandene Aktion ohne doppelte Schaltfläche.
Nach Ausschluss wird der umgebende Wissensstand neu geladen. Backend unverändert;
UI-Build, Assetmanifest, 137 gezielte Abnahmetests und geschützter Docker-Browser
bestanden. Abbrechen, 503-Fehler/Wiederholung, aktualisierte Akte, Wiederzulassung
und erneuter Ausschluss sowie unabhängiger Beleg geprüft. Eine anfängliche
Testnavigation lief vor dem abgeschlossenen Neuladen weiter; anschließend wurde
der tatsächliche Seitenwechsel abgewartet und der ganze Ablauf frisch bestanden.
Nach Sicherung lokal ausgerollt und echter Mac-Kalender erneut geprüft.
Die vorherigen offenen Abnahmevermerke sind durch ACCEPTANCE-SOURCES.md ersetzt:
Punkt 10 ist erfüllt, Gesamtstand 11/20 = 55 %.
