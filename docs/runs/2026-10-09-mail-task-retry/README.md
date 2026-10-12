# Manuell geprüfte Mailaufgaben nach verlorener Antwort

Codebasis: `3667e4e18b9e255780c755889370b46368cf0a6d` (main). Implementierungsstand: `061acef414cc213c24ebd10006c7a7aa0d6e902b`; dessen Backend-Dateien und Backendtests sind bytegleich zum vollständig geprüften Archiv `d14c28b`. `061acef` ergänzt nur die kompakte Bestätigungsdarstellung; die vollständige UI-Prüfung und der Build laufen auf dessen sauberem Archiv. Diese Lieferung ist unabhängig vom Voice-/CoS-Preview und noch nicht auf dem persönlichen Mac installiert.

## Problem und Verhalten

Der manuelle Mailaufgaben-Endpunkt legte bei jeder Wiederholung eine neue Aufgabe an. Nach erfolgreicher Speicherung mit verlorener Antwort konnten deshalb zwei Aufgaben entstehen. Außerdem ließ sich aus einer bereits ausgeschlossenen Originalquelle weiterhin eine neue manuelle Aufgabe anlegen.

Der manuelle Formularweg behält jetzt eine zufällige Auftragskennung bis zur bestätigten Speicherung. Sie wird vor der Anfrage lokal abgelegt; erneutes Öffnen desselben Formulars kann sie wiederverwenden. Gespeichert werden nur Mail-UID und Kennung, weder Mailtext noch Aufgabenfelder. Fehler beim dauerhaften Ablegen sperren die Anfrage. Mehrfaches Absenden vor einer erneuten React-Darstellung wird ebenfalls verhindert.

Der Server bindet die Kennung an Quelle, Textstelle, Titel, Projekt, Fälligkeit und wartende Person. Derselbe Auftrag gibt die aktuelle Aufgabe zurück, einschließlich späterer Bearbeitung oder Erledigung; geänderte Felder mit bereits verwendeter Kennung ergeben 409. Quellenänderung, entfernte Mailanbindung und ausgeschlossene Quelle werden vor der Wiederholung geprüft. Die ursprüngliche Originalquelle bleibt erhalten.

Nach einer ungeklärten Antwort bleiben Wiederholung und Aufgabenprüfung möglich. Ein bewusst neuer Auftrag benötigt die ausdrückliche Bestätigung, dass vorhandene Aufgaben geprüft wurden; der Knopf bereitet nur vor. Sichtbare Felder und zuvor gelesene Quellenfassung bleiben erhalten, es gibt weder automatisches Speichern noch stilles Umbinden auf eine neue Originalfassung. Eine fremde ungeklärte Kennung wird durch diesen Weg nicht gelöscht.

## Speicherung und Verträglichkeit

TaskStore-Migration 3 ergänzt ausschließlich `task_requests`. Aufgabe, anfänglicher Wartestatus, Historieneintrag und Auftragsbindung werden in einer SQLite-Transaktion geschrieben. Fehler rollen alle vier Teile zurück. Vorhandene Aufgaben und Historie werden durch die Migration nicht umgeschrieben. Ältere TaskStore-Versionen unterstützen dieses Schema nicht; für ein Zurücksetzen ist die Sicherung vor dem Update nötig, kein Öffnen der migrierten Datei mit alter Software.

`request_id` bleibt für ältere API-Aufrufer optional. Deren manueller Weg besitzt dadurch weiterhin keine Wiederholungsgarantie. Das neue Formular sendet die Kennung immer; die direkte Vorschlagsübernahme verwendet weiterhin ihre bestehende Inhalts-/Quellenidentität. Absichtlich neue Aufträge mit verschiedenen Kennungen dürfen dieselben Felder enthalten. Es wird keine globale Deduplikation verschiedener Nutzeraktionen oder gleichzeitiger unabhängiger Browserfenster behauptet.

## Prüfungen und Grenzen

