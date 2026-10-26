// Kleine reine Hilfen für „Projekte von selbst“ (sidecar: projekt_automatik.py); ohne React, damit `node --test` sie
// prüft. Ein Projekt ist Ablage, kein Fakt: Kingfisher legt klare selbst an, sagt es in einer Zeile mit Grund und bietet
// „Rückgängig“ an. Personen gehören nur abgeleitet dazu (wer in denselben Quellen vorkommt), nie als gespeicherte Aussage.

export type NeuesProjektKurz = { name: string; anzahl: number; wort: string; personen: string[] };
export type Verbunden = { sache: string; name: string; art: string };

/** „Anna Keller“, „Anna Keller und Ben Braun“, „A, B und C“. */
export function aufzaehlung(namen: string[]): string {
  const liste = namen.filter(Boolean);
  if (liste.length <= 1) return liste[0] ?? "";
  return `${liste.slice(0, -1).join(", ")} und ${liste[liste.length - 1]}`;
}

/** „Umbau Praxis, aus 4 Mails mit Anna Keller und Ben Braun“: Name, Zahl, Menschen. */
export function projektGrund(p: NeuesProjektKurz): string {
  const zahl = p.anzahl > 0 ? `, aus ${p.anzahl} ${p.anzahl === 1 ? einzahl(p.wort) : p.wort}` : "";
  const mit = p.personen.length ? ` mit ${aufzaehlung(p.personen)}` : "";
  return `${p.name}${zahl}${mit}`;
}

function einzahl(wort: string): string {
  return ({ Mails: "Mail", Notizen: "Notiz", Terminen: "Termin", Quellen: "Quelle" } as Record<string, string>)[wort] ?? wort;
}

/** Die eine Zeile auf Heute: ein Projekt mit Grund, mehrere zusammengefasst mit ihren Namen. Leer: kein Satz. */
export function neueProjekteZeile(liste: NeuesProjektKurz[]): string | null {
  if (!liste.length) return null;
  if (liste.length === 1) return `Neues Projekt: ${projektGrund(liste[0])}`;
  return `${liste.length} neue Projekte: ${aufzaehlung(liste.map(p => p.name))}`;
}

/** Unter dem Kopf einer Akte: bei einer Person ihre Projekte, bei einem Projekt seine Beteiligten (abgeleitet aus
 * „Zusammenhänge“, häufigste zuerst). Nur angelegte Projekte, keine bloßen Erwähnungen. Höchstens drei Namen. */
export function verbundenZeile(art: string, beteiligte: Verbunden[]): { titel: string; eintraege: Verbunden[]; weitere: number } | null {
  const passend = art === "person" ? beteiligte.filter(b => b.art === "projekt" && !b.sache.startsWith("projekt:n:"))
    : art === "projekt" ? beteiligte.filter(b => b.art === "person") : [];
  if (!passend.length) return null;
  const eintraege = passend.slice(0, 3);
  return { titel: art === "person" ? "Projekte" : "Beteiligte", eintraege, weitere: passend.length - eintraege.length };
}
