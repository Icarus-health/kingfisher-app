# Enger unabhängiger Drawer-Review – 01.11.2026

**Ergebnis: kein Befund im geprüften Delta.** Commit **a2a0bab65a9c4e438a143e4420bee853e9a3ab3c** gegen `90b287cec109b79df809b6ad2bf445c6e7bd696a` ändert nur App.tsx und den zugehörigen Verhaltenstest. Keine Produktänderungen durch diesen Reviewer; keine Modelle, privaten Daten oder Backendtests.

## Rückweg, Fokus und Zustand

- `App.tsx:323–331`: Jede Auswahl schließt den Drawer. Gleiche Gesprächs-ID fokussiert den bestehenden Toggle und kehrt zurück, bevor navigate/History ausgeführt werden. Anderes Gespräch verwendet weiterhin denselben navigate-Pfad. Keine Änderung an Gesprächsdaten, Senden, Entwurfsablage oder Quellenpanel.
- `App.tsx:467–469`: Die Navigation erhält den neuen Handler; der bleibende Headerbutton besitzt den Fokusref und weiter korrekt aria-expanded.
- `Workspace.css:197–204`: Bei 900px ist dieser Toggle sichtbar; das Overlay liegt unter dem Header. Auf Desktop bleibt die Navigation sichtbar, der Toggle dagegen display:none. Das Schließen des Klassenstatus verändert diese Desktop-CSS nicht; ein Fokusversuch auf den ausgeblendeten Button erzeugt keinen neuen Navigations-/Historyschritt. Dies ist Code-/CSSprüfung, kein eigener Desktop-Browsertest.
- `App.tsx:980` verwendet weiterhin die Gesprächs-ID als React-Key. Der Same-ID-Handler wechselt weder ID noch Route; CommandBar bleibt demselben Gespräch zugeordnet. Die bestehende conversationDrafts-Ablage und ihre Revision werden nicht angefasst.

UI/UX Pro Max gezielt verwendet: passender Web-Treffer für vollständige Tastaturnavigation und sichtbaren Fokus. Keine zusätzliche Designrunde oder Funktionsvorschläge.

## Unabhängige Ausführung

Rootprüfkopie `/private/tmp/kf-root-ui-check-20261101/app/kingfisher`: App.tsx und conversation-workspace.test.mjs separat als hashgleich zum eingefrorenen Root geprüft.

- `node --experimental-strip-types --test tests/conversation-workspace.test.mjs`: **9 bestanden**, 0 Fehler, etwa 1,73 s. Enthält Same-ID-Drawer/Fokus/History-Kontrolle und weiterhin Navigation, verspätete Antworten, Scrollverhalten, Quellen und progressive Originalanzeige.
- `node --experimental-strip-types --test tests/conversation-input.test.mjs`: **10 bestanden**, 0 Fehler, etwa 1,54 s. Mehrzeilige/fehlgeschlagene und zwischen Gesprächen isolierte Entwürfe, Diktat sowie verspätetes Senden bleiben abgesichert.
- Eigene zusätzliche Kontrolle ausschließlich in `/private/tmp/kf-drawer-independent-ui-20261101/tests/conversation-workspace.test.mjs`: **1 bestanden**, etwa 1,27 s. Dreimal dieselbe ID ausgewählt: Drawer geschlossen, dreimal Fokus zurück, kein pushState/popstate, genau ein Lesen/Vorwärmen, unveränderter mehrzeiliger Entwurf samt Revision, vorhandenes Quellenpanel und Lesescrollposition erhalten. Anschließende andere ID: genau ein bisheriger Navigations-/popstate-Schritt, kein zusätzlicher Toggle-Fokus, alter Entwurf unverändert. Die erste Scratch-Fassung hatte den initialen Scroll-Effekt des Testtreibers nicht abgearbeitet; nach korrekter Initialisierung samt tatsächlichem onScroll-Ereignis bestand die Kontrolle. Kein Produktfehler daraus abgeleitet.

`git diff --check` für das eingefrorene Delta ohne Fehler. Root war zu Beginn sauber; am Ende waren parallele Root-Releaseänderungen an VERSION und docs/fassungen/1.0.38.md sichtbar, von diesem Reviewer nicht verändert.

## Grenze

Kein eigener CUA-/Browserklick oder tatsächlicher Mac-Fensternachweis in diesem Review. Die echte synthetische 900px-Bedienprobe und der vollständige Frontend-Build laufen separat beim Root. Die hiesigen Ergebnisse belegen den Handler und seine Zustands-/Navigationsgrenzen, nicht die vollständige visuelle Abnahme.
