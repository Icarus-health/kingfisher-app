# Mail im Gesprächsfenster

Stand 2026-08-01. Verbindlich für die `/mail`-Endpunkte in `server.py` und den
Posteingang in `app/kingfisher/src/` (`Messages.tsx`, `MailReader.tsx`).

Mail dort, wo man ohnehin schreibt: lesen, antworten, ins Gedächtnis nehmen —
ohne die Anwendung zu wechseln.

## Die eine Regel, die hier alles bestimmt

> **Jeder kann dir eine Mail schreiben.**

Das ist der gefährlichste Eingabekanal, den es gibt, und der einzige, bei dem
ein Fremder den Zeitpunkt bestimmt. Alles Weitere folgt daraus.

| Passiert | Passiert nie |
| --- | --- |
| Nachrichten lesen und anzeigen | Aus einer Mail wird eine Anweisung |
| Eine Antwort verfassen | Eine Antwort geht ohne Freigabe hinaus |
| Eine Mail als Episode aufnehmen | Aus einer Mail wird ein Fakt im Bestand |
| Den Wortlaut als fremd rahmen | Der Posteingang läuft von selbst ins Gedächtnis |

## Der Sendeknopf ist keine Abkürzung

Er ruft `POST /tools/mail_senden` — **dasselbe Werkzeug wie das Modell**. Damit
geht er durch Policy, Freigabe mit vollem Trockenlauf und Protokoll.

```
E-Mail senden
An:      Dr. Meier <meier@example.com>
Betreff: Re: Jour fixe Dienstag
Antwort auf: <abc123@example.com>
---
Zehn Uhr passt.
```

Der Knopf ist kein zweiter Weg an der Kontrolle vorbei, sondern derselbe Weg,
kürzer: Antwort tippen, senden, und die Freigabe steht direkt darüber.

**Die Bestätigung bleibt streng.** Außenwirksames verlangt, die Empfängeradresse
zu wiederholen. Bei einer Antwort wiegt das schwerer als sonst: Die Adresse
kommt aus `Reply-To`, und den setzt der Absender. Eine Mail, die aussieht, als
käme sie von Dr. Meier, kann `Reply-To: angreifer@example.com` tragen — die
Wiederholung ist genau die Stelle, an der das auffällt.

## Antworten hängen am Verlauf

`In-Reply-To` und `References` gehen mit. Ohne sie erscheint die Antwort beim
Empfänger als neue Nachricht statt im Verlauf, und wer zwanzig Mails am Tag
bekommt, findet sie dann nicht wieder.

Der Betreff bekommt `Re:` — aber nicht `Re: Re: Re:`.

## Ins Gedächtnis heißt Rohmaterial, nicht Wissen

`POST /mail/{uid}/remember` legt eine **Episode** an: `kind=message`,
`source_type=email`, `source_ref` die `Message-ID`, `occurred_at` der Zeitpunkt
der Mail. Der Bestand bleibt unberührt.

Der Unterschied ist der ganze Punkt und der Grund, warum der Knopf trotz der
Herkunft unbedenklich ist. Eine Episode hält fest, **dass etwas vorlag**; sie
behauptet nichts über die Person. Ob daraus eine dauerhafte Aussage folgt,
entscheidet die Verdichtung ([`10`](10-verdichtung.md)) — und die legt vor,
statt zu schreiben.

Eine Mail mit „IGNORIERE ALLE VORHERIGEN ANWEISUNGEN“ darf deshalb aufgenommen
werden: Sie ist eine Tatsache über den Absender. Was nicht passieren darf, ist
dass daraus ein Fakt oder eine Handlung wird — und beides prüft
`test_posteingang.py` ausdrücklich.

**Auf Zuruf, nicht von selbst.** Ein Posteingang, der vollständig in die
Episoden liefe, brächte Werbung und Newsletter mit, und jedes Stück davon ginge
später als Material ins Modell. Der Zeitplan ([`11`](11-zeitplan.md)) rührt Mail
deshalb nicht an.

## Der Wortlaut ist sichtbar fremd

Der geöffnete Text steht monospaced im selben Rahmen wie ein Trockenlauf. Er
darf nie so aussehen, als hätte Icarus ihn geschrieben — die Verwechslung von
Beleg und Behauptung ist der Fehler, gegen den das ganze Projekt gebaut ist.

