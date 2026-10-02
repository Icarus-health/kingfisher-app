// Die zuletzt getippte Mailadresse, damit niemand sie zweimal tippt (Fremdprobe 2, Befund 3): Der Assistent merkt sie,
// „Postfach hinzufügen“ unter Zugänge bietet sie an. Nur in dieser Browsersitzung, nie auf dem Server; ohne Speicher
// (privates Fenster) bleibt das Feld eben leer.
const SCHLUESSEL = "kingfisher.adresse-entwurf";

export function adresseLesen(): string {
  try { return sessionStorage.getItem(SCHLUESSEL) ?? ""; } catch { return ""; }
}

export function adresseMerken(adresse: string) {
  try {
    if (adresse.trim()) sessionStorage.setItem(SCHLUESSEL, adresse.trim()); else sessionStorage.removeItem(SCHLUESSEL);
  } catch { /* ohne Speicher kein Entwurf */ }
}
