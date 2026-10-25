# Verbesserungen nach dem Oberflächen-Durchgang (25.10.2026)

Auf die Frage „Was würdest du noch verbessern?“ kam eine Liste mit sechs Punkten, einer Entscheidung (Dunkelmodus) und
kleinen Resten. Der Nutzer: „Mach alles bitte.“ Gebaut in drei Wellen, jede mit Tests, Sabotageproben und
Browserbildern; nur synthetische Daten (Messlatte-Welt; für die Messungen eine große synthetische Welt mit 8.000 Mails).

## Was sich ändert

| Punkt | Ergebnis | Bild |
| --- | --- | --- |
| „Neu eingegangen“ ehrlich | Nur Quellen von heute bis vorgestern (Kalendertag in der Zeitzone des Nutzers); Altbestand aus dem ersten Einlesen zählt nicht. Eine Regel im Sidecar (`neu_eingegangen.py`). | [heute-neu-eingegangen-1280.jpg](heute-neu-eingegangen-1280.jpg) |
| Aufgabenzeile auf Heute | Dieselbe Zeile wie in der Aufgabenliste: Kreis erledigt sofort, die Zeile öffnet die Aufgabe. | wie oben |
| Ein Satz Stand in der Akte | Ohne Modell aus vorhandenen Feldern, z. B. „Änderung am 17.9.: Absage Workshop am 28. Oktober. 2 Punkte brauchen dich.“ Doppelungen ausgeblendet, Kopf auf dem Handy über dem Namen. | [akte-stand-satz-390.jpg](akte-stand-satz-390.jpg) |
| Einrichtung schlägt vor | Name aus Umgebung, eigenem Postfach oder Mac-Benutzer: „Hallo Lea. Stimmt der Name?“, gespeichert erst mit dem Klick. Zugänge ohne falsche Ladebalken. | [einrichtung-name-1280.jpg](einrichtung-name-1280.jpg) |
| Ein „Rückgängig“ für alles | Hinweis unten mittig („… erledigt · Rückgängig“, 6 s, ⌘Z) für alle Aktionen mit vorhandenem Rückweg; Rückfrage nur noch, wo es keinen gibt. | [hinweis-rueckgaengig-1280.jpg](hinweis-rueckgaengig-1280.jpg) |
| Viel Bestand | Betreff und Namen mit Umlauten richtig dekodiert, Graph ohne technische Scheinthemen, Listen ohne den ganzen Graphen; Gruß auf Heute unter 1 s auch beim ersten Öffnen. Messungen: [`../2026-10-25-viel-bestand/README.md`](../2026-10-25-viel-bestand/README.md). | – |
| Dunkelmodus | Die Arbeitsflächen folgen dem Systemmodus (ersetzt die Festlegung vom 15.10., `docs/16-gestaltung.md`). Alle Farben über Rollen, Hellmodus unverändert (15.058 berechnete Farben gleich). | [hell-dunkel-heute-1280.jpg](hell-dunkel-heute-1280.jpg), [hell-dunkel-einstellungen-390.jpg](hell-dunkel-einstellungen-390.jpg) |
| Kleine Reste | Bausteine (Schalter, Gruppe mit Zahl und Aktion, Zeile mit eigenem Bedienelement, Unterkopf, Bestätigungskarte) in der Grundlage; Jahresansicht mit 44-px-Zielen; Nachfrage zu Terminen mit Namen statt Adressen; „zuletzt“ nicht in der Zukunft. | – |

## Offen

- Abnahme am Mac: Systemschrift, Dunkelmodus im nativen Fenster, Name und Zeitzone aus der Mac-App (nur strukturell geprüft).
- Erster Aufruf nach einer Änderung im Hintergrund kostet wieder so viel wie vorher (Zwischenspeicher wird ungültig).
- Im Hellmodus liegen einige leise Texte knapp unter 4,5:1 Kontrast (Quellverweise der Akte 3,87); eine Änderung wäre
  eine Änderung am Hellmodus und ist nicht Teil dieses Pakets.
