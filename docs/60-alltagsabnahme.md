# Alltagsabnahme: Nimmt Kingfisher Arbeit ab?

Stand: 7. Oktober 2026. Ergänzt den [Kernablauf](59-kernablauf-gedaechtnis-cos.md). Der Maßstab ist weniger Suchen, Erinnern, Klicken und Koordinieren bei nachvollziehbaren Angaben. Diese Liste ist eine Abnahmevorgabe, kein bereits bestandener Praxistest.

## Was ohne Bedienung am Mac geprüft werden kann

Lokale Prüfungen verwenden künstliche Quellen und kontrollierte Modellausgaben. Sie belegen die Verarbeitung, Quellenrechte, Speicherung und Schutzregeln. Sie belegen nicht, dass ein echtes Modell jede Mail richtig versteht oder jede relevante Quelle findet. Es werden keine echten Schlüssel, kostenpflichtigen Anbieter oder persönlichen Postfächer für diese Prüfung verwendet.

| Situation | Erwartetes Verhalten | Vorbereitung ohne Mac |
|---|---|---|
| Eine zehn Jahre alte Bitte wird heute importiert | Originaldatum bleibt alt; keine neue Verpflichtung in „Heute“ | Zeitklassifikation und Aufgabenprüfung lokal prüfen |
| Ein Dokument hat kein Quelldatum | Datum bleibt unbekannt; Importdatum begründet weder „letzte Woche“ noch „außerhalb des Zeitraums“ | Zeitraum-Auswahl und gerenderte Antwort prüfen |
| Eine spätere Mail sagt eine Bitte ab | Frühere Bitte bleibt nachvollziehbar, erscheint aber nicht ungeprüft als aktuelle Aufgabe | Kontogebundene Antwortverweise und Prüfwarteschlange prüfen |
| Zwei Menschen heißen gleich | Angaben bleiben getrennt; bei fehlender Zuordnung gezielte Rückfrage | Identitätsregeln mit konkurrierenden Quellen prüfen |
| Zwei Projekte enthalten ähnliche Vorgänge | Keine stillschweigende Zusammenführung; Projekt bei Bedarf erfragen | Bereichsauswahl und Quellenbelege prüfen |
| Eine Zusage gilt nur unter einer Bedingung | Die Bedingung bleibt in der Antwort sichtbar | Volltextbeleg einschließlich weiterer Absätze prüfen |
| Zwei Quellen widersprechen sich | Beide Belege bleiben sichtbar; ein neueres Datum allein entscheidet nicht, welche Aussage wahr ist | Konfliktzustand mit kontrollierten Modellausgaben prüfen; echtes Erkennen bleibt offen |
| Eine Information fehlt | Fehlende Information oder unvollständige Suche benennen; keine erfundene Antwort | Antwortzustände und unzulässige Referenzen prüfen |
| Eine Quelle wird ausgeschlossen | Sie verschwindet auch aus gespeicherten Antworten und späterem Modellkontext | Quellenentzug über Gespräch und Abruf prüfen |
| Eine Mail oder Aufgabenübernahme wird wiederholt | Keine doppelte Quelle oder Aufgabe, auch nach Neustart | Gemeinsamen Pilotablauf mit SQLite-Neustart prüfen |
| Die erste Einordnung ist noch nicht fertig | Aufnahmestand, Einordnungsstand und Begrenzungen auseinanderhalten | Fortschrittszähler prüfen; tatsächliche Bestandsabdeckung bleibt offen |
| Eine Aktion würde nach außen wirken | Vorbereitung und Ausführung sind sichtbar getrennt; Freigabe wird nicht doppelt ausgeführt | Lokalen Freigabeablauf ohne echten Versand prüfen |

## Was am Mac nachgeholt wird

