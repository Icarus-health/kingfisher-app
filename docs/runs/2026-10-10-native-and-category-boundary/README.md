# Native Teilprüfung und Grenze der Themenprüfung

10. Oktober 2026. Geprüfter Checkout: `99073b2cbb7b41b65855bd75224a8bc07fbe3801`.
Die folgende Prüfung ändert keinen Produktcode und keinen persönlichen Bestand.

## Tatsächlich bediente installierte App

App und Backend: `1.0.6-local.3403623`, native App-Kennung
`local.kingfisher.window`, lokaler Dienst auf Port 8890. Das neuere gemeinsame
Preview ist weiterhin nicht installiert. Die Bedienbelege gelten für die ältere
installierte App, nicht automatisch für das Preview.

Native Navigation, laufende Uhr beim Seitenwechsel, Quellen auf-/zuklappen und
Rückkehr aus einem Nachrichtendetail nach Heute geprüft. Einstellungen → KI &
Modelle → Cloud-Zugänge ist auffindbar; weder Zugang aktiviert noch Inferenz
gestartet. Aufgabenliste war leer, deshalb keine tatsächliche
Mail→bestätigte-Aufgabe-Kette belegt. Die sichtbaren Google-Termine ersetzen
keinen vollständigen Kalenderabgleich. Unter Arbeit/Projekte stehen weiterhin
Newsletter und Dienstmeldungen: persönliche Einordnungsqualität nicht abgenommen.

Der lokale Kalenderstatus war `not_determined`, drei Auswahlkennungen waren
gespeichert, null lokale Termine geliefert. Der Statusdienst antwortete; das ist
keine bestätigte leere Agenda. App-spezifische TCC-Diagnose meldete eine nicht
mehr passende bestehende Code-Anforderung für `local.kingfisher.window` und
`kTCCServiceCalendar`. Ein korrekt signiertes aktuelles Bundle beweist nicht,
dass die alte TCC-Freigabe zu seiner Signatur passt. Zwei explizite Klicks auf
Freigabe öffnen ergaben keinen zugänglichen Systemdialog.

Die automatische Freigabeprüfung lehnte unbeschränktes Lesen des Maildetails
wegen möglicher privater Inhalte ab. Anschließend nur Bedienelemente gelesen
und Detail geschlossen; keine Umgehung. Der Nutzer hat danach die Erneuerung
der app-spezifischen Kalenderfreigabe und das Lesen einzelner Ausschnitte erlaubt,
ist aber wieder vom Mac weg. Beides ist noch nicht ausgeführt. Keine
Berechtigungsrücksetzung, keine Termine geändert, keine Nachricht gesendet.
Der beobachtete Import blieb pausiert bei 1.587 von 122.399 Mails.

## Frische netzlose Codeprüfung

78 Tests bestanden, eine vorhandene Starlette/httpx-Abkündigungswarnung:

```sh
/private/tmp/kingfisher-review-20261006-venv/bin/python -m pytest \
  sidecar/tests/test_memory_categories.py \
  sidecar/tests/test_memory_areas.py \
  sidecar/tests/test_local_category_quotes.py \
  sidecar/tests/test_category_diagnostics.py -q
```

Die Checkout-venv enthält kein pytest; der erste Start darüber führte deshalb
keine Tests aus. Der genannte vorhandene Testinterpreter lädt nachweislich den
aktuellen Checkout. Kein Paket installiert, kein Backend-Gesamtlauf wiederholt.

`probe.py` benutzt temporäre SQLite-Stores und feste synthetische Antworten,
keinen tatsächlichen Anbieter. Beide belegten Modi (`absolute`, `block_quote`)
akzeptieren einen absichtlich sachlich falschen Arbeit-Hinweis auf einen gültigen
Werbe-Originalblock. Nicht vorhandene Block-IDs werden abgewiesen. Eine eigene
Korrektur zu Information bleibt bei Wiederprüfung erhalten. Entzug verbirgt die
Hinweise; Originaltext bleibt erhalten. **Originalbindung ist keine Garantie für
richtige semantische Kategorien.** Dies ist eine reproduzierte Grenze, keine
reproduzierte Qualität eines bestimmten Modells und keine erfolgte Korrektur.

```sh
/private/tmp/kingfisher-review-20261006-venv/bin/python \
  docs/runs/2026-10-10-native-and-category-boundary/probe.py
```

`quality-cases.json` bereitet acht vollständig künstliche Inhaltsfälle für die
spätere tatsächliche Modellprüfung vor. Erwartungen sind manuelle Sollwerte,
keine bereits erzielten Modellresultate. Positive Gegenfälle erhalten konkrete
Aufträge, automatische Rechnungen und Buchungen sowie gemischte Newsletter mit
persönlichem Auftrag. Ein pauschaler Absender-/Newsletterfilter wäre deshalb
keine ausreichende Korrektur. Bedingungen und spätere Absagen gehören zusätzlich
in die Antwort-/Aufgabenprüfung; eine Themenkategorie allein beantwortet das nicht.

## Update und nächster Abnahmeschritt

Die dauerhafte Datei `Kingfisher.dmg` des Pakets `1.0.6-preview.e326f81` stimmt
frisch per SHA-256 mit dem vorher signaturgeprüften Lieferartefakt überein.
Das ist eine Integritätsprüfung, kein neuer Signatur-, Installations- oder
Fenstertest. Maßgeblich bleibt das DMG, nicht die lose App-Kopie.

Wenn der Nutzer wieder am Mac ist: ausschließlich Kingfishers Kalenderfreigabe
erneuern, tatsächlichen Systemdialog bestätigen, die drei ausdrücklich gewählten
Kalender samt Anzeige abgleichen. Dann persönliche Sicherung vollständig prüfen,
bevor ein Schema-v21-Preview installiert wird; die ältere App kann v21 nicht
direkt öffnen. Anschließend eine begrenzte tatsächliche Einordnungs-/Abrufprobe
gegen Originale prüfen. Ein größerer Import bleibt bis dahin pausiert. Das neue
Okay ist kein zusätzlicher Kostenrahmen für einen großen Cloud-Lauf.
