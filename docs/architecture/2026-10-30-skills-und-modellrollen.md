# Wiederverwendbare Abläufe und kleine Modellrollen

Stand: 30. Oktober 2026. Der nachfolgende Entwurf wurde anschließend zur Umsetzung freigegeben. Eine begrenzte erste [Ablaufbibliothek](../67-bewaehrte-ablaeufe.md) ist im Reparaturbranch implementiert; Veröffentlichung und Mac-Abnahme werden im Lieferprotokoll getrennt nachgewiesen. Die Modelloptionen unten bleiben Recherche, Qwen9B und BGE-M3 unverändert. Keine automatische Wiederaufnahme des Großimports.

## Sinnvolle Trennung

| Schicht | Enthält | Beispiel |
|---|---|---|
| Gedächtnis und Akten | Belegte Fakten, Identität, Beziehungen und zeitliche Gültigkeit | Wer ist Alex, welches Projekt, welche Frist gilt? |
| Bestätigte Präferenzen | Persönliche Schreibweise je Konto, Kreis und Kontakt | Offizielle Zunftmail sachlich, Gruß und Anrede passend zum Empfänger |
| Wiederverwendbare Abläufe | Vorgehen, Eingaben, Schritte, Ergebnisprüfung | Aktuelle Frist mit Originalquelle finden; offiziellen Mailentwurf vorbereiten |

Eine Akte braucht keinen eigenen Ablauf. Ein gemeinsames Verfahren erhält die passende Akte als Eingabe. Ein personenbezogener Schreibstil ist eine Präferenz, keine Kopie des ganzen Mailverfahrens. Sonst entstehen viele ähnliche Anweisungen, Widersprüche und teure Auswahl.

Im heutigen Code existieren bereits `mail_style.py`, `kreis.py` und `stilprofil.ts`: eigener Ton allgemein → bestätigter Kreis → Kontakt und Konto. Eigene gesendete Mails und ausdrücklich bestätigte eigene Beispiele liefern Vorschläge. Ein zurückgezogener Beleg macht abhängige Regeln unwirksam. Hierauf sollte die Weiterentwicklung aufbauen. `model.Kind.SKILL` beschreibt bisher Fähigkeiten des Nutzers und ist kein ausführbarer Agenten-Skill.

## Vorschlag für späteres Lernen

1. Ein erfolgreiches Verfahren oder eine ausdrückliche Nutzerkorrektur liefert einen **Entwurf**. Ein einzelner Erfolg beweist keine allgemeine Regel. Fremde Mailinhalte bleiben Daten und werden nicht zu vertrauenswürdigen Arbeitsanweisungen.
2. Vorhandenes Verfahren suchen: wiederverwenden oder gezielt versionieren, statt für jeden Kontakt und Durchlauf einen neuen Skill anzulegen.
3. Beschreiben: Zweck, Anwendungsbereich, notwendige Eingaben, zulässige Werkzeuge, Schritte, Ergebnisvertrag, Belege/Abhängigkeiten und Gegenfälle.
4. Positive und negative Beispiele prüfen. Automatisches Aktivieren wäre allenfalls für zuvor freigegebene, umkehrbare und eng begrenzte Verfahren geeignet. Identitätszusammenführung, neue Außenaktionen, Datenweitergabe und neue Berechtigungen werden durch einen Lernentwurf nicht automatisch erlaubt.
5. Nur passende aktive Verfahren laden. Zuerst bekannte Handlung und Metadaten prüfen, danach bei Bedarf semantische Suche oder ein kleines Auswahlmodell. Bei Mehrdeutigkeit nachfragen. Kein vollständiger Bibliotheksinhalt im Prompt und keine unendliche Kette von „Skill sucht Skill“.
6. Ergebnis erneut gegen Original, aktuelle Personenidentität und Quellenstand prüfen. Ein Skill darf die normale Beleg-, Frist- oder Freigabeprüfung nicht umgehen.

Änderungen würden über konkrete Abhängigkeiten laufen: betroffene Quellen-/Identitäts-/Regelversionen markieren abgeleitete Verfahren als prüfbedürftig. Alte Versionen bleiben nachvollziehbar und rücknehmbar; bis zur Prüfung gilt der sichere Standard. Datenänderung und Verfahrensänderung sind verschieden: eine neue Frist ändert die Akte, gewöhnlich nicht das Verfahren „Frist finden“.

