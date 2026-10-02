# Identitätskontext: neun lokale Qwen2.5:14b-Diagnosen

14.09.2026, immutable sauberer Commit 4e4a0f96b73460d758b2bf9d0e1dddbf35d823d2,
vorhandenes lokales Ollama, keine Downloads oder private Konfiguration. Drei Varianten
des bestehenden Gleichnamigkeitsfalls, jeweils Agent, unveränderter Quellenreferenzmodus
und neuer reference_identity_context/v1. Alle neun technischen Versuche vollständig,
Metadaten vor/nach jedem Versuch stabil. Drei Varianten sind keine drei unabhängigen
Szenarien. Der Antwortprompt wurde noch nicht korrigiert. Diese neun Versuche protokollieren
Ollama 0.34.0; der ältere M0-Vergleich protokollierte 0.33.3. Auch deshalb ist der
Vergleich mit den alten Antworten kein isolierter Vorher/Nachher-Versuch.

## Vorläufige inhaltliche Prüfung durch Codex

Die zusätzlichen kanonischen Referenzen allein qualifizieren das Modell nicht:

- Agent 01 erkennt mehrere Kontexte und fragt nach, nennt aber nicht die verlangte
  konkrete Auswahl Einkauf/Schule. Keine willkürliche Adresse gewählt.
- Agent 02 und beide Referenzmodi 02 interpretieren die Frage nach der E-Mail weiterhin
  als Frage nach Nachrichteninhalt. Die vorhandenen Adressen lösen die Frage damit
  nicht. Im Identitätsreferenzmodus fehlt auch die nötige Klärungsfrage.
- Agent 03 beantwortet die eindeutige Adresse richtig, nennt aber S1 nicht ausdrücklich.
  Zusätzlich wurde S2 mitgeliefert (unnötig, im Fall nicht verboten).
- Quellenreferenz 01 beschreibt einen Alex mit zwei kontextbezogenen Adressen und
  stellt keine konkrete Klärungsfrage. Dieser Modus enthält keine Personenkennungen;
  daraus lässt sich kein Versagen trotz vollständigem Identitätskontext ableiten.
- Identitätsreferenz 01 weicht auf eine physische Adresse aus und klärt die zwei
  Kontaktkontexte nicht. Identitätsreferenz 03 zitiert die ganze Kontaktbeobachtung
  statt knapp Adresse und S1 zu nennen. Die Adresse selbst ist enthalten.
- Quellenreferenz 03 gibt die richtige Adresse wieder, ebenfalls ohne S1-Verweis.

Die Rohdaten behalten semantic_verdict=review_required. Dies ist keine menschliche
Abnahme, keine Fehlerquote für reale Nutzer und kein Beleg einer Promptverbesserung.
Die drei Modi unterscheiden Kontext und diagnostischen Pfad; Modellzufall und kleine
Fallzahl erlauben keine isolierte kausale Aussage über die Wirkung der Kennungen.
Die Antwortklasse bleibt ungeprüft für eine allgemeine Freigabe. Als nächstes folgen
ein expliziter Antwortvertrag und vorher festgelegte positive wie negative Gegenfälle.
