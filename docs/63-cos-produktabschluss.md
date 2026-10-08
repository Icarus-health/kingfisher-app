# Produktabschluss: vom vorhandenen Kern zum verlässlichen persönlichen CoS

Stand: 8. Oktober 2026. Dieses Dokument trennt gebaute Funktionen von ihrem Nachweis im persönlichen Alltag. Ein vorhandener Endpunkt, Test oder Modellname belegt für sich weder vollständige Quellenaufnahme noch zuverlässige Antworten oder geringe Bedienlast.

## Abnahmematrix

| Bereich | Bereits gebaut | Noch offen für den Produktnachweis | Abnahme im Alltag |
|---|---|---|---|
| Quellen | Mail- und Kalenderadapter, ausgewählte lokale Ordner, Google-/Apple- und Microsoft-Zugangswege, Outlook/Graph-Aufnahme sowie Transkript- und Mitschriftenbausteine | Tatsächlich gewünschte Konten, Ordner, Zeiträume, Anlagen und Kalender gegen den jeweiligen Ausgangsbestand abgleichen. „Verbunden“, „ausgewählt“, „aufgenommen“, „eingeordnet“ und „für Antworten verfügbar“ getrennt anzeigen. Hochschul-Tenant-Rechte und der echte Mac-Kalenderhelfer sind noch nicht als vollständig nutzbar abgenommen. | Für jedes gewünschte Konto und jeden Kalender einen nachvollziehbaren Bestand vergleichen; Lücken und Fehler sichtbar lassen. |
| Gedächtnis | Originalquellen, Quellen- und Erfassungszeit, Personen/Projekte/Akten, belegte Aussagen, Verlauf, Konfliktfragen, Korrektur und Quellenentzug | Echte Antwortqualität und Suchvollständigkeit am vorgesehenen Bestand fehlen als unabhängiger Nachweis. Begrenzte Kandidatensuche und eine vorsichtige Antwort beweisen nicht, dass keine passende Quelle ausgelassen wurde. | Vorab festgelegte Fragen zu Person, Projekt, Quelldatum, Bedingung, Absage, Konflikt und fehlender Information beantworten; Beleg öffnen und Quellenentzug erneut prüfen. |
| Entscheidungen | Heute, Aufgabenprüfung, Mail-Originale und Verläufe, Quellenbefunde, direkte Aufgabenaktionen, Aufgaben-Wiedervorlage, Bestätigungsschutz und normaler Prüfbereich `/review` mit verständlichen Rückfragen | Die unterschiedlichen fachlichen Entscheidungen sind verbunden, bleiben aber getrennt belegt. Am Mac prüfen, ob eine Person ohne technische Kennungen vom Hinweis zum Original und zur passenden Entscheidung kommt, den Stand versteht und danach zum Arbeitsschritt zurückfindet. | Einen Arbeitstag begleiten: Heute → Originalquelle → prüfen/korrigieren/übernehmen → Aufgabe oder Wiedervorlage → zurück zum Kontext. Keine ungeprüfte Aussage als bestätigtes Wissen behandeln. |
| Aufgaben | Aufgaben anlegen/bearbeiten, Fristen, Projekt, Wartestatus, Verlauf, exakte Aufgabenlinks, terminierte Wiedervorlage sowie Bestandssuche und begrenzte Seiten mit Gesamtzahl und Änderungsstand | Suche und Seiten sind mit mehr als 200 offenen und mehr als 500 gemischten Aufgaben geprüft. Reale Bedienung, Geschwindigkeit am großen persönlichen Bestand und Serienaufgaben bleiben offen. Eine Wiedervorlage ist keine Fälligkeit und erzeugt bei geschlossener App keine Push-Benachrichtigung. | Aufgaben außerhalb der ersten Seite bleiben such- und erreichbar; eine Erinnerung ändert Frist und Wartestatus nicht; Zustand bleibt nach Neustart erhalten. |
| Kalender | Mehrere lesende Quellen, Zeit-/Monatsansichten, Vorbereitung/Nachbereitung und Projektbezug; laufende mehrtägige Termine werden in der Siebentageliste berücksichtigt; sichtbare Zeiträume über Jahresgrenzen, konkrete Vorkommen und separate Google-Schreibentwürfe | Zeitbereiche, Ladezustände, Vorkommen und Google-Schreibschutz sind mit künstlichen Anbietern geprüft. Echte Kalenderabdeckung und Schreibaktionen sind noch nicht persönlich abgenommen. Schreiben verlangt zusätzliche OAuth-Rechte; Serientermine, neue Gäste und ganztägige Neuanlage werden im neuen Formular nicht angeboten. Unklare Ausgänge bleiben gesperrt und verlangen Prüfung beim Anbieter. | Dezember/Januar und Wochen über Jahreswechsel gegen den Originalkalender prüfen. Schreibaktionen nur mit sichtbarer Vorschau, ausdrücklicher Freigabe, Schutz vor Dopplung und bestätigtem Anbieterzustand abnehmen. |
| Bedienung und Einrichtung | Bestehende Today-/Gedächtnis-/Nachrichten-/Aufgabenansichten und sichtbarer Verarbeitungsstand | Native Mac-Prüfung für Lesbarkeit, Fokus/Tastatur, schmale Fenster, tatsächliche Klickzahl, Einrichtungszeit und Rückkehrposition steht noch aus. Der gesperrte Mac und die nicht verfügbare Browserfreigabe sind kein UX-Nachweis. | Getrennter Testbestand und getrennte Sicherung verwenden; einen normalen Ablauf ohne Nachschlagen erledigen und unnötige Wege oder missverständliche Zustände dokumentieren. |

