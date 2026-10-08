# Akku-Schutz für automatische Mac-Verarbeitung

Der Nutzer musste Kingfisher beim Schreiben eines Protokolls schließen, weil der
Akkuverbrauch seine übrige Arbeit störte. Der gemessene Zustand am Folgetag
belegt nicht den Verursacher des Vortags: der persönliche Dienst 1.0.5 lief noch,
war in der Einzelmessung aber kaum ausgelastet. Auch eine getrennte ältere
Testinstanz und andere Docker-Dienste waren aktiv. Kein Dienst wurde gestoppt,
kein persönlicher Bestand neu verarbeitet und kein Modell gestartet.

## Änderung

- Beide nativen App-Wege melden nur `ac`, `battery` oder `unknown` an den eigenen
  authentifizierten Loopback-Endpunkt. Sofortiger Bericht nach erfolgreichem
  Start, anschließend alle 30 Sekunden. Keine Weiterleitungen, kurze Zeitlimits,
  begrenzte Antwortgröße, keine Prozentsätze, Nutzungsdaten oder Identifikatoren.
- Automatische Schedulerarbeit einschließlich Mailaufnahme wartet auf Akku oder
  ohne frischen Bericht. Nach 90 Sekunden ist eine Messung ungültig. Ein Bericht
  vom vorherigen Prozessstart wird nie wiederverwendet. Die Pflicht zur Meldung
  bleibt gespeichert, auch wenn später das Geräteprofil fehlt.
- Manuelle Pause und Modellfreigaben bleiben eigenständig. Direkte Anfragen und
  Lesen bleiben möglich. Der Fortschritt zeigt den Wartegrund auch beim reinen
  Mailimport und nennt während der Energiesperre keine Fertigstellungszeit.
- Eine bereits laufende Modellanfrage darf enden. Vor einem weiteren Aufruf
  tritt der Hintergrund geordnet zum nächsten Scheduler-Takt zurück; die
  Energiepause darf keine Ausführungssperre oder Wiederherstellungsfreigabe
  dauerhaft halten. Sie zählt nicht als Anbieter- oder Quellenfehler.
- Fertige Abschnitte der aktuellen Quelle bleiben im vorhandenen begrenzten
  RAM-Zwischenspeicher für die Fortsetzung. Ein Prozessneustart kann diese
  noch unbestätigten Abschnitte erneut auswerten; gespeicherte Quellen und
  abgeschlossene Einordnungen bleiben erhalten.
- Fassung 1.0.6 verlangt das neue native App-Bündel. Nur das Backend in einer
  älteren App auszutauschen liefert den Reporter nicht nach.

## Gegenprüfung und Grenzen

Das unabhängige Review fand die fehlende Markeranlage bei bereits bekanntem
Mac-Profil sowie eine unbegrenzte Wartezeit innerhalb eines laufenden
Schedulerjobs. Beide Korrekturen erhalten gezielte Regressionen. Ein erneuter
Legacy-Start erzeugt keinen zweiten Reporter.

## Prüfung am 8. Oktober

- 145 gezielte Backendprüfungen bestanden, eine bestehende Prüfung übersprungen:
  Hostmessung, Energieunterbrechung, Hintergrund, Zeitplan, Aufgabenprüfung,
  Arbeitsspeicher, Upload-Einordnung, Lernplan, Wiederherstellungsgrenze und
  Release-Seite. Zusätzlich 29 Sicherungs-/Update-Sicherungsprüfungen bestanden.
- 355 UI-Logik-/Vertragsprüfungen bestanden; TypeScript und Produktionsbuild
  erfolgreich. Bestehender Hinweis zur JavaScript-Bündelgröße bleibt.
- 26 Mac-App-Prüfungen bestanden; eine Prüfung des Nicht-Mac-Abbruchs ist auf
  macOS erwartungsgemäß übersprungen. Darin wird das Swift-Logikprogramm samt
  Energieparser und Anfragevertrag wirklich übersetzt und ausgeführt.
- Beide nativen App-Wege separat für macOS 11.3 erfolgreich typgeprüft. Der
  beschreibbare Clang-Modulcache liegt nur für diese Prüfung unter `/private/tmp`.
- Die neuen Sichtbarkeits- und Neustarttests scheiterten vor ihren jeweiligen
  Korrekturen. Die zusätzlichen Energieunterbrechungsfälle prüfen Locks,
  abgelaufene Hostmessung, manuelle Pause, Stop, Analyse-Leases und Fortsetzung
  ohne Wiederholung schon fertiger Abschnitte.
- Release-Vorprüfung für `v1.0.6` und `git diff --check` erfolgreich. Keine
  vollständige Wiederholung sämtlicher Backendtests und kein CI-Neustart.

Native Übersetzung und Logiktests belegen keinen Fenstertest oder gemessenen
Akkurückgang. Kein persönlicher Pilot wurde aktualisiert, keine App installiert,
kein Release veröffentlicht. Docker, andere Container, separat gestartete
Quellenhelfer und bewusst ausgelöste Modellanfragen bleiben außerhalb dieses
automatischen Zeitplan-Schutzes. Das Schließen des Fensters stoppt diese Prozesse
nicht. Die Messung im echten Alltag nach vollständiger Aktualisierung bleibt
offen.
