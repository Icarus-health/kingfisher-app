import {MemoryEntityLink} from "./MemoryEntityLink";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ApiError, api, type Akte, type AkteBrauchtDich, type AkteEntscheidung, type AkteLage, type AkteRichtung, type AkteVorschlagStand, type AkteZeile, type AkteZeitpunkt } from "./api";
import { entscheidungSatz, fehlerSatz, vorschlagFrage, zurueckBeschriftung } from "./akteVorschlag";
import { blickZeile, obenGenanntSatz, offenOhneBrauchtDich, standSatz, termineObenGenannt, type StandSatz } from "./akteAnzeige";
import { displayLabel } from "./displayIdentity";
import { ArtKarte, GeburtstagKarte, KreisKarte } from "./KreisKarten";
import { WiederkehrendKarte } from "./WiederkehrendKarte";
import { ProfileSource } from "./ProfileSource";
import { Sidebar } from "./chrome";
import { navigate } from "./ui";
import { memoryReturnPath } from "./profileReturn";
import { InterfaceIcon } from "./InterfaceIcon";
import { Leer, zeigeHinweis } from "./grundlage";
import { initials } from "./WorkspaceMemoryModel";
import "./AkteAbschnitte.css";
import "./Gedaechtnis.css";

const BETEILIGT_ART: Record<string, string> = { person: "Person", organisation: "Organisation", projekt: "Projekt", ort: "Ort", thema: "Thema" };
const BETEILIGT_ZEICHEN: Record<string, "people" | "building" | "project" | "pin" | "brain"> = { person: "people", organisation: "building", projekt: "project", ort: "pin", thema: "brain" };

const TAG = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric", year: "numeric" });
const TAG_ZEIT = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

const KURZTAG = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric" });
const MONAT = new Intl.DateTimeFormat("de-DE", { month: "short", year: "2-digit" });
const LANGTAG = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "long", year: "numeric" });

const ERSTELLT = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

function tag(value: string | null | undefined) {
  if (!value) return "";
  // Ein reines Datum („2026-11-12“) ist ein Kalendertag, keine Uhrzeit in UTC.
  const zeit = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
  return Number.isNaN(zeit.getTime()) ? "" : TAG.format(zeit);
}

function zeitpunkt(value: string | null | undefined) {
  if (!value) return null;
  const zeit = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
  return Number.isNaN(zeit.getTime()) ? null : zeit;
}

function datum(zeile: AkteZeile) {
  return zeile.occurred_at ? tag(zeile.occurred_at) : `erfasst ${tag(zeile.recorded_at)}`;
}

function Quelle({ zeile }: { zeile: { episode_id: string; titel: string } }) {
  return <ProfileSource kind="episode" id={zeile.episode_id} label={zeile.titel ? `Quelle: ${zeile.titel}` : "Quelle öffnen"} quiet />;
}

function Zeile({ zeile, zusatz }: { zeile: AkteZeile; zusatz?: ReactNode }) {
  return <article>
    <small>{zeile.art} · {datum(zeile)}{zeile.participants.length ? ` · ${displayLabel(zeile.participants[0]).name}` : ""}{zusatz ? ` · ${zusatz}` : ""}</small>
    <blockquote>{zeile.text}</blockquote>
    <Quelle zeile={zeile} />
  </article>;
}

const GRUND: Record<string, string> = { erledigt: "Später als erledigt gemeldet", absage: "Später abgesagt", aufgabe_erledigt: "Aufgabe erledigt", aufgabe_verworfen: "Aufgabe fallengelassen", nutzer_erledigt: "Von dir als erledigt abgelegt", nutzer_gilt_nicht: "Gilt laut dir nicht mehr" };
/** Was nach einem Klick dasteht (Grundsatz 4: Jede Aktion antwortet). */
const GEMERKT: Record<AkteEntscheidung, string> = { erledigt: "Als erledigt abgelegt.", gilt_nicht: "Abgelegt: gilt nicht mehr.", offen: "Gemerkt: gilt weiter." };
const GEMERKT_TERMIN: Record<AkteEntscheidung, string> = { erledigt: "Gemerkt: abgesagt und erledigt.", gilt_nicht: "Gemerkt.", offen: "Gemerkt: findet statt." };

/** Von wem ein Punkt stammt, in einem Satzteil: „Deine Zusage“, „Bitte von Silke Vogt“. */
function herkunft(e: { art: string; participants: string[]; richtung?: AkteRichtung }) {
  const wer = e.participants.length ? displayLabel(e.participants[0]).name : "";
  if (e.richtung === "von_mir") return e.art === "Zusage" ? "Deine Zusage" : e.art === "Bitte" ? "Deine Bitte" : `${e.art} von dir`;
  if (e.richtung === "an_mich" && wer) return `${e.art} von ${wer}`;
  return wer ? `${e.art} · ${wer}` : e.art;
}

type Entscheiden = (ziel: string, entscheidung: AkteEntscheidung, termin?: boolean) => void;
const GRUNDLAGE: Record<string, string> = { anker: "Adresse oder Zuordnung", modell: "Im Text erkannt", nutzer: "Von dir" };

/** Ein Abschnitt der Akte als Gruppe der Grundlage: die Überschrift klein über der Fläche, darunter höchstens ein Satz. */
function Teil({ titel, kind, fussnote, neben, children }: { titel: string; kind?: string; fussnote?: ReactNode; neben?: ReactNode; children: ReactNode }) {
  return <section className={`mappe-teil akte-teil g-gruppe${kind ? ` akte-${kind}` : ""}`} aria-label={titel}>
    <div className="g-gruppe-kopf"><h3 className="g-gruppe-titel">{titel}</h3>{neben ? <span className="akte-teil-neben">{neben}</span> : null}</div>
    <div className="g-flaeche akte-flaeche">{children}</div>
    {fussnote ? <p className="g-gruppe-fussnote">{fussnote}</p> : null}
  </section>;
}

function Gesamt({ gezeigt, gesamt, wo }: { gezeigt: number; gesamt: number; wo?: string }) {
  // Keine stille Grenze: Was nicht gezeigt wird, wird gezählt.
  return gesamt > gezeigt ? <p className="mappe-mehr">{gezeigt} von {gesamt}{wo ? ` · ${wo}` : ""}</p> : null;
}

/** Auf einen Blick: wenige Zahlen und Tage, die man sonst zusammensuchen müsste. Eine leise Zeile, keine Kacheln;
 * eine Null wird nicht gezählt. */
function Blick({ data, art }: { data: Akte; art?: string }) {
  const termin = data.termine.kommend[0];
  const frist = data.fristen.kommend[0];
  // „Zuletzt“ ist die jüngste Quelle bis heute, nicht ein Termin, der noch kommt.
  const jetzt = zeitpunkt(data.stand) ?? new Date();
  const zuletzt = data.verlauf.eintraege.find(e => (zeitpunkt(e.datum) ?? jetzt) <= jetzt);
  const zeile = blickZeile({ offen: data.offen.gesamt, frist: frist ? KURZTAG.format(zeitpunkt(frist.datum) ?? new Date()) : null,
    termin: termin ? KURZTAG.format(new Date(termin.start)) : null, abgesagt: Boolean(termin?.vermutlich_abgesagt), zuletzt: zuletzt ? tag(zuletzt.datum) : null });
  const ganz = [art, zeile].filter(Boolean).join(" · ");
  return ganz ? <p className="akte-blick" aria-label="Auf einen Blick">{ganz}</p> : null;
}