## Was die Liste nicht trägt

`GET /mail` liefert Absender, Betreff, Datum und Vorschau — **keinen
Volltext**. Zwanzig ganze Mails sind ein Vielfaches der Datenmenge, und sie
stehen ohnehin zusammengefaltet da. Der volle Text kommt erst beim Öffnen über
`GET /mail/{uid}`.

Abgeschnitten wird im **Endpunkt**, nicht im Konnektor: So hängt die Zusage
daran, was ausgeliefert wird, statt daran, dass `inbox()` den Text zufällig
nicht füllt.

**Nichts wird als gelesen markiert.** IMAP wird durchgehend mit `readonly=True`
geöffnet. Wer seine Mail woanders bearbeitet, soll dort denselben Zustand
vorfinden — Icarus schaut zu, es räumt nicht auf.

## Zwei Fehler, die beim Prüfen auffielen

Beide von derselben Art: Der Code las die **Einstellungsdatei**, wo die
**Umgebung** die Wahrheit ist.

**Der Einrichtungsassistent löschte den Mailzugang.** `PUT /setup` räumte alle
bekannten Umgebungsvariablen weg, bevor es die Einstellungen neu anwandte. Wer
`ICARUS_IMAP_HOST=…` vor den Start setzte, verlor seinen Posteingang beim ersten
Speichern — still, ohne Meldung, und der Assistent speichert beim Überspringen.
Jetzt werden nur die Namen geräumt, die beim Start **aus der Datei** kamen;
`apply_to_env` meldet sie ohnehin zurück.

**Das Antwortfeld war grau, obwohl SMTP eingerichtet war.** `can_send` las
`settings.mail.smtp_host` statt der Umgebung — und daraus liest
`MailConfig.from_env`, also die tatsächlich wirksame Konfiguration.

## Welche Ordner

Die Aufnahme älterer Mails (`mail_intake.py`, [`46`](46-hintergrund.md)) liest je
Postfach feste Ordner, die `connectors/mail.py:folders()` beim Start einmal
ermittelt:

| Konto | Gelesen wird | Satz in der Oberfläche |
| --- | --- | --- |
| Gmail (Ordner mit SPECIAL-USE `\All`) | der Gesamtbestand, er enthält Posteingang, Gesendet und Archiv | „Posteingang, Gesendet und Archiv über den Gmail-Gesamtbestand; ohne Spam und Papierkorb.“ |
| Microsoft 365 (Graph) | `INBOX` und `SentItems` ([`50`](50-microsoft-365.md)) | „Posteingang und Gesendet; ohne Junk-E-Mail und Gelöschte Elemente.“ |
| Jedes andere IMAP-Konto (seit Oktober 2026) | `INBOX` **und** der Gesendet-Ordner: SPECIAL-USE `\Sent` (RFC 6154), sonst der erste Ordner mit einem üblichen Namen (`Sent`, `Sent Items`, `Sent Messages`, `Gesendet`, `Gesendete Objekte`, `Gesendete Elemente`, `INBOX.Sent`, `INBOX/Sent`; ohne Groß/Klein, `connectors.mail.GESENDET_NAMEN`) | „Posteingang und Gesendet; ohne Spam und Papierkorb.“ |
| IMAP-Konto ohne erkennbaren Gesendet-Ordner | nur `INBOX` | „Nur der Posteingang; gesendete und archivierte Mails sind bei diesem Konto nicht dabei.“ |

Papierkorb, Spam und Junk bleiben immer ausgeschlossen, auch wenn sie `\Sent`
tragen. Warum Gesendet: Ein Stabschef kennt die eigenen Zusagen. Die Logik
dafür war da (`task_review` mit `own_commitment`, `fristlage.richtung`
„von_mir“, „Was habe ich zugesagt?“ in [`17`](17-stabschef.md)), aber ohne
Gesendet fehlten bei jedem Konto außer Gmail und Microsoft die Daten.

