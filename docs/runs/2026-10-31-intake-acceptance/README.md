# Aufnahme und Abruf: vollständige lokale Probe und Reparaturen

## Verbindlicher Stand

Basis ist die veröffentlichte und auf dem Mac installierte 1.0.35 (`68767ac`).
Die folgenden Reparaturen sind zunächst lokal auf `fix/intake-acceptance-20261031`;
Auslieferung, erneuter Modelllauf und echte Quellenprobe sind noch offen.
Der persönliche Großimport bleibt pausiert. Keine Cloudaufrufe oder neuen Modelle.

## Erster vollständiger Modelllauf

24 künstliche Mails und 16 unabhängige Fragen, vorhandenes Qwen9B und BGE-M3.
Unveränderter Katalog SHA-256:
`ba46791a16c41f45dad04540918cd7f384ae73d85108fe10849050ebe250eeda`.
Native 8K-Diagnose, keine Abnahme des normalen 32K-Produkttransports.
284,5 Sekunden, Speicherreserve mindestens 31 %, Speicherdruck höchstens Stufe 2;
beide Modelle danach automatisch entladen. Native Navigation unter Last geprüft.
Alle Originale erhalten, keine Aufgabe ohne Bestätigung angelegt.

[Inhaltliche Einzelprüfung](baseline-review.md): zehn akzeptable Antworten, eine
falsche Zuständigkeit und fünf technisch nicht vollständig geprüfte Fragen.
Keine Genauigkeitsschätzung für echte Postfächer; insbesondere richtige Uhrzeit
und Quellen-ID beweisen keine richtige verantwortliche Person.

## Gezielte Reparaturen

- **Rechnung:** Ein unbelegter Zusatz im Modelltitel verwirft nicht mehr die
  klare belegte Handlung. Statt der Nummer 184 wird nur der vollständige exakte
  Originalbeleg als Vorschlagstitel erhalten. Beleg- und Zuständigkeitsprüfung
  bleiben bestehen. `requests-v4` prüft alte leere Auswertungen erneut, weiterhin
  innerhalb vorhandener Pause und Budgets.
- **Offene Uhrzeit:** Eine erkannte klare direkte Bitte mit zwei ausdrücklich
  offenen Uhrzeitoptionen bleibt manuell prüfbar; keine Uhrzeit wird gewählt,
  kein positiver Autoanlage-Marker vergeben. Gewöhnliche Anrede/Gruß sind möglich;
  Absage, andere Zuständigkeit, Bedingungen und zitierter Verlauf werden nicht
  abgeschnitten. Die Erkennungsregel ist begrenzt, keine allgemeine Grammatik.
- **Zuständigkeit in Antworten:** Aus einem Namen im Mailkopf wird keine Handlung
  erschlossen. Die Ausgabeprüfung bindet bekannte Beteiligte und typisierte Personenaliase
  an vollständige sichtbare Originalsätze. Überschriften und großgeschriebene
  Projektnamen gelten dabei nicht als Personen. Sprecherabhängiges „Ich/Du/Wir“ braucht auch bei
  wortgleicher Übernahme den gerahmten Originalbericht. Das gilt ebenfalls beim
  Rücklesen alter Antworten. Neue Antworten halten typisierte Personenaliase als reine Einschränkung fest.
  Bei alten untypisierten Namenslisten können vorsichtshalber auch Projektangaben
  auf Originalberichte zurückfallen. Neue neutrale Projektangaben bleiben umformulierbar. Kein vollständiger semantischer Wahrheitsprüfer.
- **Auswahlgröße:** Kurzer identischer Quelltext steht nur einmal in der
  Modellanfrage; `context` verweist dann auf `text`. Unterschiedliche Nachsätze,
  Negationen, Metadaten und sämtliche Quellen bleiben erhalten. Die drei früher
  zu großen Nachrichten passen damit unter die unveränderte Grenze.
- **Diagnoseadapter:** Überträgt vollständige Werkzeugdefinitionen; kein vom
  Modell verlangter ToolCall gelangt zur Ausführung. Eingabebyte einschließlich
  Schema/Werkzeugen, Fehlerursprung und betroffene Frage werden protokolliert.
  Technischer Rückfall wird nicht als fehlendes Wissen gewertet.

## Offlineprüfungen und unabhängige Gegenprüfung

