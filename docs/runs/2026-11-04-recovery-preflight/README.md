# Sicherungen prüfen, ohne historische Rechte wiederzubeleben

## Ergebnis

Die historische Wiederherstellungsansicht hat jetzt einen ausdrücklich gestarteten
Prüfweg. Er untersucht die zentrale Sicherungs-Allowlist, meldet lesbare,
fehlende und ungeklärte Datenbereiche und vergleicht vorhandene
`.vor-wiederherstellung-*`-Gruppen getrennt. Keine Daten werden geändert oder
automatisch vereinigt. Modelle, Konten und Aktionen bleiben ausgeschaltet.

Ein reiner Dateivergleich genügt nicht: Eine nach dem Snapshot entzogene Quelle
und ein widerrufener Skill haben weiterhin dieselbe Zeilenzahl. Die neue Probe
erkennt beide Änderungen anhand eindeutig zugeordneter Tabellenzeilen.
Gleiche Tabellen nach SQLite-Neuordnung werden dagegen nicht als geänderte
Zeilen ausgegeben. Namen, Inhalte, einzelne Schlüssel und Zeilenhashes gelangen
nicht in den Bericht. Aufbewahrte Einstellungen/Schlüssel werden nur als Dateien
mit Prüfsummen erfasst, nicht eingelesen oder aktiviert.

**Kein Abschluss der operativen Wiederherstellung:** Die Dateinamen beweisen
weder Herkunft noch Reihenfolge. Eine unbekannte spätere Korrektur kann fehlen.
Deshalb bleiben `operational`, `activation_allowed` und `comparison_complete`
ausdrücklich false. Der Berichts-Fingerprint ist keine Freigabe und kein Token.

## Technische Grenzen

- Neue authentifizierte Route `POST /api/v1/recovery/preflight`, nur `{}`.
  Ohne konfigurierten lokalen Zugang 503, ohne gültigen Zugang 401. Ein weiterer
  Prüfauftrag in derselben App wird während laufender Prüfung mit 409 abgewiesen.
- SQLite ausschließlich lesend/immutable, ohne Store-Konstruktoren/Migrationen.
  WAL/SHM/Journal einschließlich möglicher Sidecars am ursprünglichen Dateinamen
  bleiben ungeklärt. Symlinks, beschädigte/neue Schemas und veränderte Dateien
  dürfen nicht als unveränderte Inhalte durchgehen.
- Fingerprints sind typisiert; Tabelle ohne brauchbaren eindeutigen Schlüssel,
  virtuelle Tabelle oder abweichendes Schema erhält keine erfundene Null bei
  den Änderungszahlen. Alle Sicherungsbereiche werden inventarisiert.
- Kooperative Arbeitsgrenzen: 15 Sekunden, 200.000 gelesene Tabellenzeilen,
  512 MiB insgesamt gelesene Hashdaten, acht Vergleichsgruppen, 10.000
  Verzeichniseinträge und 128 Tabellen je Datei. Erreichte Grenzen bleiben
  sichtbar. Dies ist keine harte Unterbrechung blockierender Dateisystem-I/O.
- Der Bericht verändert die Inspection-Markierung nicht. Kein neuer Startpfad,
  keine Arbeitskopie und keine Quelle werden durch diese Lieferung freigegeben.

## Gegenprüfung

- Erste neun Tests vor Implementierung rot: Route fehlte (423).
- 18 gezielte Backendfälle bestanden: Quelle/Skill nach Snapshot entzogen,
  getrennte Vergleichsgruppen, Typunterschiede Text/BLOB, fehlende/unlesbare
  Daten, neue Schemas, WAL, Symlink, geänderte Datei, Limits, Authentifizierung,
  keine privaten Inhalte, wiederholte Prüfung ohne Datenänderung.
- Unabhängiges Backendreview fand zwei Fehler: Fehlercode-Konstanten neuerer
  Python-Versionen und falsche Schlüsselposition bei generierten Spalten.
  Beide separat rot reproduziert, korrigiert und grün geprüft. Kein echter
  Python-3.10-Lauf lokal; dessen fehlende API wurde gezielt nachgestellt.
- 82 betroffene Wiederherstellungs-/Boundary-/Launcher-Tests bestanden in
  14,55 s. Der erste Lauf hatte 78 erfolgreiche Fälle und einen Sandboxfehler
  beim Binden eines lokalen Testports; die genehmigte Wiederholung des
  synthetischen Launcher-Tests und danach der betroffenen Suite bestanden.
  Kein echter Docker-/App-Start durch diese Tests.
- Zusätzliche Kontrolle der vollständigen verschlüsselten Sicherung:
  alle 18 SQLite-Bereiche und beide Zusatzdateien lesbar; Aufgaben, Quellen,
  Beziehungen, Skills und Korrekturen bleiben nach dem Roundtrip erhalten.
  Nach letzter Änderung 20 direkte/angrenzende Backendtests in 4,46 s bestanden.
- Unabhängiges UI-Review reproduzierte frühe/leere und überholende Ladeanfragen,
  eine irreführende 409-Meldung und einen unbelegten Datenerhalt-Satz. Behoben;
  die zwei funktionalen Fälle vorher rot, danach grün. Die Einleitung sagt
  jetzt nur, dass ein historischer Stand vorliegt.
- 1.083 Frontendtests in 12,44 s bestanden, darunter sieben Tests des tatsächlich
  eingebetteten Seitencontrollers mit künstlicher DOM-/Fetch-Grenze. Kein
  Browser- oder Fensternachweis. Bestehende Starlette/httpx-Warnung bleibt.

Produktions-/Testdateiprüfsummen: [validation.json](validation.json).

## Offen

Aktuelle Zustandsabstimmung, eine separate normale Arbeitskopie, neue Rechte
und ein sicherer Start ohne geerbte Umgebungs-/Betriebssystemschlüssel. Danach
eine neue Aufgabe speichern und nach Neustart abrufen. P5 bleibt offen.

Die native Start-/Nutzungsfreigabe für das getrennte Testfenster steht weiterhin
aus; kein Umweg verwendet. Keine Installation, keine privaten Daten, keine
Modell-/Cloudaufrufe und keine API-Kosten. Großimport weiterhin pausiert.
Der vorherige PR124-Head bf78d764 bestand CI41900788227 und Container41900788301;
das ist kein CI-Nachweis für diese spätere Änderung.
