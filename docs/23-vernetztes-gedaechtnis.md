# Vernetztes Gedächtnis: Belege vor Behauptungen

Kingfisher soll Beziehungen verstehen, ohne eine beiläufige Aussage aus einer
Mail oder einem Meeting zur Wahrheit zu erklären. Das Gedächtnis trennt daher
vier Ebenen:

1. **Quelle / Episode** – unveränderte Beobachtung mit Zeit, Herkunft und
   Digest. Sie belegt nur, was vorlag oder gesagt wurde.
2. **Kandidat** – eine mögliche fachliche Aussage mit Beleg, Gültigkeitsbereich
   und Konfidenz. Sie ist noch nicht bestätigt.
3. **Bestätigte Aussage** – vom Nutzer bestätigtes, korrigierbares und
   widerrufbares Wissen. Alte Stände bleiben nachvollziehbar.
4. **Graph-Projektion** – eine jederzeit neu berechenbare Sicht auf Personen,
   Projekte, Themen, Entscheidungen, Dokumente, Orte, Gespräche und Aufgaben.
   Der Graph ist kein zweiter Wahrheitsspeicher.

## Konflikte und „Wahrheit"

Kingfisher kann Inkonsistenzen erkennen, aber keine Lüge und keine Absicht
feststellen. Zwei widersprüchliche Quellen werden daher weder automatisch
zusammengeführt noch nach vermeintlicher Glaubwürdigkeit entschieden.

Ein Konflikt erzeugt eine kurze Klärung unter „Braucht dich":

- die beiden konkreten Aussagen,
- Quelle und Zeitpunkt beider Seiten,
- der betroffene Kontext,
- die Auswahl „A gilt", „B gilt", „beides gilt in verschiedenem Kontext" oder
  „noch offen lassen".

Solange die Klärung offen ist, darf keine der beiden Aussagen ungekennzeichnet
für Empfehlungen oder externe Aktionen verwendet werden. Eine Auflösung wird
als Ersetzung, Widerruf oder Kontexttrennung protokolliert; sie überschreibt
nie die ursprüngliche Quelle.

## Personen und Kontexte

Eine Person erhält eine stabile interne Identität. Namen, E-Mail-Adressen und
andere Kontaktmerkmale sind belegte Identitätsmerkmale mit Gültigkeitszeitraum,
nicht die Identität selbst. Unsichere Dubletten werden als Zusammenführungs-
kandidat gezeigt; Fuzzy-Matching führt nie selbständig Profile zusammen.

Dasselbe Personenpaar darf mehrere Beziehungen haben, jeweils mit eigenem
Kontext und Beleg, zum Beispiel privat, „VDD / Fachgruppe Digitalisierung" und
„IR-Kliniken / Projekt X". Ein Personenprofil ist eine Projektion mit:

- Übersicht und bestätigten Kontaktdaten,
- Kontexten und gemeinsamen Projekten,
- Gesprächen, Dokumenten und Notizen,
- offenen Themen, Aufgaben und Zusagen,
- letztem belegtem Kontakt und den zugehörigen Quellen.

Eine veraltete E-Mail-Adresse wird nicht aus der Geschichte gelöscht. Ihre
Gültigkeit endet, eine neue Adresse tritt mit eigener Herkunft an ihre Stelle.

## Projekte

Eine Projektakte projiziert Status, Beschreibung, Timeline, Aufgaben,
Entscheidungen, Dokumente, Team und Stakeholder aus denselben Quellen. Rollen
wie „Stakeholder" werden nur angezeigt, wenn sie strukturiert belegt oder vom
Nutzer bestätigt wurden. Die bloße Erwähnung eines Namens in einem Dokument
erzeugt keine solche Rolle.

## Markdown und semantische Suche

Markdown-Dateien können Rohquellen und menschenlesbare Exporte sein. Cognee
oder ein anderer semantischer Index kann später Suche und Vorschläge
beschleunigen. Weder Markdown-Projektionen noch ein Vektor- oder Graphindex
sind jedoch die kanonische Wahrheit. Sie müssen aus SQLite und den belegten
Quellen verlustfrei neu aufgebaut werden können.

## Umsetzungsschritte

1. Belegte Graph-Projektion und abgeleitete Personen-/Projektakten.
2. Stabile Entitäten sowie belegte Alias- und Kontaktmerkmale.
3. Allgemeines Kandidatenmodell für Beziehungen und Sachaussagen außerhalb des
   Selbstmodells.
4. Konflikterkennung mit sichtbarer, reversibler Klärung.
5. Freigegebene UI für Personen, Projekte und Graphnavigation.

Der erste Schritt ist rein additiv und lesend. Es gibt noch keine neue UI und
keine automatische Ableitung fachlicher Beziehungen aus Freitext.

## Implementierter Stand

Der lokale Unterbau umfasst inzwischen:

- die rein lesende Graph-Projektion mit Personen- und Projektakten;
- allgemeine Wissenskandidaten mit Subjekt, Beziehung, Wert und Kontext;
- zwingende Episode, Originalzitat und Digest als Beleg;
- bestätigte, append-only Entitätsaussagen außerhalb des Selbstmodells;
- Ersetzung nur bei vollständiger, ausdrücklicher Angabe der widersprechenden
  bisherigen Aussagen;
- eine deterministische Klärungsliste für konkurrierende Kandidaten und
  bestätigte Aussagen;
- idempotente Annahme bei Wiederholung oder Parallelzugriff.

Die Klärungsliste ist noch eine geschützte lokale Schnittstelle und besitzt
absichtlich noch keinen erfundenen Screen. Sie wird erst in „Braucht dich"
integriert, wenn dafür eine kanonische oder ausdrücklich freigegebene
Darstellung vorliegt. Die endgültige Identity-Resolution mit bestätigten
Aliasen und zeitlich gültigen Kontaktdaten bleibt der nächste Datenmodellschritt.