Neue Fehlerfälle wurden vor der jeweiligen Korrektur fehlschlagend geprüft.
954 betroffene Gedächtnis-/Aufgabentests bestanden; ergänzende Satz-/Scriptgruppe
119 bestanden. Diese Gruppen überschneiden sich und sind keine addierte Gesamtzahl.
Die vollständige Backendprüfung dieses Kernstands bestand 8.491 Tests und
26 Subtests; ein Plattformfall wurde ausgelassen. Zwei bekannte Warnungen.
Die neue Personenbindung bestand zusätzlich 309 gezielte Gegenproben.

Ein unabhängiges Review fand bei der ersten Reparatur eine zu enge
Bitte-/Zusagen-Formulierung und verlorene Kandidaten bei normalem Mailrahmen.
Beide wurden mit Gegenproben korrigiert. Die eingegrenzte Nachprüfung bestätigt
beide Korrekturen und nennt keine neue blockierende Regression.
Der automatisierte q05-Wort-/Quellenvertrag übersieht weiterhin eine mögliche
Zuständigkeitsvertauschung; die vollständige semantische Einzelprüfung bleibt nötig.

## Verbleibende Abnahmen

- Erneuter vollständiger unveränderter Katalog mit anschließender Einzelprüfung.
- Personenprojektion tatsächlich über Graph/Verzeichnis prüfen: Angebots-,
  Buchungs- und Redaktionsadressen dürfen keine ungeprüften Menschen vortäuschen.
- Die Fixture belegt keine vertrauenswürdige Newsletterfreigabe. Selbstbehauptung
  im Quelltext ist keine Nutzerauswahl; diese gesondert prüfen.
- Historisches Angebot m14 vs. Erledigung m15 bleibt als Sollwertkonflikt sichtbar.
- Neu entstandene Gesprächsquellen und noch ausstehende Originalindizierung
  getrennt ausweisen; keine unvollständige Suchabdeckung vollständig nennen.
- Vollständige Suite, geprüfter GitHub-Stand, Veröffentlichung und Mac-Update.
- Gemischte echte Mailprobe vor Großimport, normaler Produkttransport und
  abschließende Alltagswoche des Nutzers. Keine globale Fehlerfreiheit behauptet.

## Zweiter vollständiger Modelllauf (lokaler Prüfkandidat)

Unveränderter Katalog, 88 Modellaufrufe; kompletter Ablauf beendet, aber keine
Qualitätsfreigabe. Die drei ursprünglichen Fehler sind inhaltlich korrigiert:
q05 erhält den richtigen Originalbericht, m19 die belegte Zahlung und m24 die
Handlung ohne erfundene Uhrzeit. Alle 24 Aufgabenentscheidungen wurden semantisch
geprüft, einschließlich des offenen Sollwertkonflikts m14. Personen-/Serviceprüfung
besteht sowohl aktuelle Produktprojektion als auch getrennte alte Diagnose.

13 Endantworten sind inhaltlich akzeptabel, eine ist falsch und zwei sind im
Diagnosewerkzeugpfad unvollständig. q03 macht aus der Frist zum 4. November
unzulässig „gilt ab dem 4. November“; diese neue beobachtete Bedeutungsänderung
wird vor Freigabe repariert. m08 ist als Sprecherzusage statt als Bericht über
Anna etikettiert; die Antwort nennt weiterhin Anna und erzeugt keine Lea-Aufgabe.
Die Newsletterfreigabe m20 ist nicht nachgewiesen; die Originalquelle bleibt
erhalten, der verlangte lesende Abruf ist noch nicht vollständig geprüft.

419 Ressourcenmessungen: mindestens 26 Prozent Reserve, maximal Speicherdruck2;
parallel liefen zwei Backend-Testprozesse. Native Navigation Heute → Gedächtnis
→ Heute erfolgreich (Klick+AX-Rücklesen etwa0,9s bzw.5,4s). Kein Benchmark der
gesamten Mac-Arbeit und keine32K-Produktabnahme. Nach dem Lauf bleiben zwei neu
entstandene Gesprächsquellen unklassifiziert; keine vollständige globale
Suchabdeckung behauptet. Persönlicher Großimport unverändert pausiert.

Die Quellstände der lokalen Probe sind per Datei-Hash gesichert, inklusive
separater Kennzeichnung des damals uncommitteten Testadapters. Kein Nachweis
einer veröffentlichten Fassung aus einem Patchlauf abgeleitet.
