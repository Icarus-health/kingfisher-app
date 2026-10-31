# Aufnahme und Abruf: belastbarer Zwischenstand am 31.10.2026

Die Mac-App bleibt auf 1.0.35. Die folgenden Reparaturen sind noch nicht
veröffentlicht. Beide persönlichen Postfächer bleiben eingerichtet, der
Großimport bleibt global pausiert. Keine Cloudaufrufe, neuen Modellgewichte oder
Änderungen an persönlichen Originalquellen.

## Was repariert ist

- Belegte Aufgaben bleiben als prüfbare Vorschläge erhalten, auch wenn das
  Modell eine unbelegte Rechnungsnummer zum Titel ergänzt. Bei zwei offenen
  Uhrzeiten bleibt die Uhrzeit offen. Keine automatische Übernahme.
- Mailkopf und Name allein beweisen keine Zuständigkeit. Sprecherabhängige
  Aussagen werden nötigenfalls als gerahmter Originalbericht angezeigt; das
  gilt bis zur Übernahme und beim Rücklesen alter Antworten.
- Eine Frist darf beim Umformulieren nicht ohne Beleg zum Beginn werden.
  Das ist eine begrenzte Relationsprüfung, keine allgemeine Wahrheitsprüfung.
- Technische Serviceadressen und unbekannte Absender werden nicht als
  ungeprüfte Menschen dargestellt. Bestätigte Identitäten haben Vorrang.
- Die Klassifikation erhält den rollenbelegten Mailabsender. Drittpersonen-
  berichte und substanzielle Newsletterinformationen sind keine eigenen Zusagen
  oder persönlichen Aufgaben. Eine Behauptung im Quelltext gewährt kein Opt-in.
- Leere enge Themenfragen bleiben beim beleggebundenen Abruf. Eine Wissenslücke
  wird nicht durch freien Chat gefüllt.

## Modellnachweise und ihre Grenzen

Der unveränderte Katalog enthält 24 künstliche Mails und 16 Fragen. SHA-256:
`ba46791a16c41f45dad04540918cd7f384ae73d85108fe10849050ebe250eeda`.
Alle Läufe sind erhalten; Sollwerte wurden nicht an Modellergebnisse angepasst.

| Lauf | Tatsächlicher Weg | Aussage |
| --- | --- | --- |
| E, `2a0b228` | Begrenzter nativer Diagnoseadapter | Vollständig, 88 Aufrufe, 24/24 BGE-Belege indexiert; alle 24 Aufgabenentscheidungen und 16 Antworten einzeln gegen Originale geprüft. |
| F, `7d16d27` | Normaler v1-Produkttransport mit demselben Qwen als 8K-Alias | Vollständig und inhaltlich zu E gleich; **kein Nachweis des neuen nativen Produktprofils**. |

F wurde zunächst als nativer Produktlauf bezeichnet. Das unabhängige Review
fand, dass die abgeschottete Messinstanz den Konfigurationsschalter entfernt
hatte. Deshalb fehlen auch die erwarteten nativen Einzelpayloads. Diese falsche
Transportzuordnung ist hier ausdrücklich korrigiert. Die erneute Probe muss den
Schalter innerhalb der Messinstanz prüfen und tatsächliche Requests aufzeichnen.

Beide Läufe erfüllen 155 von 157 mechanischen Verträgen. Die zwei Abweichungen
bleiben sichtbar: m14 erwartet einen Kandidaten für einen alten Antrag, während
keiner vorliegt; die spätere Erledigung m15 stand dem Einzelklassifikator nicht
zur Verfügung und ist daher keine belegte Erklärung. q15 liefert korrekt
`unknown`, der Katalog erwartet ausschließlich `working_unknown`. Keine
Vertragsänderung zum Erzeugen einer grünen Gesamtzahl.

Die unabhängige Inhaltsprüfung fand keine kritische falsche Endantwort in E/F.
Das Rohmodell verwechselt weiterhin vereinzelt Handelnde oder Datumsrelationen;
Schutzprüfungen verwerfen diese Umformulierungen zugunsten der Originalberichte.
Newsletterauswahl vor dem Eingang ist in diesem Katalog nicht enthalten und
wird durch diese Ergebnisse nicht abgenommen. Keine universelle Trefferquote.