1. **Bedienung auf dem getrennten Testbestand:** KI-Zugang finden, Fortschritt verstehen, Quelle aus einer Antwort öffnen, Vorschlag prüfen und übernehmen. Festhalten, wo unnötige Klicks oder unklare Rückmeldungen entstehen.
2. **Sicherung und Update:** Bestehenden Pilot sichern, vorbereitete Fassung installieren, Erhalt von Originalquellen, bestätigten Aufgaben und Zugängen prüfen. Keine Testbereinigung des persönlichen Bestands.
3. **Quellenumfang bestätigen:** Gewünschte Konten, Ordner, Kalender und Zeiträume mit dem Ausgangssystem vergleichen. „Verbunden“ ist kein Nachweis vollständiger Aufnahme.
4. **Echtes Verstehen messen:** Aus vorhandenen Quellen Fragen mit vorher festgelegten Sollantworten wählen. Quelle, Person, Projekt, Zeit, Bedingung und fehlende Information getrennt bewerten. Ausgelassene relevante Quellen zählen als Fehler, auch wenn die Antwort vorsichtig klingt.
5. **Einen Arbeitstag begleiten:** Heute-Übersicht gegen Mail, Kalender und Aufgaben gegenprüfen. Wiederholte Bedienhürden und zusätzliche Kontrollarbeit notieren. Daraus die nächsten Verbesserungen ableiten.

## Zusätzliche Bedienfälle für die drei Anschlussfunktionen

- **Gedächtnisfrage auf Heute:** Beide Werte und Originalbelege verstehen, Quelle öffnen und bewusst entscheiden. In einem zweiten Fenster die Quelle ausschließen oder den Vorschlag ändern; die alte Entscheidung muss abgewiesen und die Ansicht aktualisiert werden. Unbekanntes Quelldatum darf nicht wie das Erfassungsdatum wirken.
- **Mailüberblick:** Einen Verlauf mit ursprünglicher Bitte und späterer Absage öffnen, den Überblick ausdrücklich starten und die ausgewählten Originalstellen vergleichen. Kategorien bleiben ungeprüft. „Verlauf zur Prüfung vormerken“ darf nur einen Prüfauftrag vorbereiten, keine alte Bitte als aktuelle Verpflichtung übernehmen. Quellenwechsel während der Erstellung darf keinen alten Überblick ausliefern.
- **Wiedervorlage:** Einer wartenden Aufgabe einen eigenen Erinnerungszeitpunkt geben, Anzeige auf Heute prüfen, auf morgen verschieben und abschließen. Fälligkeit und Wartestatus müssen unverändert bleiben. Mit zwei Fenstern eine überholte Änderung provozieren; die neuere Wiedervorlage darf nicht überschrieben werden. Aktualisierung bei erneutem Fokus und ein schmales Fenster mitprüfen.

Die isolierte HTTP-Prüfung dieser Zustandswechsel ist bestanden. Verständlichkeit, Tastatur/Fokus, tatsächlicher Klickaufwand und die Darstellung im nativen Fenster sind noch offen. Die Wiedervorlage erzeugt keine Hintergrundbenachrichtigung bei geschlossener App.

## Freigabemaßstab

Falsche Personenzuordnung, erfundene Frist, verlorene Bedingung, weiterhin zugängliche entzogene Quelle oder unerwartete Ausführung blockieren die Freigabe des betroffenen Ablaufs. Ein nicht belegter oder nicht vollständig geprüfter Fall bleibt ausdrücklich offen.

Erst die Kombination aus technischer Prüfung, korrekter tatsächlicher Quellenabdeckung, echtem Modelltest und verständlicher Bedienung belegt Nutzbarkeit. Weder eine Testanzahl noch ein Modellname allein belegt ein fehlerfreies Gedächtnis. Ein späterer Cloud-Vergleich braucht einen festgelegten Umfang und Kostenrahmen.

## Nutzungswoche für die Alltagsversion — ergänzt am 5. November 2026

Diese Woche gehört zum [Produktplan P0–P5](superpowers/plans/2026-11-04-kingfisher-product-completion.md).
Sie ist **vorbereitet, noch nicht durchgeführt**. Sie beginnt erst nach bestandener
repräsentativer Modellprüfung, geprüftem normalen Update und der getrennten
Mac-Bedienprüfung. Der Großimport braucht weiterhin eine eigene Freigabe; die
Nutzungswoche startet ihn nicht.

Vor dem Start hält die technische Abnahme installierte App-/Backendversion,
Modell und freigegebenen Quellenumfang fest. Sicherung, Wiederherstellung,
Quellen-/Skillentzug, Fehlerfälle und Bedienung unter Last werden davor am
getrennten Testbestand geprüft. Dafür muss Sören keine persönlichen Daten
absichtlich beschädigen, Zugänge trennen oder Aufgaben doppelt auslösen.

