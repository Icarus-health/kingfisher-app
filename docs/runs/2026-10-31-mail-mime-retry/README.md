# Vorhandene Mailquellen erneut lesen – 31.10.2026

Der vorhandene Konto-Knopf zum erneuten Versuchen kann jetzt alte, bereits
aufgenommene MIME-Präfixe über den begrenzten Anlagenleser nachholen. Zuvor
öffnete er nur gescheiterte/ausgefilterte Einträge und Analysefehler erneut;
`captured`/`duplicate` blieben auch nach Neustart endgültig gespeichert.

## Begrenzung und Erhalt

- Nur auf ausdrücklichen Konto-Retry: aktuelle, nicht ausgeschlossene
  Mailquellen mit unvollständigem MIME-Abruf oder einem alten Bericht über
  nicht unterstützte Dateien. Eine reine Mailtextgrenze reicht nicht, wenn
  der Bericht bereits vollständige MIME bestätigt.
- **Altberichte nennen die nicht unterstützten Formate nicht.** Deshalb kann
  der einmalige Wiederabruf sowohl ein früher ausgelassenes Word-Dokument
  erfassen als auch ein weiterhin nicht unterstütztes Logo erneut laden.
  Diese Mehrdeutigkeit lässt sich mit dem alten Bericht nicht vermeiden.
  Harte MIME-Lücken haben vor solchen unklaren Formaten Vorrang.
- Migration 26 ergänzt nur `mime_refresh_version` am vorhandenen Aufnahme-
  eintrag. Ein Versuch je aktuellem Abrufvertrag/Quellschlüssel; alle
  Gmail-Labelverweise verbrauchen denselben Marker, nur einer wird eingereiht.
  Die Migration selbst liest keine Mail und ändert kein Original.
- Vorhandene Batchgrenze, Kontopause, Freigabeprüfungen und Zeitplan gelten.
  Im leichten Takt (`nur_neu`, auch während globaler Pause) werden diese alten
  Quellen nie geholt, selbst wenn sie früher in der Spur für neue Post lagen.
  Retry reiht nur ein; er setzt keine Pause, Modellfreigabe oder Zeitplanoption um.
- Vor und nach dem Abruf werden aktuelle Fassung, Zustand, Fingerabdruck,
  Ordnergeneration und die konto-/ordner-/anbietergebundene Quellenkennung
  geprüft. Änderungen während des Abrufs führen zum Erhalt der gespeicherten
  Quelle. Beschädigte gespeicherte Snapshots werden konservativ übersprungen.
- Ein weiterhin unvollständiger oder strukturell unsicherer Abruf bleibt
  terminal für diesen Vertrag; Original und vorhandene Anlagen bleiben.
  Normale Verbindungs-/Anmeldefehler behalten die bisherige Fehlerbehandlung.
- Vollständig nachgeladene Inhalte laufen durch bestehende Quellenversionierung
  und Anlagenerfassung. Der frühere Originaltext bleibt gespeichert; eine
  unveränderte Logo-Mail behält auch ihren Quellenfingerabdruck. Keine neue
  Filtermodellrunde für eine schon aufgenommene Quelle.
- Der bestehende Retry-Knopf wird auch bei solchen reparierbaren Quellen
  angeboten. Es gibt keinen neuen Endpunkt, Hintergrunddienst oder Bedienelement.

Ein konservativ abgewiesener Kennungsalias nach UIDVALIDITY-Wechsel wird nicht
als erfolgreich repariert dargestellt: `mime_incomplete` zählt verbleibende
aktuelle echte MIME-Lücken unabhängig vom verbrauchten Versuch. Dann bleiben
Abschlussanzeige und Kontohinweis unvollständig, ohne einen weiteren Retry oder
Abrufschleife anzubieten. Vollständig geladene Logo-Berichte und durch einen
vollständigen MIME-Bericht erklärte Textgrenzen lösen diesen Hinweis nicht aus.
Der exakte Quellenkey-Guard bleibt unverändert; keine Aliasfreigabe wird erraten.

## Synthetischer Nachweis

Der zentrale Test erfasst eine gültige 2,6-MB-Multipart-Mail zunächst mit der
alten 2-MiB-Gesamtgrenze, schließt den Store und öffnet ihn erneut. Vor der
Änderung löste Retry keinen neuen Wire-Abruf aus (rot: ein statt drei Abrufe).
Danach erreichen die vollständigen Bytes den bestehenden PDF-Extraktionspfad;
eine vollständige neue Quellenversion samt Anlage entsteht, das alte Original
bleibt unverändert gespeichert. PDF-Textextraktion ist hier als Grenze ersetzt,
keine OCR oder Modelle. Ein kleines gültiges Word-Dokument mit altem
Unsupported-Bericht wird ebenfalls nachträglich eine Anlage.

Weitere Gegenproben: globale/Kontopause, deaktivierter Zeitplan, Freigabeentzug,
leichter Takt, Quelle während Abruf ausgeschlossen/ersetzt/geändert,
abweichende Anbieterkennung, veränderte Ordnergeneration, inkonsistenter
Snapshot, Gmail-Label-Duplikate, normales Batchbudget, Priorität für MIME-Lücken,
weiterhin unvollständiger Abruf sowie unverändertes Logo nach erneutem Retry
und Neustart. Historische Schemafixtures wurden um den Abbau der neuen Spalte
ergänzt; bestehende strenge Altverifier bleiben bestehen.

Gezielte Backendprüfung (Aufnahme, Retry, Routen, Pause, Migration, Backup und
Restore-Version): **171 bestanden**. Zusätzliche direkt betroffene historische
Migration-/Recoveryprüfung: **258 bestanden**. Ein bestehender Starlette/httpx-
Abkündigungshinweis bleibt. Bestehende UI-Logikprüfung einschließlich neuer
Retry-Verfügbarkeit: zunächst **26 bestanden**. Nach der unabhängigen
Kennungsalias-Gegenprobe waren zwei Backendfälle und ein UI-Fall gezielt rot.
Die enge Statuskorrektur ist mit **52 Backendtests und 27 UI-Logiktests** grün
geprüft, einschließlich Restart/erneutem Retry ohne weiteren I/O, Logo- und
Textgrenzen-Kontrollen.

`git diff --check` sauber. Der erste lokale Typecheck-Versuch fand kein `tsc`;
kein Paket installiert. Typecheck und UI-Build werden nach Freeze gesondert
durch Root geprüft. Keine vollständige Suite, Browserabnahme,
persönliche Laufzeit-, Anbieter- oder Modellprüfung durch diesen Arbeitslauf.
Alle Daten erfunden; keine privaten Nachrichten oder Zugangsdaten gelesen.
