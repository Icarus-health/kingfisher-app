# Mailüberblick und gezielte Gedächtnispflege · 6. Oktober 2026

## Lieferung

- Mail öffnen → lokales Modell wählt bis zu drei vollständige Originalpassagen; Originaltext bleibt erreichbar.
- Aufgabenvorschlag → vorhandenes Formular wird mit Titel und Quelle vorbereitet. Keine automatische Frist-/Personen-/Projektzuordnung und kein automatisches Speichern oder Versenden.
- Wiederholtes Öffnen derselben unveränderten Mail nutzt einen begrenzten Prozesscache. Änderungen an Quelle, Konto, Anbieter oder Modell verwerfen ein überholtes Ergebnis; auch Cachetreffer lesen die Quelle erneut.
- Gedächtnisauswertungen tragen eine Version. Künftig veraltete Einordnungen werden durch den bestehenden begrenzten Hintergrundlauf erneuert; die alte Interpretation derselben unveränderten Quelle bleibt bis zum erfolgreichen Austausch verfügbar.
- Migration 18 setzt bestehende Einordnungen auf Version 1. Kein pauschales neues LLM-Lesen des Bestands bei diesem Update. Originalquellen und bestätigte Aussagen bleiben unverändert.

## Nachweise

| Prüfung | Ergebnis / Grenze |
|---|---|
| Kompletter Backendlauf auf `1791565` | 4.788 bestanden, 1 übersprungen; 695,85 Sekunden. Bestehende Starlette/httpx- und Escape-Warnungen. |
| Abschließende Mail-/Antwort-/Posteingangstests nach Cachekorrektur und Promptklarstellung | 47 bestanden. Cache-Race-Test zuvor reproduzierbar rot; anschließend grün. Kein erneuter kompletter Backendlauf nach diesen isolierten Änderungen. |
| Oberfläche | 282 Tests bestanden, Typecheck und Produktionsbuild erfolgreich. Bestehende Bundlegrößenwarnung; Tests sind Quelltextverträge, kein DOM-Nachweis. |
| Mac-Code | 26 Tests bestanden, 1 übersprungen; arm64-Testfenster erfolgreich gebaut und ad hoc signiert. Native Produktionsdateien unverändert. |
| Unabhängige Gegenprüfung | Veraltete Auswertungen waren teilweise fälschlich als fertig gezählt und nicht priorisiert. Korrigiert, inklusive Wiederholungsabstand. Abschließende Cachekorrektur ohne weitere konkrete Beanstandung. |
| Echtes lokales Modell | Installiertes `kingfisher-qwen3.5:9b-32k`, ausschließlich erfundene Mail. Finaler Überblick 2,72 Sekunden, identischer Cachetreffer, keine Aufgabe geschrieben. |
| Lokaler Dockerkandidat auf Code `73f5478` | Eigener Port 8893, flüchtige Beispieldaten, keine produktiven Konten oder Datenvolumes. Finale Mail-API-Antwort in 3,85 Sekunden mit beiden relevanten Originalpassagen; weiterhin null Aufgaben. |
| Gerenderter Nutzerfluss | Am 7. Oktober in der freigegebenen nativen Test-App auf Port 8893 geprüft; Einzelheiten unten. Die vorherige Zugriffssperre ist für dieses Testfenster aufgehoben. |
| Produktive Mac-Installation / Updater | Nicht durchgeführt; bisheriger Kingfisher und Daten unverändert. Kein öffentlicher Release oder neues Updateangebot veröffentlicht. |

Modellbeispiel: Die Auszüge enthalten „Bitte sende mir den Atlas-Bericht bis Freitag.“ und den vollständigen Satz „Das Hotel ist noch nicht gebucht. Erst nach der Freigabe durch Nora dürfen wir buchen.“ Der abschließende Prompt lässt reine Anreden aus. Das ist ein einzelner Nützlichkeitsbeleg, keine Messung einer allgemeinen Fehlerrate. Generierte Aufgabentitel bleiben prüfpflichtige Vorschläge.

## Noch offene Auslieferung

Die native Abnahme der künstlichen Mailbeispiele ist erledigt. Integration und Veröffentlichung stehen weiterhin aus: Fassung/Notizen auf main, veröffentlichte GHCR-Version und Manifest, anschließend Mac-Updater mit Sicherung und Bestandsprüfung. Ein lokaler Kandidat ist kein herunterladbares Update. Reale Postfächer wurden in dieser Abnahme nicht verwendet.

## Ausführung und Daten

