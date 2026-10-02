# Synthetischer Docker-/Ollama-Nachweis für M1

14.09.2026. Eigenes Testvolume, eigener nur an Loopback gebundener Port, keine privaten
Daten oder Mailkonten. Docker-Image `sha256:b8ad6803419c` (vollständige ID in state.json),
Quellcommit `b0798b4e17860bfaf0766500f3647b011ec712c2`. Dieses Image enthält die vier
M1-Kernkorrekturen, aber noch nicht den späteren vierzeiligen Approval-Egress-Fix
`6166e9f`; dessen Nachweis besteht separat aus den 112 fokussierten Tests und Review.
Kein Nachweis einer aktualisierten produktiven App.

Ein Originalbeleg und bestätigter Claim „Ada leitet das synthetische Projekt Quellprobe“
werden mit einer 90-Sekunden-Gültigkeit über die regulären Store-/Bestätigungs-APIs
angelegt. Die App beantwortet anschließend echte HTTP-Gesprächsanfragen mit dem
vorhandenen lokalen Qwen2.5:14b über Ollama.

1. Vor Ablauf: richtige Rollenangabe, Claim in aktuellen Kontextkarten und versionierter
   Claim-Lineage. Antwort: „Ada leitet das Projekt Quellprobe.“
2. Nach natürlichem Zeitablauf: kein gültiger Claim mehr in den Karten, gespeicherter
   Resetmarker, Antwort benennt fehlende aktuelle Grundlage. Ursprüngliche Antwort
   bleibt im sichtbaren Gespräch.
3. Nach Container-Neustart und neuem HTTP-Aufruf desselben Gesprächs: alter Claim
   bleibt ausgeschlossen; kein wiederholter Reset. Antwort nennt fehlende spezifische
   Belege. Gespräch und Quellenbestand wurden nicht gelöscht.

Die HTTP-Ausgaben belegen Laufzeitantwort, Metadaten und Persistenz. Vollständige
Modellanfragen werden hier nicht mitgeschnitten; deren Ausschluss wird zusätzlich
in den synthetischen CapturingProvider-Regressionsprüfungen nachgewiesen. Dies ist
kein allgemeiner semantischer Modelltest und keine Freigabe aller Gedächtnispfade.

## Umgebungsprobleme und Wiederaufnahme

Zwei vorherige Starts scheiterten vor der ersten Modellfrage wegen vollem Docker-
Dateisystem. Unbenannte Kingfisher-Buildstufen wurden anhand ihrer Buildhistorie
identifiziert und entfernt, ohne Datenvolumes, Container oder benannte App-Versionen
zu löschen. Danach waren rund 6,9 GB frei. Es wurden keine fehlgeschlagenen Antworten
als erfolgreiche Versuche ersetzt; diese Starts erzeugten keine Modellantwort.

Nach dem erfolgreichen Ablauf änderte Docker beim Neustart den zufällig zugewiesenen
Hostport. Der erste Nachtest erreichte deshalb keinen Server; die Testhilfe liest nun
die tatsächliche Portzuordnung erneut. Erst danach wurde die dritte Modellfrage
abgesendet. Die drei erhaltenen Antworten gehören zu den drei erfolgreich abgesendeten
HTTP-Gesprächsfragen, keine Auswahl aus mehrfach angeforderten Antworten. Die Anzahl
interner Provideraufrufe pro Gesprächsfrage wurde hier nicht separat mitgeschnitten.

Die Rohantworten und ihre Prüfsummen liegen neben diesem Dokument. Die nur für den
Test erzeugte Authentisierungskonfiguration ist bewusst nicht Bestandteil des Repos.
