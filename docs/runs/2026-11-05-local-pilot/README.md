# Erneute lokale Pilotprobe: Lastwächter greift

Code `f4be12554791fb58ed8cd3344dc2d8e20b2d2611`, 05.11.2026.
Zehn unveränderte künstliche Pilotmails, fünf Fragen; derselbe geprüfte native
8K-Diagnosetransport und dieselben Qwen-Gewichte wie am Vortag. Der archivierte
[Runner](runner.py) ändert ausschließlich die Pfade auf den aktuellen Checkout
und den eingefrorenen Pilot. Seine `--check`-Prüfung bestand vor dem Lauf.

Der vorherige Abbruch wurde nicht blind wiederholt: Die rein lesende Vorprüfung
zeigte normalen Speicherdruck 1 und 49 % freie Reserve, gegenüber Druck 2 und
43 % vor dem ersten Versuch. Der Auslagerungsspeicher war weiterhin hoch.
Daher erfolgte genau ein erneuter begrenzter Versuch mit unveränderten Grenzen:
60 lokale Modellaufrufe, 600 Sekunden, Abbruch bei Druck 4 oder Reserve unter
25 %, kein zusätzlich geladenes Fremdmodell erlaubt.

Nach 6,1 Sekunden lagen Druck 4 und nur noch 22 % Reserve vor. Der Wächter
beendete ausschließlich seinen eigenen Prüfarbeitsprozess (Exit -15). Ein
Modellaufruf war begonnen, keine Antwort abgeschlossen. BGE-M3 und die fünf
Abruffragen wurden nicht erreicht. Nach dem Lauf meldete Ollama keine geladenen
Modelle; Druck 1 und 55 % Reserve wurden rein lesend bestätigt. Keine fremden
Programme wurden geschlossen, keine Schutzgrenzen verändert.

[Unveränderter Bericht](attempt.json), [Validierung](validation.json).
`model_seconds: 0` ist die Summe abgeschlossener Antworten und keine gemessene
Antwortzeit. Personen-, Aufgaben- und Fristqualität sind **nicht bewertet**.
Dieser native Diagnosetransport ist auch keine Prüfung des installierten
App-Transports oder der Mac-Oberfläche. Keine Cloudkosten, persönlichen Quellen,
App-Einstellungen oder Fortsetzung des Großimports.

Für die nächste echte Inhaltsprüfung bleibt der vorbereitete Mistral-Pilot
mit Schlüssel und konkreter Kostenfreigabe vorgesehen. Unter unverändertem
Arbeitszustand werden keine weiteren lokalen Versuche gestartet; ein neuer
lokaler Versuch verlangt eine substanzielle, tatsächlich belegte Entlastung.
