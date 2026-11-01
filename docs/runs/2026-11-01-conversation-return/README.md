# Gesprächsliste: verlässlicher Rückweg

Die künstliche Browser-Bedienprobe für die neue Originalansicht zeigte bei 900 × 800 Pixeln einen Rückwegfehler: Die Auswahl des bereits geöffneten Gesprächs ließ die Liste über dem Inhalt stehen. Ein weiterer Klick zum Schließen war nötig. Der Entwurf ging dabei nicht verloren.

Die Korrektur schließt die Liste bei jeder Auswahl. Bei derselben ID bleibt die Gesprächskomponente erhalten; es gibt keinen zusätzlichen Navigationsschritt. Der Tastaturfokus kehrt zum sichtbaren Listenknopf im Kopf zurück. Die Auswahl eines anderen Gesprächs navigiert wie bisher.

## Nachweis

- Neuer Verhaltenstest vor der Korrektur: genau der neue Rückwegtest schlägt fehl, acht bestehende Tests bestehen. Danach alle neun bestanden.
- Vollständige Frontend-Prüfung: **978 bestanden**, keine Fehler. TypeScript und produktiver Vite-Build erfolgreich; vorhandener Bundlegrößenhinweis unverändert.
- Unabhängiger enger Review des Produkt-/Testcommits `a2a0bab65a9c4e438a143e4420bee853e9a3ab3c`: kein Befund. Zusätzliche Kontrollen für wiederholte Auswahl, Entwurf, Fokus, Scrollposition und Quellenpanel siehe Nachbarbericht.
- Echte CUA-Browserprobe gegen die normale API mit ausschließlich künstlicher Mail und geskriptetem Testanbieter: Originalansicht geschlossen → öffnen → vollständig lesen → per Enter schließen; Quellenknopf öffnet das Original. Quellenentzug entfernt Inhalt und Verweise auch nach Neuladen. Keine Modellinferenz oder persönlichen Konten.
- Anschließend wurde exakt der neue Produktionsbuild geladen. Bei 900 Pixeln schließt die erneute Auswahl per Enter die Liste; der Fokus steht auf dem sichtbaren Listenknopf. Der ungesendete Entwurf ist unverändert. Keine horizontalen Überläufe, Fehleroverlays, Konsolenfehler oder -warnungen in dieser Probe. Bei 1.280 Pixeln wurden die Originalanzeige und ihr Quellenzugang geprüft.
- Der Browserzugriff auf die Länge des Seitenverlaufs ist in der schreibgeschützten DOM-Auswertung nicht verfügbar. Die Kontrolle gegen zusätzliche Verlaufseinträge stammt aus den ausgeführten Verhaltenstests, nicht aus einer behaupteten Browsermessung.

Die temporäre Testgröße wurde zurückgesetzt, der Testtab geschlossen und ausschließlich der eigene Testserver sauber beendet. Die Bildnachweise liegen lokal außerhalb des Repositorys.

Keine Änderungen am Gedächtniskern, Originalquellen, Modellen, Konten oder pausierten Großimport. Die persönliche Mac-Installation und deren Fenster-/Alltagsabnahme bleiben separate offene Schritte.
