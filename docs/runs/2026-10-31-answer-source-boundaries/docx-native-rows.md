# Vollständige native DOCX-Zeilen als wörtlicher Quellenbericht

Basis: `2cfea10fe0e3f41d87fbf56bc70ad3d5ad2332f1`. Dieser separate
Nachtrag schließt die dort dokumentierte Anhang-Kompositionsgrenze für eng
geeignete skalare Tabellenzeilen. Alle Belege sind synthetisch; keine privaten
Quellen, tatsächlichen Modelle, Netzprovider, Apps oder Root-Dateien wurden
verwendet. Eine reale Modell- oder Nutzerabnahme ist damit nicht behauptet.

## Vertrag und Provenienz

`docx_text(bytes) -> str` bleibt erhalten. Der vorhandene strikte XML-Leser
kann zusätzlich die Offsets ganzer einfacher Tabellenzeilen liefern. Nicht
unterstützte Zeilenstrukturen liefern weiterhin Haupttext, aber keinen nativen
Nachweis. Bei mehr als 64 Zeilen endet die Nachweiserfassung vor den
Volltext-Spansuchen; die bestehenden XML-/Text-/Paketgrenzen bleiben aktiv.

Die normale Anhangaufnahme kann den Nachweis als interne versionierte Tags
speichern. Er bindet absolute Raw-Offsets an den unveränderten Body-Hash,
genau eine Haupttextregion mit eigenem Hash, den Anhang-Source-Key und die
Elternmail. Ein vollständig gelesener DOCX neben einem ungelesenen Logo darf
seinen eigenen Nachweis behalten; unvollständiger MIME-Abruf, unklare
Zuordnung oder ein abgeschnittener DOCX erlauben ihn nicht. Das Logo wird
dadurch nicht als gelesen behandelt.

Jedes Lesen prüft den aktuellen WMA-Fingerprint, aktuelle Sourceversion,
`DOCUMENT`/`EMAIL`, aktuelle gültige Elternbindung, exakte JSON-Typen und
Schemafelder, eindeutige Tags/Schlüssel sowie vollständige, eindeutige,
nicht überlappende Raw-Zeilen innerhalb der Haupttextregion. Manipulierter
Nachweis sperrt die Ausgabe. Gültige Metadaten ohne geeignete sichtbare Zeile
sperren gewöhnliche Originalaussagen nicht.

Der generierte Anhangkopf ist Metadatum. Seine Anführungszeichen und
Transportautoren beweisen keinen Dokumentinhalt oder Personenbezug. Echte
Quote-/Entwurfszeichen im gebundenen Haupttext bleiben Ausschlussgründe.
Bestehende Norm-/Bedingungskontexte bleiben atomar. Pronomen, Rollen,
bekannte Personennamen und finite Aussagen werden auf der ganzen nativen
Zeile geprüft; eine unabhängige spätere Formularfrage wird nicht durch den
globalen freien Satzsplitter zur Rollenbehauptung der früheren Feldzeile.

## Enger Ausgabe- und Prüfvertrag

Nur eine vollständige sichtbare Raw-Zeile bis einschließlich 400 Zeichen
kann angeboten werden. Das Format umfasst opaque Labels mit skalaren
Zahl-/Datumswerten, auch `Label\nWert`, mehrere Zellen und leere Felder.
Einwortlabels werden nicht semantisch interpretiert. Formatprüfung darf
Horizontalraum am Skalarwert ignorieren; die ausgegebene Zeile bleibt exakt
unverändert. Freie Textwerte, unbeschriftete Skalare, Teilstücke und
Paraphrasen bleiben außerhalb dieses Vertrags. Normale vollständige
Originalaussagen aus demselben Dokument benutzen weiterhin den bisherigen
Prüfpfad.

Die native Ausgabe lautet immer `Quelle berichtet: „<ganze Raw-Zeile>“`.
Sie erzeugt keine bestätigte Personen-/Nutzerbehauptung, Datumsrolle oder
Handlung. Die vorhandene aktive Gegenprüfung erhält im selben Aufruf die
Frage separat, die exakte ganze Zeile und den unveränderten vollen Rawbeleg.
Der native JSON-Prüfauftrag verlangt sowohl Quellentreue als auch tatsächliche
Fragepassung einschließlich der erfragten Datumsrolle. Kein zusätzliches
Modell wird aufgerufen. Ein tragender Vorbehalt im vollen Rawtext darf nicht
entfallen: Ein bedingter Terminkopf außerhalb der unveränderten Row verlangt
`nein`/`unklar`. Inaktives Tor, nicht unterstützter Adapter,
`nein`/`unklar`, Timeout, Frage über 2000 Zeichen oder Rawbeleg über 4000
Zeichen führen zum bestehenden Zitat-/Unsicherheitsrückfall. Native Belege
werden nicht als Vollbeweis gefenstert.

