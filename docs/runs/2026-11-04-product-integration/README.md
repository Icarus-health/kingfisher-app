# Gemeinsame Prüfung: Lernen, Mistral-Vorbereitung, Mailaufgabe und Kalender

Zusammengeführter Produktstand `d8581e8aed1febafa1297ade9ba87d4804645a88`, danach ausschließlich CI-Trennung und Dokumentation. Enthält die separat geprüften Pakete PR120, PR121, PR122 einschließlich `caee3bc` und PR123. Keine Konfliktauflösung oder neue Produktlogik beim lokalen Zusammenführen. Basis `1b5a262`.

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

## Kleine offene Bedienbefunde

Die Aufgabenansicht bewahrt die genaue Frist im Speicher, zeigt in der kompakten und geöffneten Ansicht zunächst aber nur den Tag. Die Uhrzeit ist über den Beleg auffindbar; ihre direkte Darstellung sollte verständlicher werden. Der optionale Mistral-Bereich zählt aktuell passende prüfbare Korrekturen, bezeichnet die Zahl jedoch pauschal als „markierte Arbeitskorrekturen“. Bereits zu einem lokalen Vorschlag gebündelte Korrekturen können daher als Null erscheinen. Beide Beobachtungen bleiben gezielte Darstellungsarbeit; sie wurden hier nicht still mit geändert.

Die persönliche native Prüfung, echte Mistral-Stichprobe nach Schlüssel/Umfang/Budget, Lastmessung und Alltagsabnahme bleiben erforderlich. Die breitere Produktziellinie P0–P6 ist durch diese Integration nicht erreicht.
