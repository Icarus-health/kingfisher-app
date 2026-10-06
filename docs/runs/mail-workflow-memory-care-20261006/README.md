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
| Lokaler Dockerkandidat | Eigener Port 8893, flüchtige Beispieldaten, keine produktiven Konten oder Datenvolumes. Mail-API und lokales Modell erfolgreich geprüft. |
| Gerenderter Nutzerfluss | Noch offen. Eigene Test-App nicht für Computersteuerung aktiviert; Browserzugriff auf den Testport wurde abgelehnt. Nutzer kündigte Freigabe an, technischer Zugriff beim letzten Versuch weiterhin gesperrt. |
| Produktive Mac-Installation / Updater | Nicht durchgeführt; bisheriger Kingfisher und Daten unverändert. Kein öffentlicher Release oder neues Updateangebot veröffentlicht. |

Modellbeispiel: Die Auszüge enthalten „Bitte sende mir den Atlas-Bericht bis Freitag.“ und den vollständigen Satz „Das Hotel ist noch nicht gebucht. Erst nach der Freigabe durch Nora dürfen wir buchen.“ Der abschließende Prompt lässt reine Anreden aus. Das ist ein einzelner Nützlichkeitsbeleg, keine Messung einer allgemeinen Fehlerrate. Generierte Aufgabentitel bleiben prüfpflichtige Vorschläge.

## Noch offene Abnahme

1. Einmalige technische Freigabe für die getrennte Test-App und ihren lokalen Testport abwarten. Keine Umgehung über andere Browser.
2. Im tatsächlichen Fenster prüfen: Mail öffnen, Fortschritt/Abbruch, Original aufklappen, Aufgabenvorschlag übernehmen, leere Frist/Projekt/Person kontrollieren, vor dem Speichern vorhandene Aufgaben zählen, Wechsel zur zweiten Beispielmail und Schutz eigener Änderungen.
3. Erst danach den PR für Integration freigeben. Normaler Updateweg: Fassung/Notizen auf main, veröffentlichte GHCR-Version und Manifest, anschließend Mac-Updater mit Sicherung und Bestandsprüfung. Ein lokaler Kandidat ist kein herunterladbares Update.

## Ausführung und Daten

Alle Prüfungen liefen lokal, ohne GitHub-Actions-Neustart. Commitnachrichten tragen `[skip ci]`; keine Workflowabschaltung und keine neuen Modell-Downloads. Die getrennte Testversion verwendet keine produktiven Gmail-/Kalenderzugänge. Private Testkonfiguration und Rohlogs stehen nicht im Repository.

Entwurf und weitere Reihenfolge: `docs/superpowers/specs/2026-10-06-mail-workflow-memory-care.md`; ausführbarer Plan: `docs/superpowers/plans/2026-10-06-mail-workflow-memory-care.md`.