**Konten von vor dem Umbau** sind mit nur dem Posteingang gestartet. Unter
Für Techniker → Zeitplan und Hintergrund → Ältere Mails einlesen steht bei
ihnen „Gesendete Mails auch einlesen“ (`POST /api/v1/mail/intake/{id}/ordner-ergaenzen`):
Kingfisher ermittelt die Ordner neu und trägt nur nach, was fehlt
(`Intake.ergaenzen`, kein zweiter Eintrag, eine Pause bleibt). Die Antwort ist
ein Satz: „Gesendete Mails werden jetzt mit eingelesen.“, „Gesendete Mails sind
schon dabei.“ oder „Dieses Postfach hat keinen Gesendet-Ordner, den Kingfisher
erkennt.“ Danach verschwindet der Knopf; im letzten Fall bis zum nächsten Start
der App (das Ergebnis der Ordnersuche wird nicht gespeichert). Der Stand sagt
währenddessen „Der Posteingang ist gelesen (5 Mails). Gesendete Mails werden
nachgelesen: bisher keine gefunden.“ statt aufs ganze Postfach „wird
durchgesehen“ zurückzufallen (`mail_stand.konto_stand`).

**Eigene Mails und der Filter.** Eine Mail, deren Absender eine eigene Adresse
ist (`Message.own_addresses`), geht ohne Werberegeln und ohne Modell in die
Aufnahme (`mail_intake._step`): Sie ist keine Werbung, und ein KI-Filter ohne
lokale KI hielte sonst jede eigene Zusage als „unklar“ zurück. Nur der
Spam-Kopf des eigenen Servers gilt weiter (`X-Spam-Flag`): Ein gefälschter
eigener Absender ist das klassische Spam-Muster, und den Kopf setzt der
Anbieter, nicht die Mail.

**Entwürfe.** Gmail führt Entwürfe im Gesamtbestand mit dem Flag `\Draft`. Sie
sind nichts, was geschah: nicht aufgenommen, aber gezählt (Status
`filtered:entwurf`, in der Oberfläche unter „ausgefiltert“), damit der Ordner
nicht für immer auf „4 von 5“ steht. „Erneut prüfen“ liest sie erneut und
überspringt sie wieder.

**Grenze: Mails an sich selbst.** Die Message-ID wird absichtlich nicht
ordnerübergreifend verglichen (`mail_ingestion._dieselbe_mail_im_konto`, nur
dieselbe Postfachkennung desselben Ordners). Eine Mail an die eigene Adresse
liegt im Posteingang und in Gesendet und wird zweimal zur Quelle, wie heute
schon bei Microsoft 365. Bewusst so gelassen: Eine fremde Message-ID darf keine
andere Mail ersetzen, und die Dublette ist sichtbar und harmlos.

## Schnittstelle

| Weg | Was |
| --- | --- |
| `GET /mail` | Liste ohne Volltext, Anzahl ungelesen, ob Senden geht |
| `GET /mail/{uid}` | Eine Nachricht mit vollem Text, `Message-ID`, Antwortadresse |
| `POST /mail/{uid}/remember` | Als Episode aufnehmen; `409` ohne Mailkonto |
| `POST /tools/mail_senden` | Erzeugt eine Freigabe, sendet nicht |

Ohne eingerichteten Mailzugang antworten alle mit `409` und einem Satz, der
sagt, was zu tun ist — statt eines nackten Fehlers.

## Was offen ist

**Kein Verfassen ohne Bezug.** Antworten geht, eine neue Mail von Hand
schreiben noch nicht. Über das Gespräch geht es (`mail_senden` als Werkzeug),
über den Posteingang nicht.

**Keine Anhänge.** Weder lesen noch senden. Anhänge sind der zweite gefährliche
Kanal nach dem Text selbst, und sie gehören eigens bedacht.

**Nur `text/plain`.** Eine reine HTML-Mail zeigt einen leeren Text. Das ist
ehrlicher als ein halbherziger Umbau, aber es fehlt.

**Kein Ordnerwechsel im Posteingang.** Die Liste im Gesprächsfenster zeigt
INBOX; die Aufnahme älterer Mails liest daneben Gesendet (oben, „Welche Ordner“).

## Verwandte Dokumente

- [`03-delegation.md`](03-delegation.md) — Aktionsklassen und Freigaben
- [`05-sicherheit.md`](05-sicherheit.md) — warum fremder Text eingerahmt wird
- [`08-gedaechtnisschichten.md`](08-gedaechtnisschichten.md) — was eine Episode ist
- [`13-nutzerfreundlichkeit.md`](13-nutzerfreundlichkeit.md) — wie der Zugang eingerichtet wird
