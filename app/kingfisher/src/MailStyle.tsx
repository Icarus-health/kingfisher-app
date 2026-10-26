import { useEffect, useRef, useState } from "react";
import { ProfileSource } from "./ProfileSource";
import { LEERE_REGELN, REGEL_WERTE, belegeTitel, bestaetigtSatz, tonSatz, type StilBeleg, type StilProfil, type StilRegeln, type StilVorschlag } from "./stilprofil";
import "./MailStyle.css";

type Rules = StilRegeln;

type StyleData = {
  contact: string;
  kreis: { kreis: string; kreis_text: string } | null;
  profiles: { global: StilProfil | null; kreis: StilProfil | null; contact: StilProfil | null };
  examples: Array<{ id: string; text: string; created_at: string }>;
  gesendete: StilBeleg[];
  proposal: StilVorschlag | null;
  abgelehnt: boolean;
};

const EMPTY: Rules = LEERE_REGELN;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 60000);

  try {
    const response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      signal: controller.signal,
      headers: {
        ...(init?.body ? { "content-type": "application/json" } : {}),
        ...init?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json() as T;
  } finally {
    window.clearTimeout(timeout);
  }
}

function readableDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
}

type MailStyleProps = {
  uid: string;
  draft: string;
  originalSuggestion: string | null;
};