## Begrenztes lokales Profil

Ein zusätzlicher 8K-Alias verwendet exakt die vorhandenen Qwen9B-Gewichte.
Der bisherige 32K-Alias bleibt unverändert. Nur ein ausdrücklich ausgewählter,
positiv geprüfter Alias nutzt den nativen Ollama-Weg mit `truncate:false` und
`shift:false`. Vollständiger Eingang einschließlich Schema und Werkzeugverlauf
bleibt begrenzt; unpassende Eingänge werden nicht abgeschnitten.

Der installierte Server hat einen absichtlich zu großen synthetischen Eingang
mit HTTP 400 abgewiesen. Eine gezielte Lifecycle-Korrektur verhindert zudem
Modellvorbereitung nach abgelaufener Auftragsfrist. 125 betroffene Prüfungen
bestanden auf `7d16d27`; der vorherige volle Lauf mit 8.551 Erfolgen gehört zum
Stand **vor** dieser Profilergänzung. Nach weiterer verlustfreier Packung ist ein
neuer eingefrorener Gesamt- und Produktlauf erforderlich.

## Verlustfreie Packung vor der erneuten Produktprobe

Die F-Eingänge wurden einschließlich vollständigem Schema und sämtlichen
Kandidaten erneut durch den echten Payloadaufbau gerechnet. q02/q03 lagen über
der unveränderten Grenze. Kompakte JSONsyntax und ein kürzerer Verweis bei
vollständig identischem `text`/`context` erhalten alle Quellfelder und IDs; der
Marker für echte lange Ausschnitte bleibt erhalten und beide werden erklärt.
Keine Quelle, Negation, Kandidat oder Schemaeintrag wurde entfernt.

Alle 88 rekonstruierten F-Requests passen danach unter 16.000 Byte, maximal
15.912 Byte nativ. Da F das Ausgabetokenbudget nicht protokollierte, wurde es
explizit aus den fünf unveränderten Aufrufstellen rekonstruiert. Das ist ein
Offline-Packungsnachweis, kein nachträglicher Wire-Nachweis für F.
Fünf neue Regressionsfälle scheiterten vorher; die betroffenen Packungs-/Profil-
prüfungen bestehen. Die Root-Gegenprüfung umfasste 200 betroffene Tests mit
lokalem Loopbacktest und Diagnosegruppen. Die Gesamtprüfung folgt eingefroren.

Der neue Profilschalter bleibt auch im verschlüsselten Sicherungsdownload
erhalten. Der tatsächliche Download→Entschlüsselung→Restore-Test verlor ihn
zunächst; nach der gezielten Ergänzung der Konfigurationsliste bestehen alle
fünf Sicherungsdownload-Prüfungen. Persönliche Sicherungen wurden dabei nicht
wiederhergestellt.

## Echte Quellen und Mac

Eine kleine lokale echte Stichprobe liegt ausschließlich in getrennten privaten
Dateien. Zwei unvollständige Originale werden vor dem Modell gehalten. Die
normale 32K-Probe brach am unveränderten Speicherwächter ab; daraus folgt keine
abgeschlossene Aufgaben-/Abrufabnahme. Persönliche Originale wurden nicht
geändert, private Inhalte gehen weder in dieses Repository noch an Reviewer.

Das bestehende Mac-Fenster ist wieder erreichbar; Heute → Gedächtnis → Heute
wurde geprüft. Das ist keine Installation der neuen Reparaturen und kein
Nachweis für flüssige Arbeit bei längerem Modellbetrieb.

## Noch erforderliche Abnahme

1. Verlustfreie Gesamtpackung unter denselben Eingabegrenzen; tatsächlicher
   nativer Produktlauf mit Requestnachweis und erneuter Einzelprüfung.
2. Vollständige Backendprüfung des endgültig eingefrorenen Stands.
3. Dieselbe echte Stichprobe über den begrenzten Produktweg; unvollständige
   Quellen bleiben gehalten, fehlende Abdeckung bleibt sichtbar.
4. Geprüfte Veröffentlichung, Sicherung, normaler Mac-Updateweg und Bedienung.
5. Eine Alltagswoche durch den Nutzer. Erst die bestätigte Stichprobe kann eine
   gesonderte Entscheidung über die Fortsetzung des Großimports tragen.
