# Nicht auswählbare Personenrückfrage – enger Read-only-Befund

Stand: HEAD `184fca4`, Arbeitsbaum `/private/tmp/kf-skill-categories-20261031` zu Beginn sauber. Keine Produkt-/Teständerungen, Modelle, Netzwerkzugriffe oder privaten Dateien. Nur ein Offline-Skript mit isolierten synthetischen Stores unter `/private/tmp`.

## Nachgewiesener Weg

- `source_selection_pages.py:105–114`: Gesamtvergleich liefert zwar reports[S3], aber eine positive Seite meldet person[S6]. Der Code erhält ausdrücklich die Seitenunsicherheit und vereinigt S3/S6. Diese Schutzregel ist beabsichtigt und durch `test_source_selection_pages.py:115–122` abgesichert; kein sicherer Grund für ihre Abschwächung gefunden.
- `working_memory_answers.py:767–820`: Seitenstatus/ID-Menge werden gebunden; nachfolgende Helfer dürfen daraus keine stille Teilantwort machen. `:826–828` speichert unclear/person.
- `working_memory_answers.py:940–962`: Personenoptionen werden aus dem ersten Quellenbeteiligten gruppiert. Bei identischen Beteiligten oder fehlender Unterscheidbarkeit entstehen keine Optionen. Das ist durch `test_working_memory_choices.py:124–134` bewusst erlaubt.
- `working_memory_answers.py:1365–1378`: Die Darstellung fragt dennoch pauschal „Welche der genannten Personen meinst du?“. Der kompakte Zweig `:1340–1343` gilt nur bei status=reports; unclear/person fällt deshalb auf vollständige Originaltexte zurück. `_zitate` fügt `episode.body` in `:1272–1273` vollständig ein.
- `working_memory_answers.py:1454–1457`: Leere Optionen werden korrekt nicht als clarification_choices ausgegeben. `App.tsx:500–501` zeigt Auswahltasten nur bei tatsächlich vorhandenen Optionen. Der falsche Fragesatz und Maildump entstehen damit bereits im Backend, nicht durch ein erfundenes Frontend-Auswahlmenü.

## Reproduktion

Skript: `/private/tmp/kf-page-uncertainty-readonly-20261101.py`.

Sechs synthetische eigene Mails mit demselben strukturiert bekannten eigenen Absender, sechs echte gespeicherte/indexierte fact-Referenzen. Lokales Skriptmodell ohne Transport; Budgetpreview erzwingt zwei Seiten zu drei Quellen. Keine reale Anbieterinstanz.

Exakte Skriptauswahl:

```
Seite 1 [S1,S2,S3] -> source_reports[S3]
Seite 2 [S4,S5,S6] -> needs_person_choice[S6]
Gesamt [S3,S6]    -> source_reports[S3]
```

Frage: „Habe ich das ausgefüllte Formular schon zurückgeschickt?“

Beobachtet:

```
status = working_unclear
uncertainty = person
choices = []
clarification_choices_present = false
link_count = 2
raw_body_present = true
rendered_characters = 2532
```

Antwort beginnt mit „Quelle berichtet · automatisch eingeordnet / Welche der genannten Personen meinst du?“ und enthält beide vollständigen künstlichen Mailkörper. Die Reproduktion lief in etwa 0,24 s. Sie beweist den Darstellungsweg; sie misst keine Modellqualität.

## Kleinste belegbare Korrektur

Wenn uncertainty=person erhalten ist, aber `choices(answer, episodes)` keine quellenbelegt unterscheidbaren Optionen liefern kann: Status und sämtliche ausgewählten Referenzen unverändert lassen; generischen ehrlichen Hinweis auf ungeklärte Quellenauswahl statt behaupteter Personenmehrdeutigkeit zeigen; nur aktuelle Quellenverweise/Kopfdaten ohne vollständige Mailkörper ausgeben. Reale Personenrückfragen mit auswählbaren Unterscheidungsmerkmalen bleiben unverändert. Quellen müssen weiterhin jederzeit öffnbar sein und beim Wiederöffnen auf Entzug/Änderung geprüft werden.

Das behebt Darstellung und Bedienbarkeit. Es macht die ursprüngliche Ich-Frage nicht beantwortet. Ob S6 tatsächlich unpassend ist oder eine relevante Unklarheit enthält, kann dieser Statusmechanismus nicht semantisch beweisen. `Ich` oder eine eigene Mail allein rechtfertigt kein Ignorieren der zweiten Seitenauswahl; „im Anhang“ ist außerdem keine allgemeine Versand-/Erledigtgarantie. Kein Vorschlag für eine Ich-Heuristik, Musterliste, Promptänderung oder zusätzlichen Modellaufruf.
