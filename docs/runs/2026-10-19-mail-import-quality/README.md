# Mailimport: Qualität und vorgeschaltete Relevanzprüfung

## Umfang

Drei Befunde einer begrenzten Claude-Probe werden korrigiert: ein Funktionspostfach als Person, eine bedingte Angebotsantwort als unbedingte Bitte und ein zu kleines Anfragebudget für einen längeren Verlauf. Die anschließende unabhängige Prüfung deckt zusätzlich technische Plattform-/Relay-Absender sowie die Fortsetzung einer ausdrücklich freiwilligen Verteileraufnahme ab.

Originalquellen, bestätigte Zuordnungen und lokale Modellrollen bleiben erhalten. Aus einer Bitte wird keine automatisch bestätigte eigene Aufgabe. Der pausierte Großimport wird nicht fortgesetzt.

## Ablauf vor einer teuren Einordnung

1. Spam- und Papierkorbquellen bleiben ausgeschlossen. Explizite Sperren und bekannte Spamkennzeichen gelten vor der Absenderfreigabe.
2. Gewünschte Absender oder Newsletter können ausdrücklich erlaubt werden.
3. Listenkennzeichen sowie eng zusammenpassende automatische Absender und Werbebetreffzeilen halten eindeutige Werbung ohne Modell zurück. Antworten, vorhandene Threadbezüge sowie Transaktions- und Arbeitsbetreffzeilen werden durch die neuen Werberegeln nicht ausgeschlossen.
4. Was Metadaten nicht beweisen, wird nicht als Spam erfunden. Bei eingeschaltetem lokalem KI-Filter bleiben dessen bestehende Prüfung und Zurückstellung erhalten. Die Cloud-Vorschau selbst startet keinen zusätzlichen lokalen oder entfernten Modellaufruf. Bereits gespeicherte, unklare Mails werden bei eingeschaltetem KI-Filter zur Prüfung gehalten; bei ausgeschaltetem KI-Filter gilt die bisherige konservative Aufnahme. Die Regeln garantieren deshalb keine vollständige Werbeerkennung.
5. Vor einer Cloudfreigabe stehen Quellenumfang und gespeichertes Anfragebudget fest. Filter, Quelle und Zugang werden beim Start, vor jedem Aufruf und vor dem Speichern erneut geprüft. Eine spätere Freigabeänderung verhindert die Übernahme bereits laufender Ergebnisse.

Zurückhalten löscht weder die Originalmail im Postfach noch vorhandene Quellen. Erwähnte Namen und Postfachkennungen beweisen keine natürliche Person oder Aufgabenverantwortung.

## Längere Quellen und Antwortprüfung

Das Budget berücksichtigt die tatsächliche Anzahl von Klassifikations- und Belegabschnitten. Kurze Quellen behalten die bisherige Mindestreserve. Teilmengenauswahl übernimmt nur ihren eigenen Plan. Alte gespeicherte Aufträge behalten ihre Obergrenze; alte Vorschauen müssen neu geprüft werden. Neustarts und Fortsetzungen erweitern das Budget nicht.

Die Klassifikation verlangt jede Block-ID als eigenen erforderlichen Schlüssel. Doppelte JSON-Schlüssel, fehlende Blöcke und ungültige Werte werden verworfen. Das direkte Anthropic-Tool nutzt das unterstützte strikte Schemaformat; wörtliche Belege, Textstellen und Mengen werden weiterhin lokal geprüft. Striktes JSON beweist keine inhaltliche Wahrheit.

Die Produktgrenzen für Pakete, Anfragen und Ausgabetokens sind keine garantierte Euro-Obergrenze. Die private Prüfung verwendet zusätzlich eine konservative Kostenreserve vor jedem Aufruf. Keine automatische Wiederholung und kein Ausweichanbieter.

## Prüfnachweis

Die echten Stichprobendaten, Providerantworten und Personenakten verbleiben außerhalb des Repositorys. Veröffentlicht werden nur aggregierte Ergebnisse. Der abschließende frische Lauf derselben zehn Quellen war technisch vollständig: 28 API-Aufrufe, keine verworfenen Quellen, 105.342 Eingabe- und 7.623 Ausgabetokens. Berechnet wurden 0,286914 USD bei Sonnet 5 mit 2 USD je Million Eingabe- und 10 USD je Million Ausgabetokens; kein Token-Cache. Einschließlich der vorangegangenen Diagnosen und Vergleichsläufe: 0,676230 USD. Das ist eine Berechnung aus den Provider-Verbrauchswerten, keine Rechnungsbestätigung und keine Hochrechnung für ein ganzes Postfach.

