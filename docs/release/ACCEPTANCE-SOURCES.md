# Abnahme 10: Quellenverhalten

Stand: 8. September 2026. Der bestehende Abnahmepunkt lautet unverändert:
**„Quellenänderung, Entzug, Teilausfall und Wiederholung nachvollziehbar behandeln“.**
Er ist erfüllt. Damit sind 11 von 20 Punkten abgenommen (55 %).

## Anforderung und Beleg

| Anforderung | Geprüftes Verhalten | Nachweis |
| --- | --- | --- |
| Quellenänderung | Ordnerdateien: Text und Metadaten bilden nachvollziehbare Fassungen, frühere Belege und abhängiges Wissen werden gesperrt. Geleerte Dateien und entfernte CSV-Zeilen werden berücksichtigt. Mail: Konto/Server-UID trennen Quellen; erneute Aufnahme einer Änderung sperrt nur den betroffenen Beleg. Kalender: vollständige Snapshots ersetzen Änderungen und entfernen entfallene Termine. | test_source_versions.py; test_mail_ingestion.py; test_mac_calendar.py einschließlich test_changed_and_deleted_events_replace_snapshot_without_duplicates; Docker-Abläufe in SOURCE-VERSIONS-QA.md |
| Entzug | Kalenderfreigabe/Quellenauswahl sperrt alte und verspätete Daten; Mailentzug während Abruf verhindert Aufnahme. Gespeicherte Episoden können in ihrer Originalansicht ausdrücklich ausgeschlossen werden. Die Akte aktualisiert sich, abhängige Aussagen bleiben nur im fraglichen Verlauf. | test_mac_calendar.py; test_mail_conversation_flow.py; test_source_exclusion.py; gemeinsamer Browserablauf unten |
| Teilausfall | Nicht lesbare Dateien sind keine angenommenen Löschungen. Begrenzte oder fehlerhafte Läufe melden Probleme. Ein fehlender Kalender oder Gedächtnisbereich verdeckt gesunde Bereiche nicht. Unlesbare Dokumente werden vor Aufnahme abgewiesen; Mailfortschritt bleibt vor der fehlgeschlagenen Nachricht. | test_ingest.py; test_document_text.py; test_document_upload.py; test_calendar_preparation.py; test_mail_ingestion.py |
| Wiederholung | Entdopplung je identifizierter Quelle, erhaltener Mailfortschritt, idempotenter Entzug und explizite Wiederzulassung. Neustart und Sicherung erhalten Originale/Versionszeiger. Wiederzulassung und Rückkehr zu alten Fassungen bestätigen kein früheres Wissen. | test_source_versions.py; test_source_exclusion.py; test_mail_ingestion.py; test_complete_recovery.py |
| Sichtbarkeit und gemeinsamer Kern | Originaltext/Herkunft bleiben lesbar. Die Mailansicht unterscheidet geändert, bekannt und ausgeschlossen. Ausschluss/Abbrechen/Fehler/Wiederholen/Wiederzulassung verwenden dieselben geschützten Endpunkte und denselben Claim-Store. | MailReader.tsx; ProfileSource.tsx; Docker-Browser und SOURCE-VERSIONS-QA.md |

## Gemeinsamer Abschlusslauf

137 Tests aus test_mac_calendar.py, test_calendar_preparation.py,
test_source_versions.py, test_source_exclusion.py, test_ingest.py,
test_document_upload.py, test_document_text.py, test_mail_ingestion.py,
test_mail_conversation_flow.py, test_mail_uid.py und test_complete_recovery.py
bestanden. Der vorherige vollständige Backendlauf bestand mit 980 Tests;
seitdem wurde produktiv nur die gemeinsame Ausschlussbedienung ergänzt.
UI-Build und Assetmanifest (14 Dateien, 17 Icons) bestanden.

Geschützter Docker-Browser bei 1521 × 1034 und 1280 × 900:
Eine bestätigte Mailaussage öffnen, Originalquelle öffnen, Ausschluss abbrechen,
einen 503-Ausfall auslösen und wiederholen, Ausschluss bestätigen, aktualisierte
Akte ohne aktuelle Aussage sehen, alten Originaltext öffnen, Quelle wieder
zulassen ohne Wissensbestätigung und erneut ausschließen. Ein unabhängiger
Beleg bleibt gültig. Keine unerwarteten Konsolen- oder Seitenfehler.
Screenshot source-exclusion-profile.png visuell geprüft. Browser plugin nicht
verfügbar; reguläres Playwright verwendet. Nach Sicherung lokal ausgerollt;
echte Mac-Kalenderteilnehmer erneut in der Terminvorbereitung geprüft.

## Produktgrenzen bleiben sichtbar

Direkte Uploads sind ausdrücklich gespeicherte Text-Snapshots. Ein Dateiname
allein wird nicht als Ersetzungsauftrag gedeutet; ein früherer Snapshot kann
sichtbar ausgeschlossen werden. Ebenso entzieht das Trennen eines Postfachs
den weiteren Zugriff, löscht aber keine ausdrücklich gespeicherten Originale.
Unzuordenbare Altbelege werden nicht anhand gleicher Texte oder fremder Header
umgedeutet. Sie bleiben prüfbar und ausdrücklich ausschließbar.

Diese Abnahme ersetzt nicht Punkt 09 (fortlaufende Einrichtung einschließlich
echtem Mailanbieter), Punkt 07 (echte befüllte Nutzerakten), Punkt 16 (vollständiger
Referenzvergleich), Punkt 17 (Docker-Desktop-Neuinstallation) oder Punkt 20
(Alltagstest). Mobile bleibt gemäß Produktplan zurückgestellt. Die Kriterien
und Zählweise dieser Punkte werden nicht verändert.
