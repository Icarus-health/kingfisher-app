# Aufnahme und Abruf: belastbarer Zwischenstand am 31.10.2026

Der laufende Backend-/Oberflächenstand bleibt 1.0.35; die native Mac-Hülle
ist noch 1.0.18 und reicht den neuen Profilschalter nicht weiter. Die folgenden
Reparaturen sind noch nicht veröffentlicht. Beide persönlichen Postfächer bleiben eingerichtet, der
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
| G, `34e0739` | Tatsächlich gewählter nativer Produktweg mit Einzelrequests/-responses | Transport vollständig nachgewiesen; zwei wichtige Antwortfehler verhindern die fachliche Freigabe. |

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

## G: Transport bestanden, Antwortabnahme noch blockiert

88/88 tatsächliche native Requests und Responses erfasst: exakt 8192 Kontext,
`truncate:false`, `shift:false`, begrenzte Ausgabe und unveränderte vollständige
Nachrichten. 2.332–15.855 gesendete Byte, höchstens 4.183 Prompttoken; alle
Antworten regulär beendet. Quellstände unverändert. Keine technische Störung,
alle 24 Originalmails erhalten, keine Aufgabe ohne Bestätigung angelegt.
25 passende Abschnitte sind indexiert: ein separater Signaturblock wurde dieses
Mal zusätzlich als Fakt eingeordnet. Das ist kleineres Suchrauschen, kein Beweis
perfekter Klassifikation und keine zusätzliche Originalquelle.

Die unabhängige Prüfung aller 24 Quellen-/Taskentscheidungen und 16 Antworten
fand zwei wichtige Antwortfehler:

- q08: Die Frage nach der eigenen Kalkulationszusage zeigt zusätzlich Noras
  anders gerichtete Unterlagenzusage. Wörtliche Zitate verhindern hier noch
  keinen falschen Antwortumfang.
- q09: Die richtigen negierten Statussätze werden von der Belegprüfung verworfen;
  als Rest bleibt lediglich die fortbestehende Frist. Die Frage nach Fertigstellung
  bleibt so unbeantwortet. Der alte Worttest zählt „noch nicht fertig“ aus dem
  Quelltitel im Belegfuß und meldet diesen Fall fälschlich grün.

154/157 mechanische Verträge bestanden; die zwei bekannten m14/q15-Abweichungen
bleiben, q08 ist zusätzlich rot. Der grüne q09-Wortcheck ersetzt ausdrücklich
keine vollständige Antwort. Neue Diagnosegegenprobe zuerst rot; der Pflichttext
wird nun ohne den erkennbaren gerenderten Belegfuß geprüft. 65 Scriptprüfungen
bestehen. Dieser begrenzte Formatfilter ist kein semantischer Prüfer.

599,344 Modellsekunden und 613 Ressourcenmessungen: mindestens 26 Prozent freie
Reserve, maximal Druckstufe 2. Dieser Lauf war langsamer als E/F; daraus folgt
kein kontrollierter Geschwindigkeitsvergleich. Das Mac-Fenster ließ sich während
der Auswertung bedienen, was keine allgemeine Fluenzgarantie für andere Arbeit
ist. Die beiden Antwortfehler werden gezielt korrigiert; Eingangsklassifikation
und Taskerkennung bleiben unverändert. Der nächste Abrufnachweis kann dieselben
unveränderten frischen G-Originale und gespeicherten Einordnungen verwenden,
ohne die Mails erneut per Modell zu klassifizieren.

## Gezielte Antwortreparaturen nach G

Nach jeder aufgezeichneten Satzverwerfung verwendet der bestehende Prüfpfad
jetzt erneut geprüfte Originalstellen statt eines möglicherweise irreführenden
Satzrests. Das gilt beim Erzeugen und beim Öffnen alter Antworten. Keine
Belegregel wurde gelockert. Der Schritt ist konservativ und kann auch gültige
Restprosa durch vollständige Zitate ersetzen. Für Antworten ohne Verwerfung
wird keine allgemeine Vollständigkeit behauptet.

