# Paket K: Konten und Bereiche (26.10.2026)

Wunsch des Nutzers ([66-automatik.md](../../66-automatik.md)): Postfach und Kalender verlässlich und einfach, auch mit
mehreren Konten; Privat und Arbeit (oder eigene Bereiche) in Kalender und Aufgaben unterscheiden. Entscheidung:
**Bereich je Postfach und Kalender**, Kingfisher schlägt vor, der Mensch bestätigt einmal, alles Weitere erbt.
Beschreibung der Funktion: [47-einstellungen.md, „Konten und Bereiche“](../../47-einstellungen.md#konten-und-bereiche-paket-k-26102026).

## Was gebaut ist

* **Name je Konto**: Umbenennen mit einem Klick auf den Namen (Enter, Escape), Name je Art eindeutig. Neue
  Passwort-Postfächer heißen nach ihrer Adresse; zwei gleichnamige (früher „Gmail / Google Workspace“ zweimal) heißen
  beim Start nach ihrer Adresse. Ein doppeltes Passwort-Postfach wird erkannt: ein Satz statt eines zweiten Eintrags.
* **Bereich je Konto mit Vorschlag**: private Anbieter-Adresse → Privat, eigene Domäne → Arbeit; Kalender aus dem Namen,
  dem Postfach derselben Adresse oder der Adresse; sonst keiner („Welcher Bereich?“). Der Vorschlag steht als Satz mit
  Grund da, „Übernehmen“ ist ein Klick, „Alle Vorschläge übernehmen“ ab zwei; eigene Bereiche mit Namen. Gespeichert wird
  nur Bestätigtes (`Settings.konten`), ohne Migration. Jede Änderung antwortet mit dem Hinweis und „Rückgängig“.
* **Stand je Konto in einem Satz** unter Zugänge („Zuletzt gelesen vor 4 Min.“, Fehler rot mit Weg). Kalender: aus dem
  letzten Lesen oder Abgleich; Mac-Kalender aus dem Stand des Mac-Helfers.
* **Vererbung** (`sidecar/icarus_memory/bereiche.py`, öffentlich für die Pakete A und P): Mail → Postfach, Termin →
  Kalender, Aufgabe → Quelle, sonst Projekt; Projekt → `area`, sonst überwiegender Bereich der Quellen. Feld `bereich`
  in `/api/v1/calendar`, `/api/v1/tasks`, `/api/v1/projects`, `/api/v1/local-mail`.
* **Filter** „Alle · Arbeit · Privat · …“ auf Kalender- und Aufgabenseite (nur ab zwei Bereichen), Wahl je Seite
  gemerkt. Ausgeblendete Kalender bleiben ausgeblendet (gespeichert statt beim Neuladen vergessen).

## Zahlen

* Neu: `sidecar/tests/test_konten_bereiche.py` (20 Tests: Vorschlag, Vererbung für Mail, Mac-Kalender, Aufgabe,
  Projekt, Routen für Name, Bereich, eigenen Bereich, ausgeblendete Kalender, doppeltes Postfach, eindeutige Namen,
  Stand je Postfach und Kalender, Felder in Aufgaben, Projekten, Mails, Terminen) und
  `app/kingfisher/tests/konten-bereiche.test.mjs` (6 Tests). Angepasst: `postfach-weg.test.mjs` (Name nach Adresse).
* Volle Backend-Suite (`-n 4`, Rechner unter Last anderer Pakete): 8.051 bestanden, 3 skipped, 3 fehlgeschlagen. Allein
  wiederholt: `test_cloud_access.py::…source_scoped` und `test_ical_termine.py::…unter_einer_sekunde…` grün (Zeitgrenzen
  unter Last); `test_cloud_memory.py::test_bulk_accepts_101…` (bekannt lastabhängig, Faden noch am Leben) auch allein bei
  Last um 10 rot, von diesem Paket nicht berührt.
* Oberfläche: `tsc --noEmit` ohne Befund, `node --test tests/*.test.mjs` 932 bestanden, `vite build` grün.
* `scripts/probe_seiten_ui.py` hell und dunkel: 75 Breiten geprüft, 0 Befunde.

## Sabotageproben

Jede Zusicherung einmal gebrochen, der passende Test wurde rot, danach zurückgesetzt:

| Bruch | rot |
|---|---|
| private Anbieter als Arbeit | `test_vorschlag_postfach…`, `test_vorschlag_kalender…`, `test_konten_zeigen_vorschlag…` |
| Aufgabe: Projekt vor Quelle | `test_aufgabe_erbt_von_quelle_sonst_vom_projekt` |
| Projekt ohne Mehrheit bekommt trotzdem einen Bereich | `test_projekt_ohne_area_nimmt_den_ueberwiegenden…` |
| unbestätigter Vorschlag vererbt sich | `test_nur_bestaetigtes_vererbt_sich` |
| doppeltes Postfach nicht erkannt | `test_doppeltes_passwort_postfach_wird_erkannt` |
| gleichnamige Postfächer nicht umbenannt | `test_zwei_gmail_konten…`, `test_umbenennen…`, `test_doppeltes…` |
| ausgeblendete Kalender nicht gespeichert | `test_ausgeblendete_kalender_bleiben_gespeichert` |
| Verweis „unter Einstellungen → Zugänge“ bleibt im Zugänge-Satz | `test_stand_in_einem_satz` |
| Filter schon ab einem Bereich | „Den Filter gibt es erst ab zwei Bereichen …“ |
| Einträge ohne Bereich passen zu jedem Filter | „Gefiltert wird genau nach dem Bereich …“ |
| „Alle übernehmen“ nimmt auch Bestätigte mit | zuerst **nicht** gefangen; Test um ein bestätigtes Konto mit Vorschlag ergänzt, dann rot |

## Browser

`scripts/probe_konten_ui.py` (Chromium, synthetische Konten: zwei Gmail-Adressen, ein Firmenpostfach
`winter-catering.example`, zwei Kalender „Arbeit“ und „Gemeinsam“; Attrappen für Kalenderleser und Postfachzugang,
kein Netz): Namen nach Adresse, Stand, Vorschläge mit Grund, „Alle Vorschläge übernehmen“ mit Rückgängig, eigener
Bereich „Verein“, Umbenennen bleibt nach dem Neuladen; Kalenderfilter „Arbeit“ zeigt nur den Arbeitstermin und bleibt
nach dem Neuladen gewählt; ein ausgeblendeter Kalender bleibt ausgeblendet; Aufgabenfilter „Privat“. 390 px ohne
seitliches Rollen. Konsole ohne Fehler.

| Bild | Inhalt |
|---|---|
| [konten-1-zugaenge.jpg](konten-1-zugaenge.jpg) | Zugänge mit Vorschlägen, Stand, „Welcher Bereich?“ (1280, hell) |
| [konten-1-zugaenge-390.jpg](konten-1-zugaenge-390.jpg) | dasselbe bei 390 px |
| [konten-2-eigener-bereich.jpg](konten-2-eigener-bereich.jpg) | eigener Bereich „Verein“, Hinweis mit Rückgängig |
| [konten-3-zugaenge-fertig.jpg](konten-3-zugaenge-fertig.jpg) | bestätigt: Bereiche als Pille, „Familie“ umbenannt |
| [konten-4-kalender-arbeit.jpg](konten-4-kalender-arbeit.jpg), [390](konten-4-kalender-390.jpg) | Kalender, Filter „Arbeit“ |
| [konten-5-aufgaben-privat.jpg](konten-5-aufgaben-privat.jpg), [390](konten-5-aufgaben-390.jpg) | Aufgaben, Filter „Privat“ |
| [konten-6-zugaenge-dunkel.jpg](konten-6-zugaenge-dunkel.jpg) | Zugänge dunkel |

## Grenzen

* Der Filter auf **Heute** fehlt noch (66-automatik.md nennt ihn); `TodayOverview.tsx` ist geteilt, die Felder
  `bereich` an Terminen und Aufgaben sind dafür da.
* Der Aufgabenfilter wirkt auf die geladene Seite (bis 200 Aufgaben); die Zahlen an den Segmenten zählen ungefiltert.
* Der Stand eines Kalenders ist nur im Speicher; nach einem Neustart steht „Wird beim nächsten Abgleich gelesen.“, bis
  Kalenderseite, Heute oder der Abgleich ihn gelesen haben.
* Ein Projekt, dessen `area` keinen Bereich nennt (etwa „Garten“), nimmt den Bereich seiner Quellen.
* Die gemerkte Filterwahl liegt im Browser; die ausgeblendeten Kalender liegen in der Konfiguration.
* Abnahme am Mac mit echten Konten steht aus.
