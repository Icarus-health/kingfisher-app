# Kodierte Mailnamen lesbar anzeigen und wiederfinden

Code eingefroren bei `408df41695cb6a6c49fe5d3366d581c60f9bcfaf`, aus `4f50dbd627c16b3d6dea113dda27f101080b8077`. PR [35](https://github.com/Icarus-health/kingfisher-app/pull/35). Nur künstliche Daten in den öffentlichen Prüfnachweisen.

## Problem und Korrektur

`kontakte.text_form` verwendet `email.utils.formataddr`: Namen mit Umlauten werden dabei wieder nach RFC 2047 kodiert. Die nächste Kontaktlesung behandelte diesen technischen Text als Namen. Das traf neue Empfänger ebenso wie alte gespeicherte Mailköpfe. Anzeigen und Personenfragen hatten zusätzlich eigene Teilnehmerpfade; ein vollständig kodierter Name konnte bereits vor der Namensprüfung am Rohtext-Vorfilter scheitern.

Die gemeinsame Kopflesung dekodiert Namen jetzt strikt. Die Adresse wird vorher aus dem unveränderten Kopf gelesen und bleibt der Identitätsanker. Nur bekannte Mailköpfe werden dekodiert; Herkunft geht bei reduzierten Suchprojektionen nicht verloren. Kodierte Mailköpfe sind zusätzliche Kandidaten, danach gilt weiterhin der genaue Namensvergleich. Ein gleichnamiger Kontakt mit anderer Adresse bleibt getrennt. Nicht-Mailtexte und Textstellen bleiben wörtlich. Alte Quellen werden lesbar projiziert, nicht umgeschrieben.

Unbekannte Zeichensätze und defekte Bytes behalten die rohe kodierte Beschriftung. Dekodierte oder bereits unkodierte Unicode-Steuerzeichen (Cc/Cf/Cs) dürfen keine irreführende Personenbeschriftung erzeugen. Ein unsicherer bereits unkodierter Name entfällt; die Adresse bleibt erhalten. Der unabhängige Review hat beide Steuerzeichenvarianten nachgewiesen, bevor der Stand eingefroren wurde.

## Nachpflege ohne Quellenumschreiben

Der veränderte Namensregister-Token erneuert abhängige abgeleitete Bezüge beim normalen Abgleich. Die bestehende Prüfung der Akten erneuert Hinweistext unter seinem stabilen Sach-/Belegschlüssel. `sach_nutzer` sowie erledigte/abgewiesene Befunde bleiben erhalten. Eine tatsächlich andere Sache erhält weiterhin einen anderen Schlüssel; eine frühere Entscheidung wird nicht still übernommen.

29 neue Tests belegen Parser-/Empfängerpfad, Herkunftsgrenze, rohe Standardabfragen, Einzel- und Bulkbeschriftungen, Personenfrage, gleichnamige Adressen, generische Postfächer, Ausschluss, Register-/Hinweisnachpflege und unveränderte Originalmetadaten/Digest/Stützgeneration. Vor der jeweiligen Korrektur scheiterten fünf erste Kopf-/Anzeigefälle, zwei Suchfälle und die Steuerzeichenproben erwartungsgemäß. Nach der endgültigen Korrektur: 29/29; betroffene Gesamtauswahl: 132 bestanden. Ein vorbereitender Pflicht-/Identitäts-/Lintlauf bestand 222 Prüfungen. Zwei frühe Volltest-Anläufe wurden ausdrücklich für die Reviewkorrekturen abgebrochen und sind kein vollständiger Prüfnachweis.

**Abschließender eingefrorener Backend-Volltest:** 5.863 bestanden, 1 übersprungen, 26 Subtests bestanden, 2 Warnungen; 892,25 Sekunden. Exit 0. Der gesamte Pythonbestand entspricht weiterhin dem eingefrorenen Paketmanifest. Keine Produktcodeänderung während des Prüflaufs.

## Echtes Paket

Das lokale Paket `1.0.6-local.408df41` basiert auf der installierten `1.0.6-local.7295b2e`. Sieben geprüfte Pythonmodule und die Paketversion ändern sich; Oberfläche und native Hülle bleiben erhalten. Paket-ID `sha256:a0edfc060043ef0d83716e6a024bf4012540ce5a2bdde71fb4c9fa61463c59de`.

Exakte Dateimenge und Hashes: 266 Python- und 112 UI-Dateien bestanden. Die unveränderte integrierte Namensprobe scheitert im alten Paket erwartungsgemäß am Unicode-Empfänger. Im neuen Paket bestand der [integrierte Prüflauf](integration-header-smoke.py) zehn Kriterien an sechs künstlichen Datensätzen im echten Paket mit echten Abhängigkeiten, ohne Netzwerk oder persönlichen Datenbestand. SQLite-Neustart, alte kodierte Kontakte, Unicode-Empfänger, unveränderte Originale/Stützgeneration, gleichnamige Adressen und ignorierte/entzogene Quellen wurden geprüft. Die zusätzliche bisherige Statusbeleg-/Verlaufsprobe bestand weiterhin: keine unbelegte Übertragung des Rechnungsstatus auf die Lieferung, sichere Originalstellen, Quellenentzug nach Neustart.

**Mac:** nach kalter Sicherung auf demselben Datenvolume installiert. 344 Originale, 17 Datenbanken, Konten/Einstellungen und Hintergrundpause frisch geprüft und erhalten; Schema 20, keine Migration, native signierte Hülle unverändert. Der laufende Container besteht die genaue Paketprüfung auch nach der Bedienprüfung. Die App wurde regulär beendet, aktualisiert und geöffnet. Auf Heute waren vorher zwei kodierte Beschriftungen sichtbar; nach Installation war die Aktenbeschriftung korrigiert, der alte Hinweistext noch kodiert. Die normale Aktion „Jetzt prüfen“ erneuerte die Hinweise: anschließend null kodierte Beschriftungen in Menschenliste (112 Einträge) und geladenem Tagesüberblick. Keine Erledigt-/Ignorieren-/Zusammenführen-Aktion ausgeführt. Die Uhr läuft, Einlesen bleibt pausiert. Das ursprüngliche Installationsprotokoll behält seinen technischen Status vor der Fensterprüfung; ein getrenntes privates Fensterprotokoll dokumentiert die danach tatsächlich erfolgte Abnahme.

## Grenzen

Diese Lieferung korrigiert Kopfnamen und ihre Such-/Anzeigeprojektionen. Sie ist kein neuer Modellqualitätsnachweis und behebt nicht alle Auslassungen der Personenextraktion. Keine erneute Einordnung privater Mailbestände, keine Freigabe neuer Quellen, kein Modellwechsel, kein Cloudaufruf. Die zuvor gemessenen Grenzen (CoS-Personen 8/9; Regeln 14 ausreichend/2 teilweise) bleiben bestehen. Die native Menschenliste enthält weiterhin einige Organisationen und automatische Absender; diese Einordnungsgrenze ist bei der Fensterprüfung sichtbar geworden und bleibt ein eigener Folgeauftrag. Produktiver Großimport, Akku-/GPU-Budget, Mac-Kalenderhelfer und Alltagstauglichkeit bleiben separat abzunehmen. Die Ursache des Helfer-Ausfalls und der begrenzte Folgeauftrag stehen [hier](calendar-helper-followup.md). CI wurde nicht erneut gestartet; alle Commits und der vorgesehene Merge verwenden `[skip ci]`.
