# Unabhängige Abrufkontrolle · 8. Oktober 2026

`catalog-20261008.json` ist eine neu verfasste synthetische Kontrollmenge mit
14 Originalquellen und 23 Fragen. Sie wurde vor dem ersten Modelllauf eingefroren
und nicht anhand eines Modellresultats abgestimmt. Das Setup enthält ähnliche
Personen und Auftragskennungen, explizite Freigabe- und Ausschlussbedingungen,
eine ersetzte Terminplanung, eine Absage mit ähnlicher weiter bestehender
Veranstaltung sowie Fragen nach nicht vorhandenen sensiblen Angaben.

Jede Frage nennt die erwarteten Quell-IDs, ob die Antwort belegt ist, und eine
kurze Begründung. Antwortbare Fragen brauchen eine oder höchstens zwei Quellen.
Nicht beantwortbare Fragen haben `expect: []`; thematisch nahe
Quellen bleiben im Korpus, damit sie als Ablenker wirken können. Direkte und
umformulierte Fragen sind gemischt. Alle Personen, Aufträge, Termine und Notizen
sind erfunden; das Korpus enthält keine Anweisungen an ein Quellmodell.

Bei der Erstellung wurde kein Modell ausgeführt. Die Goldwerte wurden gegen
die hier abgelegten Originaltexte geprüft. Die Datei dient der unabhängigen
Messung, nicht als Trainings- oder Tuningmaterial. Die anschließend ausgeführte
CPU-Rankingmessung liegt getrennt in `docs/runs/2026-10-08-cpu-retrieval/`; sie
ändert diesen Katalog nicht und belegt keine vollständigen Modellantworten.

Vor dem ersten Modelllauf hat das Elternreview die frühere Datumsfrage RQ11 präzisiert: Gefragt werden ausdrücklich beide Notizen. Nur nach dem ursprünglichen Datum zu fragen hätte RCS05 oder RCS06 als ausreichende alternative Quelle zugelassen; beide zwingend zu verlangen wäre ein falscher Goldwert. Das einheitliche q/expect/type-Schema entspricht dem bestehenden Messwerkzeug.