## Lieferung vom 7. Oktober

Die zuvor gefundenen Listen- und Jahresgrenzen sind im Entwicklungsbranch korrigiert. „Heute“ verlinkt direkt auf einen normalen Prüfbereich; technische Kennungen sind Zusatzdetails. Das neue Kalenderformular zeigt Konto, Kalender, vorherigen und geplanten Stand sowie bestehende Gäste und Benachrichtigungswahl. Eine bestätigte Vorschau wird persistent und gegen parallele Ausführung gesichert. Verlorene Antworten werden nicht als Erfolg behandelt. Das Ausführungsjournal wird mitgesichert.

Mail → Aufgabe und Antwortentwurf nutzen weiterhin die vorhandenen quellengeschützten Wege. **Mail → Kalender mit automatischer Übernahme ist noch offen:** ohne Bindung an Originalfassung, Prüfung von Absagen und eindeutige Zeit-/Personenzuordnung wäre das ein neuer Fehlerrisikopfad. Der neue Terminentwurf ist deshalb manuell; er behauptet keine verifizierte Mailauswertung.

## Reihenfolge

Vor dem nächsten persönlichen Dauerlauf gilt der Akkuschutz aus
[`46-hintergrund.md`](46-hintergrund.md): automatische Zeitplanarbeit nur mit
frischer Netzteilmeldung der neuen Mac-App. Der Schutz wird im Code geprüft;
die Installation und ein vergleichbarer Akkutest im Alltag stehen noch aus.
Der gemeldete hohe Verbrauch des Vortags ist durch eine spätere Einzelmessung
nicht einem bestimmten Prozess zuzuordnen.

1. Einen normalen Arbeitstag auf dem getrennten Testbestand durchlaufen und dabei die tatsächliche Quellenabdeckung sowie offene Aufgaben-/Kalendergrenzen messen.
2. Nur die dabei beobachteten Blocker schließen: verlässliche Bestandsauswahl, verständlicher Eingang für Entscheidungen, Rückkehr zum Ausgangskontext und vollständige Kalenderzeiträume. Keine neue Datenbank oder Gedächtnisarchitektur ist dafür Voraussetzung.
3. Das echte lokale Antwortmodell an vorab festgelegten Antworten und Originalbelegen beurteilen. Kritische Fehler sind falsche Person, Frist oder Bedingung, übersehene Absage und weiter nutzbare entzogene Quelle.
4. Erst nach bestandenem Kernablauf gezielte neue Quellen ergänzen und jeweils ihre eigene Vollständigkeit und Rückverfolgbarkeit abnehmen.

