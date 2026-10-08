export function cloudIssueText(issue:{stage:string;code:string;reason?:string}):string {
  const reasons:Record<string,string> = {
    entity_missing:"Die genannte Originalstelle fehlt im angegebenen Abschnitt.",
    entity_ambiguous:"Der Name kommt mehrfach vor; die gemeinte Originalstelle ist unklar.",
    entity_sender:"Die Zuordnung zum Absender ist nicht belegt.",
    entity_duplicate:"Die Modellantwort enthält einen doppelten Personen- oder Entitätsbeleg.",
    entity_span:"Der angegebene Originalbereich ist ungültig.",
    entity_format:"Die Personen- oder Entitätsangaben haben ein ungültiges Format.",
    category_evidence:"Der Themenvorschlag ist nicht durch den angegebenen Originalabschnitt belegt.",
    output_format:"Die Modellantwort hat ein ungültiges Format.",
  };
  const detail=issue.code==="unsupported_source"
    ? "Die Quelle ist unvollständig oder überschreitet eine Auswertungsgrenze."
    : (issue.reason && Object.hasOwn(reasons,issue.reason) ? reasons[issue.reason]
       : "Die Modellantwort ließ sich nicht vollständig an der Originalmail belegen.");
  return issue.stage==="categories"
    ? `Themen und Personen offen. ${detail} Die gespeicherte Grundeinordnung bleibt erhalten.`
    : detail;
}
