import type {IntegrationOverview, MailIntakeStatus, MacCalendarState, Schedule, SourceFolderStatus} from './api';
import {deriveIntakeProgress} from './mailIntakeProgress.ts';

export type SourceOverviewData = {
  intake: MailIntakeStatus; integrations: IntegrationOverview; schedule: Schedule;
  mac: MacCalendarState; documents: SourceFolderStatus; meetings: SourceFolderStatus;
};
export type SourceSlot<T> = {data?: T; failed: boolean; checkedAt?: number};
export type SourceOverviewState = {[K in keyof SourceOverviewData]?: SourceSlot<SourceOverviewData[K]>};
export type SourceOverviewRow = {
  id: string; title: string; kind: string; status: string; details: string[];
  stale: boolean; warning?: string; lastSuccess: string | null; lastSuccessLabel: string; href: string; linkLabel: string;
};

// Require a source timestamp with an offset; never replace it with the time we read metadata.
export function sourceTimestamp(value: unknown): string | null {
  return typeof value === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value)) ? value : null;
}
const number = (n: number) => new Intl.NumberFormat('de-DE').format(n);
const fresh = (stamp: unknown, at: number, maxAge: number) => {
  const value=sourceTimestamp(stamp); const age=value ? at-Date.parse(value) : Infinity;
  return age>=0 && age<=maxAge;
};
const staleStatus = 'Letzter bekannter Stand · der aktuelle Abruf ist fehlgeschlagen.';
const time = (value: string) => new Date(value).toLocaleString('de-DE', {dateStyle:'medium',timeStyle:'short'});
const base = (id: string, title: string, kind: string): SourceOverviewRow => ({id,title,kind,status:'',details:[],stale:false,
  lastSuccess:null,lastSuccessLabel:'Letzter erfolgreicher Abgleich',href:'/settings#zugaenge',linkLabel:'Zugang prüfen'});
const missing = (id: string, title: string, kind: string, failed: boolean) => ({...base(id,title,kind),
  status:failed ? 'Der Quellenstand konnte nicht geladen werden.' : 'Quellenstand wird geladen …',stale:failed});

