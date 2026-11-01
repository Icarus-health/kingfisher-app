# Begrenzter vollständiger MIME-Abruf – 31.10.2026

Lokale Reparatur auf der veröffentlichten Basis 1.0.36; noch kein Release oder
Nachweis am persönlichen Postfach. Ausschließlich erfundene Daten und
IMAP-Attrappen im Speicher, keine Anbieter-, OCR- oder Modellaufrufe.

## Fehler und Änderung

Eine gültige Multipart-Mail von etwa 2,6 MB mit einer unterstützten PDF wurde
nach dem bisherigen einzelnen 2-MiB-Abruf als unvollständig behandelt. Damit
blieb ihr Anhang ungelesen, obwohl die Aufnahme bereits fünf Anlagen mit jeweils
höchstens 5 MiB unterstützt. Der Reproduktionstest war vor der Reparatur rot.

Der Connector fordert nun nacheinander höchstens 2 MiB je `BODY.PEEK[]` an,
insgesamt höchstens 40 MiB MIME. Fünf Anlagen zu je 5 MiB brauchen mit Base64 und
Zeilenumbrüchen etwa 35 MiB; der Rest lässt Raum für MIME-Köpfe und Mailtext.
Das sind höchstens 20 FETCH-Anfragen je Versuch. Vor jeder Fortsetzung wird der
Ordner frisch schreibgeschützt gewählt. UIDVALIDITY, UID, Gesamtgröße und der
zurückgelieferte Byte-Ursprung müssen passen; eine während FETCH gemeldete neue
Generation wird auch beim letzten Teil abgewiesen. Die bestehende Sitzung darf
nach Verbindungsabbruch einmal vollständig neu beginnen, ohne alte Teile
weiterzuverwenden: höchstens zwei Versuche, keine neuen Wiederholungsschleifen.

Die Literale und ihre UID-/Größenangaben müssen demselben zusammenhängenden
FETCH-Datensatz angehören; ein nachfolgender Datensatz darf keine fehlende
Identität ergänzen. Mehrere gemeldete Generationswerte werden vollständig
geprüft: Identische Wiederholungen sind zulässig, Widersprüche und ungültige
Werte nicht. Eine ausdrücklich begonnene, beschädigte BODY-Abschnittsangabe
gilt als Fehler und wird nicht wie fehlende Metadaten behandelt.

Eine kurze, leere, überlieferte oder widersprüchliche Antwort wird niemals als
vollständige MIME ausgegeben. Eindeutig zugeordnete Präfixe bleiben sichtbar
unvollständig; unklare Identität oder falsche Abschnitte werden abgewiesen.
Eine komplette erste kleine Antwort bleibt bei passender UID und exakter Größe
auch ohne ausdrückliche Ursprungsangabe vollständig. Bewusste strengere
Sicherheitsregel: Ohne RFC822.SIZE bleibt auch eine kurze Antwort unvollständig;
sie beweist weder das Mailende noch die Abwesenheit weiterer Anlagen.

Die Posteingangsvorschau bleibt bei 64 KiB, der Mailtext bei 20.000 Zeichen.
Anzahl, Dateigröße, Seiten-, Zeit- und OCR-Grenzen der Anlagen bleiben bestehen.
Originalquellen und Nachrichten werden vom Connector nicht umgeschrieben.

## Nachweis

- Neue synthetische Tests zunächst **25 fehlgeschlagen, 4 bestanden**; darunter
  die gültige 2,6-MB-Mail. Zwei weitere gezielt rote Fälle für fehlerhafte erste
  Abschnittsangaben vor deren Korrektur.
- Die unabhängige Durchsicht fand danach drei weitere Protokoll-Grenzfälle:
  Identität aus einem fremden FETCH-Datensatz, widersprüchliche Generationslisten
  und eine explizite BODY-Angabe ohne schließende Klammer. Die neuen Gegenproben
  waren zunächst **13 fehlgeschlagen, 2 bestanden**. Ein zusätzlicher roter Fall
  erfasste eine Generationsliste, die mit einem leeren Wert beginnt. Alle drei
  Schutzprüfungen wurden gezielt korrigiert; gültige Wiederholungen und
  Metadaten im selben Nachlauf bleiben erlaubt.
- Abschließende gezielte Prüfung: **155 bestanden**, darunter **56 neue Fälle**.
  Ein bestehender Starlette/httpx-Abkündigungshinweis bleibt.
- Vollständige MIME und identische PDF-Bytes erreichen den bestehenden
  Extraktionspfad. Die gültige PDF mit exakt 5 MiB wird gelesen; eine gültige PDF
  mit 5 MiB plus einem Byte wird weiterhin vor der Extraktion abgewiesen.
  Nur die PDF-Textextraktion ist in diesen Wire-Tests ersetzt; ihre bestehenden
  Parameter (30 Seiten, 12 Sekunden, ohne OCR) werden geprüft. Die bestehenden
  PDF-/Anlagentests laufen zusätzlich mit.
