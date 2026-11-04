# Arbeitskopie nach vollständigem Ausfall

P5-Anschluss an die lesende Vorprüfung. Ziel ist eine normale, lokal benutzbare
Kingfisher-Instanz mit erhaltenem gewähltem Datenstand und frischen Freigaben.
Kein neues Mini-UI als Ersatz für Aufgaben, Projekte und Gedächtnis.

## Entscheidung

Eine getrennte Kopie statt Entfernen der historischen Schutzmarkierung. Der
Nutzer wählt ausdrücklich den restaurierten Stand oder eine der vorhandenen
Vergleichsgruppen. Kein Dateidatum gilt automatisch als Wahrheit, keine Tabellen
werden automatisch vereinigt. Andere Stände bleiben vollständig unverändert.
Unbekannte spätere Änderungen werden ausdrücklich bestätigt, nicht als gelöst
ausgegeben. Diese Implementierungsentscheidung folgt dem autonomen Auftrag.

## Verträge

`recovery_workspace.py` liefert:

- `read_working_contract(directory) -> dict | None`: gültiger, geschlossener
  `restore-state.json`-Vertrag, Version 1, `mode=working_copy`, `policy_version=1`,
  `restore_id` (neue UUID-hex), `source_fingerprint` (64 hex),
  `selection` (`restored` oder Zeitgruppenkennung),
  `unknown_history_acknowledged=true`, `permissions_reset=true`,
  `operational=true`. Keine Symlinks, maximal 8 KiB. Kein Vertrag heißt keine
  besondere Arbeitskopienfreigabe; vorhandene ungültige Marker bleiben gesperrt.
- `prepare_working_copy(source, target, *, fingerprint, selection,
  acknowledge_unknown) -> Path`: nur neues Ziel außerhalb des Originalbaums.
  Frischen Preflight gegen Fingerprint prüfen; nur reguläre, lesbare Dateien
  des ausdrücklich gewählten Stands kopieren. Mindestens eine DB, kein
  ungeklärter vorhandener Bereich, keine Schreib-Sidecars. Fehlende Bereiche
  bleiben im Bericht sichtbar; normale Store-Migrationen dürfen sie anlegen.
  Nach Kopieren Original erneut gegen ursprünglichen Fingerprint prüfen.
  Fehler hinterlassen weder veröffentlichtes Ziel noch veränderte Originale.
- `launch_environment(folder) -> dict`: nur kleine Host-Allowlist
  (`PATH,HOME,USER,LOGNAME,TMPDIR,LANG,TZ,LC_*`), neu erzeugte
  `ICARUS_DATA_DIR`, `ICARUS_SIDECAR_TOKEN`, `ICARUS_SECRETS_PASSPHRASE`,
  `ICARUS_RECOVERY_BOOT_ID`. Keine alten Anbieter-, Connector-, Harness-,
  Proxy- oder Telemetrievariablen. Startdatei liegt außerhalb `data` mit 0600.
- `boot_allowed(directory, environ) -> bool`: Vertrag und Boot-ID müssen
  übereinstimmen; sonst Inspection vor jedem Store/Schlüssel/Adapter. Die
  Startumgebung muss genau der Allowlist entsprechen. Nach dem Start kann die
  normale Einrichtung neue Einstellungen/Schlüssel setzen.

Die Arbeitskopie enthält `data/` und eine neue private `settings.env`. Alte
Schlüsseldatei und historische Umgebung werden nicht in den aktiven Bestand
übernommen; sie bleiben im Original erhalten. Metadaten zur Herkunft und den
zurückgesetzten Rechten liegen in einer privaten Quittung außerhalb `data`.

## Rechte zurücksetzen, Inhalte behalten

Frische Settings; alte eigene Adressen und deaktivierte Konten/Kalender sowie
rein lokale Zuordnungs-/Anzeigepräferenzen dürfen erhalten bleiben. Kein
Modell, Sync, Zeitplan, MCP, externe Wetter/News/Logo-Freigabe, automatischer
Export oder Hintergrundimport. Taskauto ausdrücklich aus. Updateprüfung aus.
Aktive Dauerregeln werden in der Kopie widerrufen. Aktive persönliche Skills
werden zur erneuten Prüfung vorgemerkt (Inhalte/Versionen bleiben erhalten,
Bestätigungsbasis wird konsistent auf die verbleibenden bestätigten Versionen
gesetzt). Bestehende Widerrufe bleiben Widerrufe. Mac-Kalenderfreigabe aus,
gespeicherte Daten erhalten. Alte Aktions-/Cloudhistorie bleibt erhalten;
frische Schlüssel/Einwilligungen werden über die bestehenden Produktwege nötig.

Der Schlüsselzugang aller normalen und Fallback-Konstruktoren erkennt den
Arbeitskopienvertrag: eigener verschlüsselter Dateispeicher, kein globaler
OS-Schlüsselbund. `server.create_app` verweigert unsauberen Start vor jedem
Aufbau. `restore_boundary.pending` erkennt nur den gültigen Arbeitsvertrag;
normale Restores schreiben weiterhin ausschließlich Inspection-Marker.

## Abnahme

Künstlich reichhaltiger Altbestand samt gefährlicher Environment- und
Schlüsselbund-Vorbelegung; gewählte Daten bleiben erhalten, vorhandene Entzüge
im gewählten Stand wirken. Quellen/Projekt/Task normal lesen, neue Aufgabe
speichern und nach Neustart wiederfinden. Keine alten Kontakteinwilligungen,
Modellaufrufe, Syncs oder automatischen Aktionen. Ungültiger Vertrag,
veränderter Prüfbefund, Symlink, Kopierfehler und vorhandenes Ziel scheitern
geschlossen. Originale bleiben unverändert.

Der erste Ausführungsweg ist ein kontrolliertes lokales Startskript. Die
Produktbedienung im nativen Wiederherstellungsablauf sowie aktuelle individuelle
Wiederfreigaben bleiben separat abzunehmen. Dieser technische Nachweis allein
schließt P5 und die Nutzungswoche nicht ab.
