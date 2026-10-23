import { useEffect, useState } from "react";
import { api, type MailStand } from "./api";
import { postfachAufHeute, postfachMussHandeln } from "./heute";
import { SatzMitVerweis } from "./VerweisLink";

/** Auf Heute nur, wenn ein Postfach den Menschen braucht, etwa weil die Anmeldung abgelaufen ist: dann der Satz mit
 * dem Weg als Klick, offen und ohne Klappe. Sonst nichts; der Stand jedes Postfachs steht unter Einstellungen →
 * Zugänge (Paket U, H6). Dass die Post noch geholt wird, sagt die Zeile unter dem Kopf. */
export function PostfachStand({ ausstehend = false }: { ausstehend?: boolean }) {
  const [stand, setStand] = useState<Array<MailStand & { label: string; account_id: string }> | null>(null);
  useEffect(() => {
    // Erst nach der Post lesen: Der Blick in den Posteingang macht aus „noch nicht abgerufen“ erst „leer, abgerufen um …“.
    if (ausstehend) return;
    let aktiv = true;
    api.mailStand().then(daten => { if (aktiv) setStand(daten.accounts); }).catch(() => { /* Heute bleibt ohne diese Zeile benutzbar. */ });
    return () => { aktiv = false; };
  }, [ausstehend]);
  const zeigen = (stand ?? []).filter(eintrag => postfachAufHeute(eintrag.zustand) && Boolean(eintrag.verweis));
  const mussHandeln = postfachMussHandeln(zeigen);
  if (ausstehend || !mussHandeln) return null;
  return <div className="today-postfach" role="status">
    {zeigen.map(eintrag => <p key={eintrag.account_id}><SatzMitVerweis satz={eintrag.satz} ziel={eintrag.verweis} /></p>)}
  </div>;
}