- Kleine Mails, INBOX/Gesendet, Textgrenze, 40 MiB und 40 MiB plus ein Byte,
  fehlende Größen, kurze/leere Antworten, ignorierte Offsets, Überlieferung,
  veränderte oder doppelte Metadaten, Metadaten hinter der Literale sowie
  Wiederverbindung und wiederverwendete Sitzung sind abgedeckt.
- Sabotage nur im Prozessspeicher: Weglassen der Fortsetzungsprüfung lässt den
  Test für fehlenden Ursprung fehlschlagen. Verdopplung der Gesamtgrenze lässt
  den Test für 40 MiB plus ein Byte fehlschlagen. Dateien blieben dabei unverändert.

Reproduzierbarer gezielter Lauf aus dem Repository mit installierten
Testabhängigkeiten:

```sh
PYTHONPATH=sidecar:. python -m pytest -q \
  sidecar/tests/test_mail_bounded_mime.py \
  sidecar/tests/test_mail_inventory.py sidecar/tests/test_mail_uid.py \
  sidecar/tests/test_mail_inbox_preview_budget.py sidecar/tests/test_mail_session.py \
  sidecar/tests/test_attachment_coverage.py sidecar/tests/test_anhaenge.py
```

Ein zusätzlich versuchter Lauf der bestehenden Socket-Tests für Gesendet konnte
vier Fixtures nicht aufbauen: Die Sandbox verweigert `bind(127.0.0.1)` mit
`PermissionError`. Betroffen: `test_posteingang_und_gesendet_werden_erkannt_und_eingelesen`,
`test_gesendete_zusage_wird_eigene_zusage_und_steht_unter_was_habe_ich_zugesagt`,
`test_altes_konto_liest_gesendet_nach_und_der_stand_sagt_es` und
`test_mail_an_sich_selbst_erscheint_in_beiden_ordnern`. Keine Rechteausweitung.
Die obigen In-Memory-Tests prüfen beide Ordner ohne Socket. Keine vollständige
Projekt-Suite oder reale Postfachabnahme durch diesen gezielten Lauf behauptet.

## Grenze des Nachweises

Akzeptierte Teilbytes und die an den MIME-Parser übergebene Gesamtmenge sind
begrenzt; jede Anfrage enthält eine Bereichsgrenze. `imaplib` puffert jedoch
bereits die vom Server deklarierte Literale, bevor der Connector sie prüft.
Ein regelwidriger Server kann daher weiterhin mehr Transportdaten liefern als
angefordert. Die Reparatur verwirft dessen Überlieferung für die Vollständigkeit
und begrenzt den Parser, ersetzt aber nicht den IMAP-Transport. Keine Behauptung
einer festen Speichergrenze gegen einen bösartigen Server oder einer realen
Anbieter-, Laufzeit- oder Modellabnahme.

## Bereits aufgenommener Bestand

Der vorhandene Wiederholen-Knopf kann aktuelle, nicht ausgeschlossene
Mailquellen mit einem unvollständigen MIME-Bericht erneut in die bestehende
Aufnahme einreihen. Der Status zeigt diese Möglichkeit ohne Mailabruf an.
Auch alte Berichte mit nicht unterstützten Anlagen sind einmalig auswählbar:
Sie enthalten noch keine Formatkennung, daher lassen sich damalige Word-Dateien
und Logos erst nach dem erneuten Abruf unterscheiden.

Schema 26 ergänzt dafür ausschließlich einen persistenten Versionsmarker je
Aufnahmeeintrag. Ordnerverweise derselben Anbieterquelle verbrauchen den Versuch
gemeinsam; nur einer wird geladen. Der Abruf verwendet das bestehende Paketbudget.
Pause, abgeschalteter Zeitplan, fehlende Berechtigung und der leichte Takt für
neue Post verhindern den Altbestandsabruf. Quellenkopf und Fingerabdruck werden
vor und nach dem Lesen geprüft. Der normale Aufnahmeweg erhält die Originalfassung
und veröffentlicht eine neue Fassung nur bei passender Quellenidentität.
Weiterhin unvollständige Ergebnisse werden nicht bei jedem Takt erneut geladen;
unveränderte Logo-Berichte lösen keine neue Modellanalyse aus.

Die gezielte synthetische Nachprüfung und unabhängige Durchsicht dieses
Altbestandswegs werden vor Veröffentlichung separat festgehalten. Dieser Text
behauptet keine Reparatur des persönlichen Bestands und keine bestandene
Modell- oder Mac-Abnahme.
