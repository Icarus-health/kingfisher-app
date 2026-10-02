# Lokales Audio-Briefing auf dem Mac

8. September 2026: Funktionaler Teilschritt von Roadmap-Punkt 15, weiterhin 15/20 (75 %). Browsersteuerung, Sprachinput und gemeinsame Automationsabnahme bleiben offen. Keine allgemeine UI-Neugestaltung.

Der eingebettete Browser bietet in dieser Installation kein `speechSynthesis`. Das Morgenbriefing wird deshalb auf ausdrücklichen Knopfdruck über die installierte macOS-Stimme Anna als PCM-WAV erzeugt und mit HTML-Audio abgespielt. Keine Modellanfrage, Cloud-Ausweichroute oder zusätzlicher Download. Dieser erste lokale Sprachweg ist keine Zusage einer hochwertigen Studio-Stimme.

Der neue ausgehende Mac-Helfer `scripts/mac_audio_worker.py` verwendet dieselbe private lokale Zugriffskonfiguration wie die bestehenden Helfer. Er bindet keinen Port, folgt keinen Umleitungen und arbeitet nur mit 127.0.0.1. Der Doppelklick-Starter startet ihn künftig ebenfalls; eine Dateisperre verhindert doppelte Helfer. Die Stimme muss bereits installiert sein.

Aufträge entstehen nur bei Nutzeraktion. Maximal ein flüchtiger Auftrag, maximal 8000 Textzeichen/10 MiB Audio; Verarbeitung nach 120 Sekunden fehlgeschlagen. Serverzustand wird bei Zugriffen/Workerpolling nach fünf Minuten bereinigt, außerdem bei Ersatz und Neustart. Keine Aufträge oder Audiodateien in SQLite oder Sicherungen. Private temporäre Dateien auf dem Mac werden nach Erzeugung entfernt; Browser-Blob-URLs bei Abbruch, Quellenwechsel und Verlassen freigegeben. Abbrechen kann eine bereits laufende Synthese noch auslaufen lassen, ihr Ergebnis wird jedoch verworfen und nicht abgespielt.

## Nachweise

- Reale macOS-Erzeugung eines synthetischen Testtexts: WAV/PCM16, 22050 Hz, 3,60 Sekunden.
- Isolierter geschützter Docker-Browser mit echtem Mac-Helfer: 21,59 Sekunden Audio erzeugt, laufende Wiedergabe/echter Zeitfortschritt, Pause, 1,25-fache Geschwindigkeit sowie Vor-/Zurückspringen geprüft.
- Fehlender Helfer wird angezeigt; nach Start erneute Anforderung erfolgreich. Kontrollierter Abbruch vor Fertigstellung bleibt ohne Audioquelle; Schließen und Wiederöffnen starten nichts automatisch. Keine Browserwarnungen/-fehler.
- Dockerneustart verwirft einen offenen Auftrag, alte Kennung liefert 404; Worker erhält danach keinen alten Auftrag.
- Tests prüfen alle geschützten Endpunkte, leeren/ungültigen Text, WAV-Parameter und abgeschnittene Daten, konkurrierenden Ersatz, Abbruch, verspätete Ergebnisse, TTL und Helfergrenzen.
- Vollständige Suite: 1155 bestanden, zwei lokale Skip-Fälle; Frontend- und Docker-Build bestanden. GitHub-CI vor Merge erforderlich.

Die Wiedergabeprüfung belegt den funktionierenden Audiopfad und die Playerzustände; eine subjektive Hörprobe zur Stimmqualität steht aus. Falls ein Browser automatisches Abspielen nach der Erzeugung blockiert, bleibt eine ausdrückliche Wiedergabe-Schaltfläche verfügbar. Zu lange Briefings werden verständlich abgelehnt, nicht still gekürzt.
