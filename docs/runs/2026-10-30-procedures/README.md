# Gedächtnis und ergänzende Ablaufbibliothek

30.10.2026. Ausgangspunkt: `main`/1.0.30, Personenreparatur `1fb2934` und
Fristvorschlagsreparatur `a1cf873`. Kandidat: 1.0.31. Ausschließlich künstliche
Quellen in Modell- und Bedienproben; Großimport unverändert pausiert.

## Reparaturen und Grenzen

Mehrdeutige Personen werden vor Recherche geklärt. Ein allgemeines Wort wie
„Frist“ wählt keinen Alex mehr aus. Der Fristwächter erkennt ausdrücklich
benannte alte/neue Daten derselben aktuellen Passage bei exakten Beteiligten,
Konto und Aufgaben-/Projektbezug. Er schreibt keinen neuen Auftrag aus dem
alten Beleg: der alte Vorschlag bleibt mit neuer Quelle zur Prüfung sichtbar,
verliert die alte Fristvorbelegung und lässt sich direkt, gesammelt oder
automatisch nicht unbesehen übernehmen. Historische Anfragen bleiben als
historische Prüfung erhalten; daraus wird kein heutiger Rückstand behauptet.
Nicht alle freien Formulierungen einer Friständerung sind damit erkannt.

Die [Ablaufbibliothek](../../67-bewaehrte-ablaeufe.md) ergänzt den Kern. Ein
deterministischer Verteiler lädt Grundverfahren und passende bestätigte
Zusatzverfahren; kein Modellaufruf zur Auswahl. Lernvorschläge bleiben inaktiv
bis zur Bestätigung. Gleiche Verfahren werden wiederverwendet, neue Versionen
prüfen den alten Stand erneut. Quellenentzug, Rücknahme und Versionswechsel
sperren alte Ableitungen auch nach erneutem Laden des Gesprächs.