Eine geschlossene einfache Frage nach der eigenen Zusage schließt nun eine
belegbar fremde direkte Ich-Zusage aus Auswahl und zusätzlichem Satz-Aktenkontext
aus. Strukturierte Rollen und vollständiger Originalwortlaut müssen passen;
Namen oder Betreff reichen nicht. Berichte, Zitate, Weiterleitungen, unbekannte
Rollen und zusammengesetzte Fragen bleiben beim bisherigen Verfahren. Ein
unabhängig gefundener Mehrteilfragenfehler wurde vor Freeze geschlossen; die
drei konkreten Gegenfälle behalten beide Quellen. Alte problematische
Satzbelege werden beim Öffnen erneut geprüft.

191 Workerprüfungen für Teilantworten und 171 für den engeren Zusagepfad bestehen
mit Überschneidungen, nicht addiert. Root prüfte 293 betroffene Fälle vor den
letzten sechs Fragegegenfällen, anschließend die endgültigen 43 Zusagefälle.
Unabhängige Nachprüfungen schließen beide belegten Fehler ohne verbleibenden
Befund im engen Scope. Echter erneuter Abruf und endgültige Vollsuite folgen.

Anweisungen im Quelltext bleiben für Modell und Satzprüfung geschwärzt. Der
Originalmodus zeigt dagegen das eingerahmte unveränderte Original, auch dessen
Anweisung; daraus entstehen weder Ausführung noch Einwilligung. Eine anders
lautende erste Workerberichtsaussage wurde nach Review korrigiert. Keine neue
Anzeige-Schwärzung oder veränderte Quelle eingeführt.

## Echte Quellen und Mac

Eine kleine lokale echte Stichprobe liegt ausschließlich in getrennten privaten
Dateien. Zwei unvollständige Originale werden vor dem Modell gehalten. Die
normale 32K-Probe brach am unveränderten Speicherwächter ab; daraus folgt keine
abgeschlossene Aufgaben-/Abrufabnahme. Persönliche Originale wurden nicht
geändert, private Inhalte gehen weder in dieses Repository noch an Reviewer.

Das bestehende Mac-Fenster ist wieder erreichbar; Heute → Gedächtnis → Heute
wurde geprüft. Das ist keine Installation der neuen Reparaturen und kein
Nachweis für flüssige Arbeit bei längerem Modellbetrieb.

## Echte Stichprobe B: noch keine Freigabe

Dieselben sechs bestehenden privaten Quellen wurden ausschließlich lokal als
Kopie geprüft. Vier vollständige Quellen durchliefen die Einordnung, zwei
unvollständige Quellen wurden vor dem Modell gehalten. Vierzehn Aufrufe, davon
zwei vor Versand technisch abgewiesen; keine Aufgabe im persönlichen Bestand
angelegt und kein Großimport fortgesetzt. Der Lauf blieb innerhalb des Wächters
(minimale Reserve 26 Prozent, maximal Druckstufe 2).

Zwei Rückfragen überschreiten das vollständige Eingabebudget. Eine weitere
Quelle enthält eine erkennbare aktuelle Bitte in einer Portalbenachrichtigung,
doch die Aufgabenerkennung liefert leer. Die echte Stichprobe ist damit **nicht**
bestanden. Die Quotierung allein ist kein bewiesener deterministischer
Aussortierungsgrund; die beiden Modellwege entscheiden unabhängig. Inhalte,
Adressen, Belege und Rohreports bleiben privat.

Die nächste gezielte Reparatur hält Originale und Budget unverändert:

- Ein exakt rückauflösbarer Kopierverweis vermeidet wiederholte Feldwerte im
  reinen Modelleingang. Alle Kandidaten, IDs, Quelltexte und Reihenfolgen bleiben
  erhalten; Herkunft und Identität werden dadurch nicht zusammengeführt. Die
  zusätzliche Erklärung wird nur bezahlt, wenn die gesamte verschachtelte
  Anfrage tatsächlich kleiner wird. 192 betroffene Prüfungen bestehen.
