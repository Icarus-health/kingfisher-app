# Fortlaufende Aufnahme aus einem ausgewählten Mac-Ordner

Stand: 8. September 2026. Roadmap weiterhin **14/20 = 70 %**.
Punkt 09 bleibt offen, bis auch ein echter Mailanbieter geprüft ist.

## Verhalten

Ein eigener lokaler Ordnerhelfer übernimmt ausschließlich den lokal gewählten
Ordner. Die App kann dessen Aufnahme aktivieren, pausieren oder erneut anfordern;
sie kann dem Helfer keinen anderen Dateipfad vorgeben. Ohne Ordnerauswahl und
Aktivierung wird nichts eingelesen. Der bestehende Mac-Starter liest die Auswahl
bei Bedarf aus `<private-env-basename>.folder.json` neben seiner privaten
Konfiguration, zum Beispiel `{"folder":"/absoluter/ausgewaehlter/Ordner"}`.
Die Datei gehört zum lokalen Mac-Setup und wird nicht ins Repository übernommen.
Nach einer Wiederherstellung auf einem anderen Mac muss der Eingangsordner dort
neu ausgewählt werden.

Unterstützt sind UTF-8-Text, Markdown, Org, RST, CSV, DOCX-Haupttext, PDF-Textebene
und SRT/VTT aus beispielsweise MacWhisper. Der Helfer erstellt keine Aufnahmen.
Alle Belege landen in denselben Episoden- und Wissensspeichern wie manuelle Importe.
Originalquellen lassen sich direkt in der Oberfläche öffnen.

Grenzen: 2.000 verwaltete Dateipfade, 5 MiB pro Datei, 512 KiB extrahierter Text;
versteckte Dateien/Ordner und symbolische Links werden nicht verfolgt. Die Prüfung
läuft einmal pro Minute. Dateien müssen seit mindestens zwei Sekunden stabil
sein. Ein unvollständiger oder fehlgeschlagener Scan gilt niemals als leerer
Ordner. Unveränderte Bytes werden nicht erneut geparst. Ein erneuter identischer
Import hebt einen ausdrücklichen Quellenausschluss nicht automatisch auf.

Neue Dateifassungen entwerten die bisherigen Belege. Bei ungültigem übertragenem
Inhalt wird auch der alte Beleg ausgeschlossen. Gelöschte Dateien werden erst
nach einem vollständigen Scan ausgeschlossen; historische Belege bleiben
aufrufbar. Ein ausgetauschter Ordner entwertet alte Quellen und erfordert neue
Freigabe. Pause und neue Läufe sperren verspätete Übertragungen über Laufkennung
und Freigabeversion. Der Helfer verwendet eine lokale HTTP-Adresse, keine
Umgebungs-Proxys und keine Weiterleitungen für sein Authentifizierungstoken.

Mailabrufe speichern jetzt einen bereinigten letzten Erfolgs-/Fehlerstatus über
Neustarts hinweg. Konten ohne Zugangsdaten sind nicht für die automatische
Aufnahme auswählbar. Ein echter Mailzugang wurde dabei nicht eingerichtet.

## Prüfung

- Gesamtsuite: 1.121 bestanden, zwei übersprungen (vor den letzten drei
  ergänzten Ordnerregressionstests). Zwei bekannte Starlette/httpx-Warnungen.
- Anschließend 53 gezielte Tests bestanden: Ordner-API, Mac-Helfer, Mailstatus,
  Zeitplan und Mac-Starter, einschließlich der abschließenden Änderungen.
- UI-Build und Docker-Build bestanden; Assetmanifest: 14 Dateien, 17 Icons.
- Isolierter Docker auf Port 8897 mit ausschließlich synthetischen Quellen:
  echter HTTP-Token, Text in Unterordnern, VTT, Dubletten, neue Fassung,
  entfernte Quelle, Pause, Containerneustart und tatsächlicher Hintergrundprozess
  bestanden. Testquellen gelangten nicht in den Nutzerbestand.
- Browser: Aktivieren, Jetzt prüfen, Pausieren, Dateiliste und Quellenausschluss
  bedient; kein horizontaler Überlauf, keine Konsolenfehler im isolierten Lauf.
- Vor lokaler Aktualisierung: Datenvolume mit 181 Dateien kopiert und jede Datei
  per SHA-256 verglichen. Vorheriger Container und Sicherungsvolume bleiben
  erhalten. Lokaler Mac-Starter startet genau einen Ordnerhelfer.

## Offene Abnahme

Der Nutzer hat den neuen leeren Ordner `Dokumente/Kingfisher-Eingang` freigegeben.
Er ist lokal eingerichtet. Für Punkt 09 fehlt der ausdrücklich ausgewählte echte
Mailanbieter einschließlich Zugang und Ende-zu-Ende-Prüfung. Die vollständige
visuelle Überarbeitung bleibt der anschließende eigene Schritt (Punkt 16).