Beim Wiederöffnen und HTTP-GET wird der aktuelle Nachweis erneut gelesen;
ein gespeichertes Ja genügt nicht. Der gespeicherte Prüfbezug bindet Frage,
exakte Zeile, aktuelle Quellverweise und Prüfmodell. Entzug der Elternmail
oder Quellenänderung entfernt die gültige gerenderte Satzstruktur. Der
bestehende interne gespeicherte Arbeitsstand bleibt historisch erhalten,
wird aber nicht erneut als gültige Antwort ausgegeben. Fehlende Antwort aus
der nativen Teilmenge wird nicht zur globalen Abwesenheitsbehauptung.

## Synthetischer End-to-end-Beleg

Echte MIME-Komposition → `remember` → generierter Anhangbody → WMA-Index →
`prepare` → Formulierung → aktive Fake-Gegenprüfung → `render`:

| Fall | alte freie Originaleinheit | Ergebnis | Prüfaufrufe |
|---|---:|---|---:|
| Passendes Prüfdatum, leeres Rücksendefeld | 534 Zeichen | kurzer wörtlicher Quellenbericht | 1 |
| Rücksendefrist gefragt, nur Prüfdatum gefüllt | 534 Zeichen | Zitat-/Unsicherheitsrückfall | 1 |

Der Fake-Prüfer erhielt jeweils die separate Frage und den gesamten
unveränderten 958-Zeichen-Rawbody. Die Quelle blieb unverändert, es entstanden
keine Claims. [Exakter synthetischer Laufnachweis](docx-native-rows-result.json).
Die kontrollierten Ja-/Nein-Antworten belegen Parser, Provenienz und Gates;
sie messen keine reale Modellqualität.

Neue Capture-Metadaten erzeugen über den vorhandenen Versionsweg eine normale
neue Quelle, auch bei gleichem Body. Alte Originale werden nicht umgeschrieben.
Alte Aufnahmen ohne Nachweis gewinnen durch diesen Commit keinen nativen
Status. Für diese Quellen bleibt erneutes normales Einlesen notwendig.

## Gezielte Prüfungen

RED auf der Basis war der vollständige MIME-Positivfall im Zitatmodus.
Die späte unabhängige Formularfrage wurde ebenfalls vor der engen Korrektur
RED reproduziert; eine normative Wenn-Einschränkung bleibt negativ.
Die einzelne Kopfbedingung „Die folgenden Termine gelten nur nach
schriftlicher Freigabe.“ bleibt vollständig im Rawbeleg. Ihr Test prüft
den ausdrücklichen Vorbehaltsauftrag und den bestehenden Nein-Rückfall;
er unterstellt einem Always-Ja-Fake kein semantisches Verständnis.

Der Abschlusslauf umfasst native MIME-/Parser-/Provenienzfälle, bestehende
DOCX-/Upload-/Anhang-/Retry-Prüfungen, Original-/Zitat-/Absatz-/Satzbindung,
Frische-/Bedingungskontexte sowie die Pflichtkernprüfungen aus
`CONTRIBUTING.md`. Keine komplette Suite. Der genaue Abschlussstand wird mit
dem Commitbericht übergeben: **730 bestanden in 52,30 Sekunden**, eine bereits
vorhandene Starlette/httpx-Deprecation-Warnung. Der Lauf verwendet
`PYTHONPATH=sidecar:.` und das vorhandene Python-3.12-Testvenv; keine Installation.

Die neuen Kontrollen enthalten außerdem manipulierte/doppelte Metadaten,
überlange/unsupported Rows, unvollständige Quellen, echte Quotes/Drafts,
Rollen-/Norm-/Personenaussagen, verschiedene Datumsrollen, Raw-Leerabsätze,
Skalar-Layoutspaces, inaktive/nicht unterstützte Prüfer, Timeout,
Frage-/Rawbudgets, gespeicherte Antwortmanipulation, neue SQLite-Verbindungen,
HTTP-GET nach Elternentzug und gewöhnliche Originalaussagen mit bzw. ohne
geeignete native Felder.

Kein Push, PR, Release oder persönliche Nachklassifikation. Der Root-Branch
bleibt für unabhängigen Review und die anschließende begrenzte Stichprobe
unverändert.