export function MailStyle({ uid, draft, originalSuggestion }: MailStyleProps) {
  const [data, setData] = useState<StyleData | null>(null);
  const [scope, setScope] = useState<"global" | "contact">("contact");
  const scopeRef = useRef<"global" | "contact">("contact");
  const [rules, setRules] = useState<Rules>(EMPTY);
  const [own, setOwn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");

    request<StyleData>(`/api/v1/messages/${encodeURIComponent(uid)}/style`)
      .then(next => {
        if (!active) return;
        const selectedScope = scopeRef.current;
        setData(next);
        setRules({ ...EMPTY, ...(next.profiles[selectedScope]?.rules ?? {}) });
      })
      .catch(() => {
        if (active) setError("Der Schreibstil konnte nicht geladen werden.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [uid, revision]);

  async function save(
    nextRules: Rules,
    evidenceIds: string[] = [],
    targetScope: "global" | "contact" = scopeRef.current,
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");

    try {
      await request<StyleData>(
        `/api/v1/messages/${encodeURIComponent(uid)}/style`,
        {
          method: "PUT",
          body: JSON.stringify({
            scope: targetScope,
            rules: nextRules,
            evidence_ids: evidenceIds,
          }),
        },
      );
      setNotice(evidenceIds.length ? "Übernommen. Dieser Ton gilt jetzt für Entwürfe an diesen Kontakt." : "Schreibstil gespeichert.");
      setRevision(value => value + 1);
    } catch {
      setError("Der Schreibstil konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss(evidenceIds: string[]) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await request<StyleData>(
        `/api/v1/messages/${encodeURIComponent(uid)}/style/ablehnen`,
        { method: "POST", body: JSON.stringify({ evidence_ids: evidenceIds }) },
      );
      setData(next);
      setNotice("Nicht übernommen. Kommt eine neue gesendete Mail dazu, fragt Kingfisher wieder.");
    } catch {
      setError("Das ließ sich gerade nicht merken. Bitte noch einmal versuchen.");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    if (busy) return;
    const selectedScope = scopeRef.current;
    setBusy(true);
    setError("");
    setNotice("");

    try {
      const next = await request<StyleData>(
        `/api/v1/messages/${encodeURIComponent(uid)}/style/${selectedScope}`,
        { method: "DELETE" },
      );
      setData(next);
      setRules({ ...EMPTY, ...(next.profiles[selectedScope]?.rules ?? {}) });
      setNotice("Schreibstil zurückgesetzt.");
    } catch {
      setError("Die Regeln konnten nicht zurückgesetzt werden.");
    } finally {
      setBusy(false);
    }
  }

  async function learn() {
    if (!data || !own || !draft.trim() || draft === originalSuggestion || busy) return;
    setBusy(true);
    setError("");
    setNotice("");

    try {
      const next = await request<StyleData>(
        `/api/v1/messages/${encodeURIComponent(uid)}/style/examples`,
        {
          method: "POST",
          body: JSON.stringify({
            text: draft,
            original_suggestion: originalSuggestion,
            own_text_confirmed: true,
          }),
        },
      );
      setData(next);
      setOwn(false);
      setNotice("Eigener Entwurf als Lernbeleg gespeichert.");
    } catch {
      setError("Der Lernbeleg konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function removeExample(id: string) {
    if (busy) return;
    const selectedScope = scopeRef.current;
    setBusy(true);
    setError("");

    try {
      const next = await request<StyleData>(
        `/api/v1/messages/${encodeURIComponent(uid)}/style/examples/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      );
      setData(next);
      setRules({ ...EMPTY, ...(next.profiles[selectedScope]?.rules ?? {}) });
    } catch {
      setError("Der Lernbeleg konnte nicht entfernt werden.");
    } finally {
      setBusy(false);
    }
  }

  const canLearn = Boolean(draft.trim()) && draft !== originalSuggestion;
  const profile = data?.profiles[scope];
  const controlsDisabled = busy || loading;

  return (
    <details className="mail-style">
      <summary>Mein Schreibstil</summary>

      {!data && !error ? <p role="status">Schreibstil wird geladen …</p> : null}

      {data ? (
        <>
          {data.proposal ? (
            <section className="mail-style-proposal mail-style-ton" aria-label="Vorschlag für den Ton">
              <p className="mail-style-ton-satz">{tonSatz(data.contact || "diesen Kontakt", data.proposal)}</p>
              <div className="mail-style-actions">
                <button
                  className="secondary-action"
                  type="button"
                  disabled={controlsDisabled}
                  onClick={() => void save(data.proposal!.rules, data.proposal!.evidence_ids, "contact")}
                >
                  Übernehmen
                </button>
                <button
                  className="secondary-action"
                  type="button"
                  disabled={controlsDisabled}
                  onClick={() => void dismiss(data.proposal!.evidence_ids)}
                >
                  Nicht übernehmen
                </button>
                <button
                  className="text-action"
                  type="button"
                  disabled={controlsDisabled}
                  onClick={() => void save(data.proposal!.rules, data.proposal!.evidence_ids, "global")}
                >
                  Für alle Kontakte übernehmen
                </button>
              </div>
            </section>
          ) : null}

          {data.gesendete.length ? (
            <details className="mail-style-belege">
              <summary>{belegeTitel(data.gesendete.length)}</summary>
              <p>Deine Mails an {data.contact || "diesen Kontakt"}, ohne zitierte frühere Nachrichten. Sie bleiben auf diesem Rechner.</p>
              {data.gesendete.map(beleg => (
                <article key={beleg.id}>
                  <strong>{beleg.title || "(Ohne Betreff)"}</strong>
                  <small>{readableDate(beleg.occurred_at)}</small>
                  <p>{beleg.text}</p>
                  <ProfileSource kind="episode" id={beleg.id} label="Mail öffnen" readOnly />
                </article>
              ))}
            </details>
          ) : null}

          <p>
            Bestätigte Regeln für {scope === "global" ? "alle Kontakte" : data.contact || "diesen Kontakt"}.
            „Standard“ übernimmt die allgemeine Vorgabe{data.kreis ? ` oder die des Kreises „${data.kreis.kreis_text}“` : ""}.
          </p>
          {data.kreis ? (
            <p className="mail-style-kreis">
              Kreis „{data.kreis.kreis_text}“: {data.profiles.kreis ? bestaetigtSatz(data.profiles.kreis.rules) : "ohne eigene Regel."}{" "}
              Den Ton je Kreis legst du unter Einstellungen → Kingfisher und du fest.
            </p>
          ) : null}

          <label className="mail-style-scope">
            Geltungsbereich
            <select
              disabled={controlsDisabled}
              value={scope}
              onChange={event => {
                const next = event.target.value as "global" | "contact";
                scopeRef.current = next;
                setScope(next);
                setRules({ ...EMPTY, ...(data.profiles[next]?.rules ?? {}) });
              }}
            >
              <option value="contact">Diesen Kontakt</option>
              <option value="global">Alle Kontakte</option>
            </select>
          </label>

          {(["address", "anrede_form", "length", "emoji", "sprache"] as const).map(field => (
            <label className="mail-style-rule" key={field}>
              {{ address: "Anrede", anrede_form: "Form der Anrede", length: "Länge", emoji: "Emojis", sprache: "Sprache" }[field]}
              <select
                disabled={controlsDisabled}
                value={rules[field]}
                onChange={event =>
                  setRules(current => ({ ...current, [field]: event.target.value }))
                }
              >
                {Object.entries(REGEL_WERTE[field]).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          ))}
          <label className="mail-style-rule">
            Grußformel
            <input
              type="text"
              maxLength={60}
              disabled={controlsDisabled}
              placeholder="Standard"
              value={rules.gruss}
              onChange={event => setRules(current => ({ ...current, gruss: event.target.value }))}
            />
          </label>

          <div className="mail-style-actions">
            <button
              className="secondary-action"
              type="button"
              disabled={controlsDisabled}
              onClick={() => void save(rules)}
            >
              Regeln speichern
            </button>
            {profile ? (
              <button
                className="text-action"
                type="button"
                disabled={controlsDisabled}
                onClick={() => void reset()}
              >
                Regeln zurücksetzen
              </button>
            ) : null}
          </div>

          <section className="mail-style-learning">
            <h3>Eigene Lernbelege für {data.contact || "diesen Kontakt"}</h3>
            <p>
              Als Belege für deinen Ton zählen deine gesendeten Mails an diesen Kontakt und Entwürfe, die du hier
              ausdrücklich als eigene bestätigst. Eine Regel entsteht erst, wenn du den Vorschlag übernimmst.
            </p>
            <label>
              <input
                type="checkbox"
                disabled={controlsDisabled || !canLearn}
                checked={own}
                onChange={event => setOwn(event.target.checked)}
              />
              Das ist mein eigener bearbeiteter Entwurf.
            </label>
            <button
              className="secondary-action"
              type="button"
              disabled={controlsDisabled || !own || !canLearn}
              onClick={() => void learn()}
            >
              Meinen bearbeiteten Entwurf als Lernbeleg merken
            </button>

            {data.examples.length ? data.examples.map(example => (
              <article key={example.id}>
                <p>{example.text}</p>
                <small>{new Date(example.created_at).toLocaleString("de-DE")}</small>
                <button
                  className="text-action"
                  type="button"
                  disabled={controlsDisabled}
                  onClick={() => void removeExample(example.id)}
                >
                  Lernbeleg entfernen
                </button>
              </article>
            )) : <p>Noch keine eigenen Lernbelege.</p>}
          </section>
        </>
      ) : null}

      {error ? (
        <p role="alert">
          {error}{" "}
          <button
            type="button"
            disabled={controlsDisabled}
            onClick={() => setRevision(value => value + 1)}
          >
            Erneut versuchen
          </button>
        </p>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
    </details>
  );
}
