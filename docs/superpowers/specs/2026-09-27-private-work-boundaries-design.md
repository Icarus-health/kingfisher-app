# Private und berufliche Informationen gezielt nutzen

Stand: 27. September 2026. **Architekturentwurf für den nächsten Ausbau**, keine
Behauptung bereits umgesetzter Isolation. Der separat umgesetzte erste Schritt
schließt die Empfängerlücke im bestehenden Mailantwortweg.

## Ziel und bewusste Grenze

Kingfisher soll den Alltag als Ganzes verstehen und trotzdem Informationen nur
für zulässige Zwecke verwenden. Die persönliche Tagesübersicht darf einen
privaten Termin und eine berufliche Aufgabe zusammen planen. Eine berufliche
Mail darf dadurch keine privaten Termindetails erhalten. Ebenso wenig dürfen
Informationen verschiedener Auftraggeber ungefragt zusammenfließen.

Prioritäten des Produktverantwortlichen: wenige Einstellungen, wenige Rückfragen, nachvollziehbare
Quellen und korrigierbare Entscheidungen. Keine automatische Tatsachenbestätigung.
Keine pauschale Zusage absoluter Datengenauigkeit oder vollständiger Spamerkennung.

## Architekturentscheidung

Drei Wege wurden gegen den vorhandenen Code geprüft:

- Separate vollständige Privat-/Arbeitsdatenbanken erschweren gemeinsame Planung,
  gemischte Quellen, Identitätsbezüge und Widerrufe über mehrere Kopien.
- Bloße Tags und Promptregeln passen leicht in den Bestand, erzwingen aber keine
  Grenze vor dem Modellaufruf oder beim tatsächlichen Versand.
- **Empfohlen: gemeinsames Gedächtnis mit technisch erzwungenen Nutzungsbereichen.**
  Originale bleiben einmal gespeichert; jeder Lese- und Weitergabeauftrag erhält
  einen begrenzten Bereich. Ableitungen behalten die Einschränkungen aller Inputs.

Die dritte Variante erfüllt den gewünschten gemeinsamen Überblick. Ihr größerer
Aufwand liegt in der Durchsetzung an sämtlichen Ein- und Ausgängen; eine einzelne
Prüfung im Mailformular genügt nicht.

## Drei getrennte Angaben

| Angabe | Beispiel | Bedeutung |
|---|---|---|
| Herkunft | Konto A, Ordner B, Quelldatum, Fassung | Woher kommt die Information? |
| Zusammenhang | Privat, Arbeit/Projekt A, Arbeit/Kunde B, gemischt, unbekannt | Worum geht es? Kann mehrere Bereiche betreffen. |
| Erlaubte Nutzung | persönliche Planung, interner Projektkontext, konkrete Weitergabe | Wer darf welchen Ausschnitt für welchen Zweck erhalten? |

Ein Arbeitskonto ist kein Beweis, dass jede Nachricht beruflich oder extern
teilbar ist. Gleicher Name, Absender, Arbeitgeber oder Betreff erweitert keine
Rechte. Eine Modellklassifikation darf Einschränkungen vorschlagen, aber keine
Weitergabeberechtigung schaffen. Sensitivität, etwa Gesundheitsdaten, ist eine
zusätzliche Einschränkung, kein Ersatz für diese drei Angaben.

## Datenmodell und Verantwortlichkeiten

`SourceUsage` wird an die konkrete Quelle/Fassung gebunden: `episode_id`,
`source_fingerprint`, `contexts`, `classification_origin`, `policy_revision`.
Unbekannt ist ein ausdrücklicher Zustand. Die technische Quellenidentität bleibt
von der inhaltlichen Klassifikation unabhängig. Account-/Ordnerzuordnungen sind
Vorschlagswerte für den Kontext und erteilen allein keine externe Freigabe.

`UsageGrant` enthält den durch den Nutzer festgelegten Zweck, zulässige Quellen
oder Ausschnitte, Zielbereich, Empfänger/Empfängergruppe, erlaubte Operation,
Gültigkeit und Revision. Keine frei formulierte Modellantwort ist ein Grant.
Wiederverwendbare Regeln sind möglich, soweit ihr Umfang konkret und widerrufbar
ist; keine Regel „alle Inhalte dieses Kontos immer teilen“ als Standard.

