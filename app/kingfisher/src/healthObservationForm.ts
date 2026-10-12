export type HealthPayload = {subject: 'self'; metric: string; value: string; unit: string; observed_at: string; note: string};
export type HealthForm = {own: boolean; metric: string; value: string; unit: string; localTime: string; offset: string; note: string};

export function healthFormFromObservation(value: HealthPayload): HealthForm {
  const match = value.observed_at.match(/^(.*?)(Z|[+-]\d{2}:\d{2})$/);
  return {own:false,metric:value.metric,value:value.value,unit:value.unit,note:value.note,
    localTime:match?.[1] || '',offset:match?.[2] || ''};
}

export function healthPayload(form: HealthForm): HealthPayload {
  if (!form.own) throw new Error('Bitte bestätigen: Dies ist deine eigene Angabe.');
  if (!form.metric.trim() || form.metric.length > 100 || !form.unit.trim() || form.unit.length > 40)
    throw new Error('Bitte Messgröße und Einheit angeben.');
  if (form.value.length > 32 || !/^[+-]?[0-9]+(?:[.,][0-9]+)?$/.test(form.value))
    throw new Error('Bitte einen Zahlenwert ohne Tausendertrennzeichen angeben.');
  if (form.note.length > 4000 || [form.metric,form.unit].some(v=>/[\u0000-\u001f]/.test(v)) || /[\u0000-\u0008\u000b-\u001f]/.test(form.note))
    throw new Error('Bitte lesbaren Text angeben.');
  const match = form.localTime.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(:\d{2}(?:\.\d{1,6})?)?$/);
  if (!match || match[1].startsWith('0000') || !/^(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(form.offset))
    throw new Error('Bitte Datum, Uhrzeit und UTC-Zeitversatz prüfen.');
  const clock = `${match[1]}T${match[2]}${match[3] || ':00'}`;
  const test = new Date(clock + 'Z');
  if (!Number.isFinite(test.getTime()) || test.toISOString().slice(0,19) !== clock.slice(0,19))
    throw new Error('Bitte einen gültigen Messzeitpunkt angeben.');
  return {subject:'self',metric:form.metric,value:form.value,unit:form.unit,observed_at:clock+form.offset,note:form.note};
}

/** Suggest only a unique device-zone offset; a repeated/missing DST hour needs a deliberate choice. */
export function deviceOffsets(localTime: string): string[] {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(localTime)) return [];
  const base = new Date(localTime);
  if (!Number.isFinite(base.getTime())) return [];
  const wall = (d: Date) => `${String(d.getFullYear()).padStart(4,'0')}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}${localTime.length > 16 ? ':'+String(d.getSeconds()).padStart(2,'0') : ''}`;
  const offsets = new Set<string>();
  for(let delta=-180;delta<=180;delta+=30) {
    const candidate = new Date(base.getTime()+delta*60000);
    if(wall(candidate)!==localTime) continue;
    const minutes=-candidate.getTimezoneOffset();
    offsets.add(`${minutes<0?'-':'+'}${String(Math.floor(Math.abs(minutes)/60)).padStart(2,'0')}:${String(Math.abs(minutes)%60).padStart(2,'0')}`);
  }
  return [...offsets];
}

/** Changed data gets a fresh identifier; retrying the same failed send keeps it. */
export class HealthSaveRequest {
  private key = '';
  private id = '';
  private allocate: () => string;
  constructor(allocate: () => string = () => crypto.randomUUID()) {this.allocate=allocate;}
  for(payload: HealthPayload, correction?: {id: string; expected_support_fingerprint: string}) {
    const key=JSON.stringify([payload,correction]);
    if(key!==this.key) {this.key=key;this.id=this.allocate();}
    return {...payload,request_id:this.id,...(correction ? {expected_support_fingerprint:correction.expected_support_fingerprint} : {})};
  }
  done() {this.key='';this.id='';}
}
