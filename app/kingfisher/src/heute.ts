// Kleine reine Hilfen für Heute und das Briefing (Fremdprobe 2, Befund 10); ohne React, damit `node --test` sie prüft.

/** Was im Zähler einer Kachel steht: die Zahl, oder nichts, wenn es nichts gibt. Eine Signalfarbe für „0“ ruft ohne Grund. */
export function zaehlerText(anzahl: number): string | null {
  return Number.isFinite(anzahl) && anzahl > 0 ? String(anzahl) : null;
}

/** Welche Aussagen über ein Postfach Heute zeigt: die, die erklären, warum keine Mails dastehen (leer, noch nicht
 * abgerufen, angehalten, Fehler). Was gerade gelesen wird, steht in „Kingfisher lernt gerade“; ein gelesenes Postfach
 * zeigt seine Mails selbst (Fremdprobe 2, Befund 17). */
export function postfachAufHeute(zustand: string): boolean {
  return zustand === "leer" || zustand === "nicht_abgerufen" || zustand === "pausiert" || zustand === "fehler";
}

/** Ob der eingeklappte „Postfachstand“ auf Heute von selbst aufgeht: wenn ein Postfach den Menschen braucht (sein Satz
 * verweist in die Einstellungen, etwa „Melde dich unter Einstellungen → Zugänge neu an.“). */
export function postfachMussHandeln(staende: ReadonlyArray<{zustand: string; verweis?: string | null}>): boolean {
  return staende.some(stand => postfachAufHeute(stand.zustand) && Boolean(stand.verweis));
}

/**
 * Was nach „Aktualisieren“ unter „Nachrichten“ steht (Fremdprobe 2, Befund 18): wann abgerufen wurde und ob etwas
 * Neues kam. `vorher` ist die Liste vor dem Klick (null beim ersten Laden: dann kein Satz).
 */
export function aktualisiertSatz(vorher: string[] | null, nachher: string[], uhrzeit: string): string | null {
  if (vorher === null) return null;
  if (!nachher.length) return `Gerade abgerufen um ${uhrzeit}: Der Posteingang ist leer.`;
  const bekannt = new Set(vorher);
  const neu = nachher.filter(id => !bekannt.has(id)).length;
  if (neu === 0) return `Gerade abgerufen um ${uhrzeit}, nichts Neues.`;
  return `Gerade abgerufen um ${uhrzeit}: ${neu === 1 ? "eine neue Nachricht" : `${neu} neue Nachrichten`}.`;
}

/** Der nächste Termin, wenn heute keiner ansteht (Paket U, H8): „Mi., 30.9., 14:00 Rheinauenblick“, ganztägig ohne
 * Uhrzeit. In der Zeitzone des Briefings; ohne Termin oder mit unlesbarem Datum nichts. */
export function naechsterTerminText(termin: {title: string; start: string; ganztags?: boolean} | null | undefined, zeitzone?: string): string | null {
  if (!termin) return null;
  const start = new Date(termin.start);
  if (Number.isNaN(start.getTime())) return null;
  const zone = (() => { try { new Intl.DateTimeFormat("de-DE", {timeZone: zeitzone}); return zeitzone; } catch { return undefined; } })();
  const teile = Object.fromEntries(new Intl.DateTimeFormat("de-DE", {timeZone: zone, weekday: "short", day: "numeric", month: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false}).formatToParts(start).map(teil => [teil.type, teil.value]));
  const tag = `${teile.weekday.replace(/\.$/, "")}., ${teile.day}.${teile.month}.`;
  return termin.ganztags ? `${tag}, ${termin.title}` : `${tag}, ${teile.hour}:${teile.minute} ${termin.title}`;
}

function kalendertag(datum: Date, zone?: string): string {
  try { return new Intl.DateTimeFormat("de-DE", {timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit"}).format(datum); }
  catch { return datum.toDateString(); }
}

function kurzesDatum(datum: Date, zone: string | undefined, jetzt: Date): string {
  const optionen: Intl.DateTimeFormatOptions = {timeZone: zone, day: "numeric", month: "short"};
  const jahr = (d: Date) => { try { return new Intl.DateTimeFormat("de-DE", {timeZone: zone, year: "numeric"}).format(d); } catch { return String(d.getFullYear()); } };
  if (jahr(datum) !== jahr(jetzt)) optionen.year = "numeric";
  try { return new Intl.DateTimeFormat("de-DE", optionen).format(datum); } catch { return datum.toLocaleDateString("de-DE"); }
}

function langesDatum(datum: Date, zone?: string): string {
  try { return new Intl.DateTimeFormat("de-DE", {dateStyle: "medium", timeStyle: "short", timeZone: zone}).format(datum); }
  catch { return datum.toLocaleString("de-DE"); }
}

/**
 * Die eine leise Zeile unter einem Eintrag in „Neu eingegangen“ (P1): wer oder welche Art, wann die Quelle entstand und,
 * wenn das an einem anderen Tag war, wann Kingfisher sie erfasst hat („Zusage · 26. Sept. · erfasst 29. Sept.“).
 * Quelldatum und Erfassung bleiben so unterscheidbar; die genauen Zeitpunkte stehen im Hinweis (`titel`).
 * „Quelle berichtet“ steht schon in der Überschrift der Liste und in „Quelle ansehen“, die Art „Angabe“ sagt nichts.
 */
export function eingangZeile(item: {source?: string | null; detail?: string | null; occurred_at?: string | null; recorded_at?: string | null},
  zeitzone: string | undefined, jetzt: string | Date): {zeile: string; titel?: string} {
  const zone = (() => { try { new Intl.DateTimeFormat("de-DE", {timeZone: zeitzone}); return zeitzone; } catch { return undefined; } })();
  const nun = new Date(jetzt);
  const arten = (item.detail ?? "").replace(/^Quelle berichtet · /, "").split(", ").map(art => art.trim()).filter(art => art && art !== "Angabe");
  const teile = arten.length ? [arten.join(", ")] : [];
  if (item.source !== "mail" && item.source !== "working_memory") return {zeile: teile.join(" · ")};
  const lesen = (wert?: string | null) => { if (!wert) return null; const d = new Date(wert); return Number.isNaN(d.getTime()) ? null : d; };
  const entstanden = lesen(item.occurred_at), erfasst = lesen(item.recorded_at);
  const heute = Number.isNaN(nun.getTime()) ? null : kalendertag(nun, zone);
  const wann = (d: Date) => heute && kalendertag(d, zone) === heute
    ? `heute, ${new Intl.DateTimeFormat("de-DE", {timeZone: zone, hour: "2-digit", minute: "2-digit", hour12: false}).format(d)}`
    : kurzesDatum(d, zone, Number.isNaN(nun.getTime()) ? d : nun);
  teile.push(entstanden ? wann(entstanden) : "Datum unbekannt");
  if (erfasst && (!entstanden || kalendertag(erfasst, zone) !== kalendertag(entstanden, zone))) teile.push(`erfasst ${wann(erfasst)}`);
  const gleich = entstanden && erfasst && entstanden.getTime() === erfasst.getTime();
  const titel = `Quelldatum: ${entstanden ? langesDatum(entstanden, zone) : "unbekannt"}${erfasst && !gleich ? ` · Erfasst: ${langesDatum(erfasst, zone)}` : ""}`;
  return {zeile: teile.join(" · "), titel};
}
