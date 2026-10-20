import { useEffect, useRef, useState } from "react";
import { api, type MailStand } from "./api";
import { postfachAufHeute, postfachMussHandeln } from "./heute";
import { SatzMitVerweis } from "./VerweisLink";

/** Auf Heute: je Postfach der Satz, der erklärt, warum keine Mails dastehen; derselbe wie unter „Für Techniker“.
 * Eingeklappt unter „Postfachstand“ (das Wesentliche zuerst); muss der Mensch etwas tun, etwa sich neu anmelden, weil
 * die Anmeldung abgelaufen ist, steht die Klappe offen und der Weg im Satz ist ein Klick. */
export function PostfachStand({ ausstehend = false }: { ausstehend?: boolean }) {
  const [stand, setStand] = useState<Array<MailStand & { label: string; account_id: string }> | null>(null);
  const klappe = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    // Erst nach der Post lesen: Der Blick in den Posteingang macht aus „noch nicht abgerufen“ erst „leer, abgerufen um …“.
    if (ausstehend) return;
    let aktiv = true;
    api.mailStand().then(daten => { if (aktiv) setStand(daten.accounts); }).catch(() => { /* Heute bleibt ohne diese Zeile benutzbar. */ });
    return () => { aktiv = false; };
  }, [ausstehend]);
  const zeigen = (stand ?? []).filter(eintrag => postfachAufHeute(eintrag.zustand));
  const mussHandeln = postfachMussHandeln(zeigen);
  // Einmal aufklappen, wenn es nötig wird; wer die Klappe danach schließt, behält sie geschlossen.
  useEffect(() => { if (mussHandeln && klappe.current) klappe.current.open = true; }, [mussHandeln]);
  return <details ref={klappe} className="quiet-details today-runtime"><summary>Postfachstand</summary>
    {ausstehend ? <p className="today-post-laedt" role="status">Deine Post wird gerade geholt …</p>
      : zeigen.length ? <div className="today-postfach" role="status">
        {zeigen.map(eintrag => <p key={eintrag.account_id}><SatzMitVerweis satz={eintrag.satz} ziel={eintrag.verweis} /></p>)}
      </div> : null}
  </details>;
}
