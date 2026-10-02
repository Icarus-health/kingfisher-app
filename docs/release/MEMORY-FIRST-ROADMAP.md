# Kingfisher: Roadmap für einen verlässlichen Chief of Staff

Produktpräzisierung vom 23. September 2026: [CoS: automatische Einordnung und gezielte Rückfragen](../architecture/cos-automatische-einordnung-2026-09-23.md). Nächste fachliche Lieferung ist ein automatisch aufgebauter, abrufbarer Arbeitsstand aus einer vollständigen Korrespondenz. Eindeutige Routinefälle benötigen keine Einzelbestätigung; notwendige und unnötige Rückfragen werden getrennt gemessen. PR #62/#63 sind übernommen und die Mac-App ist auf `f749d9e`; die folgenden Datumsangaben bleiben historische Nachweise.

Aktueller Abgleich vom 21. September 2026: [CoS-Gedächtnisaudit mit reproduzierten Lücken, Korrekturen und nächster Umsetzungsfolge](../evaluations/memory-quality/audits/2026-09-21/README.md). Die Gedächtnis-Produktfreigabe ist weiterhin offen. Der neue Nachweis trennt Aufnahme, Identität, Zeit, Abruf und Antwortqualität; er ersetzt veraltete Integrationsangaben des folgenden Zwischenstands.

