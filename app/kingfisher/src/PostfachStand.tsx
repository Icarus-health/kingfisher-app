import { useEffect, useState } from "react";
import { api, type MailStand } from "./api";
import { postfachAufHeute } from "./heute";

/** Auf Heute: je Postfach der Satz, der erklärt, warum keine Mails dastehen; derselbe wie unter „Für Techniker“. */
export function PostfachStand() {
  const [stand, setStand] = useState<Array<MailStand & { label: string; account_id: string }> | null>(null);
  useEffect(() => {
    let aktiv = true;
    api.mailStand().then(daten => { if (aktiv) setStand(daten.accounts); }).catch(() => { /* Heute bleibt ohne diese Zeile benutzbar. */ });
    return () => { aktiv = false; };
  }, []);
  const zeigen = (stand ?? []).filter(eintrag => postfachAufHeute(eintrag.zustand));
  if (!zeigen.length) return null;
  return <div className="today-postfach" role="status">
    {zeigen.map(eintrag => <p key={eintrag.account_id}>{eintrag.satz}</p>)}
  </div>;
}