- Aufgabenextraktion erhält optional frisch gelesenen, begrenzten Absender-,
  Beteiligten- und Zeitkontext. Quellendatum, Eingang und Erfassung bleiben
  getrennt; weder äußeres Datum noch Zitatformat beweisen den Inhalt einer Bitte.
  Originalbelege und nachgelagerte Zuständigkeits-/Marketingprüfung bleiben
  unverändert. 103 betroffene Prüfungen bestehen, kein Versionsbump oder
  pauschaler Wiederanlauf alter Auswertungen.
- Ein unabhängiges Review führte zehn enge Offline-Gegenproben erfolgreich aus.
  Umkehrbarkeit ist kein Nachweis des Modellverständnisses. Eine private reine
  Payloadmessung bestätigt beide Rückauflösungen: Eine Anfrage passt danach,
  die andere ist weiterhin zu groß. Deshalb ist eine vollständig begrenzte
  Quellenauswahl in mehreren Paketen erforderlich; keine Quelle wird still
  entfernt und keine Grenze erhöht.

Die konkrete Aufgabenerkennung und beide Antworten werden mit unveränderten
Sollwerten erneut geprüft. Keine Reparaturbehauptung allein aus neuen Prompts.

## Noch erforderliche Abnahme

1. Die beiden belegten Antwortfehler q08/q09 korrigieren und sämtliche 16
   Rückfragen mit tatsächlichem Profil erneut gegen dieselben Originale prüfen.
2. Vollständige Backendprüfung des endgültig eingefrorenen Stands.
3. Dieselbe echte Stichprobe über den begrenzten Produktweg; unvollständige
   Quellen bleiben gehalten, fehlende Abdeckung bleibt sichtbar.
4. Geprüfte Veröffentlichung, Sicherung, normaler Mac-Updateweg und Bedienung.
5. Eine Alltagswoche durch den Nutzer. Erst die bestätigte Stichprobe kann eine
   gesonderte Entscheidung über die Fortsetzung des Großimports tragen.


## Begrenzte Reparaturen vor der endgültigen Wiederholungsprobe

Die reine Duplikatpackung reicht nicht für jede Auswahl. Das ausdrücklich
gewählte kleine lokale Profil plant jetzt höchstens vier vollständige Seiten
und nötigenfalls einen gemeinsamen Vergleich ihrer ausgewählten Originalzeilen.
Kein Kandidat oder Quellfeld wird abgeschnitten. Ein gemeinsames Zeitbudget,
Quellenstandsprüfung vor jeder Runde und das Verwerfen aller Teilresultate bei
Fehlern bleiben bindend. Ein allein zu großer Kandidat oder ein zu großer
Gesamtvergleich meldet weiterhin eine verständliche Grenze.

Bei E-Mails darf ein nichtliterales Modellzitat nur über einen eindeutigen,
positionsgebundenen Darstellungsabgleich auf die exakte Originalstelle zeigen.
Vollständige HTML-Entities und Leerraum dürfen gleich dargestellt werden;
Zitatpräfixe nur bei vollständig markierten mehrzeiligen Absätzen. Einzelne
oder gemischte Größerzeichen und innere Vergleichsoperatoren bleiben erhalten.
Das unabhängige Review fand zunächst eine Verwechslung von Operator und
Zitatpräfix; der konkrete Gegenfall und positive mittig beginnende Zitate sind
nach der strukturellen Korrektur unabhängig nachgeprüft. Die nachfolgende
Zuständigkeits-/Fristprüfung erhält den unveränderten Originalspan.

Ausdrückliche lokale Lernbitten erhalten klarere Auslöserhinweise und höchstens
eine zusätzliche strukturgebundene Korrekturrunde. Beide Versuche teilen ihre
Frist und dieselbe Quellen-/Providerfreigabe. Anbieterfehler werden nicht
wiederholt, ungültige Modellprosa wird nicht zur neuen Instruktion. Auch ein
valider Entwurf bleibt bis zur Bestätigung inaktiv.

Root prüfte diese fünf betroffenen Testdateien gemeinsam: 140 bestanden.
Das unabhängige enge Nachreview ergänzte 30 fokussierte Tests und drei eigene
Gegenproben; kein verbleibender Blocker im abgegrenzten Scope. Diese Zahlen
überschneiden sich und werden nicht addiert. Die neue volle Suite sowie echte
Modell- und Inhaltsprüfungen sind dadurch nicht ersetzt.