/** Der Stand in einem Satz unter dem Namen (`standSatz`): Art, Tag, Titel der Quelle, Absender, dazu das Nächste. Der
 * Titel ist ein Verweis und öffnet die Quelle unter dem Kopf in voller Breite; nichts davon ist geschrieben oder geraten. */
function StandKopf({ satz, offen, umschalten }: { satz: StandSatz; offen: boolean; umschalten: () => void }) {
  return <div className="akte-stand-satz" aria-label="Stand">
    <p>{satz.vor}<button type="button" className="akte-stand-quelle" aria-expanded={offen} aria-controls="akte-stand-original" title={offen ? "Quelle schließen" : "Quelle öffnen"} onClick={umschalten}>{satz.titel}</button>{satz.nach}{satz.naechstes ? <> <span className="akte-stand-naechstes">{satz.naechstes}</span></> : null}</p>
  </div>;
}

/** Braucht dich: was eine Entscheidung braucht. Ein Satz, das Zitat, ein Klick; die Antwort gilt in jeder Akte. */
function BrauchtDich({ punkte, gesamt, arbeitet, entscheiden, aufgabeZurueck }: { punkte: AkteBrauchtDich[]; gesamt: number; arbeitet: string | null; entscheiden: Entscheiden; aufgabeZurueck: (ziel: string, aufgabeId: string) => void }) {
  if (!punkte.length) return null;
  return <section className="akte-braucht g-gruppe" aria-label="Braucht dich">
    <div className="g-gruppe-kopf"><h3 className="g-gruppe-titel">Braucht dich</h3>{gesamt > 1 ? <span className="akte-zahl">{gesamt}</span> : null}</div>
    <ol className="g-flaeche akte-flaeche">
      {punkte.map(p => <li key={p.ziel} aria-busy={arbeitet === p.ziel}>
        <p className="akte-braucht-satz">{p.art === "aufgabe_post" && p.aufgabe ? <>„{p.aufgabe.title}“: {p.satz}</> : p.satz}</p>
        {p.zeile ? <blockquote>{p.zeile.text}</blockquote> : null}
        <div className="akte-braucht-fuss">
          <div className="akte-wahl">
            {p.wahl.map(w => <button key={w.entscheidung} type="button" className="akte-knopf g-knopf-getoent g-kompakt" disabled={arbeitet !== null} onClick={() => entscheiden(p.ziel, w.entscheidung, p.art === "abgesagter_termin")}>{w.text}</button>)}
            {p.art === "aufgabe_post" && p.aufgabe ? <button type="button" className="akte-knopf akte-knopf-leise" disabled={arbeitet !== null} onClick={() => aufgabeZurueck(p.ziel, p.aufgabe!.id)}>Rückgängig</button> : null}
          </div>
          <div className="akte-belege">
            {p.zeile ? <Quelle zeile={p.zeile} /> : null}
            {p.laut ? <ProfileSource kind="episode" id={p.laut.episode_id} label={`Laut: ${p.laut.titel || "Quelle"}`} quiet /> : null}
            {p.art === "aufgabe_post" && p.episode_id ? <ProfileSource kind="episode" id={p.episode_id} label="Mail öffnen" quiet readOnly allowIgnore={false} /> : null}
          </div>
        </div>
      </li>)}
    </ol>
    {gesamt > punkte.length ? <p className="g-gruppe-fussnote">{gesamt - punkte.length} weitere stehen unten bei „Offen“ und „Fristen“.</p> : null}
  </section>;
}

/** Neue Akte?: ein nur erwähntes Projekt, das sich in den Quellen bildet. Frage, Grund, Textstellen, zwei Knöpfe;
 * angelegt ist nichts, bis geklickt wird. Danach steht die Entscheidung da und lässt sich zurücknehmen. */
function NeueAkte({ stand, arbeitet, anlegen, ablehnen, zurueck }: { stand: AkteVorschlagStand; arbeitet: string | null; anlegen: (kennung: string) => void; ablehnen: (kennung: string) => void; zurueck: (kennung: string) => void }) {
  const v = stand.vorschlag;
  const e = stand.entscheidung;
  if (v) return <section className="akte-braucht akte-neue g-gruppe" aria-label="Neue Akte?" aria-busy={arbeitet === v.kennung}>
    <div className="g-gruppe-kopf"><h3 className="g-gruppe-titel">Neue Akte?</h3></div>
    <div className="g-flaeche g-flaeche-frei">
    <p className="akte-braucht-satz">{vorschlagFrage(v.grund)}</p>
    <ul className="akte-neue-quellen">{v.quellen.map(q => <li key={q.episode_id}>{q.zitat ? <q>{q.zitat}</q> : null} <Quelle zeile={q} /></li>)}</ul>
    {v.anzahl > v.quellen.length ? <p className="mappe-mehr">{v.quellen.length} von {v.anzahl} Quellen</p> : null}
    <div className="akte-wahl">
      <button type="button" className="akte-knopf g-knopf g-kompakt" disabled={arbeitet !== null} onClick={() => anlegen(v.kennung)}>Akte anlegen</button>
      <button type="button" className="akte-knopf akte-knopf-leise g-knopf-schlicht g-kompakt" disabled={arbeitet !== null} onClick={() => ablehnen(v.kennung)}>Nein danke</button>
    </div>
    </div>
  </section>;
  if (e) return <p className="mappe-hinweis akte-neue-stand">{entscheidungSatz(e.entscheidung, e.quellen)} <button type="button" className="akte-knopf akte-knopf-leise" disabled={arbeitet !== null} onClick={() => zurueck(e.kennung)}>{zurueckBeschriftung(e.entscheidung)}</button></p>;
  return null;
}

/** Der Hinweis (grundlage/hinweisOrt.ts) gehört der App, nicht der Akte: Sein „Rückgängig“ meldet mit diesem Ereignis,
 * dass die offene Akte neu laden soll – auch wenn sie inzwischen eine andere ist (etwa nach „Akte anlegen“). */
const AKTE_GEAENDERT = "kingfisher-akte-geaendert";
function akteGeaendert() { if (typeof window !== "undefined") window.dispatchEvent(new Event(AKTE_GEAENDERT)); }
/** „Neue Akte?“ zurücknehmen: Hat sich damit die Akte geändert, in der man steht (die neue gibt es dann nicht mehr), führt
 * der Weg zu der, die der Sidecar nennt; sonst lädt die offene Akte neu. Gibt den Satz des Sidecars zurück. */
function vorschlagZurueckWeg(kennung: string) {
  return async () => {
    const antwort = await api.akteVorschlagZuruecknehmen(kennung);
    if (typeof window !== "undefined" && decodeURIComponent(window.location.pathname) !== decodeURIComponent(antwort.link.split("?")[0])) navigate(antwort.link);
    else akteGeaendert();
    return antwort.satz;
  };
}