Für Sören: täglich eine ohnehin anstehende Arbeit in Kingfisher erledigen und
kurz gegen das bisherige Programm beziehungsweise das Original prüfen. Eine
Minute Rückmeldung genügt: **Was wollte ich tun? Hat es gestimmt? Wo musste
ich suchen oder nacharbeiten?** Die folgenden Situationen können innerhalb der
Woche verschoben werden; ein nicht vorgekommener Fall bleibt offen.

| Tag | Arbeit aus dem Alltag | Woran ich den Nutzen erkenne |
|---|---|---|
| 1 | Morgens „Heute“ öffnen und einen Termin samt Vorbereitung ansehen. | Die wichtigen Aufgaben und Termine stimmen mit den Originalen überein. Ein nicht aktualisierter Bereich wird sichtbar benannt. |
| 2 | Eine wichtige Mail öffnen, den Überblick lesen und Person/Projekt ansehen. | Richtige Person, richtige Zuordnung und ein direkter Weg zurück zur Mail. Automatische Absender oder Namensgleichheit erzeugen keine falsche Person. |
| 3 | Aus einer echten Bitte eine Aufgabe samt Projekt übernehmen. | Zuständigkeit und Frist stimmen; ein Treffen wird nicht zur Abgabefrist. Die Aufgabe erscheint genau einmal und ist später wiederzufinden. |
| 4 | Zu einer Person oder einem Projekt im Gespräch nachfragen und den Beleg öffnen. | Die Antwort beantwortet die Frage, zeigt das passende Original und fragt bei echter Mehrdeutigkeit nach. Fehlendes Wissen wird nicht ergänzt. |
| 5 | Eine wiederkehrende Nachricht als Entwurf vorbereiten und bei Bedarf den Ton korrigieren. | Der passende Ablauf hilft, eine private Nachricht erhält keinen unpassenden Geschäftston. Ein Lernvorschlag bleibt bis zur Bestätigung inaktiv; nichts wird ungefragt versandt. |
| 6 | Eine offene Arbeit nach einem normalen App-Neustart fortsetzen. | Entwurf, Aufgabe, Korrektur und Konten sind erhalten. Kingfisher bleibt neben den anderen Arbeitsprogrammen bedienbar. |
| 7 | Die Woche überblicken: Was ist erledigt, worauf warte ich, was steht als Nächstes an? | Eigene Aufgaben, fremde Zusagen und bestätigte Erledigungen sind unterscheidbar. Eine korrigierte Information wird nicht wieder falsch ausgegeben. |

Den Verlauf privat auf dem Mac festhalten. Für ein GitHub-Ticket genügt eine
anonymisierte Fehlerbeschreibung; Mailtexte, Namen, Zugangsdaten und persönliche
Screenshots gehören nicht in den öffentlichen Nachweis. Der vorhandene
Rückmeldeweg an der Antwort kann Fehler melden. Eine solche Meldung ist noch
keine bestätigte Änderung von Fakten oder Arbeitsweisen.

**Wenn eine falsche Person, falsche Frist, verlorene Korrektur oder unerwartete
Aktion auffällt:** den betroffenen Ablauf nicht weiter automatisch verwenden,
Original und Zeitpunkt festhalten und die Korrektur prüfen lassen. Eine
stockende Oberfläche oder ein unklarer Weg zählt ebenfalls als Befund; Sören
muss die App nicht mit Entwicklerwissen umgehen. Repariert und erneut geprüft
wird der betroffene Ablauf mit Gegenfällen, ohne erfolgreich absolvierte Tage
pauschal zu wiederholen. Breite Änderungen können eine gezielte neue Abnahme
erfordern.

Private Abschlussnotiz:

- Zeitraum, installierte Versionen, Modell und freigegebener Quellenumfang:
- Tatsächlich erledigte Tagesabläufe (mindestens fünf; Datum und Ergebnis):
- Falsche Zuordnungen, Fristen, fehlende Informationen oder verlorene Arbeit:
- Bedienhürden und merkliche Belastung des Mac:
- Korrigierte Befunde und Ergebnis der Nachprüfung:
- Offene Fälle:
- Sörens Urteil: im Alltag nutzbar / noch nicht nutzbar, mit kurzem Grund:

Sieben vergangene Tage oder leere Fehlerfelder gelten nicht als bestanden.
Die tatsächlichen Abläufe, offene Befunde und Sörens Urteil entscheiden.
Der Abschluss dieser Woche ersetzt weder die technische P0–P5-Abnahme noch
die spätere gesonderte Prüfung der Erweiterungsplattform P6.
