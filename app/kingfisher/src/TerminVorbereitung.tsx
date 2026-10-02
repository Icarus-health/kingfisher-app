import type { ReactNode } from "react";
import type { TagFrist, TagPerson, TagTermin, TagZeile } from "./api";
import { ProfileSource } from "./ProfileSource";

// Die Vorbereitung eines Termins, wie sie ohne Klick entstanden ist: wer kommt, was sie wollen, letzter Kontakt,
// Hintergrund, Fristen, Einpacken, Weg. Jede Zeile ist ein Zitat mit Quelle; was nur vermutet wird, sagt es.
const ROLLE: Record<string, string> = {
  wunsch: "Wünscht sich, vermutlich", sie_bittet: "Bittet, vermutlich noch offen", du_sagtest_zu: "Du hast zugesagt, vermutlich noch offen",
  sie_sagte_zu: "Hat zugesagt, vermutlich noch offen", du_batest: "Du hast gebeten, vermutlich noch offen", genannt: "Hat genannt",
  offen: "Vermutlich noch offen",
};

// Datum und Uhrzeit stehen so im Text, wie der Sidecar sie in der Zeitzone des Nutzers liefert („…T14:00:00+02:00“).
// Der Browser rechnet nicht um: Ein Termin um 14 Uhr bleibt 14 Uhr, auch wenn dieser Rechner in einer anderen Zone steht.
const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
function datum(iso: string | null) {
  const treffer = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return treffer ? `${Number(treffer[3])}. ${MONATE[Number(treffer[2]) - 1]} ${treffer[1]}` : "";
}
function uhr(iso: string | null) {
  const treffer = /T(\d{2}:\d{2})/.exec(iso ?? "");
  return treffer ? treffer[1] : "";
}

function Zitat({ zeile, kopf }: { zeile: TagZeile; kopf?: string }) {
  return <li className="vorbereitung-zeile">
    {kopf && <span className="vorbereitung-kopf">{kopf}</span>}
    <blockquote>{zeile.text}</blockquote>
    <p className="vorbereitung-beleg">
      {zeile.beleg ? `${zeile.beleg.art || "Quelle"} vom ${datum(zeile.beleg.datum)}: ${zeile.beleg.titel}` : ""}
      {zeile.hinweis ? ` · ${zeile.hinweis}` : ""}
    </p>
    {zeile.beleg && <ProfileSource kind="episode" id={zeile.beleg.episode_id} label="Quelle öffnen" quiet readOnly allowIgnore={false} />}
  </li>;
}

function Frist({ frist }: { frist: TagFrist }) {
  return <li className="vorbereitung-zeile">
    <span className="vorbereitung-kopf">{frist.satz}</span>
    <blockquote>{frist.text}</blockquote>
    <p className="vorbereitung-beleg">{`${frist.quelle_art || "Quelle"}: ${frist.titel}`}</p>
    <ProfileSource kind="episode" id={frist.episode_id} label="Quelle öffnen" quiet readOnly allowIgnore={false} />
  </li>;
}

function Abschnitt({ titel, children }: { titel: string; children: ReactNode }) {
  return <section className="vorbereitung-abschnitt"><h4>{titel}</h4>{children}</section>;
}

function Person({ person }: { person: TagPerson }) {
  const kontakt = person.letzter_kontakt;
  return <article className="vorbereitung-person">
    <header><h3>{person.name}</h3>{person.organisation && <span>{person.organisation}</span>}</header>
    {person.will.length > 0 && <Abschnitt titel="Was sie wollen"><ul>{person.will.map((z, i) => <Zitat key={i} zeile={z} kopf={ROLLE[z.rolle] ?? ROLLE.offen} />)}</ul></Abschnitt>}
    {kontakt && <Abschnitt titel="Letzter Kontakt"><ul><Zitat zeile={kontakt} /></ul></Abschnitt>}
    {person.stand.length > 0 && <Abschnitt titel="Aktueller Stand"><ul>{person.stand.map((z, i) => <Zitat key={i} zeile={z} />)}</ul></Abschnitt>}
    {person.fristen.length > 0 && <Abschnitt titel="Fristen"><ul>{person.fristen.map(f => <Frist key={f.episode_id + f.datum} frist={f} />)}</ul></Abschnitt>}
    {person.erster_kontakt && <Abschnitt titel="Seit wann ihr euch kennt"><ul><Zitat zeile={person.erster_kontakt} /></ul></Abschnitt>}
    {!person.will.length && !kontakt && !person.stand.length && <p className="vorbereitung-leer">Zu {person.name} liegt noch nichts Näheres vor.</p>}
  </article>;
}

export function TerminVorbereitung({ termin }: { termin: TagTermin }) {
  const weg = termin.wegezeit;
  return <div className="vorbereitung" role="region" aria-label={`Vorbereitung: ${termin.titel}`}>
    <header className="vorbereitung-kopfzeile">
      <h3>{termin.titel}</h3>
      <p>{`${datum(termin.beginn)}, ${uhr(termin.beginn)}${termin.ende ? ` bis ${uhr(termin.ende)}` : ""} Uhr${termin.ort ? `, ${termin.ort}` : ""}`}</p>
      {termin.projekt && <p className="vorbereitung-beleg">{`Projekt ${termin.projekt.name}${termin.projekt.herkunft === "vorschlag" ? " (Vorschlag)" : ""}`}</p>}
    </header>
    {weg && weg.status !== "ohne_ort" && <Abschnitt titel="Weg"><p>{weg.satz}</p>{weg.status !== "berechnet" && weg.grund && <p className="vorbereitung-beleg">{weg.grund}</p>}</Abschnitt>}
    {termin.personen.length === 0 && <p className="vorbereitung-leer">Zu den Teilnehmern liegt im Gedächtnis noch nichts vor.</p>}
    {termin.personen.map(p => <Person key={p.sache ?? p.name} person={p} />)}
    {termin.unbekannt.length > 0 && <p className="vorbereitung-beleg">{`Nicht im Gedächtnis: ${termin.unbekannt.join(", ")}.`}</p>}
    {termin.hintergrund.map(h => <Abschnitt key={h.sache} titel={`Hintergrund: ${h.name}${h.herkunft === "vermutet" ? " (vermutet)" : ""}`}>
      <ul>{h.zeilen.map((z, i) => <Zitat key={i} zeile={z} />)}</ul></Abschnitt>)}
    {termin.einpacken.length > 0 && <Abschnitt titel="Einpacken, laut deinen Quellen"><ul>{termin.einpacken.map((s, i) => <li className="vorbereitung-zeile" key={i}>
      <blockquote>{s.text}</blockquote><p className="vorbereitung-beleg">{`${s.art === "termin" ? "Notiz zum Termin" : s.art === "notiz" ? "Notiz" : "Mail"}${s.datum ? ` vom ${datum(s.datum)}` : ""}: ${s.titel}`}</p>
      {!s.episode_id.startsWith("termin:") && <ProfileSource kind="episode" id={s.episode_id} label="Quelle öffnen" quiet readOnly allowIgnore={false} />}</li>)}</ul></Abschnitt>}
  </div>;
}
