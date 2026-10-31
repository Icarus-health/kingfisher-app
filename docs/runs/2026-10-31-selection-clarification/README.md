# Rückfragen erhalten, erfolglose Satzantworten knapp anzeigen

Ausgangspunkt: Eine lokale paginierte Quellenauswahl meldete auf Seite A passende
Berichte, auf Seite B eine ungeklärte Person und im Gesamtvergleich wieder nur
Berichte. Der bestehende Guard verhinderte korrekt eine faktische Teilantwort;
die Oberfläche bat anschließend jedoch lediglich um erneutes Fragen.

Die Auswahl behält jetzt genau einen gemeinsamen Unklarheitstyp aus allen
Seiten **und** dem gültigen Gesamtvergleich samt vollständiger geordneter
Auswahlunion. Mehrere verschiedene Unklarheitstypen, technische Teilfehler,
fehlendes Budget oder eine veränderte Grundlage bleiben ein Abbruch. Es gibt
keine zusätzliche Modellrunde. Eine interne Marke erhält diesen Zustand bis
nach sämtlichen bestehenden Personen-, Projekt-, Zeit-, Quellen- und
Eigenzusagenfiltern: Verändern sie den Typ oder Quellenbestand, entsteht keine
positive Teilantwort. Insbesondere wird eine unzutreffende Zeitrückfrage nicht
in einen Bericht umgewandelt und kein unbekanntes Quelldatum erfunden.

Für automatische Berichte ohne bestätigte Claim-Basis ändert sich bewusst der
Präsentationsvertrag nach einem erfolglosen Satzversuch: Ein gültig versionierter
Status `nichts` oder `zitate` zeigt einen kurzen Hinweis auf die noch nicht
verlässlich beantwortbare Frage, Quellenbeschriftungen und sämtliche frischen
Originalquellenlinks. Die vollständigen Originale bleiben unverändert über die
bestehende Quellenansicht zugänglich. Es gibt keine globale Behauptung, es gebe
keine Information, keine gekürzten Zitate und keine verbleibende Teilprosa.
Erfolgreiche Sätze, bestätigte Angaben, unversuchte Originaldarstellung und
alte/ungültige Satzversionen behalten ihre bisherigen Pfade. Beim gespeicherten
Lesen gelten dieselben Frische- und Entzugsprüfungen ohne Modellaufruf.

## Synthetischer Nachweis

`test_answer_clarification_projection.py` benutzt echte Stores, den echten
Budget-Builder, Auswahl, Rendering und HTTP-Endpunkte mit vorgegebenen Antworten
an der Modellgrenze. Sechs Quellen erzeugen zwei Seiten und einen Gesamtvergleich.
Die erhaltene Personenrückfrage enthält beide Originalquellen, bleibt beim
Gesprächs-GET erhalten, lässt sich durch den bestehenden Auswahlklick ohne neue
Modellrunde eingrenzen und wird nach Quellenentzug gesperrt. Ein anderer finaler
Unklarheitstyp bleibt ein Fehler. Bekannte Quellenzeit und veränderte
nachgelagerte Quellenmengen werden ebenfalls nicht als Bericht freigegeben.

Die Langtextprobe sendet eine echte HTTP-Frage, liest das gespeicherte Gespräch
und öffnet den Quellenlink: 5.664 Zeichen Original werden nicht mehr in die
Antwort kopiert, bleiben aber vollständig über den Original-Endpunkt abrufbar.
Sie prüft `nichts` und `zitate`, unveränderte Wissensrevision und Quellenentzug.
Bestätigte Claims und unversuchte/alte Satzversionen haben eigene Kontrollen.

Vor dem Patch: 48 gezielte Ausgangstests bestanden. Die neuen Erwartungen waren
mit sieben tatsächlichen Fehlern rot (Rückfrage sowie beide langen Ausgaben).
Eine spätere Sabotage nur der neuen nachgelagerten Unsicherheitsprüfung machte
vier gezielte Kontrollen rot; die unveränderte Implementierung wurde sofort
wiederhergestellt. Die alten Inline-Erwartungen prüfen nun dieselben vollständigen
Originale hinter allen Quellenlinks; Rejectiongründe, Rollen-/Negations-/
Datumsprüfungen, Modellaufrufe und Entzugskontrollen bleiben erhalten. Reine
Auswahl-/Original-Flowfixtures versuchen ausdrücklich keine Satzformulierung;
der neue HTTP-Test prüft die erfolglose Satzformulierung separat.

Keine privaten Daten, Modell-, Anbieter- oder Netzaufrufe; kein neues Schema,
Endpoint, Modellrouting oder automatische Bestätigung. Keine Vollsuite und
keine Live-Modellqualität aus diesen Offlineprüfungen abgeleitet.

Abschließender gezielter Lauf: **364 bestanden in 43,74 Sekunden**. Er umfasst
die neue HTTP-/Projektionsgruppe sowie Auswahlseiten, Satzantwort, zweites Tor,
Quellengrenzen, negative Antworten, Auswahlentscheidungen, Identität, Projekte,
Eigenzusagen, Auswahlklicks, Original-Flow, Teilantwortverlust, Originalsatzwahl,
Antwortstatus, Zeitbereich und Quellenreihenfolge. Ein bestehender
Starlette/httpx-Deprecation-Hinweis blieb bestehen.

## Enge Nachkorrektur aus unabhängigem Review

Der erste Patch markierte nur die Union nach einem Gesamtvergleich. Bei genau
einer positiven, aber unklaren Seite und einer zweiten irrelevanten Seite fehlte
die Marke. Ein echter Sechs-Quellen-Gegenfall mit bekannten Quelldaten zeigte,
dass der Zeithelfer daraus einen Bericht machte. Jetzt trägt auch dieser
paginiert ermittelte einzelne Unklarheitsbescheid die interne Marke bis nach
allen WMA-Helfern. Ein klarer einzelner Bericht bleibt unverändert; keine
zusätzliche Modellrunde entsteht.

Der Gegenfall und vier Unklarheitstypen waren vor dem Fix **5 Fehler**; danach
bestanden **84 gezielte Tests in 17,96 Sekunden** (Projektion, Auswahlseiten,
Auswahlentscheidungen, Auswahlklicks und Quellengrenzen). Im echten Gegenfall
bleibt es bei zwei Auswahlaufrufen und einem sicheren Abbruch ohne Links oder
erfundene Datumsfrage. Alle vollständigen Quellenauswahlen sind weiterhin gebunden.