* Vorher: neue Endpunktkontrollen gegen das unveränderte main-Archiv: 7 erwartete Fehlschläge, 1 unveränderter positiver Kontrollfall. Die Fehlschläge betreffen Duplikate, Neustart/Bearbeitung, unzulässiges Umbinden und Quellenentzug.
* Gezielte Server-, Transaktions-, Migrations- und Historienkontrollen: 75 bestanden. Enthalten sind zwei parallele Storeverbindungen, vollständiger Rollback bei Fehler in Historie oder Bindung, v2-Upgrade und Sicherungs-/Wiederherstellungswege.
* Elf echte TSX-Handlerkontrollen, einschließlich Wiederöffnung, alter WebKit-Zufallsquelle, Speicherfehlern, bewusstem Neuauftrag und fremder Kennung. Die anfänglichen Fehler und der unabhängige Reviewfund wurden jeweils zuerst reproduziert, dann korrigiert.
* Sauberes Git-Archiv `061acef`: vollständige UI-Suite 439 bestanden; TypeScript-/Vite-Build bestanden (bestehender Hinweis auf große Bundle-Datei).
* Vollständiger Backendlauf auf `d14c28b`: 5904 bestanden, 26 Unterprüfungen bestanden, 1 erwarteter plattformspezifischer Skip. Ein Repository-Lint scheiterte zunächst ausschließlich an fehlenden Git-Metadaten des Archivs (`git ls-files`, Exit 128); der Lauf hatte deshalb Exit 1. Dieselbe Kontrolle bestand danach im echten Repository und im Archiv mit dem ursprünglichen getrackten Dateiinventar. Kein Produktcode musste dafür geändert werden; kein zweiter vollständiger Backendlauf wird behauptet.
* Assetprüfung bleibt rot: `Icon nicht in Manifest-Allowlist: expired`. Der identische Fehler wurde separat gegen das unveränderte main-Archiv reproduziert. Der globale Stringpaar-Regulärausdruck des Prüfers behandelt unter anderem die Statusliste `["failed", "expired"]` wie Iconreferenzen. Dieser Patch ergänzt keine Icons; die Prüferkorrektur bleibt separat offen und der rote Check wird nicht als grün gezählt.

Ein erster Vollversuch im Arbeitsordner wurde abgebrochen: 11 fehlgeschlagen, 36 Setupfehler, 2502 bestanden, 1 übersprungen. Das war kein grüner Abnahmenachweis; localhost-Testserver wurden durch die Sandbox blockiert und der Ordner enthielt unversionierte ältere Synchronisationskopien. Die Originalkopien wurden nicht gelöscht. Die abschließende Prüfung erfolgt aus dem versionierten Archiv mit ausschließlich künstlichen Daten und lokalen Testservern.

Unabhängiger begrenzter Code-Review: Das zunächst gemeldete Risiko produktiver Testdaten wurde nach Prüfung des bestehenden Autouse-Isolationsfixtures zurückgenommen; das neue Fixture setzt den Datenpfad zusätzlich ausdrücklich. Bestätigte Reviewpunkte waren die verlorene Kennung bei Wiederöffnung, der fehlende bewusste Recovery-Weg und ein zu schwacher Vergleich mit einer fremden gespeicherten Kennung; alle wurden korrigiert und mit echten Handlerkontrollen geprüft. Der Reviewer führte selbst keine Tests aus.

Keine reale Mail, kein persönlicher Kalenderbestand, keine Modellinferenz und kein nativer Fenstertest wurden für diese Lieferung verwendet. Die korrekte inhaltliche Erkennung von Aufgaben, Personen und Fristen am persönlichen Bestand und der echte Tagesablauf bleiben eigene Abnahmegates. Der Pilotimport bleibt pausiert. Der Nutzer hat den Fenstertest verschoben. Die reale Browser-/Mac-Bedienkontrolle sowie der rote Assetcheck bleiben vor einer Produktabnahme offen; diese Lieferung bleibt ein Draft-PR.
