# Word-Haupttext und eigene Mailadresse

Diese Korrektur ergänzt die begrenzte MIME-Aufnahme. Alle veröffentlichten
Testdaten und Reviews sind künstlich. Persönliche Mailkopien bleiben außerhalb
des Repositorys; keine private Zuordnung oder Importfreigabe wurde hier geändert.

## Bestehenden Word-Leser wiederverwenden

Die Dokumentvorschau und Ordneraufnahme verwenden bereits `document_text.docx_text`.
Der Mail-Anhangsweg verwendete ihn noch nicht. Er übernimmt jetzt denselben
begrenzten Haupttext-Leser einschließlich Datei-/XML-/Textgrenzen und Ablehnung
von XML-Entitäten sowie gelöschten Änderungsresten. Die bestehende Anhangsgrenze
von fünf Dateien und 60.000 Zeichen je Quelle bleibt erhalten. Zu großer oder
unlesbarer Inhalt wird nicht als vollständig ausgewertet dargestellt.

Word-Haupttext ist keine Seitenansicht: Berichte nennen den Textumfang,
Seitenwerte bleiben `null`. Selbst eine Originalzeile „Seite 7“ liefert keine
Seitenreferenz. Kopf-/Fußzeilen, Kommentare, Bilder und Layout werden nicht als
gelesen behauptet. PDF-/Bildberichte behalten ihr bisheriges Format.

Der rote Integrationstest ergab zunächst 22 Fehlschläge und 10 bestehende
Negativkontrollen. Nach der Anbindung bestanden alle 32 neuen Fälle. Die
gezielte Regression mit PDF, Bildern, Quellenersatz/-entzug und dem vorhandenen
Dateileser bestand ebenfalls. Das beweist Text-/Quellenverarbeitung, keine
allgemeine Modellinterpretation eines Formulars.

## Eigene Gmail-Schreibweisen

Google dokumentiert, dass Punkte im privaten `gmail.com`-Nutzernamen dasselbe
Postfach bezeichnen; für Arbeits- und andere Domains gilt diese Regel nicht.
[Primärquelle](https://support.google.com/mail/answer/7436150).

Der gemeinsame Vergleich wird ausschließlich für eigene konfigurierte Konten
verwendet. Er verändert weder gespeicherte Adressen noch die Anker fremder
Personen. Plus-Zusätze werden nicht neu erweitert; die bestehende Parser-
Normalisierung bleibt und ist keine Validierung beliebiger SMTPUTF8-Adressen.
Kontakte, Eingangserkennung, Personenprojektion und Aufgaben-/Fristrichtung
verwenden dieselbe Eigenzuordnung.

Ein vollständig erneut abgerufenes Original kann eine inzwischen belegte
technische `ich`-Zuordnung nachtragen. Originaltext, Digest, Quellenkennung,
Zeit und Herkunft bleiben gleich; die Stützgeneration ändert sich, damit alte
Auswertungen nicht weiter als frisch gelten. Wiederholtes Lesen ist idempotent.
Unvollständiger Abruf, ausgeschlossene Quelle und normale Kontakt-Ergänzung
ohne ausdrücklichen Modus dürfen keine solche Aufwertung auslösen.

Fünf ursprüngliche Gegenfälle waren rot. Drei zusätzliche Prüfungen belegten
die falsche Aufgaben-/Fristrichtung und wurden ebenfalls erst durch die
Korrektur grün. Die 18 neuen Tests decken gültige Eigenvarianten, fremde Anker,
andere Domains, Nachtrag, Kontextbindung und die tatsächliche Aufgabenprüfung ab.

## Urheber eines Anhangs bleibt gesondert

Das unabhängige Review reproduzierte eine wichtige vorhandene Lücke: Eine
eigene Mail leitete ausdrücklich einen fremden Entwurf weiter. Dessen Ich-Satz
wurde bei positivem Modellurteil über die geerbten Transportkontakte zu einer
automatischen eigenen Aufgabe. Das betraf sowohl neue Word- als auch bestehende
PDF-Anhänge. Vier permanente Gegenfälle waren vor der Korrektur rot.

Die Eigenzusage-Prüfung setzt jetzt eine echte Nachricht voraus. Dokumente
erhalten weder eine automatische Aufgabenanlage noch eine ungeprüfte Person
aus den geerbten Mailrollen. Ein anderweitig vorgeschlagener Auftrag bleibt
mit Originalbezug manuell prüfbar. Der unveränderte unabhängige Gegenversuch
ist geschlossen; eine echte eigene Mail bleibt als Positivkontrolle nutzbar.
Originale und Eltern-/Transportbezüge bleiben erhalten.

## Gesamtstand und Grenzen

Die erste integrierte Backendprüfung bestand 8.959 Tests und 26 Subtests; ein
Plattformfall wurde ausgelassen. Ein alter Spamkopf-Test verwendete statt eines
FETCH-Datensatzes nur `FLAGS ()` als Attrappe. Sein Datensatz wurde um die
tatsächlich angefragten Identitäts-/Größenfelder ergänzt; Spam-/Newsletter-
Erwartungen bleiben unverändert. Die abschließende Gesamtprüfung wird am
eingefrorenen Stand gesondert protokolliert. Es wurde keine Produktionsprüfung
gelockert, um die alte Attrappe zu akzeptieren.

Unabhängige Reviews: [MIME](review-mime.md),
[Word, Eigenzuordnung und Anhangsurheber](review-word-und-eigene-adressen.md).
Release, persönlicher Modelllauf, sichere Mac-Installation, Fensterprüfung und
Alltagswoche sind weitere Nachweise. Ein pausierter Großimport wird durch diese
Korrekturen nicht fortgesetzt.
