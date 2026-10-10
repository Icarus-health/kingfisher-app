import type {HealthObservation} from './api';

function instant(value: string): bigint | null {
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match) return null;
  const seconds = Date.parse(match[1]+match[3]);
  if (!Number.isFinite(seconds)) return null;
  return BigInt(seconds)*1000n+BigInt((match[2] ?? '').padEnd(6,'0'));
}

/** Plot one source-backed measurement series without changing literal values. */
export function healthSeries(items: HealthObservation[]) {
  if (items.length < 2) return null;
  const first = items[0];
  if (items.some(item => item.status !== 'current'
    || item.metric.trim().toLowerCase() !== first.metric.trim().toLowerCase()
    || item.unit.trim() !== first.unit.trim()
    || !/^[+-]?[0-9]+(?:[.,][0-9]+)?$/.test(item.value))) return null;
  const parsedTimes = items.map(item=>instant(item.observed_at));
  if (parsedTimes.some(value=>value===null)) return null;
  const stamps = parsedTimes.map(value=>value!);
  const parts = items.map(item => item.value.replace(',','.').replace(/^[+-]/,'').split('.'));
  const scale = Math.max(...parts.map(([,fraction=''])=>fraction.length));
  // Subtract exact decimal integers before converting a dimensionless ratio.
  // Otherwise two large, close original decimals could become a false flat line.
  const values = parts.map(([whole,fraction=''],i) => BigInt(whole+fraction.padEnd(scale,'0'))
    * (items[i].value.startsWith('-') ? -1n : 1n));
  const low = values.reduce((a,b)=>a<b?a:b), high = values.reduce((a,b)=>a>b?a:b);
  const start = stamps.reduce((a,b)=>a<b?a:b), end = stamps.reduce((a,b)=>a>b?a:b);
  const points = items.map((item,i)=>({id:item.id,value:item.value,observed_at:item.observed_at,stamp:stamps[i],
    x: end===start ? 0.5 : Number(stamps[i]-start)/Number(end-start),
    y: high===low ? 0.5 : 1-Number(values[i]-low)/Number(high-low)}))
    .sort((a,b)=>a.stamp<b.stamp?-1:a.stamp>b.stamp?1:0)
    .map(({stamp:_,...point})=>point);
  return {metric:first.metric,unit:first.unit,points,
    minimum:items[values.indexOf(low)].value,maximum:items[values.indexOf(high)].value};
}
