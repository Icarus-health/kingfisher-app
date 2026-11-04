# Gemeinsame Prüfung: Lernen, Mistral-Vorbereitung, Mailaufgabe und Kalender

Zusammengeführter Produktstand `d8581e8aed1febafa1297ade9ba87d4804645a88`, anschließend CI-Trennung, Dokumentation und die unten getrennt ausgewiesene Darstellungskorrektur. Enthält die separat geprüften Pakete PR120, PR121, PR122 einschließlich `caee3bc` und PR123. Keine Konfliktauflösung oder neue Produktlogik beim lokalen Zusammenführen. Basis `1b5a262`.

## Ergebnis

857 betroffene Backendtests bestanden in 121,87 Sekunden; 1.072 Frontendtests bestanden in 13,41 Sekunden. TypeScript, Produktionsbuild, Assetvertrag und Diffprüfung bestanden. Die bekannten Starlette/httpx- und Bundlegrößenwarnungen bleiben offen. Die erneute Prüfung war wegen der gemeinsamen Fassung erforderlich; sie ist kein vollständiger Backendlauf und keine echte Modellabnahme.

Der gemeinsame Ablauf wurde danach über die echte gebaute Oberfläche und das echte Backend auf einer getrennten Instanz unter `127.0.0.1:8894` bedient. Es gab ausschließlich künstliche Quellen, einen künstlichen Antwortanbieter, keine Anbieterzugänge und keinen Zugriff auf den OS-Schlüsselbund. Ausgehende Verbindungen dieses Testprozesses waren gesperrt. Die Hintergrundverarbeitung war pausiert. Die zuvor offene Test-App auf 8893 samt ungespeichertem Entwurf wurde nicht verändert.

| Bedienung | Beobachteter Nachweis |
| --- | --- |
| Dritte ausdrückliche Arbeitskorrektur im Gespräch melden | Ein Vorschlag mit drei Herkunftslinks; noch nicht aktiv |
| Vorschlag öffnen | Schritte, passendes Beispiel, Gegenbeispiel und ausdrückliche Übernahme sichtbar |
| Optionale Mistral-Prüfung ohne Zugang/Kostenlimit öffnen | Keine Cloudfreigabe; Start nicht möglich |
| Gespeicherte Mail öffnen | Bezug Anna Berg; Frist 30.11.2026, 14:30; Besprechung am 04.11. wird nicht zur Frist |
| Neues Projekt und Aufgabe gemeinsam bestätigen | Eine Aufgabe im neuen Projekt, richtige Bezugsperson und Frist |
| Aufgabe danach öffnen, nur Notiz ergänzen und speichern | Persistierte Frist bleibt exakt `2026-11-30T14:30:00+01:00` |
| Aufgabenquelle öffnen | Übernommene Textstelle und vollständige künstliche Mail erreichbar |
| Erfolgreichen Kalenderabruf danach ausfallen lassen | Bereits geladener Termin bleibt ausdrücklich ungeprüft sichtbar |
| Ungeprüften Termin öffnen | Zeit/Quelle sichtbar, Änderungen und Vorbereitung nicht angeboten |

Am Ende: ein künstlicher Modellaufruf für den Lernvorschlag, null echte Modell- und null Cloudaufrufe. Diese Prüfung bestätigt weder fachliche Mistralqualität noch Geschwindigkeit eines realen Modells. Keine echte Mail, Kalenderaktion oder persönliche Einstellung geändert; Großimport bleibt pausiert.

## CI und Auslieferung

- PR121 hatte erfolgreiche CI- und Containerläufe; beim letzten Abruf von PR120 waren keine Checks gemeldet. Das ist kein eigener Grünbeleg.
- PR122: Die zu kurze Wartezeit des unveränderten 101-Quellen-Tests wurde kontrolliert reproduziert und eng korrigiert; siehe dessen Run-Bericht. Die Produktlimits blieben gleich.
- PR123: Der unveränderte strikte Wiederholungs-Laufzeittest lag auf einem parallelen Python-3.12-Runner bei 1,39 statt unter einer Sekunde. Lokal bestanden alle 33 Fälle. CI trennt diese 33 Fälle jetzt von konkurrierenden pytest-Workern; Schwelle und Ergebnisprüfungen bleiben unverändert. Siehe dessen Run-Bericht. Kein alter roter Lauf wird als erfolgreich ausgegeben.
- Eine separate native „Kingfisher Produktprüfung.app“ mit dem vorhandenen `WebSurface` wurde gebaut und signaturgeprüft. Sie ist noch nicht gestartet; die konkrete Startfreigabe ist angefragt. Das ist weder eine native Bedienabnahme noch ein Test des normalen Updaters.
- Noch kein Release, kein Merge auf main und kein Update der persönlichen App aus diesem Gesamtpaket.

## Nacharbeit: Fristuhrzeit und prüfbare Arbeitskorrekturen

