import {navigate} from "./ui";
import {verweis} from "./verweis";

/** Ein Verweis in die Einstellungen, der dorthin springt (`ziel` wie `darf` oder `technik-hintergrund`, Befund 25). */
export function Verweis({ziel}: {ziel: string}) {
  const {href, text} = verweis(ziel);
  return <a className="verweis" href={href} onClick={event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    navigate(href);
  }}>{text}</a>;
}