Das ist Wiederverwenden von Erfahrungswissen, kein Training der Modellgewichte und kein Nachweis, dass ein kleines Modell dadurch jede schwierige Zuordnung beherrscht. Für einen ersten Ausbau wäre ein kleiner Katalog geprüfter Such- und Entwurfsverfahren sinnvoller als unkontrollierte automatische Skill-Erzeugung.

## Ollama: recherchierte Kandidaten, nicht aktiviert

Die offiziellen Ollama-Modellkarten waren am 30.10.2026 zugänglich. Die lokale Installation meldete lesend `0.40.13`; es war kein Modell geladen. Keine neuen Gewichte heruntergeladen und keine Kingfisher-Rolle verändert.

| Kandidat | Denkbarer Einsatz | Grenze / nächster Nachweis |
|---|---|---|
| [LFM3 1.7B](https://ollama.com/library/lfm3) | Kleine Textklassifikation und begrenzte Werkzeug-/Verfahrensauswahl; Download laut Karte 1.1–1.7 GB | Tri-hybrid aus Faltung und Attention; keine Behauptung, dass dies ein MoE sei. Deutsche Personen-/Fristqualität gegen dieselben Originalmails prüfen. |
| [LFM3-Audio 2B](https://ollama.com/library/lfm3-audio) | Lokale Spracheingabe, Transkription und Sprachausgabe; Deutsch aufgeführt | Karte nennt Text/Audio hinein und Text/Sprache hinaus, 32K Kontext im Readme. Namen, Datumswerte, längere Aufnahmen und reale Ollama-Audioanbindung noch nicht getestet. Kopfzeile und Readme nennen verschiedene Kontextwerte; nicht den höheren einfach übernehmen. |
| [Phonon Deutsch](https://ollama.com/library/phonon) | Sehr kleine Sprachausgabe für Antworten/Briefing | `phonon:de` ist laut Karte etwa 123 MB Download; 141 MB geladen wurden auf M5 Max berichtet, nicht hier gemessen. Deutsche 40M-Variante steht unter CC BY-NC 4.0. Kingfisher verwendet heute bereits eine lokale macOS-Stimme (`mac_audio_worker.py`); Hörvergleich vor zusätzlicher Abhängigkeit. |
| [d3 2B](https://ollama.com/library/d3) | Vorgegebene Kategorien/Entscheidungen bewerten, etwa welches Verfahren passt | Kein Chat- oder Transkriptmodell. Eigener `/v1/systemone`-Weg; Karte verlangt Ollama >=0.40.9, Versionshürde hier erfüllt. Trefferwahrscheinlichkeiten sind keine Bestätigung einer Person oder Aufgabe. |
| [Bonsai 2 9B](https://ollama.com/library/bonsai-2) | Späterer Kandidat für geringere Gewichtedateien bei ähnlicher Modellgröße | Ternäre Gewichte, kein daraus folgender MoE-Nachweis. 3.2 GB Download laut Karte; Kontext, Runtime und tatsächliche Personen-/Fristgüte separat messen. |
| [LFM2.5 24B-A2B](https://ollama.com/library/lfm2.5) | MoE-Agentenmodell als spätere Option | Nur etwa 2B aktive Parameter pro Token bedeuten nicht Speicherbedarf eines 2B-Modells. Karte nennt 15 GB Download. Gewichte, Kontextcache und Laufzeitbedarf bleiben relevant. Größere Coding-MoEs haben für diese Gedächtnisreparatur keinen belegten Vorteil. |

Praktischer Ausbau: Qwen9B und BGE-M3 bleiben zunächst bestehen. Wenn der Kern trägt, zuerst Sprachkomfort gegen den vorhandenen lokalen Weg prüfen; danach höchstens eine kleine Klassifikationsrolle mit klaren Grenzfällen. Rollen nacheinander und mit Lastgrenze betreiben, bis gleichzeitiger Betrieb am Gerät nachweislich sinnvoll ist. Routing kann teilweise Code erledigen; nicht jede Entscheidung braucht ein weiteres Modell.

## Abnahme eines künftigen Ausbaus

- Weniger Schritte und Modellarbeit bei mindestens gleicher Personen-, Aufgaben- und Fristqualität.
- Falsche, veraltete oder entzogene Grundlagen dürfen nicht über einen Skill zurückkehren.
- Explizite Korrekturen gelten im passenden Bereich und überschreiben keine unabhängigen Kontexte.
- Keine neue Verfahrenskopie, wenn eine parametrisierte bestehende Fassung genügt.
- Modellauswahl anhand derselben eingefrorenen Fälle, realer Latenz und gemessener Mac-Last; Modellkarten sind Testhypothesen.