Die gemeinsame Bedienprobe zeigte zwei Darstellungsprobleme. Die genaue Frist blieb gespeichert, war aber erst im Beleg zu sehen. Die Aufgabenliste zeigt jetzt Tag und gespeicherte Uhrzeit untereinander, das Detail beides zusammen. Beim Bearbeiten ist der gespeicherte Zeitpunkt sichtbar; ein unveränderter Tag bewahrt seine Uhrzeit. Ein neu gewählter Tag gilt weiterhin bis 23:59 Uhr, was das Formular jetzt ausdrücklich erklärt. Die Gerätezeitzone bleibt maßgeblich. Die Anzeige behauptet keine zusätzliche Genauigkeit der Originalquelle; auch gespeicherte Tagesendzeiten werden nicht als unbekannt ausgeblendet.

Die Mistral-Anzeige nennt jetzt „passende Arbeitskorrekturen für eine neue Prüfung“. Null bedeutet keine aktuell passende neue Prüfung und behauptet nicht mehr, dass keine Korrekturen gespeichert seien. Vorhandene lokale Vorschläge und Freigabeschranken bleiben unverändert.

Zwei gezielte Komponententests scheiterten vorher an der unsichtbaren Uhrzeit. Nach der Korrektur bestehen 1.074 Frontendtests in 13,19 Sekunden, einschließlich Darstellung in Liste/Detail und einer echten Notizänderung ohne ersetzte Frist im Änderungsauftrag. TypeScript, Produktionsbuild, Assetvertrag und Diffprüfung bestehen; die vorhandene Bundlegrößenwarnung bleibt. Keine Backendlogik geändert, daher kein weiterer Vollbackendlauf.

**Noch keine erneute visuelle Abnahme dieser Nacharbeit:** Die Computersteuerung lehnte am 04.11.2026 den Zugriff auf die separate Testinstanz automatisch ab, weil die angefragte Start-/Nutzungsfreigabe für das neue Testfenster noch unbeantwortet ist. Es wurde kein anderer Browser oder Umweg verwendet. Die Bediennachweise oben gelten für den früheren Produktstand, nicht für die neue Darstellung. Die persönliche App und der geschützte Testentwurf bleiben unberührt.

## Anschlussprüfung Wiederherstellung

Ein unabhängiger P5-Review fand anschließend, dass gesicherte Skills und Korrekturen im historischen Leser nicht erreichbar waren. Die feste Lese-Allowlist wurde um diese zwei vorhandenen Tabellen ergänzt. Ein verschlüsselter Roundtrip sowie 57 betroffene Tests bestanden; der unabhängige Abschlussreview fand keine weiteren Befunde. Alte Aktionen, Modelle und Freigaben bleiben gesperrt. Das ist eine zusätzliche begrenzte Backendänderung nach dem ursprünglichen Integrationslauf; [Nachweis und offene vollständige Arbeitswiederherstellung](../2026-11-04-workflow-recovery/README.md).

Die persönliche native Prüfung, echte Mistral-Stichprobe nach Schlüssel/Umfang/Budget, Lastmessung und Alltagsabnahme bleiben erforderlich. Die breitere Produktziellinie P0–P6 ist durch diese Integration nicht erreicht.

## Anschlussprüfung Mistral-Aufgaben

Der bisherige Quellenpfad führte noch keine Aufgaben-/Fristprüfung aus. Neue,
ausdrücklich freigegebene Mistral-Pakete können dafür jetzt den vorhandenen
TaskDetector samt Gegenprüfung nutzen. Alte Jobs behalten ihren Umfang;
Ablehnungen bleiben bestehen und Bulk verlangt einen passenden Pilot.
[Änderung, Tests und Grenzen](../2026-11-04-mistral-task-package/README.md).
Zusätzlich bestand ein [modellfreier 50.000-Quellen-Ablagetest](../2026-11-04-memory-area-scale/README.md).
Beides ersetzt weder echte Mistral-Qualität noch native Bedienabnahme.

## Anschlussprüfung Sicherungsstände

Die historische Ansicht hat einen authentifizierten, ausschließlich lesenden
Prüfweg mit aufklappbaren Befunden. Bekannte Vergleichsstände werden getrennt
untersucht; eine alte Quellen-/Skillfreigabe wird dabei nicht reaktiviert.
Backend- und UI-Review fanden konkrete Randfehler, die mit Gegenproben korrigiert
wurden. [Nachweis, 82 betroffene Tests und ausdrücklich offene Arbeitswiederherstellung](../2026-11-04-recovery-preflight/README.md).
Die aktuelle Oberfläche wurde noch nicht im nativen Testfenster geprüft.

## Anschlussprüfung Arbeitskopie

Der gewählte historische Datenstand kann jetzt separat mit der normalen App
weiterbearbeitet werden. Die Vorbereitung bindet sich an den Prüfbericht;
Originale bleiben unverändert. Alte ausführende Rechte und Schlüssel werden
nicht übernommen. Ein gefüllter Testbestand bestand Lesen, neue Aufgabe,
Store-Neuverdrahtung und App-Neustart, während externe Arbeit als Testfalle
gesperrt war. 37 direkte Tests bestanden; unabhängiges Review ohne offene
wesentliche Befunde. [Nachweis und noch offene native Produktbedienung](../2026-11-04-recovery-working-copy/README.md).
Der technische CLI-Einstieg ist keine Abnahme des nativen Wiederherstellungswegs
und kein persönliches Update.