`UsageContext` wird vom Anwendungsweg erzeugt, nicht von fremdem Inhalt:
`personal_overview`, `project_internal` oder `external_reply`; dazu Konto,
Empfänger, Projekt, erlaubte Bereiche, Revision und Datenbudget. Der Empfänger
stammt aus der tatsächlichen vorbereiteten Aktion. Jede Änderung erzeugt einen
neuen Kontext und entwertet nicht mehr passende Entwürfe. Ein entfernter
Modellanbieter ist selbst ein zusätzlicher Datenempfänger: Die Freigabe einer
Mail an einen Kollegen erlaubt keine Cloud-Inferenz. Anbieter, Verarbeitungszweck
und Datenumfang benötigen eine eigene Freigabe; kein stiller Cloud-Fallback.

`DerivedUsage` hält die Quellen/Fassungen **aller tatsächlich verwendeten Inputs**
und die angewandten Grants fest. Weniger Zitate in der Antwort lockern keine
Beschränkung. Caches, Zusammenfassungen, semantische Suche, gespeicherte Antworten
und Chatverlauf dürfen diese Abhängigkeit nicht verlieren.

Eine gemeinsame Policy-Funktion beantwortet vor jedem Zugriff: Ist dieser
Ausschnitt für genau diesen Kontext verfügbar? Der Normalfall liefert erlaubte
Quellen-IDs an die Suche. Nicht zugelassene Rohtexte, Titel, Personenlabels oder
Embeddings gelangen nicht erst ins Modell, um nachträglich entfernt zu werden.

## Nutzungsabläufe

### Persönliche Übersicht

Bereits zum lokalen Lesen freigegebene Daten dürfen gemeinsam geplant werden.
Die Übersicht bleibt lokal und behält ihre Herkunftsbezüge. Ein späterer Wunsch
„schick das meinem Kollegen“ übernimmt nicht den gesamten bereits aufgebauten
Modellverlauf. Der Außenentwurf wird aus dem neu erlaubten Ausschnitt neu erzeugt.

### Beruflicher Antwortentwurf

1. Konto, tatsächliche Empfänger und Vorgang festlegen.
2. Nutzungsbereich bestimmen, dann erst darin suchen und Modellkontext aufbauen.
3. Nur zulässige Quellen oder ausdrücklich freigegebene Projektionen verwenden.
4. Ist ein relevantes Detail nicht freigegeben, möglichst ohne dieses Detail
   formulieren. Eine Rückfrage nur, wenn der Auftrag sonst nicht sinnvoll
   erfüllt werden kann. Keine privaten Details in der Begründung offenlegen.
5. Entwurf mit Quelle-/Policyrevision binden; Änderungen oder Widerruf entwerten
   betroffene Entwürfe, Freigaben und gespeicherte Projektionen.
6. Direkt vor Versand tatsächlichen Empfänger, Konto, Inhalt, Revision und
   einmalige Aktionsfreigabe prüfen.

### Gemischte Quelle

Ein Dokument bleibt als Original erhalten. Für verschiedene Nutzungen werden
belegte Ausschnitte gebildet. Ist eine sichere Teilung nicht möglich, gilt für
das gesamte Dokument die strengere Grenze; der Mensch muss nicht jede Zeile
beim Import klassifizieren. Die Rückfrage erfolgt erst beim relevanten Einsatz.

### Private Belegung im Arbeitskalender

Eine ausdrücklich aktivierte Regel darf aus einem privaten Termin ausschließlich
Start, Ende und „beschäftigt“ projizieren. Titel, Ort, Teilnehmer, Notizen und
medizinische Gründe gelangen nicht in diese Projektion. Auch die Verfügbarkeit
selbst ist eine begrenzte Freigabe, kein automatisch öffentliches Detail.
Der Projektionsschritt ist deterministisch und braucht kein Sprachmodell.

## Einfachheit in der Oberfläche

Beim Verbinden einer Quelle eine verständliche Kontextvorgabe anbieten:
„Überwiegend privat“, „Überwiegend beruflich“, „Gemischt“. Erkannte Abweichungen
als Vorschlag behandeln; nicht pro importiertem Element einen Dialog öffnen.
Ein kurzer Hinweis macht klar: Diese Auswahl ordnet ein und veröffentlicht nichts.

Rückfragen bündeln und konkret formulieren, z. B. „Darf ich für dieses Projekt
nur deine freien Zeiten berücksichtigen?“ Ablehnung und Korrekturen behalten ihre
Gültigkeit, bis der relevante Inhalt oder die Regel geändert wird. Ein sichtbarer
Rückweg zeigt Quelle, Einordnung und erlaubte Verwendung zusammen.

## Erster Schritt: im bestehenden Mailpfad umgesetzt

Der bisherige Antwortweg begrenzt frühere Quellen bereits auf Konto, Absender und
Betreff. Nun muss zusätzlich genau ein tatsächlicher Antwortempfänger vorliegen,
der diesem Absender entspricht. Ein fremdes oder mehrdeutiges Reply-To führt zu
einem Entwurf ohne frühere Quellen, mit einer verständlichen Erklärung.

