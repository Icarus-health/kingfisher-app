// Mit Microsoft anmelden (docs/50-microsoft-365.md): Sätze, Restzeit und Nachfragen, ohne React, damit `node --test`
// sie prüfen kann. Die Karte dazu steht in MicrosoftAnmeldungKarte.tsx. Kein Token und kein Gerätecode kommen hier je an:
// Der Sidecar gibt nur den kurzen Code, den Link und den Stand heraus.
import type { AnbieterErkennung, MicrosoftAnmeldung } from "./api";

export const MS_LINK = "https://microsoft.com/devicelogin";
/** So oft fragt die Oberfläche nach (der Sidecar fragt Microsoft nur so oft, wie Microsoft es erlaubt). */
export const NACHFRAGE_MS = 3000;

export const SAETZE = {
  einleitung: "Du meldest dich im Browser bei Microsoft an, wie du es von deiner Hochschule oder Firma kennst. Kingfisher bekommt danach Lesezugriff auf deine Post und deinen Kalender. Es schreibt, verschickt und löscht dort nichts.",
  mitschriften: "Kingfisher liest dann auch die Mitschriften deiner Teams-Besprechungen. Microsoft gibt sie erst frei, wenn die IT deiner Hochschule oder Firma zugestimmt hat.",
  schritte: "Öffne die Seite von Microsoft, trag dort diesen Code ein und melde dich an.",
  admin: "Zeigt Microsoft „Genehmigung erforderlich“ oder „Need admin approval“, muss die IT deiner Hochschule oder Firma Kingfisher erst freigeben.",
  ohneApp: "Für die Anmeldung bei Microsoft fehlt noch die Kennung der App. Ein Techniker trägt sie unter „Für Techniker“ ein.",
  ohnePasswortWeg: "Erlaubt deine Hochschule oder Firma die Anmeldung mit Passwort, kannst du dein Postfach bis dahin auch mit Adresse und Passwort verbinden.",
  ohneSpeicher: "Auf diesem Rechner fehlt der geschützte Speicher für Zugänge; die Anmeldung bei Microsoft ist deshalb gesperrt.",
  bleibt: "Die Anmeldung bleibt im Schlüsselbund dieses Rechners. Trennen beendet sie für Kingfisher; zurückziehen kannst du sie zusätzlich in deinem Microsoft-Konto.",
} as const;

/** „noch 14 Minuten“, „noch eine Minute“, „noch 40 Sekunden“: wie lange der Code noch gilt. */
export function restText(sekunden: number | undefined): string {
  const s = Math.max(0, Math.floor(sekunden ?? 0));
  if (s >= 120) return `noch ${Math.floor(s / 60)} Minuten`;
  if (s >= 60) return "noch eine Minute";
  return s === 1 ? "noch eine Sekunde" : `noch ${s} Sekunden`;
}

export const istFertig = (stand: MicrosoftAnmeldung | null) => !!stand && stand.status !== "waiting" && stand.status !== "ready";

/**
 * Der Satz zu einem schon verbundenen Microsoft-Konto, aus dem gespeicherten Stand (`/api/v1/microsoft/konten`).
 * Der Assistent liest seinen Stand regelmäßig neu; sieht er das neue Postfach vor der Anmeldekarte, verschwindet die Karte.
 * Die Bestätigung kommt deshalb aus dem gespeicherten Konto, nicht nur aus dem Rückruf der Karte.
 */
export function kontoSatz(konto: {adresse: string; verbunden: boolean; post: boolean; kalender: boolean; mitschriften: boolean}): string | null {
  if (!konto.verbunden || !konto.post) return null;
  const teile = ["Post", konto.kalender ? "Kalender" : "", konto.mitschriften ? "Teams-Mitschriften" : ""].filter(Boolean);
  const was = teile.length > 1 ? `${teile.slice(0, -1).join(", ")} und ${teile[teile.length - 1]}` : teile[0];
  return `Verbunden: ${was} von ${konto.adresse}. Deine Post liest Kingfisher erst, wenn du „Mails einlesen“ wählst.`;
}

/** Der eine Satz zum Stand einer Anmeldung. */
export function standSatz(stand: MicrosoftAnmeldung): string {
  if (stand.status === "waiting") return `Kingfisher wartet auf deine Anmeldung bei Microsoft (der Code gilt ${restText(stand.restsekunden)}).`;
  if (stand.status === "ready") return "Anmeldung erhalten. Kingfisher richtet Post und Kalender ein …";
  if (stand.status === "connected") {
    const was = stand.mitschriften_an ? "Post, Kalender und Teams-Mitschriften" : "Post und Kalender";
    const ohne = stand.ohne_mitschriften ? " Die Teams-Mitschriften hat Microsoft nicht freigegeben; dafür muss die IT zustimmen." : "";
    return `Verbunden: ${was} von ${stand.email ?? "deinem Konto"}. Deine Post liest Kingfisher erst, wenn du „Mails einlesen“ wählst.${ohne}`;
  }
  return stand.satz ?? "Die Anmeldung bei Microsoft wurde nicht abgeschlossen. Starte sie neu.";
}

/**
 * Soll der Mail-Schritt die Microsoft-Anmeldung anbieten? Nur bei Hochschule oder Firma (Microsoft 365), wie es die
 * eine Anbieter-Erkennung meldet; private Konten (outlook.com) und Google gehen den Weg mit Adresse und Passwort.
 */
export const microsoftZuerst = (erkannt: Pick<AnbieterErkennung, "dienst" | "art"> | null) =>
  !!erkannt && erkannt.dienst === "microsoft" && erkannt.art === "organisation";

/** Fragt nach, bis die Anmeldung fertig ist; eine Anfrage zur Zeit, nach `stop()` kommt keine Antwort mehr an. */
export function nachfragen({ lesen, beiStand, beiFehler, abstand = NACHFRAGE_MS }: {
  lesen: () => Promise<MicrosoftAnmeldung>;
  beiStand: (stand: MicrosoftAnmeldung) => void;
  beiFehler: () => void;
  abstand?: number;
}) {
  let gestoppt = false;
  let laeuft = false;
  let zeitgeber: ReturnType<typeof setTimeout> | undefined;
  function stop() { gestoppt = true; clearTimeout(zeitgeber); }
  async function jetzt() {
    if (gestoppt || laeuft) return;
    clearTimeout(zeitgeber);
    laeuft = true;
    try {
      const stand = await lesen();
      if (gestoppt) return;
      if (istFertig(stand)) stop();
      beiStand(stand);
    } catch {
      if (!gestoppt) beiFehler();
    } finally {
      laeuft = false;
      if (!gestoppt) zeitgeber = setTimeout(jetzt, abstand);
    }
  }
  zeitgeber = setTimeout(jetzt, abstand);
  return { jetzt, stop };
}
