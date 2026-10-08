# Ausgewählte Quellen nach einer Satzverwerfung erhalten

## Reproduzierter Fehler

Die [getrennte native Baseline](../2026-10-08-verifier-deadline/README.md) fand zwei ausgewählte Quellen, zeigte nach einer falschen Satzverwerfung aber nur eine davon: KontrolleQ8 verlor die M-731-Versandbedingung, KontrolleQ11 den neuen Termin beim Vergleich mit der ersten Planung. Die verbliebene Aussage war korrekt; die Antwort auf die mehrteilige Frage war unvollständig. Im zweiten Fall stand damit der ersetzte Termin allein im Vordergrund.

## Begrenzte Korrektur

Nach mindestens einer Satzverwerfung wird die Quellenabdeckung über Belegnummern→Episoden-IDs geprüft. Fehlt eine der vorgelegten Quellen vollständig in den verbleibenden Sätzen, gilt der bestehende Originalzitatpfad. Er zeigt die ausgewählten, aktuell erneut gelesenen Originalstellen und ihre Links. Kein neuer Modellaufruf, keine neue Datenbank, keine Veränderung an Faktenprüfung, Suchschwellen, Prompts oder Einordnung.

Der Vergleich läuft **nach** beiden Prüftoren, programmgenerierten Wandel-Sätzen und tatsächlicher Ausgabelängenbegrenzung. Ein geprüfter Korrektursatz, der die alte und neue Quelle nennt, deckt beide ab und bleibt Prosa. Mehrere Belege derselben Episode zählen als eine Quelle. Gespeicherte Satzantworten werden beim Wiederlesen genauso geprüft; alte Teilantworten fallen ebenfalls auf Originale zurück. Entzogene oder veränderte Quellen führen weiterhin zum bestehenden Nicht-verfügbar-Zustand, nicht zu einer erneuten Anzeige des alten Textes.

**Bewusste Grenzen:** Dies prüft Quellenabdeckung, nicht semantische Vollständigkeit. Wenn ein Bedingungssatz verworfen wird, ein anderer Satz derselben Episode aber bleibt, greift der Schutz nicht. KontrolleQ5 bleibt offen. Ebenso keine Erkennung einer unvollständigen Antwort ohne verworfenen Satz. Zusätzlicher Aktenkontext kann konservativ einen Zitat-Rückfall auslösen. Eine schlechte Quellenauswahl wird durch Zitate nicht nachträglich richtig.

## Prüfung

Drei neue Fälle reproduzieren den Fehler vor der Änderung, vier Kontrollfälle bestehen bereits: lexikalische Verwerfung, Modellverwerfung, alte gespeicherte Teilantwort, Quellenentzug, vollständiger Vergleich, verworfener Zusatzsatz bei erhaltener Quellenabdeckung und unveränderte Politik ohne Verwerfung. Nachher73 enge und260 erweiterte Prüfungen bestanden, einschließlich bestehender Wandel-/Fristen-, Konflikt-, Quellenzeit-, Absatz-, Einspeisungs- und Gesprächsprüfungen. Der gespeicherte Fall wurde anschließend auf echten JSON-Roundtrip umgestellt; alle7 neuen Fälle erneut bestanden. Eine bestehende Starlette/httpx-Warnung. Kein unnötiger Voll-Backend- oder UI-Wiederholungslauf.

Ein separater günstiger Agent prüfte Code und Tests unabhängig, fand keine konkrete Regression und empfahl den umgesetzten JSON-Roundtrip. Er führte die Tests nicht selbst erneut aus. Die genannten Grenzen sind ausdrücklich Bestandteil seines Reviews.

`recorded-output-replay.json` spielt die **unveränderten aufgezeichneten Modellantworten** aus KontrolleQ8/Q11 mit eingefrorenen Originalquellen offline durch die vorherige und neue Satzprüfung: vorher jeweils ein verbliebener Satz, nachher jeweils Zitatmodus bei derselben verworfenen Aussage. Keine neue Inferenz und kein neuer Abruf-/Modell-Benchmark; dies isoliert den Kontrollfluss des Guards. Die Belegzuordnung in diesen zwei Fällen wird anhand der unter den ausgewählten Originalen eindeutigen exakten Textlängen zusätzlich geprüft. Hash des nativen Rohberichts ist festgehalten. Die modellinternen `ja`-Antworten werden nur wiedergegeben, nicht als Wahrheitsbeweis bewertet.

Das fertige Paket prüft mit anderen künstlichen Kennungen neue und JSON-wiederhergestellte Mehrquellenantworten, vollständigen Vergleich und anschließenden Quellenentzug. Fixed-Output-Testanbieter, keine Inferenz, Container ohne externes Netz. Der erste Smoke-Entwurf hatte keine lexikalischen Kandidaten zum abstrakten Wort „Freigabebedingung“; erst die explizite Frage nach Material/Freigabe/Prüfprotokoll/Unterschrift erreicht den zu prüfenden Antwortweg. Dies wird nicht als verbesserter Abruf ausgegeben.

## Lieferung

Produktcode `cde3129b1e340c1536b0cc2ee8614354af7c8aa6`, lokal **1.0.6-local.cde3129**. Image `sha256:d4f9fe7824e3ec76fe757fa59efd99bc29b7d28bb16a3231c0e47f8d1f75b4b8` enthält byteweise geprüfte264Paket- und112unveränderte UI-Dateien. Der netzlose Paket-Smoke besteht; kein öffentlicher Registry-Upload oder Release.

Kalte Sicherung `Kingfisher-Rueckweg/2026-10-08-vor-cde3129`:344Original-IDs/Digests und17SQLite-Dateien erhalten/geprüft. Konten, Kalender, Anbieter, Modellrollen, Zeitpläne und ausdrückliche Hintergrundpause erhalten; natives Programm unverändert, ad-hoc Signatur geprüft, Backend gesund. Mailstatus bleibt `pausiert`; produktives Ollama aus und Bedeutungssuche deshalb `unavailable`.

Native Fenster-/Alltags-/Akkubedienung weiterhin offen, letzter Zugang wegen gesperrtem Mac blockiert. Keine CI-Wiederholung, kein Abonnement, kein Check-in. Noch kein insgesamt abgenommener CoS.

Nächste Qualitätsarbeit: Bedingungen innerhalb derselben Quelle und zu strenge globale Verneinungsprüfung gezielt reproduzieren. Dabei Faktenprüfung nicht pauschal lockern; belegte Regeln müssen zusammen mit fehlender Freigabe sichtbar bleiben. Abruf-/Auswahlverluste und echte Einordnungs-/Quellenabdeckung bleiben separate Kernabnahmen.