Alle Prüfungen liefen lokal, ohne GitHub-Actions-Neustart. Commitnachrichten tragen `[skip ci]`; keine Workflowabschaltung und keine neuen Modell-Downloads. Die getrennte Testversion verwendet keine produktiven Gmail-/Kalenderzugänge. Private Testkonfiguration und Rohlogs stehen nicht im Repository.

Entwurf und weitere Reihenfolge: `docs/superpowers/specs/2026-10-06-mail-workflow-memory-care.md`; ausführbarer Plan: `docs/superpowers/plans/2026-10-06-mail-workflow-memory-care.md`.

**Draft PR:** https://github.com/Icarus-health/kingfisher-app/pull/3. Nicht gemergt oder als öffentliches Update veröffentlicht.


## Ergänzende Abnahme · 7. Oktober 2026

- Native App `Kingfisher Workflow Test`, eigener Port 8893, künstliche Atlas-/Boreal-Mails und vorhandenes lokales Qwen-Modell. Produktive Installation, Konten und Daten unberührt.
- Atlas: Freitag-Anfrage und vollständige Hotel-Freigabebedingung sichtbar; Original aufklappbar. Auswahl bereitet Titel/Originalbeleg vor. Eigene Titeländerung sperrt weitere Vorschlagsübernahmen. Vor dem bewussten Speichern null Aufgaben, danach genau eine. API bestätigt: Frist, Projekt und Warten-auf leer; Aufgabenansicht zeigt „Ohne Termin“.
- WebKit zeigte im leeren Datumseingabefeld optisch das heutige Datum, obwohl dessen tatsächlicher Wert leer war. Der ergänzte Hinweis „Kein Datum festgelegt. Die Aufgabe wird ohne Termin gespeichert.“ ist im nativen Fenster sichtbar. Die Speicherlogik bleibt unverändert.
- Boreal: Ladeanzeige und Abbruch geprüft; Original wird verfügbar. Nach erneuter Auswertung erscheinen ausschließlich passende Boreal-Auszüge und ein neuer Ersatztermin-Vorschlag, keine Atlas-Inhalte. Dieser zweite Vorschlag wurde vorbereitet, nicht gespeichert.
- Sofortiges Wiederholen nach Abbruch lieferte bei noch laufender serverseitiger Inferenz 429. Dafür gibt es nun eine verständliche Warte-/Wiederholungsmeldung. Der Status-zu-Text-Test war vor der Korrektur rot, danach grün. Die neue 429-Formulierung selbst wurde nicht nochmals im nativen Fenster provoziert; Abbruch beendet die Anzeige, nicht zwingend die serverseitige Inferenz.
- Unabhängige Gegenprüfung fand einen echten Kurzbelegfehler: Der Überblick konnte eine Aufgabe mit „Ruf an.“ anbieten, die die vorhandene Aufgaben-API wegen ihrer Mindestbeleglänge ablehnte. Jetzt bleiben solche Passagen sichtbar, werden aber nicht als unspeicherbare Aufgabe angeboten. Regression zunächst rot, anschließend grün; 7-/8-Zeichen-Grenze und tatsächliches Speichern des zulässigen Vorschlags geprüft. Abschließendes Review des Fixes ohne weiteren Befund.
- Aktuelle betroffene Mail-/Aufgaben-/Antworttests: **76 bestanden**. UI: **284 bestanden**, Typecheck/Produktionsbuild erfolgreich. Bekannte Starlette/httpx- und Bundlegrößenwarnungen bestehen weiter. Kein erneuter kompletter Backendlauf nach diesen kleinen Korrekturen.
- Aktualisierte Oberfläche im getrennten Testcontainer geprüft. Der vorherige Docker-Image-Tag enthält die heutigen Ergänzungen nicht automatisch; Kopieren von Testdateien ist keine Veröffentlichung. Keine Aussage über Browserkonsole, produktive Postfächer, allgemeine Fehlerrate oder einen vollständigen Cloudbetrieb.

## Cloud-Steuerung des Nutzers

Mistral und OpenRouter **nur vorbereiten**. Keine Schlüssel, keine Cloud-Aktivierung, kein kostenpflichtiger Test und keine Postfachübertragung. Geprüfte Anschlusswege, Grenzen der vorhandenen Rollenverwaltung und spätere Abnahmekriterien stehen in [Cloud-Vorbereitung](../../58-cloud-vorbereitung-mistral-openrouter.md). Eine zusätzliche Cloud-Einordnungsrolle wurde nicht eingeschaltet.