Die zweite echte künstliche Lernprobe erzeugte bereits einen strukturell
validen inaktiven Entwurf, stoppte jedoch an der zu prüfenden Diagnoseforderung
für den exakten Kontextnamen. Auswahl, Fassungswechsel und Entzug sind in
diesem Lauf noch nicht durchlaufen. Keine persönliche Skill-Aktivierung.


## C: erneute echte lokale Stichprobe und gezielte Nachprüfung

Dieselben sechs Originalkopien und vorab festgelegten Erwartungen blieben
unverändert. 19 tatsächliche native Aufrufe, alle mit 8192 Kontext und beiden
Abschneideschaltern aus. Der Lauf endet regulär; 213 Ressourcenmessungen,
minimale Reserve 28 Prozent, maximale Druckstufe 2. Vier vollständige Quellen
wurden eingeordnet; zwei unvollständige Quellen blieben vor dem Modell.

Die zuvor übersehene aktuelle Bitte wird mit exaktem Rohzitat als Vorschlag
erhalten. Eine Frist wird nicht erfunden. Alle drei Abrufe enden ohne die alten
Auswahl-Größenfehler. Die Antworten verwenden teils lange Originalberichte und
sind dadurch noch keine besonders knappe Gesprächsdarstellung.

Die erste Personen-Vorbelegung dieser Bitte war trotzdem unzulässig: Ein
mehrdeutiger Portalname wurde als eine Person vorgeschlagen. Der gemeinsame
lesende Qualitätsfilter wird jetzt auch vor der Aufgabenvorbelegung benutzt.
Normale Namen und ausdrücklich bestätigte Entscheidungen bleiben erhalten.
Root hat denselben privaten Quellenbestand ohne neue Modellaufrufe erneut
vorgelegt: Die Bitte bleibt erhalten, die Person bleibt offen. Kein Original,
Kontaktfeld oder gespeicherter Personenname wird dazu umgeschrieben.

Der Taskscan zählt außerdem die zwei unvollständigen Quellen und eine nicht
prüfbare Angebotserkennung als offen/fehlgeschlagen, statt einen falschen leeren
Erfolg zu speichern. Für diese Quelle liegt keine abgeschlossene negative
Aufgabenprüfung vor. C ist deshalb kein pauschales Qualitätsgrün für den
Großimport. Alle privaten Texte und Einzelreports bleiben außerhalb des Repos.

Auf der laufenden Fassung ist die Aufgabenprüfversion noch requests-v3. Der
Reparaturzweig verwendet bereits v4; damit werden alte leere Prüfstände im
vorhandenen begrenzten Lauf erneut betrachtet. Eine weitere globale
Versionsanhebung ist nicht erforderlich. Die globale Importpause bleibt erhalten.

## Erfolgreicher echter Skill-Ablauf v4

Dieselbe künstliche Lernbitte wie in den drei erhaltenen Fehlversuchen erzeugt
nun einen passenden inaktiven Kommunikations-Skill mit exakt den zwei verlangten
Schritten. Vier echte native Qwen-Aufrufe durch den Produktanbieter: Entwurf und
drei Agent-Aufrufe mit leerem Werkzeugumfang. Eine ausdrückliche Bestätigung und
eine manuell angelegte Revision sind ausschließlich gekennzeichnete Testaktionen,
keine automatische Aktivierung und keine persönliche Bibliotheksänderung.

Drei vorab festgelegte normale Formulierungen (Singular, Plural, getrennte Wörter)
finden den bestätigten Skill; fünf private, zitierte, negierte oder fachfremde
Kontrollen aktivieren ihn nicht. Die tatsächlichen Modellprompts enthalten
zunächst Version 1, danach nur Version 2. Nach Quellenentzug fehlt der Skill;
der Gesprächskontext wird zurückgesetzt. Ohne Anlass und Empfänger fragt Qwen
nach, statt diese zu erfinden. 32,63 Sekunden, mindestens 35 Prozent Reserve,
maximal Druckstufe 1, kein Ressourcenabbruch.