Eine frühere Wiederholung hatte einen unbelegten Namensvorschlag verworfen und den zuvor gültigen Stand bewahrt. Diese Schwankung wird nicht als durchgehend fehlerfreie Erkennung ausgegeben. Das unabhängige Inhaltsreview des Abschlusslaufs fand außerdem noch einen als Bitte eingestuften reinen Registrierungsweg. Die eng begrenzte Korrektur unterscheidet deshalb reine Verfahrensinformation von persönlicher Aufforderung und Pflicht. Sie wurde mit den aufgezeichneten Originalantworten ohne weitere API-Aufrufe geprüft; gemischte Absätze dürfen keine folgende Aufforderung verlieren.

Die Prüfung umfasst:

- 183 wörtliche Belegbereiche und die vier vorhandenen konkreten Profilreferenzen stimmen mit den Originalen überein.
- Die freiwillige Angebotsantwort und die optionale Verteileraufnahme bleiben bedingt. Funktions- und technische Relay-Adressen ergeben keine automatische natürliche Person.
- Die aktuelle Nachfrage und ihre unpräzise Monatsendfrist bleiben aktuell beziehungsweise unpräzise. Erwähnte Fußzeilenpersonen erhalten keine fremden Aufgaben. Historische Bitten werden keine neuen heutigen Pflichten.
- Einladungen bleiben ungebuchte Einladungen, ein Zahlungsplan wird keine zusätzliche manuelle Zahlungsaufgabe.
- Der getrennte Schattenlauf des Vorfilters hält die eindeutige Kontaktwerbung ohne Modell zurück. Sie bleibt im Vergleich als bewusst gewählte Negativkontrolle enthalten; normale Cloud-Vorschauen überspringen sie.
- Die zehn Quellsnapshots bleiben strukturell unverändert. Alle 2.463 Originalzeilen im laufenden Bestand bleiben unverändert. Die Prüfung schreibt keine kopierten Modellantworten in den Produktivbestand.

Der Nachweis gilt für die ausgewählte Stichprobe und rechtfertigt ein weiteres kleines, unabhängig geprüftes Paket. Er beweist weder allgemeine Fehlerfreiheit noch ein ausreichendes Kostenbudget für das ganze Postfach. Der Massengroßimport bleibt pausiert.

Preisquelle: https://platform.claude.com/docs/en/about-claude/pricing. Strukturierte Antwort: https://platform.claude.com/docs/en/build-with-claude/structured-outputs.

## Technische Regression und Mac-Abnahme

Die fachlich betroffenen Tests wurden nach jedem Review-Fix ausgeführt. Der vollständige Sidecar-Lauf prüft die integrierten Infrastrukturänderungen; die anschließend engere Registrierungssatz-Regel bekommt zusätzlich den vollständigen Arbeitsgedächtnis-Testsatz. UI-Build, UI-Tests und Asset-Vertrag sind getrennte Prüfungen und ersetzen keine Inhaltsprüfung.

Bestanden: vollständige Sidecar-Regression 7.074 Tests und 26 Untertests, eine erwartete Auslassung, zwei bestehende Warnungen (18:23 Minuten). Dieser Volltest lief auf dem integrierten Stand vor der zuletzt ergänzten Registrierungsregel. Nach dieser Ergänzung wurden zusätzlich 525 Arbeitsgedächtnis-/Cloud-/Filtertests ausgeführt; die anschließend noch engere endliche Grammatik wurde abschließend mit 130 Tests und zwölf unabhängigen synthetischen Gegenkontrollen geprüft. UI: 744 Tests, Produktionsbuild und Asset-Vertrag bestanden. Unabhängiges Code- und Inhaltsreview ohne verbleibende wichtige Findings im geprüften Umfang. Der Offline-Replay aller 28 aufgezeichneten Antworten änderte ausschließlich die bekannte Registrierungsinformation; zusätzliche API-Kosten null.

Mac-Nachweis folgt nach Veröffentlichung. Der normale Updateweg sichert vor dem Wechsel; Originalmails, Aufgaben und Projekte werden danach erneut über Zählwerte und Prüfsummen verglichen.
