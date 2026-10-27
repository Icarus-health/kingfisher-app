// Tippziele am Handy (Persona-Prüfung, Paket H, H3): jedes sichtbare Bedienelement braucht eine Trefffläche von
// mindestens 44 × 44 CSS-px, wenn der Zeiger grob ist (`pointer: coarse`, Finger). WCAG 2.5.8 verlangt 24, Apple 44.
//
// Gemessen wird nicht der Kasten des Elements, sondern die wirksame Trefffläche: von seiner Mitte aus waagrecht und
// senkrecht so weit, wie ein Tipp (`elementFromPoint`) noch dieses Element trifft. So zählt eine vergrößerte Fläche über
// ein Pseudo-Element oder ein Innenabstand mit, und ein Nachbar, der darüberliegt, zieht ab. Auch Verweise mitten im Satz
// zählen (WCAG nimmt sie aus, Apple nicht; sie zählen unter `inline` mit). Ausgenommen sind gesperrte Elemente, solche
// ohne Zeigerereignisse (etwa die Punkte im Monat, deren Ziel der Tag ist) und der Sprunglink (nur mit Tastatur zu sehen).
// Ein Feldname (`label for=…`) zählt nicht eigens: Ziel ist das Feld, und das wird gemessen (WCAG 2.5.8, „gleichwertig“);
// ein Kästchen oder Schalter in seinem Label dagegen wird über das Label gemessen.
// Jedes Element wird dafür in die Mitte des Fensters gerollt; trifft seine Mitte dann etwas anderes, steht es unter
// „verdeckt“.
//
// Aufruf aus Playwright: `seite.evaluate(TIPPZIELE_JS, {min: 44, wurzel: 'body'})`; Ergebnis
// `{klein: [{name, w, h, art}], verdeckt: [...], inline, gezaehlt}`. Benutzt von scripts/probe_tippziele_ui.py.
({min = 44, wurzel = 'body'} = {}) => {
  const SEL = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=switch], '
    + '[role=tab], [role=link], [role=checkbox], [role=radio]';
  const root = document.querySelector(wurzel) || document.body;
  const name = el => (el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('placeholder')
    || el.getAttribute('title') || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 50);
  const art = el => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
    ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  // Ein Verweis im Fließtext: inline und mit Text daneben im selben Absatz.
  const imSatz = el => {
    if (el.tagName !== 'A' || getComputedStyle(el).display !== 'inline') return false;
    const p = el.parentElement; if (!p) return false;
    return [...p.childNodes].some(n => n !== el && n.nodeType === 3 && n.textContent.trim().length > 1);
  };
  const ziele = new Set();
  for (const el of root.querySelectorAll(SEL)) {
    // Ein Kästchen oder Schalter in seinem Label: Ziel ist das Label.
    const ziel = el.tagName === 'INPUT' && /^(checkbox|radio)$/.test(el.type) && el.closest('label') ? el.closest('label') : el;
    ziele.add(ziel);
  }
  const aus = {klein: [], verdeckt: [], inline: 0, gezaehlt: 0};
  const sx = scrollX, sy = scrollY;
  for (const el of ziele) {
    if (el.closest('[aria-hidden="true"], [inert], .g-sprunglink')) continue;
    if (el.checkVisibility && !el.checkVisibility({visibilityProperty: true, opacityProperty: true})) continue;
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') continue;
    const cs = getComputedStyle(el);
    if (cs.pointerEvents === 'none') continue;
    let r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    // Eine versteckte Eingabe hinter einem Label (Datei, Schalter) ist nicht das Ziel.
    if (el.tagName === 'INPUT' && (r.width < 4 || r.height < 4)) continue;
    const satz = imSatz(el);
    if (satz) aus.inline++;
    el.scrollIntoView({block: 'center', inline: 'center'});
    r = el.getBoundingClientRect();
    aus.gezaehlt++;
    const cx = Math.min(Math.max(r.left + r.width / 2, 1), innerWidth - 1);
    const cy = Math.min(Math.max(r.top + r.height / 2, 1), innerHeight - 1);
    const trifft = (x, y) => {
      if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) return false;
      const h = document.elementFromPoint(x, y);
      return Boolean(h) && (h === el || el.contains(h));
    };
    if (!trifft(cx, cy)) {
      const h = document.elementFromPoint(cx, cy);
      aus.verdeckt.push({name: name(el), art: art(el), von: h ? art(h) : 'nichts'});
      continue;
    }
    const weit = (dx, dy) => { let n = 0; while (n < min && trifft(cx + dx * (n + 1), cy + dy * (n + 1))) n++; return n; };
    const w = 1 + weit(-1, 0) + weit(1, 0), h = 1 + weit(0, -1) + weit(0, 1);
    if (w < min || h < min) aus.klein.push({name: name(el), w, h, art: art(el), ...(satz ? {inline: true} : {})});
  }
  scrollTo(sx, sy);
  return aus;
}
