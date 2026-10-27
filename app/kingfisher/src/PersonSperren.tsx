import { useEffect, useState } from "react";
import { api, type PersonSperre } from "./api";
import { zeigeHinweis } from "./grundlage";

/**
 * Einstellungen → Kingfisher und du → „Gelöschte Personen“ (Persona-Prüfung, Paket P, D7). Wen du in seiner Akte
 * gelöscht hast, legt Kingfisher nicht wieder an. Hier lässt sich das aufheben; der Hinweis danach bietet „Rückgängig“.
 * Ohne Vermerk steht hier nichts: Eine leere Liste wäre keine Auskunft.
 */
export function PersonSperren() {
  const [sperren, setSperren] = useState<PersonSperre[] | null>(null);
  const [fehler, setFehler] = useState("");

  function laden() {
    return api.personenSperren().then(d => { setSperren(d.sperren); setFehler(""); })
      .catch(() => setFehler("Die gelöschten Personen ließen sich gerade nicht lesen."));
  }
  useEffect(() => { void laden(); }, []);

  async function aufheben(s: PersonSperre) {
    try {
      await api.personSperreAufheben(s.kennung);
      setSperren(alt => (alt ?? []).filter(x => x.kennung !== s.kennung));
      zeigeHinweis({
        text: `${s.anzeige} kommt beim nächsten Einlesen wieder herein.`,
        rueckgaengig: async () => { await api.personSperreZurueck(s.kennung); await laden(); },
        danach: `${s.anzeige} bleibt draußen.`,
      });
    } catch { zeigeHinweis({ text: `Nicht aufgehoben. Kingfisher legt ${s.anzeige} weiter nicht an.`, fehler: true }); }
  }

  if (fehler) return <p role="alert" className="settings-error">{fehler}</p>;
  if (!sperren?.length) return null;
  return <section className="darf-gruppe" aria-labelledby="ich-gesperrt-titel">
    <div className="g-gruppe-kopf"><h2 className="g-gruppe-titel" id="ich-gesperrt-titel">Gelöschte Personen</h2></div>
    <div className="ich">
      {sperren.map(s => <div className="ich-feld ich-gesperrt" key={s.kennung}>
        <div><strong>{s.anzeige}</strong>
          <button type="button" className="g-knopf-getoent" onClick={() => void aufheben(s)}>Wieder aufnehmen</button></div>
        <p className="source-hint">Gelöscht am {new Date(s.angelegt * 1000).toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" })}. Kingfisher legt diese Person beim Einlesen nicht wieder an.</p>
      </div>)}
    </div>
  </section>;
}
