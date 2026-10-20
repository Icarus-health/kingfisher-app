import {navigate} from "./ui";
import {satzMitVerweis, verweis} from "./verweis";

/** Ein Verweis in die Einstellungen, der dorthin springt (`ziel` wie `darf` oder `technik-hintergrund`, Befund 25). */
export function Verweis({ziel}: {ziel: string}) {
  const {href, text} = verweis(ziel);
  return <a className="verweis" href={href} onClick={event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    navigate(href);
  }}>{text}</a>;
}

/** Ein Satz, dessen Weg in die Einstellungen („Einstellungen → Zugänge“) als Verweis klickbar ist (`satzMitVerweis`). */
export function SatzMitVerweis({satz, ziel}: {satz: string; ziel?: string | null}) {
  const teile = satzMitVerweis(satz, ziel);
  if (!teile.verweis || !ziel) return <>{satz}</>;
  return <>{teile.vor}<Verweis ziel={ziel} />{teile.nach}</>;
}