Historischer Zwischenstand: 19. September 2026. Umsetzung im Auftrag des Nutzers.
**Produktfreigabe: noch nicht erreicht.** Der Diagnose-Runner ist mit PR #42 integriert;
die erste Evidenzkorrektur ist nach unabhängiger Prüfung und grüner CI integriert
(PR #43, `0f19ede`). Die Profil-Verlaufskorrektur ist ebenfalls geprüft und integriert
(PR #44, `b463d48`). Indizierter Abruf und Identitätsreferenzen sind mit PR #45
(`e518de9`) und PR #46 (`ca55f2b`) integriert. Die Elternbasis-Prüfung folgte mit
PR #47 (`4a2bc7b`). Die laufende private App
ist damit noch nicht aktualisiert. Nachweise und offene Grenzen werden getrennt geführt.

## 1. Was die bisherigen 80 % bedeuten

16 von 20 Punkten der [bisherigen Funktionsabnahme](ROADMAP-STATUS.md) sind erfüllt.
Dieser Nachweis bleibt bestehen. Er misst nicht die Zuverlässigkeit des Gedächtnisses,
den Anteil der verbleibenden Arbeitsstunden oder den Reifegrad der gesamten Vision.
Eine bestandene Quellenansicht kann neben einer fachlich falschen Modellantwort stehen.

Ab jetzt steht die Gedächtnisfreigabe vor einer weiteren Erhöhung der Funktionsquote.
Wir führen keine neue pauschale Prozentzahl ein: getrennte Nachweise für fachliche
Qualität, Systemgrenzen, Geschwindigkeit und tatsächliche Entlastung sind aussagekräftiger.
Der Vertrag [Memory Core v0.1](../architecture/kingfisher-memory-sicherheitsvertrag-v0.1.md)
und seine [Reviewpräzisierungen](../architecture/memory-core-review-2026-09-12.md)
bleiben gültig. Diese Roadmap konkretisiert Reihenfolge und Nutzung, ersetzt keine
Sicherheitsinvariante und erklärt keine vorhandene Aussage nachträglich für wahr.

Die frühere Schätzung von 13–28 Arbeitstagen bezog sich auf die vier offenen alten
Funktionspunkte. Sie ist keine belastbare Aufwandsschätzung für diese erweiterte
Gedächtnisfreigabe. Nach dem ersten gemessenen Durchlauf wird pro Arbeitspaket neu
aufwandsgeschätzt; insbesondere Modellqualität und historische Ableitungen sind unsicher.

## 2. Die erste wirklich brauchbare Lieferung

Der Nutzer kann morgens Termine, offene Aufgaben und relevante Nachrichten verstehen,
zu einem Vorgang nachfragen, einen Kommunikationsentwurf erhalten und Korrekturen
vornehmen, die in späteren Antworten wirksam bleiben. Quellen und zeitliche Gültigkeit
sind nachvollziehbar. Bei wesentlicher Unsicherheit fragt Kingfisher knapp nach oder
nennt die Lücke. Der Nutzer muss nicht jeden offensichtlichen Treffer einzeln sortieren.

Weder eine perfekte Erinnerung noch Fehlerfreiheit wird versprochen. Ein bekannter
schwerer Fehler im freizugebenden Pfad verhindert dessen Freigabe. Eine begrenzte
Funktion kann dagegen nutzbar sein, während eine andere ausdrücklich nur Vorschläge
liefert. Ein anderes Modell darf diese Grenzen nicht automatisch aufheben.

**Bewusste Prioritätsentscheidung:** freies Browser-/Computer-Use, OfficeCLI,
LibreOffice, zusätzliche soziale Kanäle, mobiles Frontend, LoRA/Fine-Tuning und
selbständige Codeänderungen werden bis zur tragfähigen Gedächtnis-Baseline nachgeordnet.
Das ist keine Erfüllung des alten Punkts 15 und keine Streichung der langfristigen
Vision. Bestehende Funktionen bleiben bestehen. Neue Werkzeuge lösen fehlenden Kontext
oder falsche Interpretation nicht. UI-Fehler, die Prüfung/Korrektur erschweren, werden
sofort behoben; das vollständige visuelle Finish bleibt ein eigenes Arbeitspaket.

## 3. Wo Fehler entstehen – und wie wir sie unterscheiden

| Stufe | Prüffrage | Nachweis vor Modellwechsel |
|---|---|---|
| Aufnahme | Liegt die richtige Version der Nachricht/des Termins überhaupt vor? | Quellkennung, Version, Zeit, Importumfang und Fehlerzustand |
| Interpretation | Wurde aus einem Gedankenexperiment fälschlich eine Überzeugung oder aus einer Bitte eine Zusage? | Erwartete Aussagefelder und Originalbeleg, getrennt von Schema-/Zitatprüfung |
| Speicherung/Aktualisierung | Bleibt eine alte Bewerbung trotz Absage aktiv? | Ereignisfolge, Zustandswechsel, Abhängigkeiten und Neustart |
| Abruf | Erreicht die passende, erlaubte Information die tatsächliche Modellanfrage? | Soll-/Ist-IDs, Quellversionen, Gründe, Lücken und tatsächlich versendeter Kontext |
| Modellantwort | Entsteht trotz korrektem Kontext eine falsche Aussage? | Vergleich mit kontrolliertem Referenzkontext über denselben Provider, gleiche Parameter |
| Darstellung/Aktion | Zeigt die App einen anderen Stand oder führt mehr aus als freigegeben? | API-/Browser-Nachweis und beobachtete Werkzeugaufrufe, nicht nur Modelltext |

Der Referenzkontext ist ausschließlich ein isolierter Diagnoseweg mit synthetischen,
berechtigten Daten. Er umgeht niemals produktive Quellenrechte. Diagnoseruns mit
Referenzkontext gelten nicht als bestandene End-to-End-Abnahme.

Konkreter Anlass: Der erste native Ollama-Vergleich testete sechs Fragen, aber keinen
produktiven Gedächtnisabruf. Der anschließende Agentenversuch brachte mit einer
zusätzlichen Suchheuristik sechs statt vier Quellenblöcke in die Modellanfrage; dabei
übernahm Qwen2.5:14b einen Teil einer fremden Anweisung. Die Heuristik ist deaktiviert.
Das sind Diagnosehinweise aus kleinen synthetischen Versuchen, keine Fehlerraten für
reale Postfächer. [Modellvergleich](../evaluations/model-selection/cos-diagnostic-2026-09-13/README.md),
[abgelehnter Suchversuch](../evaluations/model-selection/calendar-recall-experiment/README.md).

## 4. Verbindliche Arbeitspakete und Reihenfolge

| Paket | Ergebnis / Ende des Pakets | Vorhanden | Noch nachzuweisen |
|---|---|---|---|
| M0 – Messbare Baseline | Reproduzierbarer Agentenablauf mit getrennten Fehlerstufen, versionierten Fällen und Zeitmessung | Einzelne CapturingProvider-Tests, Modellrunner, synthetische Rohresultate | Gemeinsamer Live-Runner und 18 Entwicklungsfälle umgesetzt; 72 synthetische Versuche mit Qwen/Gemma vollständig protokolliert, vorläufige Codex-Bewertung zeigt schwere Antwortfehler ([Nachweis](../evaluations/memory-quality/runs/2026-09-14-qwen25-14b/README.md)). Unabhängige fachliche Abnahme, größere Sammlung und Holdout bleiben offen |
| M1 – Verlässlicher Wissensstand | Identität, Zeit, Korrektur, Widerruf und Vergessen wirken über alle betroffenen Ansichten/Ableitungen | Stabile Entitäten, Claims, Episoden, Abhängigkeitschecks, Historien und begrenzte Quellenausschlüsse | Vier belegte Claim-/Digest-/Verlaufsfehler repariert und geprüft; 1.364 Backendtests vor finalem Egress-Fix, 112 fokussierte danach. Synthetischer Docker-/Ollama-Ablauf vor/nach Ablauf und Neustart dokumentiert. SelfModel-Verlaufskorrektur geprüft und mit PR #44 integriert (1.398 Backendtests); [Docker-/Ollama-Nachweis](../evaluations/memory-quality/runtime/profile-20260914/README.md) mit Widerruf, Ablauf und zwei Neustarts bestanden; Elternbasis-Korrektur implementiert und unabhängig geprüft (`504c845`, 1.489 Backendtests, Frontend-Build bestanden), mit PR #47 integriert; [echter Docker-/Ollama-/UI-Ablauf](../evaluations/memory-quality/runtime/basis-20260914/README.md) bestätigt den Entzug, zeigt aber eine sprachliche Verwechslung von Beschluss und Ausführung. M1d-Episode-Belege implementiert, unabhängig geprüft und mit 1.540 Backendtests sowie Browser-/Docker-Neustart bestätigt ([Nachweis](../evaluations/memory-quality/runtime/episode-support-20260919/README.md)); Integration noch offen. Vollständiger Lösch-/Restore-Vertrag offen |
| M2 – Passender Kontext | Situativer und mehrstufiger Abruf liefert relevante erlaubte Details oder eine ehrliche Lücke | Begrenzter lexikalischer Abruf, historische Seiten, geschützte direkte Kalenderantworten | Verlust älterer relevanter Claims nach 5.001 neueren irrelevanten Zeilen reproduziert und durch begrenzten FTS-Abruf repariert (`ea8bd58`, 1.426 Backendtests, unabhängige Prüfung bestanden); mit PR #45 integriert. Suchgrenzen erreichen den tatsächlichen Modellkontext. Kanonische Identitätsreferenzen mit PR #46 integriert; kleine [Modellprobe](../evaluations/memory-quality/runs/2026-09-14-identity-qwen25-14b/README.md) zeigt weiterhin Antwortfehler. M2c ergänzt vollständige Aussagefelder und getrennte Quellenzeiten im tatsächlichen Modellkontext sowie genau gebundene Gesprächsverläufe; 1.589 Backendtests, 168 Diagnosetests, 224 Python-3.10-Kontrollen und getrennte native/Docker-Laufzeitprüfungen sind dokumentiert ([Nachweis](../evaluations/memory-quality/runtime/knowledge-time-20260919/README.md)). Integration noch offen. Mehrdeutigkeit mit heutiger Situation, Paraphrasen, Cache-Entzug und verknüpfte Projekte/Personen bleiben weitere Abnahmepunkte |
| M3 – Qualifizierte Interpretation und Geschwindigkeit | Je Aufgabenklasse ein messbar geeigneter Modell-/Regelpfad mit sicherem Rückfall | Modelladapter/Routing, Aufgabenvorschläge, kleine lokale Modellproben | Gleicher Agenten-/Referenzpfad für vorhandene Qwen2.5:14b und Gemma3:12b gemessen ([Vergleich](../evaluations/memory-quality/runs/2026-09-14-gemma3-12b/README.md)); beide nicht qualifiziert. Antwortvertrag, unabhängige Fälle, Feldbewertung und P95 unter Last offen |
| M4 – Lernendes Arbeitsprofil | Allgemeine und situative Vorlieben entwickeln sich nachvollziehbar und korrigierbar | SelfModel/Preferences; globaler und kontaktbezogener Mailstil; Gewohnheitsvorschläge | Gemeinsame Bereichs-/Zeit-/Konfliktregeln, Auswahl vor jeder Antwort, Rücknahme über Ableitungen, verständliche Profilansicht |
| M5 – Alltag und Weitergabe | Nachweisbar hilfreicher Ablauf auf dem Mac und leerer Start für andere Nutzer | Docker, Backups, Updateweg, lokale Akten-UI | Mehrtägiger Alltagstest, finaler UI-Vergleich, echte Docker-Desktop-Neuinstallation, getrennte Nutzerbestände und korrigierter Restore |

M0 zuerst. Danach bestimmt der gemessene erste Fehler den nächsten kleinen Fix in
M1/M2; die Baseline wird nicht durch vorgezogene Promptoptimierung verfälscht.
Zeitmessung beginnt bereits in M0. M3 folgt auf hinreichend korrekten Kontext; M4 nutzt
M1s Herkunft und Revisionen. M5 setzt bestandene Nutzungsfälle aus M1–M4 voraus.
Keine neue Graphdatenbank, kein zweiter Personenbestand, keine komplette Neuentwicklung
aller Stores ohne nachgewiesene Lücke. Bestehende Module werden gezielt ergänzt.

## 5. Was „minimal fehlerhaft“ messbar bedeutet

### Harte Grenzen

In der freizugebenden Testsammlung keine beobachtete Vermischung getrennter Personen,
keine Aufwertung fremder Anweisungen zu Nutzerregeln/Freigaben, kein unerlaubter
Datenabfluss oder Werkzeugaufruf. Korrigierter/entzogener Inhalt darf nicht über
Zusammenfassung, Cache, Gespräch oder Restore als weiterhin gültig wiederkehren.
Ein kritischer Befund blockiert die betroffene Fähigkeit unabhängig vom Durchschnitt.
Null beobachtete Fehler sind kein Beweis für eine Fehlerwahrscheinlichkeit von null.

### Fachliche Messungen

- Abruf: relevante erlaubte Belege gefunden, unnötige Belege mitgeliefert, veraltete
  oder nicht erlaubte Belege mitgeliefert; jeweils getrennte Zähler/Nenner.
- Antworten: fachlich korrekte Pflichtaussagen, unbelegte Zusätze, passende Quellen,
  richtige Zeit, entscheidende Auslassungen, hilfreiche vs. unnötige Rückfragen.
- Interpretation: Handelnder, Gegenpartei, Handlung, Bedingung, Frist und Zustand
  separat. Ein korrekt zitiertes „Termin mitteilen“ ist nicht „Termin bestätigen“.
- Bei eindeutigem Kontext antworten; bei entscheidender Mehrdeutigkeit eine konkrete
  Auswahlfrage. Ständiges Verweigern/Nachfragen besteht die Qualitätsabnahme nicht.
- 98 % Präzision / 95 % Erkennung aus dem Vertrag bleiben vorläufige Ziele für später
  automatisch nutzbare Verpflichtungsinterpretationen. Sie sind weder gemessen noch
  automatisch auf alle Klassen übertragbar. Erst Anfrage, Gesprächsgegenstand und
  eindeutig datiertes Ereignis qualifizieren; Verpflichtungen separat.
- Jede Kennzahl mit Fallzahl, Fehlerliste und Unsicherheit. 30 Holdout-Fälle erlauben
  insbesondere keine belastbare Behauptung seltener 1–2-%-Fehler. Bei unzureichender
  Evidenz bleibt die Klasse im Schatten-/Vorschlagsmodus, auch bei hoher Punktquote.

### Prüfbestand

Vertrag übernehmen: 300 Quellobjekte in zusammenhängenden synthetischen Szenarien,
90 fachliche Fälle (60 Entwicklung, 30 gesperrter Holdout). Ganze Threads/Szenarien
bleiben in einem Split; Paraphrasen desselben Falls sind keine unabhängigen Belege.
Der Holdout wird vor Optimierung getrennt eingefroren; heute werden keine angeblich
ungesehenen Holdout-Inhalte vom optimierenden Agenten erzeugt oder ausgewertet.
Ein später eingesehener Holdout wird als Entwicklungsbestand markiert und ersetzt.

Geplante 90 fachliche Fälle: je zehn zu Identitäten, Zeit/Gültigkeit, situativem Abruf,
Korrekturen, Sprechhandlungen und Nutzerprofil; je acht zu Quellenrechten und
Vorgangsverlauf; je sieben zu Wachstum/Abdeckung und aktueller Außenwelt. Zusätzlich
mindestens 40 adversarielle Abläufe, jeweils mit legitimem Gegenfall: Quellenangriff,
Profilvergiftung, Querverweise, Mehr-Runden, Neustart, Rechtewechsel, Löschung/Restore,
Werkzeugfreigaben (je fünf). Das ist ein Erstellungsplan, kein fertiger Testbestand.

Semantische Ergebnisse bleiben zunächst durch Menschen anhand vorher festgelegter
Rubriken bewertet. Ein Modellrichter darf unterstützen, aber weder sein eigenes
Ergebnis noch die Freigabe allein bestimmen. Jede Wiederholung und jeder Fehlschlag
bleibt sichtbar; kein Auswählen des besten Versuchs.

## 6. Geschwindigkeit auf dem vorgesehenen Mac

Zielhardware aus dem Vertrag: M2 Max, 32 GB; vor Messung tatsächlich erfassen.
Vorläufige Ziele: strukturierte lokale Abfragen P95 < 1 s, kurze warme Antworten
bis 100 Wörter P95 < 10 s. Gemeint ist Anfrage bis vollständige nutzbare Antwort,
nicht nur das erste Token. Qualität darf nicht durch Kürzen wichtiger Belege sinken.

Warm/Kalt separat: Modellladezeit, Warteschlange, Abruf, Provideraufruf und Gesamtzeit.
Timeout, leere oder abgeschnittene Antworten zählen als Fehlschlag und werden nicht
zur Verbesserung der Zeitstatistik entfernt. Kaltstart, Recherche und längere Antworten
separat berichten; noch keine verbindliche Zeitzusage dafür. Mindestens 100 warme
Anfragen je gemessener Aufgabenklasse/Lastbedingung, Verteilung und P95-Methode angeben;
Wiederholungen zählen für Latenz, nicht als neue unabhängige Qualitätsfälle.

Interaktive Antworten erhalten Vorrang vor Verdichtung/Importanalyse; keine ungebremsten
parallelen Modellaufrufe auf dem 32-GB-Mac. Beobachten: RAM/Speicherdruck, Tokenumfang,
Modellwechsel, Rückstau, Abbruch und Fortschritt. Lastfälle mit Import/Verdichtung
zusätzlich zum Leerlauf. Wachstum mit 10.000/50.000/100.000 unterschiedlichen
synthetischen Ereignissen wie im Vertrag; kein Leistungsnachweis durch Duplikate.

Erst messen, dann entscheiden: Index/Cache/Abfragebudget bei Abrufproblemen, Queue bei
Warteproblemen, kürzere passende Kontextpakete bei Überlast, anderes Modell bei
Interpretationsfehlern trotz korrekter Daten. Cloud bleibt optional und zweckgebunden;
kein stiller Versand als Ausweg aus einem lokalen Qualitätsproblem. Keine neuen
Downloads oder Trainingsläufe im heutigen Planungspaket.

## 7. Nutzerprofil: vorhandenes Gedächtnis weiterentwickeln

`mail_style.py` speichert bereits bestätigte globale/kontaktbezogene Regeln im
SelfModelStore und Beispiele als Episoden. Kontaktbereich ist derzeit Konto plus
Antwortadresse; dieser Schlüssel darf nicht allein durch Namensähnlichkeit ersetzt
werden. `learning_service.py` erzeugt belegte Gewohnheitsvorschläge, keine freie
Persönlichkeitsdiagnose. Das ist Teilfundament, kein vollständig lernendes Arbeitsprofil.

Ziel: einzelne revidierbare Präferenzen im bestehenden Kern mit Bereich, Herkunft,
Bestätigungsart und Gültigkeit. Profilansichten bleiben Projektionen. Vorgeschlagene
Darstellung einer Präferenz: Schlüssel (z.B. Antworttiefe), Wert, Bereich
(global/Aufgabenklasse/expliziter Kontakt/Sitzung), Beleg-IDs, vorgeschlagen/bestätigt/
widerrufen/ersetzt, observed_at, valid_from/valid_until und supersedes. Die genaue
Speicherabbildung wird mit den vorhandenen Assertion-/Claim-Feldern abgeglichen,
nicht als parallele Profildatenbank eingeführt. Modell-Confidence allein ist keine
Berechtigung zum Speichern einer bestätigten Eigenschaft.

Auswahl innerhalb der unveränderten Sicherheits-/Berechtigungsgrenzen: aktuelle ausdrückliche Anweisung zuerst; danach passende bestätigte
spezifische Regeln, danach allgemeine Regeln. Widersprüchliche spezifische Regeln
werden nicht zufällig aufgelöst. Aktueller Auftrag gilt nur für seinen Umfang;
„heute kurz“ erzeugt keine dauerhafte globale Kürzeregel. Wiederholung macht eine
Quelle nicht unabhängig. Schweigen und eigener Modelltext gelten nicht als Zustimmung.
Eine ausdrücklich korrigierte Vorliebe ersetzt die alte im passenden Bereich;
ungeklärte Beobachtungen bleiben Vorschläge und verursachen keine neue Pflichtregel.
Damit Lernen nicht zur dauernden Prüfarbeit wird, werden ähnliche Vorschläge gebündelt.
Bereits ausdrücklich genannte Vorlieben verlangen keine wiederholte Zustimmung.
Eine spätere niedrig riskante Anpassung, etwa vorübergehend kürzere Antworten, braucht
vorab einen begrenzten, sichtbaren und rücknehmbaren Erprobungsmodus; sie darf weder
als dauerhafte Persönlichkeitseigenschaft noch als zusätzliche Befugnis gespeichert
werden. Dieser Modus ist zu prüfen, nicht bereits durch diese Planung aktiviert.

Arbeitsweisen wie „Terminvorbereitung“ sind versionierte, geprüfte Programmroutinen.
Das Nutzerprofil liefert dazu begrenzte Einstellungen. Freie Profiltexte werden nicht
zu ausführbarem Code, Systemprompt oder Werkzeugrechten. Keine automatische Ausführung
aufgrund von „ich mache das meistens so“. Details zum Lebenslauf/Interessen bleiben
belegte persönliche Informationen; sie werden nur genutzt, wenn sie zur Frage passen.

Pflichtfälle: unterwegs kurz vs. Architektur ausführlich; Du/Sie je Kontakt; Änderung
über die Zeit; Gedankenexperiment/Frust ohne Persönlichkeitszuschreibung; korrigierte
falsche Vorliebe; gleiche Namen in zwei Konten; fremde Mail behauptet Nutzerfreigabe;
Modellwechsel lokal→Cloud; Profil-/Belegentzug nach Neustart. UI: „So arbeite ich mit dir“
mit Erklärung „Warum gilt das?“, ändern und zurücknehmen, keine undurchsichtige Biografie.

## 8. Entlastung und Freigabe für andere Nutzer

Drei zusammenhängende Abläufe: Morgenbriefing, mehrdeutige Vorgangsfrage mit Folgefrage,
Nachricht→Entwurf→Nutzerkorrektur→späterer Abruf. Im Alltag über mindestens fünf echte
Arbeitstage beobachten; Dauer allein reicht nicht. Prüfung/Korrektur, unnötige
Unterbrechungen und manuell nötige Suche mitmessen. Vertragszielhypothese: mindestens
30 % weniger Gesamtaufwand gegenüber denselben Abläufen ohne Assistenz. Nicht erreicht
oder nicht messbar bedeutet keine belegte Entlastung.

Vor Weitergabe: frische Installation mit leerem eigenen Volume, keine persönlichen
Profile/Schlüssel/Beispiele im Image oder Repository, synthetischer zweiter Nutzer,
Neustart/Backup/Restore/Entzug und UI-Fehlerwege. Eine lokale Colima-Prüfung ersetzt
weiterhin nicht den expliziten Docker-Desktop-Nachweis. Ein gemeinsames Mehrnutzer-
Backend ist nicht geplant; je Installation eigener Bestand.

## 9. Konkreter Start der nächsten Arbeitssitzung

1. [Baseline-Implementierungsplan](../superpowers/plans/2026-09-13-memory-quality-baseline.md)
   ausführen: bestehende sechs Fälle plus gezielte Varianten am tatsächlichen Agenten.
2. Pro Fehler markieren: Aufnahme, Interpretation, Speicherung, Abruf, Modell oder
   Ausgabe/Aktion. Kein pauschales „lokales Modell zu schwach“.
3. Den wichtigsten reproduzierten Fehler in einem kleinen PR beheben und alte wie
   neue Gegenfälle erneut prüfen. Keine Freigabe der deaktivierten Suchheuristik
   allein wegen höherer Trefferzahl.
4. Ergebnisse in diese Paketübersicht verlinken; nur belegte Teilfähigkeiten freigeben.
   Danach Aufwand und Reihenfolge von M1–M4 konkretisieren.

Heute fertig geplant: Prioritäten, getrennte Messungen, Nutzerprofilvertrag und
umsetzbarer Baseline-Auftrag. Nicht heute erledigt: neue Modellqualifikation,
Produktfreigabe, automatische Verdichtung oder ein neues Nutzerprofil-Lernsystem.

## Aktuelle Reihenfolge nach den Reproduktionen

M1 ClaimStore-/Profil-Verlaufskorrekturen, M2 indizierter Abruf und kanonische
Identitätsreferenzen sind integriert. Die zusätzliche Elternbasis-Prüfung ist
implementiert und unabhängig geprüft: zurückgezogene Grundlagen dürfen weder aktuelle
Schlussfolgerungen noch alte unqualifizierte Antworten erhalten; historische
Entscheidungen bleiben mit einem Prüfhinweis zugänglich.

PR #47 ist integriert. M1d unterstützt bekannte Episode-Belege bei SelfModel-Ableitungen,
einschließlich sekundärer Belege und ausdrücklicher Neubewertung nach Wiederzulassung.
Implementierung, unabhängige Prüfung und isolierte Browser-/Docker-Abnahme sind abgeschlossen
([Nachweis](../evaluations/memory-quality/runtime/episode-support-20260919/README.md));
die Integration und Aktualisierung der privaten App bleiben gesondert. Der [konkrete Plan](../superpowers/plans/2026-09-14-self-model-episode-support.md)
verlangt eine ausdrückliche Neubewertung alter nicht nachweisbarer Quellenfreigaben;
er erfindet keine Zustimmung bei einer Migration. Die [Audits](../evaluations/memory-quality/audits/2026-09-14/)
belegen außerdem den offenen Schutz beim Wiederherstellen alter Sicherungen.

Vor weiteren Promptvergleichen bleiben vollständiger tatsächlich gelieferter Kontext
und identische synthetische Vergleichseingaben Voraussetzung. Ein weiterer reproduzierter
Übergabefehler betraf fehlende kanonische Aussagefelder und getrennte Ereignis-/
Importzeiten im tatsächlichen Modellkontext ([Audit](../evaluations/memory-quality/audits/2026-09-14/context-time-audit.md)). M2c behebt diesen Fehler mit einer gemeinsamen geprüften
Projektion für Provider, API und Verlaufssignatur. Änderungen der Quellenzeit und
Entzug/Wiederzulassung auch sekundärer Belege verwerfen alte Modellableitungen;
Originaltranskripte bleiben erhalten. Die Implementierung und die unabhängige
Taskprüfung sind abgeschlossen, Integration bleibt offen
([M2c-Nachweis](../evaluations/memory-quality/runtime/knowledge-time-20260919/README.md)).
Die isolierte Restore-Gegenprobe bestätigt weiterhin: Ein alter Gesamtsnapshot kann
neuere Quellenrücknahmen zurücksetzen. Dieser Schutz bleibt ein eigenes Paket.
Die neue Neun-Fall-Probe
mit Personenkennungen liefert technisch korrekten Kontext, aber weiterhin falsche
Interpretationen von Adressfragen. Quellen-Recall und Feldübergabe allein qualifizieren
kein Modell. Anschließend Antwortvertrag und Modellpfade mit den vorher festgelegten
Gegenfällen prüfen. Keine offene Abnahme wird dadurch in „erfüllt“ verschoben.

Am 19. September wurde zusätzlich WeKnoras Rangfusion als eng begrenzter,
ausdrücklich zuschaltbarer lokaler Suchbaustein übernommen (M2d). In zehn vorab
festgelegten deutschen Entwicklungsfällen steigt der exakt passende Modellkontext
von 4/10 auf 8/10; zwei Fälle behalten Zusatztreffer. Originalbelege, Gültigkeit
und Quellengenerationen bleiben bindend. 1.786 lokale Backend-/Diagnosetests und
die unabhängige Prüfung sind bestanden. [Rohdaten und Grenzen](../evaluations/memory-quality/runtime/hybrid-search-20260919/README.md)
trennen reales lokales Embedding von nicht geprüfter Chatantwortqualität.
Keine private Datenbank, App-Konfiguration oder Funktionsquote wurde verändert;
Standardaktivierung, größere fachliche Abnahme und Hintergrundindexierung sind offen.
