# Getrennte Wiederherstellung aus dem Mac-Menü

Anschluss an `93698ef`: Der bestehende Wiederherstellungskern erhält einen
nativen Bedienweg. Im App-Menü stehen „Sicherung wiederherstellen …“ und
„Arbeitskopie öffnen …“. Datei, Passwort und Ziel kommen aus eigenen Dialogen.
Ein Prüfbericht zeigt auswählbare Datenstände, fehlende Bereiche und Details.
Es gibt keine Vorauswahl des vermeintlich neuesten Stands. Die unbekannte
spätere Historie muss ausdrücklich bestätigt werden.

Die Kopie verwendet die normale Kingfisher-Oberfläche in einem eigenen Fenster.
Konten, Modelle und automatische Aktionen müssen neu freigegeben werden.
Originalsicherung, persönliche App und fremde Vergleichsstände werden nicht
verändert oder zusammengeführt. Die Arbeitskopie behält beim Wiederöffnen ihre
gespeicherte App-Version, auch nach einem Update der Haupt-App.

## Technische Prüfung

- 108 betroffene Backend-/Helfertests bestanden. Dazu gehören vorhandene
  Quelldaten, Rechte-Reset, neue Schlüssel, Änderungen während der Prüfung,
  konkurrierende Ziele, fehlerhafte Verträge, Start und Wiederöffnung.
- 37 betroffene native Tests bestanden, einer übersprungen. Vollständiger
  Swift-Typecheck bestanden. Unabhängige Fokusprobe: sechs Fälle bestanden.
  Diese Läufe überschneiden sich und werden nicht addiert.
- Der Helfer akzeptiert nur einen vorhandenen lokalen Docker-Unixsocket und
  bindet alle Folgeaufrufe ausdrücklich daran. Netzlose Datenarbeiter sehen
  die historische Quelle nur lesend und einen neuen privaten Zielordner
  schreibend. Keine impliziten Downloads oder Remote-Docker-Verbindungen.
- Echter lokaler Docker-Ablauf mit künstlicher verschlüsselter Sicherung:
  entschlüsseln, prüfen, vorbereiten, normalen Server ohne Fenster starten,
  künstliche Aufgabe speichern, eigenen Container stoppen, erneut öffnen und
  dieselbe Aufgabe lesen. Originaldateien blieben bytegleich. Wiederöffnung
  funktionierte auch ohne übergebenes Haupt-App-Image; Instanzkennung und
  gespeicherte Version blieben gleich. Anschließend wurde nur dieser eigene
  Testcontainer gestoppt; die Kopie blieb erhalten.
- Cookie-/Browserspeicher der Arbeitskopie ist von der Haupt-App getrennt.
  Native Kalender-, Sprach-, Update- und Modulbrücken sind im separaten Fenster
  nicht angeschlossen; es gibt keinen Rückfall auf den persönlichen Dienst.
- Unabhängiges Review fand zwei Fensterprobleme: Entwurfsverlust beim Schließen
  auch unter neuerem macOS und ein globales Cmd-R, das die Haupt-App adressierte.
  Alle Arbeitskopienfenster warnen nun beim Schließen/Beenden; Neu laden folgt
  dem aktiven Fenster und ist während Auswahl/Vorbereitung deaktiviert.
  Separate Fokus-/Schließregressionen scheiterten vor den Korrekturen.

Der erste Offline-Versuch vor dem finalen Helferstand scheiterte bei `prepare`
mit einer allgemeinen Fehlermeldung. Eine genaue Ursache konnte nicht mehr
gesichert werden. Die anschließende Diagnose legte die Kopie an; drei weitere
Prüfberichte waren identisch, Vorbereitung und abschließender frischer
Gesamtablauf bestanden. Das ist kein Nachweis, dass jede mögliche Umgebung
bereits abgedeckt ist.

Der normale ARM-Paketbau mit `macos/build_dmg.sh` bestand einschließlich
Signaturprüfung und DMG. Der gebündelte Helfer stimmt bytegleich mit dem
geprüften Quelltext überein. Das lokale Testpaket trägt die bestehende
Versionsmarke 1.0.44; es ist kein neues veröffentlichtes Release. Der erste
Sandbox-Bau scheiterte am Icon-Konverter trotz korrekter Bildgrößen; derselbe
Konverter und anschließend der Paketbau bestanden mit der dafür erteilten
Ausführungsfreigabe. Die hdiutil-Abkündigungswarnung bleibt dokumentiert.

## Zusätzliche Fehlerkorrekturen

Der GitHub-Lauf auf `93698ef` zeigte unter Python 3.10 zwei tatsächliche Fehler:
Ein stark verschachtelter Vertragsmarker konnte `RecursionError` durchlassen;
der Parser verwirft ihn nun kontrolliert. Eine zusätzliche simulierte
Decodergrenze scheiterte vor dem Fix und besteht danach. Der bestehende echte
JSON-Fall bleibt erhalten. Python 3.10 liefert außerdem noch keinen
`sqlite_errorcode`: Eine kaputte Datei wird konservativ als `unreadable`
gesperrt, statt als `corrupt`. Der Test berücksichtigt diesen Unterschied;
Fehlertexte werden nicht als verlässlicher Fehlercode interpretiert.

Beim Entpacken gab es ein Rennen zwischen Zielprüfung und Verzeichnisumbenennung.
Die vorhandene atomare No-Replace-Funktion schützt jetzt auch diesen Schritt.
Der neue Regressionstest erzeugt genau zwischen Prüfung und Veröffentlichung
ein Ziel und bestätigt, dass es erhalten bleibt. Vor dem Fix scheiterte er.

Die älteren Prüfstände bleiben getrennt: Auf `93698ef` bestanden Container,
UI und Python 3.12; Python 3.10 hatte die oben genannten zwei Fehler. Es wurde
kein manueller CI-Neustart ausgelöst. Der neue Stand benötigt seine eigene CI.

## Grenze der Aussage

Keine persönlichen Quellen, Cloud-Aufrufe, Modellstarts oder API-Kosten.
Keine Installation in der persönlichen App. Die echte native Fensterprüfung
wartet weiterhin auf die konkrete Freigabe der getrennten Produkt-Test-App;
sie wurde nicht durch einen anderen Browser ersetzt. Kompilierung, isolierte
Logiktests und HTTP-Nachweise sind keine visuelle oder operative Mac-Abnahme.
Ungesendete Browserentwürfe werden nicht als dauerhaft gespeichert versprochen.
P5 und Nutzungswoche sind offen; der Großimport bleibt pausiert.
