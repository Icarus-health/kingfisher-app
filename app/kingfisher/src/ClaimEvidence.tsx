import { ProfileSource } from "./ProfileSource";

export function ClaimEvidence({claim}: {claim: Record<string, unknown>}) {
  const evidence = Array.isArray(claim.evidence) ? claim.evidence.filter(item => item && typeof item === "object") as Array<Record<string, unknown>> : [];
  if (!evidence.length) return <p>Keine direkt öffnende Originalquelle hinterlegt.</p>;
  return <div className="claim-evidence">{evidence.map((item, index) => <blockquote key={index}>
    <p>{typeof item.quote === "string" ? item.quote : "Kein Auszug hinterlegt."}</p>
    {typeof item.episode_id === "string" && item.episode_id ? <ProfileSource kind="episode" id={item.episode_id} label="Originalquelle öffnen" /> : <p>Die Originalquelle ist nicht verknüpft.</p>}
  </blockquote>)}</div>;
}
