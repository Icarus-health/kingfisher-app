# Native Standardprüfungen: 12 Sekunden pro Auftrag, 12/24 insgesamt

01.11.2026; Basis `8d47d3aaf6d4a22bf3c90e20bf64fdef5ac60a26`.
Nur `satzpruefung_modell.py`, Budgettests und dieser Nachweis geändert.
Keine privaten Quellen, echten Modelle, Netzaufrufe, Sleeps oder Root-Dateien;
keine Änderung an Quellen, Prompts, Parser, Proof-/JA-Gates oder Parallelität.

Die Fake-Uhr reproduziert zunächst RED: Eine bzw. zwei valide native
Prüfungen mit jeweils 9,2 Sekunden liefern unter dem alten 8-Sekunden-Limit
`unklar`. Der neue Standard erlaubt ausschließlich im vorhandenen
Kingfisher-Profil und bei **beiden ursprünglich nicht gesetzten Budgets**
12 Sekunden je Auftrag, insgesamt 12 für eine bzw. 24 für zwei vollständige
reine native Fragen. Nichtleere Fragen innerhalb der bestehenden Textgrenze
und vollständige Rawbelege innerhalb des vorhandenen Belegbudgets sind
Voraussetzung für diesen Zeitstandard. Die bestehende äußere JSON-Frist
klemmt ihn auch bei nur einem Auftrag; bei abgelaufener Frist erfolgen keine
Prüfaufrufe.

Normale, gemischte, drei oder mehr, nicht zum Profil gehörende und ungültige
Anfragen behalten ihr vorheriges Verhalten. Sobald Satz- **oder** Gesamtbudget
explizit gesetzt ist, greift vollständig der alte Zweig. Insbesondere bleibt
das bisherige Paar-Gesamtbudget von 16 Sekunden bei explizitem Satzbudget
und fehlendem Gesamtargument erhalten. Neue Defaults werden erst nach der
Prüfung beider ursprünglich übergebenen Argumente eingesetzt.

**44 gezielte Kontrollen bestanden in 0,39 Sekunden**, ohne echte Zeitverzögerung:

- 9,2 Sekunden ergeben ein/zwei Ja nur im neuen passenden Standard;
- mehr als zwölf Sekunden pro Auftrag und mehr als 24 Sekunden insgesamt
  bleiben `unklar`; Nein/Unklar werden niemals zu Ja;
- explizite kleinere Budgets sowie engere und abgelaufene äußere Fristen
  haben Vorrang; die bisherigen Ausnahmebudgets bleiben unverändert;
- tatsächliche synthetische MIME-/Store-/Antwortkomposition: erste Quelle Ja,
  zweite nach zwölf Sekunden ohne gültiges Ergebnis führt zum gesamten
  Zitat-/Unsicherheitsrückfall, keiner gültigen Satzstruktur und null Claims.

Der neue Test enthält 30 Kontrollen. Weitere 14 bestehende Budgetkontrollen
wurden gezielt mitgeprüft und nur ihre genehmigten nativen Standarderwartungen
angepasst. Kein 742er-Lauf und keine komplette Suite während der Root-Probe.

```sh
PYTHONPATH=sidecar:. python -m pytest -q \
  sidecar/tests/test_native_question_budgets.py \
  sidecar/tests/test_docx_native_candidates.py::test_native_profilpaar_hat_24_gesamt_und_12_je_satz_ohne_echte_wartezeit \
  sidecar/tests/test_docx_native_candidates.py::test_alle_anderen_und_expliziten_budgets_bleiben_unveraendert \
  sidecar/tests/test_docx_native_candidates.py::test_engere_aeussere_frist_wird_durch_native_paarbudget_nicht_verlaengert \
  sidecar/tests/test_satzpruefung_modell.py::test_managed_local_profile_allows_cold_start_but_respects_explicit_budget \
  sidecar/tests/test_satzpruefung_modell.py::test_die_vorgaben_sind_zwei_sekunden_je_satz_und_sechs_gesamt
```

Vorhandenes Python-3.12-Testvenv verwendet; Diffcheck sauber. Die Fake-Uhr
belegt den Fristvertrag, keine reale Modellqualität. Kein Push oder Release;
unabhängiger Review und begrenzte reale Nachprobe bleiben beim Root-Arbeitsgang.