const SPUREN: Array<{ art: AkteZeitpunkt["art"]; text: string }> = [{ art: "quelle", text: "Mails und Notizen" }, { art: "termin", text: "Termine" }, { art: "frist", text: "Fristen" }];
const QUELLE_ART: Record<string, string> = { message: "Mail", document: "Notiz", event: "Termin" };

/** Der Zeitstrahl: Quellen, Termine und Fristen auf einer Achse, „heute“ als Linie. Ein Punkt öffnet seine Quelle. */
function Zeitstrahl({ strahl }: { strahl: NonNullable<Akte["zeitstrahl"]> }) {
  const [gewaehlt, setGewaehlt] = useState<AkteZeitpunkt | null>(null);
  const [fokus, setFokus] = useState(0);
  const bahnRef = useRef<HTMLDivElement | null>(null);
  const punkte = strahl.punkte.map(p => ({ p, zeit: zeitpunkt(p.datum) })).filter((x): x is { p: AkteZeitpunkt; zeit: Date } => x.zeit !== null);
  const heute = zeitpunkt(strahl.heute) ?? new Date();
  if (punkte.length < 2) return null;
  const zeiten = [...punkte.map(x => x.zeit.getTime()), heute.getTime()];
  const tag_ms = 86400000;
  let von = Math.min(...zeiten), bis = Math.max(...zeiten);
  const rand = Math.max((bis - von) * 0.04, 3 * tag_ms);
  von -= rand; bis += rand;
  const lage = (zeit: number) => ((zeit - von) / (bis - von)) * 100;
  // Marken je Monat; bei langen Zeiträumen nur jedes Quartal oder Jahr.
  const monate = (bis - von) / (30 * tag_ms);
  const schritt = monate > 48 ? 12 : monate > 14 ? 3 : 1;
  const marken: Date[] = [];
  const start = new Date(von); start.setDate(1); start.setHours(0, 0, 0, 0);
  for (let m = new Date(start); m.getTime() <= bis; m.setMonth(m.getMonth() + 1)) {
    // Am Rand fiele die Beschriftung aus der Karte.
    if (m.getTime() >= von && m.getMonth() % schritt === 0 && lage(m.getTime()) > 3 && lage(m.getTime()) < 95) marken.push(new Date(m));
  }
  // Was fast am selben Tag liegt, steht übereinander statt aufeinander.
  const ebenen = new Map<AkteZeitpunkt, number>();
  for (const spur of SPUREN) {
    let letzte = -100, ebene = 0;
    for (const x of punkte.filter(y => y.p.art === spur.art).sort((a, b) => a.zeit.getTime() - b.zeit.getTime())) {
      const links = lage(x.zeit.getTime());
      ebene = links - letzte < 1.6 ? Math.min(ebene + 1, 2) : 0;
      letzte = links;
      ebenen.set(x.p, ebene);
    }
  }
  // Ein Tab-Stopp für den ganzen Strahl; die Pfeiltasten gehen von Punkt zu Punkt in der Zeitfolge.
  const folge = [...punkte].sort((a, b) => a.zeit.getTime() - b.zeit.getTime()).map(x => x.p);
  const nummer = new Map(folge.map((p, i) => [p, i]));
  const aktiv = Math.min(fokus, folge.length - 1);
  const tasten = (ereignis: KeyboardEvent) => {
    const ziel = ereignis.key === "ArrowRight" || ereignis.key === "ArrowDown" ? aktiv + 1
      : ereignis.key === "ArrowLeft" || ereignis.key === "ArrowUp" ? aktiv - 1
      : ereignis.key === "Home" ? 0 : ereignis.key === "End" ? folge.length - 1 : null;
    if (ziel === null) return;
    ereignis.preventDefault();
    const neu = Math.max(0, Math.min(folge.length - 1, ziel));
    setFokus(neu);
    bahnRef.current?.querySelector<HTMLButtonElement>(`[data-punkt="${neu}"]`)?.focus();
  };
  const beschreibung = (p: AkteZeitpunkt) => `${p.art === "frist" ? "Frist" : p.art === "termin" ? "Termin" : (QUELLE_ART[p.quelle_art] ?? "Quelle")} ${tag(p.datum)}: ${p.titel}${p.abgesagt ? " (vermutlich abgesagt)" : ""}${p.art === "frist" && p.offen ? " (offen)" : ""}`;
  return <section className="mappe-teil akte-teil akte-zeitstrahl g-gruppe" aria-label="Zeitstrahl">
    <div className="g-gruppe-kopf"><h3 className="g-gruppe-titel">Zeitstrahl</h3></div>
    <div className="g-flaeche g-flaeche-frei">
    <div className="akte-strahl" ref={bahnRef} onKeyDown={tasten} role="group" aria-label="Zeitstrahl: mit den Pfeiltasten von Punkt zu Punkt">
      {SPUREN.filter(spur => punkte.some(x => x.p.art === spur.art)).map(spur => <div className="akte-spur" key={spur.art}>
        <span className="akte-spur-name">{spur.text}</span>
        <div className="akte-spur-bahn">
          {punkte.filter(x => x.p.art === spur.art).map(x => <button key={nummer.get(x.p)} type="button" data-punkt={nummer.get(x.p)}
            tabIndex={nummer.get(x.p) === aktiv ? 0 : -1} onFocus={() => setFokus(nummer.get(x.p) ?? 0)}
            className={`akte-punkt akte-punkt-${x.p.art}${x.p.abgesagt ? " akte-punkt-abgesagt" : ""}${x.p.offen ? " akte-punkt-offen" : ""}${x.p.abschnitt === "Zusage" || x.p.abschnitt === "Bitte" ? " akte-punkt-zusage" : ""}${gewaehlt === x.p ? " akte-punkt-gewaehlt" : ""}`}
            style={{ left: `${lage(x.zeit.getTime())}%`, top: `${8 + (ebenen.get(x.p) ?? 0) * 9}px` }}
            aria-label={beschreibung(x.p)} title={beschreibung(x.p)} aria-pressed={gewaehlt === x.p}
            onClick={() => setGewaehlt(gewaehlt === x.p ? null : x.p)} />)}
        </div>
      </div>)}
      <div className="akte-achse" aria-hidden="true">
        {marken.map(m => <span key={m.getTime()} style={{ left: `${lage(m.getTime())}%` }}>{MONAT.format(m)}</span>)}
      </div>
      <div className="akte-heute" style={{ left: `calc(var(--akte-spurname) + (100% - var(--akte-spurname)) * ${lage(heute.getTime()) / 100})` }} aria-hidden="true"><span>heute</span></div>
    </div>
    {gewaehlt ? <div className="akte-strahl-wahl">
      <small>{LANGTAG.format(zeitpunkt(gewaehlt.datum) ?? new Date())} · {gewaehlt.art === "frist" ? "Frist" : gewaehlt.art === "termin" ? "Termin" : (QUELLE_ART[gewaehlt.quelle_art] ?? "Quelle")}{gewaehlt.abschnitt ? ` · ${gewaehlt.abschnitt}` : ""}</small>
      <ProfileSource key={`${gewaehlt.episode_id}:${gewaehlt.datum}`} kind="episode" id={gewaehlt.episode_id} label={gewaehlt.titel || "Quelle öffnen"} embedded readOnly />
    </div> : null}
    </div>
    <p className="g-gruppe-fussnote">{strahl.gezeigt < strahl.quellen ? `Die jüngsten ${strahl.gezeigt} von ${strahl.quellen} Quellen. ` : ""}Ein Punkt öffnet seine Quelle.</p>
  </section>;
}