Empfängerbereich und Konto werden im serverseitigen Quellenkontext gebunden.
Alte gespeicherte Quellenentwürfe ohne diesen Nachweis sind nicht mehr nutzbar.
Der genaue Mailstand bei Vorbereitung muss zum Token passen, auch wenn ein
zweiter Abruf wieder einen älteren Stand liefert. Am Versand prüft der Kern
zusätzlich die tatsächlichen Aktionsparameter gegen diesen Empfängerbereich.
Manuelle Antworten an eine abweichende Reply-To-Adresse bleiben mit konkreter
Versandfreigabe möglich; sie enthalten keinen automatisch hinzugefügten alten
Quellenkontext aus diesem Weg.

**Nicht dadurch gelöst:** Authentizität des Absenders, private Nachrichten im
selben Konto vom selben Absender, fremde Aliasidentitäten, Kontextweitergabe über
beliebige Chat-/Werkzeugpfade oder die vollständige Klassifikation gemischter
Quellen. Gleiche Adresse ist hier eine notwendige Begrenzung, keine umfassende
Weitergabeberechtigung. Deshalb wird dieser Schritt nicht als fertige
Privat-/Arbeitstrennung bezeichnet.

## Umsetzung des größeren Ausbaus in prüfbaren Stufen

1. Nutzungsbereich und Grants als versionierte lokale Daten, Migration bestehender
   Quellen zu „unbekannt“, authentifizierte Änderungswege, Backup/Restore mit
   Widerruf wiederaufgenommener Außenaktionen. Keine automatische Herabstufung
   vorhandener Schutzmerkmale.
2. Ein zentraler Leseweg für Quellen-/Wissenssuche, semantische Kandidaten,
   Profilprojektionen und Verlauf; Prüfung vor jedem Modellaufruf. Fehlende oder
   unbekannte Policy sperrt externe Nutzung, lässt freigegebene lokale Übersicht zu.
3. Außenentwürfe und alle Versandwege auf den Zweckkontext umstellen. Bindung
   tatsächlich gelesener Quellen einschließlich abgeleiteter Zusammenfassungen;
   erneute Prüfung unter der bestehenden gemeinsamen Sperre am letzten Ausgang.
4. Kontextvorgaben, Korrektur und gebündelte Rückfragen in vorhandene Oberfläche
   einbauen; anschließend die freigegebene Belegungsprojektion ergänzen.

Jede Stufe erhält Regressionstests und Sabotageproben. Nach Stufe 3 werden ausschließlich die ausdrücklich erfassten und geprüften
Datenwege als abgesichert bezeichnet, mit dokumentiertem Bedrohungsmodell und
verbleibenden Ausnahmen. Ein nutzbarer Gesamtablauf ist erst nach Stufe 4 und
Browser-/Mac-Prüfung belegt. Bis dahin kein gemischter Vollimport als freigegebener Standard.

## Abnahmefälle

- Private Arztnotiz mit demselben Projektnamen wie die berufliche Mail: weder in
  Kandidaten, Modellinput, Entwurf, Vorschau noch Fehlertext sichtbar.
- Dieselbe Person schreibt privat und beruflich, auch über dieselbe Adresse:
  Identität darf die Grenze nicht aufheben.
- Zwei Kunden und ein gemeinsamer Dienstleister: der Kontakt verbindet keine
  Kundendaten ohne passende Freigabe.
- Gemischte Notiz: nur freigegebener Ausschnitt, ohne Nachbartext und ohne
  private Metadaten; Modellbehauptung „genehmigt“ ändert nichts.
- Widerruf während Modelllauf, nach Entwurf und unmittelbar vor Versand:
  Ergebnis bzw. Aktion blockiert, andere erlaubte Arbeit bleibt nutzbar.
- Private Übersicht wird später weitergeleitet: neuer eingeschränkter Kontext,
  keine Übernahme des privaten Modellverlaufs.
- Wiederanlauf/Backup: Quellen bleiben erhalten, ausgelaufene bzw. widerrufene
  Außenrechte werden nicht wieder wirksam.
- Gleiche erlaubte Quelle mehrfach genutzt: keine wiederholte Grundsatzrückfrage.
- Private Belegung: ausschließlich Zeitfenster, keine Diagnose oder Teilnehmer.

Neben Fehlweitergaben auch ausgelassene nützliche Ergebnisse, falsche Blockaden
und Rückfragen je 100 Quellen messen. Ein System, das sicherheitshalber alles
verweigert, erfüllt den Produktauftrag ebenfalls nicht.
