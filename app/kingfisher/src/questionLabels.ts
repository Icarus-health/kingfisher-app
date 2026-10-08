/** Small, conservative labels for common knowledge relations. Unknown relations stay generic. */
const labels: Record<string, string> = {
  advises: "Beratung",
  budget: "Budget",
  contact: "Kontaktangabe",
  deadline: "Frist",
  has_role: "Rolle",
  has_status: "Status",
  leads: "Verantwortung",
  note: "Notiz",
  observed_email: "E-Mail-Adresse",
  owner: "Zuständigkeit",
  plan: "Planung",
  project_role: "Rolle im Projekt",
  reports: "Berichtete Angabe",
  role: "Rolle",
  status: "Status",
  works_on: "Mitarbeit an einem Vorhaben",
};

export function questionRelationLabel(predicate: string): string {
  return Object.hasOwn(labels, predicate) ? labels[predicate] : "Angabe";
}

export function questionTitle(statement: string): string {
  const clean = statement.trim();
  return clean || "Mögliche Angabe prüfen";
}
