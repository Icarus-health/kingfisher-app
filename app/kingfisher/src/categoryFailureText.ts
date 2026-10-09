const labels: Record<string, string> = {
  validation_output_format: "Das Ergebnis ließ sich nicht sicher auswerten.",
  validation_category_evidence: "Themenvorschläge ließen sich nicht mit der Quelle belegen.",
  validation_entity_format: "Erwähnungshinweise ließen sich nicht sicher prüfen.",
  validation_entity_missing: "Erwähnungshinweise ließen sich nicht sicher prüfen.",
  validation_entity_ambiguous: "Erwähnungshinweise ließen sich nicht sicher prüfen.",
  validation_entity_span: "Erwähnungshinweise ließen sich nicht sicher prüfen.",
  validation_entity_sender: "Erwähnungshinweise ließen sich nicht sicher prüfen.",
  validation_entity_duplicate: "Erwähnungshinweise ließen sich nicht sicher prüfen.",
  validation_unspecified: "Das Ergebnis ließ sich nicht sicher auswerten.",
  provider_error: "Die Themenauswertung beim Modellanbieter konnte nicht abgeschlossen werden.",
  internal_error: "Ein technischer Fehler trat auf.",
};

export function categoryFailureText(code: string | null | undefined): string {
  return typeof code === "string" && Object.prototype.hasOwnProperty.call(labels, code)
    ? labels[code]
    : "Automatische Zuordnung fehlgeschlagen; Ursache unbekannt.";
}