Ein einzelner positiver Entwurf beweist keine allgemeine Lernqualität. Andere
Lernbitten können weiter zur manuellen Eingrenzung zurückgegeben werden. Die
Bibliothek bleibt eine ergänzende Sammlung bestätigter Verfahren, kein Ersatz
für Fakten oder neue Berechtigungen.


## I: vollständige Wiederholung, neue wichtige Aufgabenlücke

Der unveränderte Katalog läuft vollständig auf dem sauberen Stand bbb6497.
Alle 87 tatsächlichen nativen Modellaufrufe sind belegt: 8192 Kontext,
2943–15749 Byte, keine Abschneidung und reguläres Ende. 572,59 Modellsekunden,
585 Ressourcenmessungen, minimale freie Reserve 25 Prozent und maximale
Druckstufe 2; kein technischer Abbruch. Quellcode und Originale bleiben
unverändert. Die knappe Speicherreserve beweist keine allgemeine Mac-Flüssigkeit.

Die unabhängige Prüfung aller 24 Aufnahme-/Aufgabenentscheidungen, 16 Antworten
und 87 Rohantworten findet alle finalen Antworten sachlich und quellengebunden
korrekt. Die reparierten Fragen nach eigener Zusage und negiertem Arbeitsstand
bleiben richtig. **Trotzdem keine Gesamtfreigabe:** Eine eigene Versandzusage
fehlt neu in den Aufgabenvorschlägen. Klassifikation und unabhängige
Aufgabenextraktion erkennen sie korrekt; erst die zusätzliche Modellprüfung
verwirft sie fälschlich als reine Information. Eine richtige Gedächtnisantwort
heilt diesen Aufgabenverlust nicht.

151 von 154 dynamisch vorhandenen Vertragsprüfungen bestehen. Neben diesem
neuen m11-Fehler bleiben der alte m14-Sollkonflikt und die q15-Statusabweichung
sichtbar. Die Anzahl ist keine Genauigkeitsquote; bei fehlenden Kandidaten
entfallen mehrere Detailverträge. Der neue Verlust wird gezielt als manueller
Prüffall geschlossen, ohne eine automatische Übernahme oder neue Frist zu
behaupten. Großimport und Auslieferung bleiben bis zur Nachprüfung zurückgehalten.


## Eng begrenzte Prüfaufbewahrung für den I-Aufgabenverlust

Eine vollständig wörtliche direkte eigene Versandzusage darf bei Widerspruch
der zusätzlichen Modellprüfung als **manueller** Originalvorschlag erhalten
bleiben. Dafür müssen der vollständige ungerahmte Text und eindeutige
strukturierte eigene Absenderrollen zusammenpassen. Metadaten allein, fremde
Sprecher, unbekannte Rollen, Berichte, Zitate, Weiterleitungen, Bedingungen,
Verneinungen und ein aufhebender Betreff reichen ausdrücklich nicht. Der
Kurzname wird nicht als gültig erklärt; Titel und Beleg sind der Originalsatz.

Ein listenkompatibler expliziter Prüfstatus wird an den bestehenden Worker
weitergegeben. Dieser vergibt dann keine positive Reviewmarke. Die vorhandene
Autoanlage bleibt mit „ungeprüft“ gesperrt; Annahme und frische Quellenprüfung
bleiben Nutzerarbeit. Bestehende positive Modellurteile werden nicht verändert.
Es handelt sich um eine enge Auffangregel für Versandzusagen, keinen allgemeinen
Grammatik- oder Wahrheitsprüfer.

Die unabhängige Nachprüfung fand zunächst fehlende Negationswörter und einen
Absage-Betreff als Gegenfälle. Die Korrektur bleibt auf Ausschlüsse im neuen
manuellen Pfad beschränkt. 161 gezielte Workerprüfungen bestehen; endgültige
unabhängige Nachkontrolle und erneuter realer Aufgaben-/Abruflauf folgen.
Dafür dürfen dieselben unveränderten I-Originale und Einordnungen verwendet
werden. Nur die abgeleiteten Prüfjobs/Vorschläge werden in einer neuen
künstlichen Kopie frisch angelegt. Dies ist keine erneute Klassifikation der
Mails und keine Veränderung der ursprünglichen I-Datenbanken.
