import {useEffect, useRef} from "react";

/**
 * Eine Meldung, die nach einem Klick erscheint, steht dort, wo der Mensch hinsieht (Fremdprobe 2, Befund 4): Sobald es
 * einen Text gibt, rollt die Seite zur Meldung und der Fokus springt hinein (Bildschirmleser lesen sie vor). Das
 * Element braucht `tabIndex={-1}`.
 */
export function useImBlick<T extends HTMLElement>(text: string) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const element = ref.current;
    if (!text || !element) return;
    element.scrollIntoView({block: "center", behavior: "smooth"});
    element.focus({preventScroll: true});
  }, [text]);
  return ref;
}
