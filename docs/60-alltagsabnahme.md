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
