import type {HealthObservation} from './api';
import {healthSeries} from './healthSeries';

export function HealthTrend({items}: {items: HealthObservation[]}) {
  const series = healthSeries(items);
  if (!series) return null;
  const x=(value:number)=>60+value*520, y=(value:number)=>20+value*120;
  return <figure className="health-trend">
    <figcaption><strong>{series.metric} · {series.unit}</strong><p>Verlauf der {series.points.length} Angaben in diesem geladenen Ausschnitt. Punkte öffnen den jeweiligen Eintrag; dort liegt die Originalquelle. Keine medizinische Bewertung.</p></figcaption>
    <svg viewBox="0 0 640 170" role="img" aria-label={`${series.metric} in ${series.unit}: datierter Verlauf im geladenen Ausschnitt`}>
      <line x1="60" y1="20" x2="60" y2="140" className="health-trend-axis" />
      <line x1="60" y1="140" x2="580" y2="140" className="health-trend-axis" />
      <polyline points={series.points.map(point=>`${x(point.x)},${y(point.y)}`).join(' ')} className="health-trend-line" />
      {series.points.map(point=><a key={point.id} href={`#health-observation-${encodeURIComponent(point.id)}`} aria-label={`${point.value} ${series.unit}, ${point.observed_at}: Eintrag öffnen`}>
        <circle cx={x(point.x)} cy={y(point.y)} r="5"><title>{point.value} {series.unit} · {point.observed_at}</title></circle>
      </a>)}
    </svg>
    <div className="health-trend-range"><span>Minimum: {series.minimum} {series.unit}</span><span>Maximum: {series.maximum} {series.unit}</span></div>
    <div className="health-trend-range"><time dateTime={series.points[0].observed_at}>{series.points[0].observed_at.replace('T',' · ')}</time><time dateTime={series.points.at(-1)!.observed_at}>{series.points.at(-1)!.observed_at.replace('T',' · ')}</time></div>
  </figure>;
}