Persönliche Verfahren werden nicht in Cloudprompts gegeben. Bei einem
konfigurierbaren Loopback-Anbieter genügt `is_local` nicht: installierte lokale
Gewichte werden vor der Übermittlung zusätzlich geprüft. Lernaufträge benutzen
beim vorhandenen Ollama-Modell 8K Kontext und höchstens 1.200 Ausgabetokens;
das ändert nicht die normalen Gesprächseinstellungen. Eigene Kingfisher-Gewichte
werden nach dieser kleinen Lernarbeit freigegeben. Grundlage:
[Ollama Chat API](https://docs.ollama.com/api/chat).

Verfahrensunterricht bleibt ein korrigierbares Original, geht aber nicht in
die Fakten-/Aufgabenerkennung. Form, Umfang und Auswahlbeispiele sind
automatisch geprüft; fachliche Richtigkeit bleibt eine sichtbare Nutzerprüfung.
Gelernte Freitexte ändern keine Belegantwortverträge, Werkzeuge oder Freigaben.

## Prüfungen

- Vollständige UTC-Regression mit zwei niedrig priorisierten Workern:
  **8.313 bestanden, 1 übersprungen, 26 Untertests**, 617,34 s. Zwei vorhandene
  Starlette/httpx-Warnungen. Anschließende Änderungen am kleinen nativen
  Lernaufruf, an dessen Kontextauswahl und am Ausschluss von Lernunterricht
  wurden gezielt nochmals geprüft; nicht als unveränderter Vollstand ausgegeben.
- Der vorherige Lauf mit 8.311 bestandenen Tests und einem Fehler ist kein
  grüner Nachweis: die vollständige Sicherungsfixture enthielt den neuen Store
  noch nicht. Sie erstellt jetzt einen echten bestätigten Ablauf und prüft
  exakte Wiederherstellung und tatsächliche Auswahl.
- Betroffene Personen-/Gedächtnis-/Ablaufketten: 111 bestanden. Weitere
  Agent-/Mail-/Wiederherstellungsnachprüfung: 107 bestanden. Abschließende
  Nachprüfung und Auslieferungsstatus werden unten ergänzt.
- Frontend: 955 Tests, Produktionsbuild und Assetvertrag bestanden. Bekannte
  Meldung zur Bundlegröße bleibt bestehen.
- Unabhängiges Review fand einen echten Verlauf-Rückkehrfehler. Der neue
  HTTP-Test wurde rot beobachtet, anschließend behoben; unabhängige fünf
  Folgerunden nach Rücknahme und Versionswechsel bestanden. Weitere
  Sabotageproben der Aufgabenreparatur reproduzierten vier erwartete Fehler.

## Echte Qwen-Proben auf dem Mac

[Lernvorschlag](qwen-learning.json): dieselben vorhandenen Qwen9B-Gewichte,
ein echter Modellaufruf, 13,634 s. Vorschlag zunächst inaktiv; unabhängige Bitte
„Schreibe eine Mail für die Zunft“ wählt ihn nach Übernahme, private Urlaubsmail
wählt ihn nicht, Quellenentzug entfernt ihn. Reine Auswahl: 0,283 ms, kein
zusätzlicher Modellaufruf. Gewichtsprüfung und Ein-/Ausgabe sind in dieser
Auswahlzeit nicht enthalten. [Lastmessung](qwen-learning-pressure.json):
mindestens 26 Prozent freie Systemquote, Druckstufe höchstens 2, danach 1.

Die vorherige 32K-Lernprobe wurde bei Druckstufe 4 vom **Prüfwächter**
abgebrochen und das Testmodell entladen ([Messung](initial-32k-pressure.json)).
Dieser Wächter gehört zur Probe, nicht zu einem neuen permanenten Systemdienst.
Unterschiedliche Ausgangslasten erlauben keinen kontrollierten prozentualen
Leistungsvergleich. Der erfolgreiche 8K-Lauf ist keine Garantie für beliebige
gleichzeitig laufende Programme.

[Abruf](qwen-recall.json): dieselben zehn künstlichen Mails aus
[Katalog](catalog.json), Aufnahmebereiche aus [früherer Qwen-Einordnung](recorded-intake.json)
unverändert wiedergegeben, **keine erneute Aufnahmegüteprüfung**. „Welche Frist
hat Alex?“ fragt zwischen drei Identitäten, ohne Modellaufruf. Nach ausdrücklicher
Wahl: ausschließlich `deadline-change`, **04.11.2026, 18 Uhr**, in 14,201 s
mit zwei Qwen-Aufrufen. Kein zusätzliches Prüfmodell eingerichtet. Historische
und private Namensvetter bleiben getrennt. [Lastmessung](qwen-recall-pressure.json):
Druckstufe höchstens 2; danach 1. Kein Cloudaufruf und kein Großimport.

## Bedienung und Paket

CUA-Prüfung im künstlichen Bestand auf 127.0.0.1:8893: Bereich aufklappen,
Schritte/Beispiele lesen, übernehmen, bei 900 Pixeln per Tastatur zurücknehmen,
erneut im Gespräch lehren und über „Ablauf prüfen“ direkt zum geöffneten
Abschnitt springen. Zusätzlich bei 1.280 Pixeln geprüft; keine Konsolenfehler.
Normale App-Daten und Konten wurden dafür nicht verwendet.

Das erste gebaute Containerpaket enthält alle fünf SKILL.md-Dateien. Lokaler
Legacy-Docker-Bau benötigt eine temporäre Dockerfile-Kopie mit vorangestelltem
`ARG BUILDPLATFORM=linux/arm64`; Produkt-Dockerfile und Releaseworkflow bleiben
unverändert. Der lokale Universal-Mac-Bau scheiterte an fehlenden Intel-Swift-
Kompatibilitätsbibliotheken des installierten CLT; er wird nicht als fertiges
DMG ausgegeben. Der native App-Code ist unverändert; Auslieferung und Prüfung
des vorhandenen Mac-Updaters sind eine getrennte Abnahme.

## Auslieferungsstand

Noch nicht als persönliche Installation abgenommen. Vor Umschaltung werden
Sicherung, Originalbestand und pausierter Import geprüft; anschließend Fassung,
Bibliothek und Normalbetrieb im Mac-Fenster erneut zurückgelesen.

## Schlusskorrekturen nach der echten Modellprobe

Der kleine native Lernaufruf ist mit installierten lokalen Gewichten abgesichert.
Allgemeine Ton-/Aufgabenwörter aktivieren keinen speziellen Ablauf allein;
verneinter Kontext bleibt konservativ beim Grundverfahren. Der reale Qwen-
Gegenfall ist als dauerhafte Regression erfasst. Zur Wiederverwendung werden nur
passende Metadaten (höchstens acht, 2.400 Bytes) geladen, keine ganzen Bibliotheken.

Ein zweiter unabhängiger Review fand einen tatsächlichen Proxyweg: lokaler
Modellname und positive Gewichtsprüfung allein reichen nicht, wenn der folgende
Transport HTTP_PROXY übernimmt. Lokale OpenAI-kompatible Aufrufe verwenden nun
immer einen direkten Client ohne Umgebungsproxy und ohne Weiterleitungen.
Die echten Chat- und Mailtransport-Tests wurden mit HTTPProxy rot, anschließend
mit ConnectionPool grün beobachtet; Remoteanbieter bleiben unverändert.
Unabhängige Wiederholung und 38 betroffene Tests bestanden.

Die alten lokalen Providerfixtures greifen nun am gemeinsamen `_client`-Einstieg
an, statt am nur noch für entfernte Anbieter verwendeten `_http`. Assertions
und Transportgarantien bleiben erhalten; alle 60 Tests dieser drei Dateien
bestanden, einschließlich unabhängiger Wiederholung und Diffprüfung.