export function buildSourceOverview(state: SourceOverviewState, at=Date.now()): SourceOverviewRow[] {
  const rows: SourceOverviewRow[]=[];
  const intake=state.intake?.data;
  if (intake) {
    if (!intake.accounts.length) rows.push({...base('mail-empty','Postfächer','Mail'),status:state.intake?.failed ? staleStatus : 'Noch kein Postfach eingetragen.',stale:!!state.intake?.failed});
    for (const account of intake.accounts) {
      const row=base(`mail:${account.account_id}`,account.label,'Mail');
      const p=deriveIntakeProgress(account);
      const warnings:string[]=[];
      if(account.error)warnings.push('Bei der Aufnahme ist ein Problem aufgetreten. Bisherige Aufnahmen bleiben erhalten.');
      row.stale=!!state.intake?.failed;
      row.status=row.stale ? staleStatus : !account.connected ? 'Verbindung noch nicht eingerichtet.'
        : intake.background_paused || account.paused ? 'Aufnahme pausiert.'
        : !account.started ? 'Postfach eingetragen · Aufnahme noch nicht gestartet.'
        : account.error ? 'Aufnahme meldet ein Problem.'
        : account.history_waiting_for_analysis ? 'Ältere Mails warten auf die Einordnung.' : 'Aufnahme eingerichtet.';
      if (account.started) {
        row.details.push(
          `${p.total===null ? 'Der Gesamtumfang ist noch nicht bekannt.' : `${number(p.total)} Mails im ausgewählten Verlauf gezählt.`} ${number(p.sources)} Mails aufgenommen oder wiedererkannt · ${number(p.filtered)} bewusst ausgelassen · ${number(p.pending)} noch zu lesen · ${number(p.failed)} ${p.failed===1 ? 'Abruf' : 'Abrufe'} fehlgeschlagen.`,
          `${number(p.analyzed)} mit abgeschlossener Einordnung · ${p.categoriesKnown ? `${number(p.categorized)} mit Kategorien` : 'Kategorienstand noch nicht bekannt'}.`,
          `Ausgewählte Mailbereiche: ${account.scope || 'Umfang nicht angegeben'}.`);
        if (p.livePending || p.liveFiltered) row.details.push(`${number(p.livePending)} neue Mails warten auf Abruf (davon ${number(p.liveFailed)} fehlgeschlagen) · ${number(p.liveFiltered)} neue Mails bewusst ausgelassen.`);
        if (p.analysisFailed || p.deferred || p.categoriesFailed || p.categoriesUnverified)
          warnings.push('Einordnungen oder Kategorien sind noch offen, zurückgestellt oder müssen erneut geprüft werden.');
      }
      row.details.push(account.attachments_supported ? 'Anlagen werden innerhalb der unterstützten Formate und Größen mitgelesen; Grenzen stehen an der Originalquelle.' : 'Anlagen sind bei diesem Zugang nicht als mitgelesen bestätigt.');
      const sync=state.schedule?.data?.mail_status?.[account.account_id];
      row.lastSuccess=sourceTimestamp(sync?.last_success);
      row.lastSuccessLabel='Letzter bekannter erfolgreicher regelmäßiger Abruf';
      if (state.schedule?.failed) warnings.push('Der aktuelle Stand des regelmäßigen Abrufs ist nicht erreichbar.');
      else if (sync?.last_failure) warnings.push('Der letzte regelmäßige Abruf ist fehlgeschlagen; frühere Aufnahmen bleiben erhalten.');
      row.warning=warnings.join(' ') || undefined;
      rows.push(row);
    }
  } else rows.push(missing('mail-unknown','Postfächer','Mail',!!state.intake?.failed));

  const sources=state.integrations?.data?.calendar_sources;
  if (sources) {
    if (!sources.length) rows.push({...base('calendar-empty','Kalender über Konten und Abos','Kalender'),status:state.integrations?.failed ? staleStatus : 'Noch kein Kalenderkonto oder Kalenderabo eingetragen.',stale:!!state.integrations?.failed});
    for (const source of sources) rows.push({...base(`calendar:${source.id}`,source.label,'Kalender'),
      stale:!!state.integrations?.failed,status:state.integrations?.failed ? staleStatus : !source.enabled ? 'Zugang ausgeschaltet.' : source.configured ? 'Zugang eingerichtet · kein bestätigter Abgleich in dieser Übersicht.' : 'Verbindung noch nicht eingerichtet.',
      details:['Die Kalenderansicht lädt Termine getrennt. Diese lokale Übersicht prüft den Anbieter nicht und belegt weder einen vollständigen Kalenderbestand noch das Fehlen von Terminen.'],
      href:'/calendar',linkLabel:'Kalender ansehen'});
  } else rows.push(missing('calendar-unknown','Kalender über Konten und Abos','Kalender',!!state.integrations?.failed));

  const mac=state.mac?.data;
  if (mac) {
    const row=base('mac','Ausgewählte Mac-Kalender','Kalender');
    row.stale=!!state.mac?.failed;
    const from=sourceTimestamp(mac.range_from),to=sourceTimestamp(mac.range_to);
    const names=mac.selected.map(id=>mac.calendars.find(c=>c.id===id)?.name);
    const rangeKnown=!!from && !!to && Date.parse(from)<=at && Date.parse(to)>at;
    const ready=mac.enabled && mac.selected.length>0 && names.every(Boolean) && mac.status==='granted' && !mac.error && mac.online &&
      fresh(mac.synced_at,at,300000) && mac.snapshot_complete===true && rangeKnown;
    row.status=row.stale ? staleStatus : !mac.enabled ? 'Mac-Kalender nicht verbunden.'
      : mac.status!=='granted' ? 'Kalenderfreigabe fehlt oder ist noch nicht bestätigt.'
      : !mac.selected.length ? 'Noch kein Mac-Kalender ausgewählt.'
      : !names.every(Boolean) ? 'Die Kalenderauswahl muss überprüft werden.'
      : mac.error ? 'Der Kalenderabgleich meldet ein Problem.'
      : !mac.online ? 'Kalenderhelfer derzeit nicht erreichbar.'
      : ready ? 'Abgleich bestätigt · nur für das gelieferte Zeitfenster.'
      : 'Kein frischer, vollständiger Abgleich für das aktuelle Zeitfenster bestätigt.';
    if (mac.selected.length) row.details.push(`Auswahl: ${names.map((name,i)=>name || `Nicht verfügbar (${i+1})`).join(', ')}.`);
    if (ready && !row.stale) row.details.push(`${number(mac.event_count)} Termine im gelieferten Zeitfenster.`, `Zeitraum: ${time(from!)} bis ${time(to!)}.`);
    else row.details.push('Ein fehlender oder alter Abgleich bedeutet nicht, dass dein Kalender leer ist.');
    row.lastSuccess=sourceTimestamp(mac.synced_at);
    row.lastSuccessLabel='Letzter gespeicherter Kalenderabgleich';
    rows.push(row);
  } else rows.push(missing('mac','Mac-Kalender','Kalender',!!state.mac?.failed));

  for (const [key,title] of [['documents','Dokumentordner'],['meetings','Meeting-Mitschriften']] as const) {
    const data=state[key]?.data;
    if (!data) {rows.push(missing(key,title,'Ordner',!!state[key]?.failed));continue;}
    const row=base(key,title,'Ordner');row.stale=!!state[key]?.failed;
    const errors=Boolean(data.last_run?.errors.length);
    row.status=row.stale ? staleStatus : !data.root_id ? 'Noch kein Ordner ausgewählt.'
      : !data.enabled ? 'Ordneraufnahme pausiert.' : errors ? 'Der letzte Lauf war nicht vollständig erfolgreich.'
      : !data.running || !fresh(data.seen_at,at,120000) ? 'Ordneraufnahme eingeschaltet · Helfer derzeit nicht erreichbar.' : 'Ordneraufnahme eingeschaltet.';
    if (data.root_id) {
      const taken=data.files.filter(file=>file.state!=='ignored').length;
      row.details.push(`${number(taken)} bekannte Dateien aufgenommen · ${number(data.files.length-taken)} ausgenommen.`,
        'Die Zählung beschreibt gespeicherte Aufnahmen, nicht sämtliche Dateien auf deinem Gerät.');
    }
    if (errors) row.details.push('Ein unvollständiger Lauf belegt keine fehlenden Dateien. Bisherige Aufnahmen und der letzte erfolgreiche Lauf bleiben erhalten.');
    row.lastSuccess=sourceTimestamp(data.synced_at);row.lastSuccessLabel='Letzter erfolgreicher vollständiger Ordnerlauf';
    rows.push(row);
  }
  return rows;
}