## Spätere Erweiterungen und Freigaben

**WhatsApp:** Der Nutzer bevorzugt ausdrücklich die offizielle API, nach dem Kernablauf. Zuerst prüfen wir dafür den gewünschten Kanal und die verfügbaren Rechte. Meta beschreibt seine [Business Platform](https://whatsappbusiness.com/products/business-platform/) für geschäftliche Kundenkommunikation; daraus folgt kein belegter Zugriff auf den gesamten privaten Chatbestand. Lokale ausgewählte Exporte bleiben nur eine mögliche Alternative, kein festgelegter erster Pflichtschritt. Kein Live-Zugang oder inoffizieller Client wird eingerichtet.

**Weltmeldungen:** eine optionale, einzelne Meldung passend zu einer bestehenden Akte ist bereits vorgesehen. Die Einstellung ist standardmäßig aus; ein Feedabruf setzt eine ausdrückliche Wahl voraus. Das ist noch kein breites Welt-Nachrichten-Morgenbriefing. Relevanz über eine echte Alltagswoche und reale Feedantworten wurden nicht abgenommen. Eine Ausweitung bleibt nachrangig.

**Sprache:** lokale Audio-Wiedergabe des Briefings ist als Funktion vorhanden. Sie belegt keinen Sprachdialog oder verlässliche Spracheingabe. Gesprächssteuerung per Sprache bleibt später; sie ist keine Voraussetzung für den Kernnachweis.

Keine neue Nachrichtenquelle, kein Cloudmodell und kein extern wirkender Vorgang wird durch diese Produktplanung aktiviert. Modell- oder Anbieterzugänge bleiben optional und gesondert freizugeben.


## Geprüfte Lieferung vom 8. Oktober

Der [Liefernachweis](runs/2026-10-08-cos-delivery/README.md) dokumentiert Ziele → Aufgaben, Entwicklung, corpusweite Gedächtnisbereiche, öffentliche Quellen mit Herkunft, Belegprüfung und wörtliche Originalstellensuche. Der Code-Stand `da5b0e6` besteht 5245 Backend-/Diagnostik-/Mac-Tests (2 übersprungen), 375 Oberflächenprüfungen und den Produktionsbuild. Er ist nach kalter Sicherung lokal auf dem Mac installiert; native Bedienprüfung nach Austausch bleibt wegen des gesperrten Macs offen.

Der echte lokale Antwortweg findet bei 16 direkten Fragen die erwarteten Quellen, aber nur bei 8 von 16 Umschreibungen. Die unabhängige Inhaltsprüfung fand außerdem erfundene Datumspräzision; Import- und Anzeigedaten dürfen jetzt keine fehlenden Quelldaten ersetzen. Zeitliche Anwendbarkeit und eine abgeschwächte Uhrzeitbedingung bleiben offen. Die Abnahme des gesamten Gedächtnisses und des täglichen CoS ist dadurch **nicht erreicht**.

Nächste Kernarbeit: Kandidatenfund und Modellauswahl getrennt prüfen, Umschreibungen mit unabhängigen Kontrollen verbessern, danach Bedingungen und aktuelle Gültigkeit am Original absichern. Reale Quellenabdeckung und Alltags-/Akkutest bleiben gesonderte Nachweise. Mehr Module oder größere Modelle ersetzen diese Abnahme nicht.


### Ergänzung: Abrufstufen und Uhrzeitbedingungen

Der [getrennte Nachweis](runs/2026-10-08-retrieval-stages/README.md) ergänzt echte Aufrufspuren für Kandidatenfund, Modellauswahl und Anzeige. Die nachgewiesene Abschwächung „erst nach 10 Uhr“ → „ab 10 Uhr“ wird nun von der gemeinsamen Satzprüfung verworfen; erkannte Zeitfenster bleiben gepaart, gespeicherte Antworten fallen bei dieser Abweichung auf Originalzitate zurück. 519 betroffene Tests und ein unabhängiges Review sind abgeschlossen. Dies schließt den konkret beobachteten Uhrzeitfehler, keine allgemeine Bedeutungsprüfung. Zeitliche Anwendbarkeit, der frische echte Modellvergleich, Quellenvollständigkeit und native Alltagsbedienung bleiben offen. Die frühere Quote von 8/16 umformulierten Fragen ist dadurch nicht verbessert nachgewiesen. PR 7 ist gemergt; lokal ist `1.0.6-local.fc5f33e` nach kalter Sicherung installiert, alle 344 Einträge samt Inhaltsprüfsummen und 17 SQLite-Dateien sind erhalten/geprüft. Native Bedienprüfung bleibt offen.


### Ergänzung: Suchabdeckung und größere Bestände

Der [CPU-Nachweis und die Abdeckungskorrektur](runs/2026-10-08-cpu-retrieval/README.md) trennen frische erfolgreiche bge-m3-Rankings von einem an Speicher/Timeouts gescheiterten Antwortmodellversuch. Knappe Schwellenfehler und ein falscher Rollen-Kandidat sprechen gegen eine blinde Schwellenabsenkung. Unvollständige Bedeutungssuche wird nun pro Suchaufruf festgehalten und in Antworten, Rückfragen und gespeicherten Quellenanzeigen offengelegt; sie darf keinen vollständigen Diagnose-Erfolg erzielen. 359 betroffene Prüfungen und das unabhängige Review bestehen. Dies ist keine nachgewiesene Verbesserung der vollständigen Antwortquote.

Der semantische Bestand bleibt auf 2048 flüchtig eingebettete Abschnitte begrenzt. Der nächste erforderliche Produktbaustein ist ein inkrementeller, dauerhafter abgeleiteter Suchindex über alle zugelassenen eingeordneten Quellen mit Modell-/Quellenfingerabdruck, Fortschritt und unmittelbarem Entzugsschutz. Originalquellen und Einordnung bleiben maßgeblich. Eine schnelle Suche im großen Bestand, die echte Antwortqualität und native Alltagsbedienung sind weiterhin offen.

Die Abdeckungskorrektur ist als [PR 8](https://github.com/Icarus-health/kingfisher-app/pull/8) gemergt und nach kalter Sicherung lokal als **1.0.6-local.66eb641** installiert. 344 Einträge mit ihren Inhaltsprüfsummen und 17 SQLite-Dateien sind erhalten/geprüft; Konten und Einstellungen unverändert. Die native Fensterprüfung bleibt offen.


### Aktueller Lieferstand: dauerhafter Abruf und Datumsgrenzen

Die oben beschriebene 2048-Abschnitt-Grenze ist der historische Ausgangsstand. [PR 9](https://github.com/Icarus-health/kingfisher-app/pull/9) liefert inzwischen den [dauerhaften, inkrementellen abgeleiteten Suchindex](runs/2026-10-08-durable-search-product/README.md) einschließlich originalgebundener Entzugsprüfung, corpusweitem Änderungsnachweis und ehrlicher Abdeckungsanzeige. Er ist auf dem Mac aktiviert. Solange Ollama ausgeschaltet ist, lautet der Zustand `unavailable`; Aktivierung allein beweist weder fertige Einbettungen noch bessere Antwortqualität.

Die [anschließende Korrektur für Kalenderdatumsgrenzen](runs/2026-10-08-calendar-bound-answers/README.md) schützt erkannte explizite Einzel-Datumsrelationen und eng begrenzte Gültigkeitsaussagen. Neue und gespeicherte fehlerhafte Sätze fallen auf Originalzitate zurück. Unabhängiges Review, 5343 bestandene Backendtests (1 übersprungen), 34 betroffene Diagnoseprüfungen und netzlose Prüfung des fertigen Pakets sind abgeschlossen. Aktuell lokal installiert ist **1.0.6-local.6052d41**; 344 Originale und 17 SQLite-Dateien sind erhalten/geprüft. Hintergrundarbeit bleibt ausdrücklich pausiert, native Alltagsbedienung wegen des gesperrten Macs offen.

Nächster konkret reproduzierter Bedienungsblocker: Mailstatus nennt einen unvollständigen Eingang weiterhin „wird gelesen“, obwohl die globale Hintergrundpause gesetzt ist. Die unabhängige künstliche Prüfung bestätigt dies über beide Mail-GET-Routen. Die Pausenanzeige muss die Zahlen erhalten und zur richtigen globalen Fortsetzen-Aktion führen; fertige Postfächer, Konto-Pause und vorübergehendes Ressourcenwarten dürfen nicht vermischt werden. Diese Korrektur ist in obiger Lieferung noch nicht enthalten. Reale Umschreibungs-/Antwortqualität, gewünschte Quellenabdeckung und native Tages-/Akkubedienung bleiben Kernabnahmen; sie werden durch diesen Lieferstand nicht als bestanden erklärt.


### Aktueller Lieferstand: sichtbare Mailpause

Der zuvor beschriebene Pausenblocker ist mit [der begrenzten, unabhängig geprüften Korrektur](runs/2026-10-08-mail-pause-flow/README.md) geschlossen. Auf Heute, im Assistenten und im technischen Mailbereich bleiben globale Pause und einzelne Postfachpause getrennt; Fortschrittszahlen bleiben erhalten und die sichtbare Fortsetzen-Aktion löst die richtige Pause. 132 betroffene Backendtests (1 übersprungen), 386 Oberflächenprüfungen, Produktionsbuild sowie gerenderte Bedienung mit künstlichem Postfach bestehen. Die technische Testinstanz wurde nach einem korrigierten fehlenden Scheduler-Stub erneut ohne Fehler geprüft.

Lokal installiert ist **1.0.6-local.722adeb** nach kalter Sicherung; 344 Originale, 17 SQLite-Dateien und Konten/Einstellungen sind erhalten. Der echte Mailstatus meldet jetzt `pausiert`. Modelle und persönlicher Import bleiben angehalten; der dauerhafte Suchindex ist dadurch weiterhin nicht verfügbar. Native Alltags-/Akkubedienung, echte vollständige Antwortqualität und gewünschte Quellenabdeckung bleiben offen. Diese Lieferung behauptet keinen fertigen CoS.

### Aktueller Lieferstand: begrenzter Fragen-Transport

Der [echte künstliche Vorher-/Nachher-Lauf](runs/2026-10-08-question-transport-budget/README.md) reproduziert einen30-Sekunden-HTTP-Aufruf trotz bereits abgelaufenem6-Sekunden-Fragenverständnis. Die Frist wird jetzt worker-lokal bis zum lokalen JSON-Transport weitergegeben; nach bereits abgelaufener Modellvorbereitung beginnt keine Generierung.199 betroffene Prüfungen (1 übersprungen), unabhängiges Review und echter langsamer Loopback-Test auch im fertigen Image bestehen. Das ist keine harte Gesamtfrist aller Modellwarte-/Nachlaufphasen.

Lokal installiert ist **1.0.6-local.f5af412** nach kalter Sicherung;344 Originale,17 SQLite-Dateien, Konten und Einstellungen erhalten. Import bleibt pausiert, produktives Ollama aus, native Fensterprüfung weiterhin blockiert. Der getrennt getestete kleine `gemma3:1b-it-qat`-Kandidat ist ungeeignet: Er wählt einen Dresden-Termin zur Frage nach bezahlter Dacharbeit, obwohl die Bedeutungssuche die richtige Rechnung findet. Zwei Direktquellen werden richtig angezeigt, eine andere Umschreibung bleibt unbeantwortet. Dies ist ein begrenzter Vier-Fragen-Befund, keine vollständige Qualitätsmessung oder Mac-GPU-Messung. Modellrollen wurden nicht geändert; stärkere freigegebene Modellmessung und native Alltags-/Quellenabnahme bleiben offen.


### Aktueller Lieferstand: Zeitgrammatik und echter Mac-Modellvergleich

Die [engere Zeitgrammatik](runs/2026-10-08-question-time-schema/README.md) verhindert erfundene Zeiträume schon bei lokaler strukturierter Generierung, ohne Validator oder Quellenprüfung zu lockern. Im vollständigen synthetischen Mac-GPU-Vergleich mit vorhandenem qwen3.5:4b/bge-m3 steigen Quellen-/Statuspunkte von28 auf30/36; neu gefundene Wartung belegt jedoch keinen Ausfall. Die23 unabhängigen Kontrollfragen bleiben identisch bei22/23, einschließlich Namen-/Auftragsunterscheidung, Freigaben, Änderung und Absage. Originalzitate, Nichtwissen und Quellenentzug wurden unabhängig geprüft. Keine allgemeine Fehlerfreiheits-, Einordnungs- oder Geschwindigkeitsabnahme.

191 betroffene Prüfungen bestehen; fertiges Paket und unveränderte Oberfläche sind byteweise geprüft. Lokal installiert ist **1.0.6-local.064a4d9** nach kalter Sicherung.344 Originale,17SQLite-Dateien, Konten/Einstellungen und explizite Importpause erhalten. Produktive Modellrollen wurden nicht auf den Kandidaten umgestellt; Ollama bleibt aus. Native Alltagsbedienung weiterhin wegen gesperrtem Mac offen. Fünf umformulierte Originalfragen erreichen noch keinen Quellen-/Statuspunkt; unabhängige RQ02 fragt unnötig nach der Person. Als nächster Qualitätsnachweis fehlen insbesondere tatsächliche freie Antwort-/Einordnungsqualität mit geeignetem lokalem Modell sowie persönliche Quellen- und Alltagsabnahme.


### Aktueller Lieferstand: Satzprüfungsfrist und freie Antwortqualität

Die [Satzprüfungs-Korrektur und die getrennte native Qualitätsmessung](runs/2026-10-08-verifier-deadline/README.md) reichen das Satzbudget worker-lokal an den lokalen JSON-Transport weiter. Vier neue Regressionen reproduzieren den zuvor fortlaufenden Transport bzw. verspätete Arbeit;260 betroffene Tests, unabhängiges Codereview, byteweiser Paketnachweis und echter langsamer Loopback-Test im fertigen Image bestehen. Kein harter GPU-/Workerabbruch und keine gemessene Akkuverbesserung.

Die59synthetischen freien Antworten messen ausdrücklich den vorherigen Produktcode064a4d9, nicht die Wirkung des Transportfixes. Alle35angezeigten freien Sätze werden im unabhängigen Quellenreview gestützt; elf bzw.zwei Fragen fallen auf Originalzitate zurück. Fehlender Abruf, verlorene Auswahl und vor allem drei materiell unvollständige Kontrollantworten bleiben: Die Prüfung verwirft belegte Bedingungen bzw.den zweiten Termin eines Vergleichs. Nächster Kernblocker ist deshalb ein allgemeiner Schutz gegen solche Teilantworten mit erhaltenen Originalen, einschließlich gespeichertem Verlauf. Keine gelockerte Faktenprüfung oder auf Testbegriffe zugeschnittene Suchliste.

Lokal installiert **1.0.6-local.0f0f5da** nach kalter Sicherung;344Originale,17SQLite-Dateien, Konten/Einstellungen und Importpause erhalten. Produktives Ollama bleibt aus. Reale Einordnungs-/Quellenabdeckung und native Tages-/Akkuabnahme bleiben offen; kein fertiger CoS behauptet.


### Aktueller Lieferstand: keine verschwundene Quelle nach Teilverwerfung

Der [quellenbezogene Teilantwortschutz](runs/2026-10-08-partial-answer-source-loss/README.md) schließt jetzt zwei der unabhängig gefundenen Anzeigeverluste: Nach einer Satzverwerfung fällt eine Antwort auf Originalstellen zurück, sobald eine vorgelegte Quelle in den übrigen Sätzen ganz fehlt. Beide aufgezeichneten Problemfälle werden offline unverändert reproduziert und gehen nachher in den Zitatmodus. Auch alte gespeicherte Teilantworten sind geschützt; geprüfte Wandel-Sätze und Quellenentzug bleiben erhalten.73 enge und260 betroffene Prüfungen, unabhängiges Review und netzloser Paket-Smoke bestehen.

Aktuell lokal **1.0.6-local.cde3129** nach kalter Sicherung;344Originale,17SQLite-Dateien, Konten/Einstellungen und Importpause erhalten. Noch offen sind verlorene Bedingungen innerhalb derselben Quelle, Auslassungen ohne Satzverwerfung, Abruf-/Auswahlverluste, echte Quellen-/Einordnungsabdeckung und native Tages-/Akkuabnahme. Der neue Guard ist keine semantische Vollständigkeitsgarantie und der gesamte CoS bleibt unabgenommen.


### Aktueller Lieferstand: Bedingungen derselben Quelle erhalten

Der [Bedingungsschutz](runs/2026-10-08-conditional-permissions/README.md) schließt den weiteren KontrollfallQ5: Nach Verwerfung einer Regel innerhalb derselben Quelle erscheinen vollständige Originalstellen statt nur „Freigabe fehlt“. Erkannte passive Erlaubnisquellen erlauben freie Antwortsätze nur mit vollständiger wörtlicher Entsprechung; daraus darf weder unbedingte Erlaubnis noch ein erfolgter Vorgang abgeleitet werden. Eigenständige wörtliche Tatsachenmeldungen bleiben möglich. Die enge Negationsausnahme bewahrt nur eine unveränderte Regel neben ihrem gleichquelligen Fehlstatus; separate Verbote und Quellenentzug bleiben streng. Auch alte gespeicherte Teilantworten werden erneut geschützt.

33 neue und270 betroffene Prüfungen bestehen. Ein günstiger unabhängiger Reviewer fand echte Umgehungen im Zwischenstand (Umgangssprache/Pronomen, Plural, Zeichenkollisionen); sie sind vor Lieferung behoben und als Tests erhalten. Die aufgezeichnete native Q5-Ausgabe geht offline von Teilantwort auf Originalzitate; kein neuer Inferenz-/Abrufbenchmark. Netzloser Paket-Smoke und byteweiser Nachweis bestehen.

Aktuell lokal **1.0.6-local.32d5a12** nach kalter Sicherung;344Originale,17SQLite-Dateien, Konten/Einstellungen und Importpause erhalten. Produktives Ollama aus. Bedingungsgrammatik außerhalb der erkannten passiven Formen, Auslassungen ohne Verwerfung, Abruf-/Auswahlverluste und echte Einordnungs-/Quellenabdeckung bleiben offen. Die native Fensterprüfung scheitert weiterhin am gesperrten Mac; Tages-/Akkuabnahme bleibt offen. Weiterhin kein insgesamt abgenommener CoS.


### Aktueller Lieferstand: Quellenfrische und ehrlicher Fortschritt

Die [Korrektur der Quellenfrische](runs/2026-10-08-source-coverage-freshness/README.md) öffnet Fortschritt und semantische Quellenlücke nach generationserhöhenden Metadatenänderungen sofort wieder. Veraltete Einordnungen werden nicht erneut eingebettet. Fehlende Altmarker werden nur nach vollständigem Fingerabdruckvergleich im nächsten autorisierten begrenzten Scan ergänzt; vorhandene passende Vektoren bleiben ohne erneute Inferenz nutzbar. Ausschluss und Entzug bleiben erhalten. 12 neue Regressionen, 170 betroffene Prüfungen, unabhängiges Review, byteweiser Paketnachweis und netzloser Smoke bestehen.

Lokal **1.0.6-local.46aeef5** nach kalter Sicherung; 344 Originale, 17 SQLite-Dateien, Konten/Einstellungen und Importpause erhalten. Der reale Postfachverlauf ist noch weitgehend unaufgenommen: 304 von 122.399 inventarisierten Einträgen aufgenommen, 120.805 warten auf Abruf. Dies ist keine durchsuchbare Gesamtabdeckung. Bedeutungssuche bei ausgeschaltetem Ollama unavailable; native Tages-/Akkuabnahme und weitere Einordnungs-/Antwortqualität bleiben offen. Insgesamt kein fertiger CoS behauptet.