/** Ein offener Punkt: wer, wann, das Zitat, die Quelle und ein Klick für „erledigt“. */
function OffenZeile({ e, arbeitet, entscheiden, zuruecknehmen }: { e: Akte["offen"]["eintraege"][number]; arbeitet: string | null; entscheiden: Entscheiden; zuruecknehmen: (ziel: string) => void }) {
  return <article aria-busy={arbeitet === e.ziel}>
    <small>{herkunft(e)} · {datum(e)}{e.aufgabe ? ` · Aufgabe: ${e.aufgabe.title}` : ""}{e.bestaetigt ? " · laut dir weiter offen" : ""}</small>
    <blockquote>{e.text}</blockquote>
    {e.danach_geaendert ? <p className="mappe-mehr">Danach: „{e.danach_geaendert.text}“ ({datum(e.danach_geaendert)})</p> : null}
    <div className="akte-zeile-fuss">
      <Quelle zeile={e} />
      {e.ziel ? <button type="button" className="akte-knopf akte-knopf-leise" disabled={arbeitet !== null} onClick={() => entscheiden(e.ziel!, "erledigt")}>Erledigt</button> : null}
      {e.ziel && e.bestaetigt ? <button type="button" className="akte-knopf akte-knopf-leise" disabled={arbeitet !== null} onClick={() => zuruecknehmen(e.ziel!)} title="„Gilt weiter“ zurücknehmen">Rückgängig</button> : null}
    </div>
  </article>;
}

const OFFEN_GRUPPEN: Array<{ titel: string; passt: (e: Akte["offen"]["eintraege"][number]) => boolean }> = [
  { titel: "Du hast zugesagt", passt: e => e.richtung === "von_mir" && e.art === "Zusage" },
  { titel: "Du wartest auf", passt: e => (e.richtung === "an_mich" && e.art === "Zusage") || (e.richtung === "von_mir" && e.art === "Bitte") },
  { titel: "Bitten an dich", passt: e => e.richtung === "an_mich" && e.art === "Bitte" },
];

/** Die Lage (Ebene 3): das Wichtigste in zwei, drei Sätzen. Jeder Satz nennt seine Quellen; ein Klick öffnet das Original. */
function Lage({ lage }: { lage: AkteLage }) {
  const erstellt = new Date(lage.erstellt_am);
  return <section className="mappe-teil akte-teil akte-lage g-gruppe" aria-label="Lage">
    <div className="g-gruppe-kopf"><h3 className="g-gruppe-titel">Lage</h3></div>
    <div className="g-flaeche g-flaeche-frei">
    <ol>
      {lage.saetze.map((satz, index) => <li key={index}>
        <p>{satz.text}</p>
        <div className="akte-belege"><small>Belege</small>
          {satz.belege.map(b => <ProfileSource key={`${b.nummer}:${b.episode_id}`} kind="episode" id={b.episode_id} label={b.titel || "Quelle öffnen"} quiet />)}
        </div>
      </li>)}
    </ol>
    </div>
    <p className="g-gruppe-fussnote">
      {lage.veraltet ? "Stand vom" : "Erstellt"} {Number.isNaN(erstellt.getTime()) ? "" : `${lage.veraltet ? "" : "am "}${ERSTELLT.format(erstellt)} `}· aus {lage.quellen === 1 ? "einer Quelle" : `${lage.quellen} Quellen`}
      {" "}· von einem lokalen Modell geschrieben, Satz für Satz gegen die Quellen geprüft{lage.verworfen ? ` (${lage.verworfen === 1 ? "ein Satz" : `${lage.verworfen} Sätze`} ohne ausreichenden Beleg verworfen)` : ""}.
    </p>
    {lage.wird_aktualisiert ? <p className="g-gruppe-fussnote akte-lage-alt" role="status">Die Akte hat sich seitdem geändert. Die Lage wird aktualisiert; bis dahin stehen hier nur Sätze, die eine neuere Meldung nicht überholt haben.</p> : null}
  </section>;
}

