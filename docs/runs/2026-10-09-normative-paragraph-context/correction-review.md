# Korrekturbericht: Absatz-/Originaleinheitenbindung

Der isolierte Patch wurde nach dem unabhängigen Review korrigiert. Die zuvor geprüfte fehlerhafte Fassung bleibt unverändert als `PATCH.reviewed-failing.diff` samt `manifest.reviewed-failing.json` erhalten. Der neue Patch ist `PATCH.diff`; seine Dateihashes, der Fixture-Fingerprint und die Testprotokolle stehen in `manifest.json`. Die unveränderte Goldfixture hat weiterhin SHA-256 `a53217e6a52aa5a6c55728cc5ccc6d12ba21317a53538a391adbda970db4a361`.

## Korrigierte Befunde

**P1 – Überschrift ohne Punkt.** Absatz- und Originalsatzprüfung verwenden jetzt dieselben Quell-Offsets. Wenn die vorhandene globale Originaleinheit eine periodlose Überschrift mit dem folgenden Regelabsatz verbindet, wird beides als gemeinsame atomare Stelle materialisiert. Dadurch kann `Entwurf\n\nDie Klappe darf geöffnet werden.` die im Folgeabsatz stehende Einschränkung nicht mehr abschneiden.

**P1 – normative Begleitsätze.** Jeder mehrsätzige Absatz mit erkanntem Regelsignal wird gebunden, auch wenn jeder Satz selbst normativ ist (`darf`, `muss`, `soll`). Es gibt keine Ausnahme mehr für Absätze ohne gewöhnlichen Begleitsatz.

**P2 – Reihenfolge und Interleaving.** Ein vollständiger Regelabsatz wird im Originalmodus als eine Quell-ID angeboten. Im Legacy-Satzmodus akzeptiert die Abschlussprüfung den Inhalt nur als lückenlose Folge derselben Quellsätze in Originalreihenfolge. Umkehr und ein dazwischen eingefügter Satz einer anderen Quelle führen zu Zitaten.

Die Bindung wird nach dem ersten Prüftor und dem zweiten Tor, nach programmgenerierten Ergänzungen sowie beim Wiederherstellen gespeicherter Antworten geprüft. Unsichtbare, abgeschnittene oder überlange Absätze werden nicht als Einzelregel angeboten. Originale Quellen, Entzug und das zweite Prüftor bleiben wirksam.

## Prüfung

RED lief mit den neuen regressionsprüfenden Tests gegen die getrennt gesicherte fehlerhafte Patchfassung: **12 fehlgeschlagen, 10 abgewählt**. Der Fehlerauszug ist `RED-correction.log`. Danach bestanden im korrigierten Archiv **224 gezielte Tests** über Absatzbindung, Quellenbindung, Originalauswahl, Before/After-Regeln, bedingte Erlaubnisse, Antwortfluss und HTTP-Antworten. Es gab eine vorhandene Starlette/httpx-Deprecation-Warnung. Die Vollsuite wurde nicht ausgeführt. Kein Modell und kein Netzwerk wurden verwendet.

## Vertragsänderung und Grenze

Normative Mehrsatzabsätze werden nun als vollständige, geordnete Gruppe ausgegeben. Ein Satz wie `RULE` allein aus einem Absatz mit Folgeeinschränkung fällt auf Quellenzitate zurück. Die Originalauswahl bietet dafür nur die vollständige sichtbare Gruppe an. Gewöhnliche Mehrsatzfakten ohne erkanntes Regelsignal und Ein-Satz-Regeln behalten den kurzen Antwortpfad. Bei gemischten Absätzen können unabhängige Begleitsätze die Antwort verlängern oder bei Ablehnung/Unsichtbarkeit den Zitatfallback auslösen. Das ist beabsichtigter Nutzbarkeitspreis.

Das bleibt eine strukturelle Begrenzung, kein allgemeiner Wahrheits-, Autoritäts- oder Sprachverständnisbeweis. Ein historischer Status in einem eigenen, abgeschlossenen Absatz (etwa `Historischer Entwurf.` als separater Block vor der Regel) wird nicht an den Regelabsatz gebunden, sofern die bestehende globale Originaleinheit die Grenze nicht überquert; das wurde als bewusste Restgrenze nicht stillschweigend gelöst. Unbekannte normative Formulierungen und weitere Grenzen der bestehenden Absatzsegmentierung bleiben offen. Der Patch ist ein isoliertes Folgeartefakt, nicht in den Produktzweig übernommen.
