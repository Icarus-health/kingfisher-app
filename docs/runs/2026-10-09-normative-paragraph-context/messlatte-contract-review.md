# Read-only review: Mainz deadline answer contract

## Ergebnis

Der Volltestfehler war ein veralteter synthetischer Testvertrag, kein Produktfehler und keine Regression des aktuellen Commits. Die ursprüngliche Testdatei schlug bereits auf dem isolierten Git-Archiv von `70cac` fehl: `1 failed, 3 passed`. Die Antwortprüfung verwirft die freie Paraphrase „Das Angebot muss bis zum 26. Oktober raus.“ und fällt sicher auf die Quellenprojektion zurück.

Der final committed Testfix `50dea3e0c982696447b48a0205c6527d058294b6` ist eng und korrekt: `sorgfaeltig` liest im normalen Textvertrag den vollständigen Absatz mit der neuen Frist aus dem Modellpayload und gibt ihn unverändert zurück. Die Antwort enthält dann „die Frist für das Angebot verschiebt sich. Bitte senden Sie es bis zum 26. Oktober.“, bezieht sich auf `mainz-003` und wird als richtig bewertet. Produktcode und Szenario-Gold sind unverändert.

Für diesen Fristfall ist eine `originalstellen`-ID kein gültiger Vertrag: Der Request enthält reguläre `text`-Felder, aber keine `originalsaetze`, weil `originalmodus` nur bei einer Quelle mit `originalregeln(source)` aktiviert wird. Dieser Bitte-Satz entspricht nicht dem erkannten Muss-/Darf-Regelsignal. Eine ID-Antwort würde vor der Antwortauswahl scheitern und sicher in den Quellenmodus zurückfallen.

## Evidenz

- Finaler Commit enthält nur `messlatte/tests/test_antwort_saetze.py` (Teständerung und eine zusätzliche Negativkontrolle); kein Produktcode und kein Gold wurden geändert.
- Finaler fokussierter Lauf aus `/private/tmp/kingfisher-messlatte-contract-focused-20261009.log`: `5 passed`.
- Isolierter Baseline-Lauf auf `git archive 70cac`, ausgeführt aus `/private/tmp/kingfisher-baseline70cac-messlatte-20261009`: `1 failed, 3 passed`, exakt dieselbe ursprüngliche Aussage.
- Unabhängiger synthetischer Direktlauf im normalen Antwortpfad mit exaktem Absatz: keine Verwerfung, `working_reports`, Beleg `mainz-003`, Bewertung `richtig`.
- Die finalen Negativkontrollen bleiben bestehen: die alte 12.-Oktober-Antwort wird gestoppt oder als falsch erkannt; die erfundene 30.-Oktober-Antwort wird nicht gezeigt; die freie Muss-Paraphrase fällt in den Quellenmodus zurück.

## Grenzen

Die Prüfung belegt synthetisches Verhalten, keine Qualität eines echten Modells. Der Quellenmodus ist konservativ, aber weniger knapp; das ursprüngliche Fehlschlagen belegt für sich genommen keinen Aktualitätsfehler. Die vollständige Produktqualität und ein neuer Lauf der gesamten Testsuite waren nicht Teil dieser unabhängigen Prüfung.