/** Die Akte einer Sache (Ebene 2): Stand, Offen, Fristen, Termine, Beteiligte, Verlauf. Jede Zeile führt zur Quelle. */
export function AkteAnsicht({ sache, fallback, mitKopf = false, compact = false }: { sache: string; fallback?: ReactNode | null; mitKopf?: boolean; compact?: boolean }) {
  const [data, setData] = useState<Akte | null>(null);
  const [zustand, setZustand] = useState<"laedt" | "keine" | "fehler" | "ok">("laedt");
  const [alle, setAlle] = useState(false);
  const [avatarId,setAvatarId]=useState<string|null>(null);
  useEffect(()=>{
    let active=true;setAvatarId(null);
    if(!mitKopf||!data) return;
    if(data.art==='organisation'){setAvatarId(data.sache);return;}
    if(data.art==='person') {
      const identity=data.sache.startsWith('person:a:') ? data.sache.slice('person:a:'.length) : data.name;
      api.personProfile(identity).then(profile=>{if(active)setAvatarId(profile.id);}).catch(()=>{});
    }
    return()=>{active=false;};
  },[mitKopf,data?.art,data?.sache]);
  const [arbeitet, setArbeitet] = useState<string | null>(null);
  const [standQuelle, setStandQuelle] = useState(false);
  const version = useRef(0);
  const versuche = useRef(0);
  const lageVersuche = useRef(0);
  const laden = useCallback(async (mitAllen: boolean) => {
    const eigene = ++version.current;
    try {
      const next = await api.akte(sache, mitAllen);
      // Eine verspätete Antwort für eine andere Sache überschreibt nichts.
      if (eigene === version.current) { setData(next); setZustand("ok"); }
    } catch (cause) {
      if (eigene === version.current) setZustand(cause instanceof ApiError && cause.status === 404 ? "keine" : "fehler");
    }
  }, [sache]);
  useEffect(() => { setData(null); setZustand("laedt"); setAlle(false); setStandQuelle(false); versuche.current = 0; lageVersuche.current = 0; void laden(false); }, [laden]);

  // Ein Klick, eine Antwort: Was gemerkt wurde, sagt der Hinweis unten, mit „Rückgängig“ (Grundsatz 4 und 5, V4). Der
  // Weg zurück stellt den Zustand vor dem Klick wieder her: die frühere Entscheidung oder die Vermutung. Er hängt nicht
  // an dieser Ansicht: Wer inzwischen weitergeklickt hat, bekommt die Akte trotzdem neu geladen (`akteGeaendert`).
  const zurueckWeg = (ziel: string, vorher: AkteEntscheidung | null) => async () => {
    if (vorher) await api.akteEntscheiden(sache, ziel, vorher);
    else await api.akteEntscheidungZuruecknehmen(sache, ziel);
    akteGeaendert();
    return vorher ? "Zurückgenommen." : "Zurückgenommen. Es gilt wieder, was die Quellen nahelegen.";
  };
  const entscheiden: Entscheiden = (ziel, entscheidung, termin = false) => {
    if (arbeitet) return;
    setArbeitet(ziel);
    void (async () => {
      try {
        const antwort = await api.akteEntscheiden(sache, ziel, entscheidung);
        zeigeHinweis({ text: (termin ? GEMERKT_TERMIN : GEMERKT)[entscheidung], rueckgaengig: zurueckWeg(ziel, antwort.vorher) });
        await laden(alle);
      } catch {
        zeigeHinweis({ text: "Das ließ sich gerade nicht merken. Bitte die Akte neu laden und noch einmal versuchen.", fehler: true });
      } finally {
        setArbeitet(null);
      }
    })();
  };
  // Aufgaben folgen der Post: „Rückgängig“ an einer Aufgabe, die die Post erledigt oder zurückgeholt hat. Ein Zurück
  // davon gibt es nicht; der Hinweis sagt, was gilt.
  function aufgabeZurueck(ziel: string, aufgabeId: string) {
    if (arbeitet) return;
    setArbeitet(ziel);
    void (async () => {
      try {
        await api.taskRueckgaengig(aufgabeId);
        zeigeHinweis({ text: "Zurückgenommen. Die Aufgabe steht wieder so, wie sie vorher war." });
        await laden(alle);
      } catch {
        zeigeHinweis({ text: "Das ließ sich gerade nicht zurücknehmen. Bitte noch einmal versuchen.", fehler: true });
      } finally {
        setArbeitet(null);
      }
    })();
  }
  // „Rückgängig“ an einer Zeile, die du schon entschieden hattest: zurück zur Vermutung. Was du vorher gewählt hattest
  // (`bisher`), lässt sich im Hinweis wiederherstellen.
  async function zuruecknehmen(ziel: string, bisher: AkteEntscheidung | null = null) {
    if (arbeitet) return;
    setArbeitet(ziel);
    try {
      await api.akteEntscheidungZuruecknehmen(sache, ziel);
      zeigeHinweis({ text: "Zurückgenommen. Es gilt wieder, was die Quellen nahelegen.",
        ...(bisher ? { rueckgaengig: async () => { await api.akteEntscheiden(sache, ziel, bisher); akteGeaendert(); return GEMERKT[bisher]; } } : {}) });
      await laden(alle);
    } catch {
      zeigeHinweis({ text: "Das ließ sich gerade nicht zurücknehmen. Bitte noch einmal versuchen.", fehler: true });
    } finally {
      setArbeitet(null);
    }
  }
  // „Neue Akte?“ (akteVorschlag.ts): Erst der Klick legt das Projekt an. Danach öffnet sich die neue Akte, und der
  // Hinweis (er gehört der ganzen App, nicht dieser Akte) bietet „Rückgängig“; „Nein danke“ ebenso (Grundsatz 4 und 5).
  function vorschlagFehler(cause: unknown) {
    zeigeHinweis({ text: fehlerSatz(cause instanceof ApiError ? cause.status : null), fehler: true });
  }
  async function akteAnlegen(kennung: string) {
    if (arbeitet) return;
    setArbeitet(kennung);
    try {
      const antwort = await api.akteVorschlagAnnehmen(kennung);
      zeigeHinweis({ text: antwort.satz, rueckgaengig: vorschlagZurueckWeg(kennung) });
      navigate(antwort.link);
    } catch (cause) { vorschlagFehler(cause); } finally { setArbeitet(null); }
  }
  async function neinDanke(kennung: string) {
    if (arbeitet) return;
    setArbeitet(kennung);
    try {
      const antwort = await api.akteVorschlagAblehnen(kennung);
      zeigeHinweis({ text: antwort.satz, rueckgaengig: vorschlagZurueckWeg(kennung) });
      await laden(alle);
    } catch (cause) { vorschlagFehler(cause); } finally { setArbeitet(null); }
  }
  // Die Zeile „Akte angelegt“/„Nein danke gemerkt“ in der Akte hat ihren eigenen Knopf; er nimmt über denselben Weg
  // zurück und sagt es im Hinweis.
  async function vorschlagZurueck(kennung: string) {
    if (arbeitet) return;
    setArbeitet(kennung);
    try { zeigeHinweis({ text: await vorschlagZurueckWeg(kennung)() }); }
    catch (cause) { vorschlagFehler(cause); } finally { setArbeitet(null); }
  }
  // Andere Stellen (der Hinweis) melden, dass sich die Akte geändert hat.
  const alleRef = useRef(alle);
  alleRef.current = alle;
  useEffect(() => {
    if (typeof window === "undefined") return;
    const neu = () => void laden(alleRef.current);
    window.addEventListener(AKTE_GEAENDERT, neu);
    return () => window.removeEventListener(AKTE_GEAENDERT, neu);
  }, [laden]);
  // Sind die Bezüge noch nicht fertig berechnet, still nachladen (höchstens sechsmal).
  const offen = data?.berechnung.offen ?? 0;
  useEffect(() => {
    if ((zustand !== "keine" && offen === 0) || versuche.current >= 6) return;
    versuche.current += 1;
    const timer = window.setTimeout(() => void laden(alle), 3000);
    return () => window.clearTimeout(timer);
  }, [zustand, offen, laden, alle, data]);

  // Eine veraltete Lage wird im Hintergrund neu geschrieben (das dauert): gelegentlich still nachsehen, höchstens sechsmal.
  const lageAlt = (data?.lage?.wird_aktualisiert ?? false) || (data?.lage_wird_aktualisiert ?? false);
  useEffect(() => {
    if (!lageAlt || lageVersuche.current >= 6) return;
    lageVersuche.current += 1;
    const timer = window.setTimeout(() => void laden(alle), 20000);
    return () => window.clearTimeout(timer);
  }, [lageAlt, laden, alle, data]);

  // Leer, Fehler, Laden: ein Satz in der Gestalt von `Leer`; auf der eigenen Seite ohne zweiten Titel „Akte“.
  const zustandKlasse = `profile-card profile-wide mappe akte akte-zustand${mitKopf ? " akte-seite" : ""}`;
  if (zustand === "keine") return fallback !== undefined ? <>{fallback}</> : <section className={zustandKlasse}>{mitKopf ? null : <h2>Akte</h2>}<Leer zeichen="document" className="profile-empty" satz="Zu dieser Sache gibt es (noch) keine Quellen." /></section>;
  if (zustand === "fehler") return <section className={zustandKlasse} role="status">{mitKopf ? null : <h2>Akte</h2>}<Leer zeichen="document" className="profile-empty" satz="Die Akte konnte gerade nicht geladen werden." aktion={<button className="chronik-mehr" onClick={() => void laden(alle)} type="button">Erneut laden</button>} /></section>;
  if (!data) return <section className={zustandKlasse} aria-busy="true">{mitKopf ? null : <h2>Akte</h2>}<p className="profile-empty akte-laedt">Wird zusammengestellt …</p></section>;

  const zeigeAlle = () => { setAlle(true); void laden(true); };
  const f = data.fristen;
  const stand = data.stand_der_dinge;
  const braucht = data.braucht_dich;
  // Ein Satz Stand unter dem Namen; wo er die jüngste Zeile aus „Stand“ nennt, wiederholt der Abschnitt sie nicht.
  const jetzt = zeitpunkt(data.stand) ?? new Date();
  const satz = compact ? null : standSatz({ name: displayLabel(data.name).name, jetzt, stand: stand.aktuell, verlauf: data.verlauf.eintraege,
    braucht: braucht?.gesamt ?? 0, termin: data.termine.kommend[0] ?? null, frist: data.fristen.kommend[0] ?? null, wer: t => displayLabel(t).name });
  const standOben = satz?.aus === "stand";
  // Ein abgesagter Termin, der oben unter „Braucht dich“ steht, steht unter „Termine“ nur als leise Zeile.
  const terminOben = termineObenGenannt(braucht?.eintraege);
  // Was oben unter „Braucht dich“ steht (gleiche Quelle, gleiche Stelle), steht unten nicht noch einmal; ein Satz sagt,
  // wo es steht. Nur die Anzeige: Zählung und Logik bleiben, wie die Akte sie liefert.
  const { sichtbar: offenSichtbar, oben: offenOben } = offenOhneBrauchtDich(data.offen.eintraege, braucht?.eintraege);
  const offenGruppen = OFFEN_GRUPPEN.map(g => ({ ...g, eintraege: offenSichtbar.filter(g.passt) }));
  const uebrige = offenSichtbar.filter(e => !OFFEN_GRUPPEN.some(g => g.passt(e)));
  const ueber = <>
    {data.art === "person" ? <KreisKarte sache={data.sache} /> : null}
    {data.art === "person" ? <GeburtstagKarte sache={data.sache} /> : null}
    {data.art === "organisation" ? <ArtKarte sache={data.sache} /> : null}
    {data.art === "person" || data.art === "organisation" || data.art === "thema" ? <WiederkehrendKarte sache={data.sache} /> : null}
  </>;
  // Zusammenhänge als ruhige Zeilen mit Zeichen (wie die Listen im Gedächtnis), keine Chips mit Strichen.
  const beteiligte = data.beteiligte.eintraege.length ? <Teil titel="Zusammenhänge" kind="zusammenhaenge" fussnote="Wer und was in denselben Quellen vorkommt; häufigste zuerst.">
    <ul className="akte-beteiligte gd-liste">{data.beteiligte.eintraege.map(b => <li key={b.sache}>
      <MemoryEntityLink className="g-zeile gd-zeile" href={`/memory/akte/${encodeURIComponent(b.sache)}`} aria-label={`Akte öffnen: ${b.name}`}>
        <span className="g-zeile-symbol" aria-hidden="true"><InterfaceIcon name={BETEILIGT_ZEICHEN[b.art] ?? "brain"} /></span>
        <span className="g-zeile-text"><span className="g-zeile-titel">{displayLabel(b.name).name}</span><span className="g-zeile-neben">{BETEILIGT_ART[b.art] ?? "Thema"}</span></span>
        <span className="g-zeile-wert">{b.anzahl} gemeinsame {b.anzahl === 1 ? "Quelle" : "Quellen"}</span>
        <span className="g-zeile-pfeil" aria-hidden="true" /></MemoryEntityLink>
    </li>)}</ul>
    <Gesamt gezeigt={data.beteiligte.eintraege.length} gesamt={data.beteiligte.gesamt} wo="häufigste zuerst" />
  </Teil> : null;
  const herkunftHinweis = <p className="mappe-hinweis akte-herkunft">
    Aus {data.quellen.gesamt === 1 ? "einer Quelle" : `${data.quellen.gesamt} Quellen`} zusammengestellt. Jede Zeile führt zur Quelle.
    {data.quellen.begrenzt ? ` Ausgewertet sind die jüngsten ${data.quellen.beruecksichtigt}.` : ""}
    {data.berechnung.offen ? ` Für ${data.berechnung.offen} weitere Quellen wird noch berechnet, wozu sie gehören.` : ""}
  </p>;
  // Die eigene Seite der Akte ist eine ruhige Lesefläche: Kopf mit Bild, Name und einer Zeile; dann Gruppen.
  return <section className={`profile-card profile-wide mappe akte${compact ? " akte-compact" : ""}${mitKopf ? " akte-seite" : ""}`}>
    <header className="akte-kopf">
      {mitKopf ? <div className="akte-kopf-bild">{avatarId ? <MemoryAvatarEditor id={avatarId} label={data.name} logo={data.art==='organisation'}/> : <span className="memory-avatar memory-avatar-large" aria-hidden="true">{initials(displayLabel(data.name).name)}</span>}</div> : null}
      <div className="akte-kopf-text">
        <h2>{mitKopf ? displayLabel(data.name).name : "Akte"}</h2>
        {compact ? <details className="akte-coverage quiet-details"><summary>{data.quellen.gesamt} {data.quellen.gesamt === 1 ? "Quelle" : "Quellen"}{data.quellen.begrenzt ? ` · jüngste ${data.quellen.beruecksichtigt} ausgewertet` : ''}{data.berechnung.offen ? ` · ${data.berechnung.offen} noch in Arbeit` : ''}</summary>{herkunftHinweis}</details> : null}
        {satz ? <StandKopf satz={satz} offen={standQuelle} umschalten={() => setStandQuelle(x => !x)} /> : !compact ? <Blick data={data} art={mitKopf ? data.art_text : undefined} /> : null}
      </div>
    </header>
    {satz && standQuelle ? <div className="akte-stand-original" id="akte-stand-original"><ProfileSource key={satz.episode_id} kind="episode" id={satz.episode_id} label={satz.titel} embedded readOnly /></div> : null}

    {data.akte_vorschlag ? <NeueAkte stand={data.akte_vorschlag} arbeitet={arbeitet} anlegen={kennung => void akteAnlegen(kennung)} ablehnen={kennung => void neinDanke(kennung)} zurueck={kennung => void vorschlagZurueck(kennung)} /> : null}

    {braucht ? <BrauchtDich punkte={braucht.eintraege} gesamt={braucht.gesamt} arbeitet={arbeitet} entscheiden={entscheiden} aufgabeZurueck={aufgabeZurueck} /> : null}

    {data.lage ? <Lage lage={data.lage} /> : null}

    {data.zeitstrahl ? <Zeitstrahl strahl={data.zeitstrahl} /> : null}

    {offenSichtbar.length || data.offen.erledigt.gesamt ? <Teil titel="Vermutlich offen" kind="offen" fussnote={offenSichtbar.length ? "Keine spätere Erledigung oder Absage gefunden; „Erledigt“ legt einen Punkt ab." : null}>
      {offenSichtbar.length || offenOben ? null : <p className="profile-empty">Nichts mehr offen, soweit die Quellen es zeigen.</p>}
      {offenGruppen.map(g => g.eintraege.length ? <div className="akte-gruppe" key={g.titel}><h4>{g.titel}</h4>
        {g.eintraege.map(e => <OffenZeile key={e.ziel ?? `${e.episode_id}:${e.text}`} e={e} arbeitet={arbeitet} entscheiden={entscheiden} zuruecknehmen={ziel => void zuruecknehmen(ziel, "offen")} />)}
      </div> : null)}
      {uebrige.length ? <div className="akte-gruppe">{offenGruppen.some(g => g.eintraege.length) ? <h4>Weitere</h4> : null}
        {uebrige.map(e => <OffenZeile key={e.ziel ?? `${e.episode_id}:${e.text}`} e={e} arbeitet={arbeitet} entscheiden={entscheiden} zuruecknehmen={ziel => void zuruecknehmen(ziel, "offen")} />)}
      </div> : null}
      {offenOben ? <p className="mappe-mehr akte-oben-genannt">{obenGenanntSatz(offenOben)}</p> : null}
      <Gesamt gezeigt={data.offen.eintraege.length} gesamt={data.offen.gesamt} />
      {data.offen.erledigt.gesamt ? <details><summary>Vermutlich erledigt oder abgesagt ({data.offen.erledigt.gesamt})</summary>
        {data.offen.erledigt.eintraege.map((e, index) => <div key={`${index}:${e.episode_id}`}><Zeile zeile={e} zusatz={GRUND[e.grund] ?? e.grund} />{e.durch ? <p className="mappe-mehr">Laut: „{e.durch.text}“ ({datum(e.durch)}) <Quelle zeile={e.durch} /></p> : null}
          {e.ziel && e.grund.startsWith("nutzer_") ? <button type="button" className="akte-knopf akte-knopf-leise" disabled={arbeitet !== null} onClick={() => void zuruecknehmen(e.ziel!, e.grund === "nutzer_gilt_nicht" ? "gilt_nicht" : "erledigt")}>Rückgängig</button> : null}
          {e.ziel && (e.grund === "erledigt" || e.grund === "absage") ? <button type="button" className="akte-knopf akte-knopf-leise" disabled={arbeitet !== null} onClick={() => entscheiden(e.ziel!, "offen")}>Doch noch offen</button> : null}
        </div>)}
      </details> : null}
    </Teil> : null}

    {f.kommend.length || f.verstrichen.length || f.ersetzt.length || f.ohne_datum.gesamt ? <Teil titel="Fristen" kind="fristen">
      {f.kommend.map((e, index) => <article key={`k${index}:${e.episode_id}:${e.datum}`}>
        <strong>{tag(e.datum)}</strong>
        <small>{e.ausdruck ? `„${e.ausdruck}“ · ` : ""}{e.art} vom {datum(e)}</small>
        <blockquote>{e.text}</blockquote><Quelle zeile={e} />
      </article>)}
      <Gesamt gezeigt={f.kommend.length} gesamt={f.gesamt.kommend} wo="kommende Fristen" />
      {f.verstrichen.length ? <details><summary>Verstrichen ({f.gesamt.verstrichen})</summary>{f.verstrichen.map((e, index) => <article key={`v${index}:${e.episode_id}:${e.datum}`}>
        <strong>{tag(e.datum)}</strong><small>{e.ausdruck ? `„${e.ausdruck}“ · ` : ""}{e.art} vom {datum(e)}</small><blockquote>{e.text}</blockquote><Quelle zeile={e} /></article>)}</details> : null}
      {f.ersetzt.length ? <details><summary>Überholt ({f.gesamt.ersetzt})</summary>{f.ersetzt.map((e, index) => <article key={`e${index}:${e.episode_id}:${e.datum}`}>
        <strong className="akte-alt">{tag(e.datum)}</strong><small>ersetzt durch {tag(e.ersetzt_durch?.datum)}{e.ersetzt_durch?.ausdruck ? ` („${e.ersetzt_durch.ausdruck}“)` : ""}</small><blockquote>{e.text}</blockquote><Quelle zeile={e} /></article>)}</details> : null}
      {f.abgelegt ? <p className="mappe-mehr">{f.abgelegt === 1 ? "Eine Frist gehört" : `${f.abgelegt} Fristen gehören`} zu Punkten, die du als erledigt abgelegt hast.</p> : null}
      {f.ohne_datum.gesamt ? <p className="mappe-mehr">Zeitangaben ohne festes Datum ({f.ohne_datum.gesamt}): {f.ohne_datum.eintraege.map(x => `„${x.ausdruck}“`).join(", ")}{f.ohne_datum.gesamt > f.ohne_datum.eintraege.length ? " …" : ""}</p> : null}
    </Teil> : null}

    {f.quellenangaben?.gesamt ? <details className="quiet-details akte-quellenfristen">
      <summary>Fristen laut Quelle ({f.quellenangaben.gesamt}) · Zuständigkeit ungeklärt</summary>
      <Teil titel="Fristen laut Quelle" kind="fristen">
        {/* Die Zusicherung steht in der Fläche, nicht als Fußnote: Sie gehört zu jeder dieser Angaben. */}
        <p className="mappe-hinweis akte-teil-satz">Quellenangaben, keine bestätigten eigenen Aufgaben. Vorbehalte stehen im Originalzitat.</p>
        {f.quellenangaben.eintraege.map(e => <article key={`${e.episode_id}:${e.datum}:${e.ausdruck}:${e.text}`}>
          <strong>{tag(e.datum)}{e.zeitbezug === "vergangen" ? " · Historie" : ""}</strong>
          <small>{e.art} · Quelle vom {datum(e)} · Zuständigkeit ungeklärt</small>
          <blockquote>{e.text}</blockquote><Quelle zeile={e} />
        </article>)}
        <Gesamt gezeigt={f.quellenangaben.eintraege.length} gesamt={f.quellenangaben.gesamt} />
      </Teil>
    </details> : null}

    {data.termine.kommend.length || data.termine.vergangen.length ? <Teil titel="Termine" kind="termine">
      {data.termine.kommend.map(t => terminOben.has(t.episode_id) ? <article key={`k:${t.episode_id}`} className="akte-termin-abgesagt akte-termin-oben"><strong>{t.titel}</strong>
        <small>{TAG_ZEIT.format(new Date(t.start))}{t.ort ? ` · ${t.ort}` : ""} · vermutlich abgesagt, steht oben unter „Braucht dich“</small>
        <div className="akte-zeile-fuss"><Quelle zeile={t} /></div></article>
        : <article key={`k:${t.episode_id}`} className={t.vermutlich_abgesagt ? "akte-termin-abgesagt" : undefined}><strong>{t.titel}</strong><small>{TAG_ZEIT.format(new Date(t.start))}{t.ort ? ` · ${t.ort}` : ""}{t.entscheidung === "offen" ? " · findet laut dir statt" : ""}</small>
        {t.vermutlich_abgesagt ? <p className="mappe-mehr">{t.entscheidung === "erledigt" ? "Abgesagt (von dir bestätigt)" : "Vermutlich abgesagt"} laut „{t.vermutlich_abgesagt.text}“ ({datum(t.vermutlich_abgesagt)}).{t.entscheidung === "erledigt" ? "" : " Der Kalendereintrag steht noch."} <Quelle zeile={t.vermutlich_abgesagt} /></p> : null}
        <div className="akte-zeile-fuss"><Quelle zeile={t} />
          {t.ziel && t.entscheidung ? <button type="button" className="akte-knopf akte-knopf-leise" disabled={arbeitet !== null} onClick={() => void zuruecknehmen(t.ziel!, t.entscheidung ?? null)}>Rückgängig</button> : null}
        </div></article>)}
      <Gesamt gezeigt={data.termine.kommend.length} gesamt={data.termine.gesamt.kommend} wo="kommende Termine" />
      {data.termine.vergangen.length ? <details><summary>Vergangen ({data.termine.gesamt.vergangen})</summary>{data.termine.vergangen.map(t => <article key={`v:${t.episode_id}`}><strong>{t.titel}</strong><small>{TAG_ZEIT.format(new Date(t.start))}{t.ort ? ` · ${t.ort}` : ""}{t.vermutlich_abgesagt ? " · vermutlich abgesagt" : ""}</small><Quelle zeile={t} /></article>)}</details> : null}
    </Teil> : null}

    {stand.aktuell && (!standOben || stand.vorher.length || stand.weitere.length) ? <Teil titel="Stand" kind="stand">
      {standOben ? null : <Zeile zeile={stand.aktuell} />}
      {stand.vorher.length ? <details><summary>{standOben && stand.aktuell.occurred_at ? `Vor dem ${tag(stand.aktuell.occurred_at)}` : "Vorher"} ({stand.vorher_gesamt})</summary>{stand.vorher.map((z, index) => <Zeile key={`${index}:${z.episode_id}`} zeile={z} />)}</details> : null}
      {stand.weitere.length ? <details><summary>Weitere Stände ({stand.weitere_gesamt})</summary>{stand.weitere.map((g, index) => <Zeile key={`${index}:${g.aktuell.episode_id}`} zeile={g.aktuell} zusatz={g.vorher_gesamt ? `vorher ${g.vorher_gesamt}×` : undefined} />)}</details> : null}
    </Teil> : null}

    {data.aussagen?.eintraege.length ? <Teil titel="Angenommen" kind="angenommen" fussnote="Von dir aus einer Antwort übernommen; jede nennt ihren Beleg.">
      {data.aussagen.eintraege.map(a => <article key={a.id} className={a.ueberholt ? "akte-aussage-ueberholt" : undefined}>
        <strong>{a.text}</strong>
        <small>Angenommen am {tag(a.angenommen)}</small>
        {a.ueberholt ? <p className="akte-ueberholt-hinweis" role="note">Möglicherweise überholt: „{a.ueberholt.text}“ ({tag(a.ueberholt.datum)}). Die Aussage gilt weiter, bis du sie widerrufst. <Quelle zeile={a.ueberholt} /></p> : null}
        {a.belege.map(b => <div key={b.episode_id}><blockquote>{b.zitat}</blockquote><Quelle zeile={b} /></div>)}
      </article>)}
      <Gesamt gezeigt={data.aussagen.eintraege.length} gesamt={data.aussagen.gesamt} />
    </Teil> : null}

    {data.aufgaben.eintraege.length ? <Teil titel="Aufgaben" kind="aufgaben">
      {data.aufgaben.eintraege.map(a => <article key={a.id}><button type="button" className="task-title-link" onClick={()=>navigate(`/vorhaben?${new URLSearchParams({task:a.id,from:'memory'})}`)}>{a.title}</button><small className={a.overdue ? "mappe-ueberfaellig" : undefined}>{a.due ? `${a.overdue ? "Überfällig seit" : "Fällig"} ${tag(a.due)}` : "Ohne Termin"}{a.wartet_auf ? ` · wartet auf ${displayLabel(a.wartet_auf).name}` : ""}</small></article>)}
      <Gesamt gezeigt={data.aufgaben.eintraege.length} gesamt={data.aufgaben.gesamt} />
    </Teil> : null}

    {compact ? <details className="quiet-details"><summary>Zusammenhänge ({data.beteiligte.gesamt})</summary>{beteiligte}</details> : <>
      {data.art === "person" || data.art === "organisation" || data.art === "thema" ? <section className="akte-ueber g-gruppe" aria-label={`Über ${data.name}`}><div className="g-gruppe-kopf akte-ueber-titel"><h3 className="g-gruppe-titel">Über {displayLabel(data.name).name}</h3></div><div className="g-flaeche g-flaeche-frei akte-ueber-flaeche">{ueber}</div></section> : null}
      {beteiligte}
    </>}

    {/* Der Verlauf: eine Gruppe, die Einträge eingeklappt, solange der Zeitstrahl sie schon zeigt. */}
    <section className="akte-history mappe-teil akte-teil akte-verlauf g-gruppe" aria-label="Verlauf">
      <div className="g-gruppe-kopf"><h3 className="g-gruppe-titel">Verlauf</h3></div>
      <details className="g-flaeche akte-flaeche akte-verlauf-auf" open={!compact && !data.zeitstrahl}><summary>{data.verlauf.gesamt} {data.verlauf.gesamt === 1 ? "Eintrag" : "Einträge"}</summary>
      {data.verlauf.eintraege.map((e, index) => <article key={`${index}:${e.episode_id}`}>
        <small>{tag(e.datum)}{e.art ? ` · ${e.art}` : ""}{e.archiviert ? " · verdichteter Monat" : ""} · {e.grundlagen.map(g => GRUNDLAGE[g] ?? g).join(", ")}</small>
        <strong>{e.titel}</strong>
        {e.text ? <blockquote>{e.text}</blockquote> : null}
        <Quelle zeile={e} />
      </article>)}
      <Gesamt gezeigt={data.verlauf.eintraege.length} gesamt={data.verlauf.gesamt} />
      {!alle && data.verlauf.gesamt > data.verlauf.eintraege.length ? <button className="chronik-mehr" onClick={zeigeAlle} type="button">Alle zeigen</button> : null}
      </details>
    </section>
    {compact ? <details className="akte-personal quiet-details"><summary>Beziehung & persönliche Angaben</summary>{ueber}</details> : null}
    {!compact ? <footer className="akte-fuss">{herkunftHinweis}</footer> : null}
    {data.einordnung.offen ? <p className="mappe-mehr">{data.einordnung.offen === 1 ? "Eine Quelle wird noch sortiert und ist" : `${data.einordnung.offen} Quellen werden noch sortiert und sind`} hier nur mit Titel berücksichtigt.</p> : null}
  </section>;
}

/** Eigene Seite für die Akte irgendeiner Sache, erreichbar aus den Listen im Gedächtnis und aus „Beteiligte“. */
export function SachenAkte({ sache, recentConversation }: { sache: string; recentConversation: string | null }) {
  return <div className="shell profile-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="profile-page">
      <button className="profile-back" onClick={() => navigate(new URLSearchParams(window.location.search).has("return_to") ? memoryReturnPath(window.location.search) : "/memory")} type="button">← Gedächtnis</button>
      <AkteAnsicht key={sache} sache={sache} mitKopf />
    </main>
  </div>;
}
import {MemoryAvatarEditor} from './MemoryAvatar';
