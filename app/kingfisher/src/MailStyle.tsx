import { useEffect, useRef, useState } from "react";
import "./MailStyle.css";

type Rules = {
  address: "default" | "du" | "sie";
  length: "default" | "short" | "detailed";
  emoji: "default" | "yes" | "no";
};

type Profile = {
  id: string;
  rules: Rules;
  evidence_ids?: string[];
};

type StyleData = {
  contact: string;
  profiles: { global: Profile | null; contact: Profile | null };
  examples: Array<{ id: string; text: string; created_at: string }>;
  proposal: { rules: Rules; evidence_ids: string[] } | null;
};

const EMPTY: Rules = { address: "default", length: "default", emoji: "default" };

const VALUES = {
  address: { default: "Standard", du: "Du", sie: "Sie" },
  length: { default: "Standard", short: "Kurz", detailed: "Ausführlich" },
  emoji: { default: "Standard", yes: "Ja", no: "Nein" },
} as const;

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
        setRules(next.profiles[selectedScope]?.rules ?? EMPTY);
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
      setNotice("Schreibstil gespeichert.");
      setRevision(value => value + 1);
    } catch {
      setError("Der Schreibstil konnte nicht gespeichert werden.");
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
      setRules(next.profiles[selectedScope]?.rules ?? EMPTY);
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
      setRules(next.profiles[selectedScope]?.rules ?? EMPTY);
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
          <p>
            Bestätigte Regeln für {scope === "global" ? "Allgemein" : data.contact || "diesen Kontakt"}.
            „Standard“ übernimmt die allgemeine Vorgabe.
          </p>

          <label className="mail-style-scope">
            Geltungsbereich
            <select
              disabled={controlsDisabled}
              value={scope}
              onChange={event => {
                const next = event.target.value as "global" | "contact";
                scopeRef.current = next;
                setScope(next);
                setRules(data.profiles[next]?.rules ?? EMPTY);
              }}
            >
              <option value="contact">Diesen Kontakt</option>
              <option value="global">Allgemein</option>
            </select>
          </label>

          {(["address", "length", "emoji"] as const).map(field => (
            <label className="mail-style-rule" key={field}>
              {field === "address" ? "Anrede" : field === "length" ? "Länge" : "Emojis"}
              <select
                disabled={controlsDisabled}
                value={rules[field]}
                onChange={event =>
                  setRules(current => ({ ...current, [field]: event.target.value }))
                }
              >
                {Object.entries(VALUES[field]).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          ))}

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

          {data.proposal ? (
            <section className="mail-style-proposal">
              <h3>Lernvorschlag</h3>
              <p>Aus {data.proposal.evidence_ids.length} bestätigten eigenen Lernbelegen:</p>
              <ul>
                <li>Anrede: {VALUES.address[data.proposal.rules.address]}</li>
                <li>Länge: {VALUES.length[data.proposal.rules.length]}</li>
                <li>Emojis: {VALUES.emoji[data.proposal.rules.emoji]}</li>
              </ul>
              <button
                className="primary-action"
                type="button"
                disabled={controlsDisabled}
                onClick={() =>
                  void save(data.proposal!.rules, data.proposal!.evidence_ids, "contact")
                }
              >
                Für diesen Kontakt übernehmen
              </button>
              <button
                className="secondary-action"
                type="button"
                disabled={controlsDisabled}
                onClick={() =>
                  void save(data.proposal!.rules, data.proposal!.evidence_ids, "global")
                }
              >
                Allgemein übernehmen
              </button>
            </section>
          ) : null}

          <section className="mail-style-learning">
            <h3>Eigene Lernbelege für {data.contact || "diesen Kontakt"}</h3>
            <p>
              Nur manuell bearbeitete und ausdrücklich bestätigte Entwürfe werden gespeichert;
              gesendete Mails werden nicht automatisch eingelesen. Allgemeine Regeln gelten für alle Kontakte.
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
