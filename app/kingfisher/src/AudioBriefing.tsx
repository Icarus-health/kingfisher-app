import { useEffect, useMemo, useRef, useState } from "react";
import type { MorningBriefing } from "./api";
import "./AudioBriefing.css";

type AudioStatus = "idle" | "generating" | "processing" | "ready" | "playing" | "paused" | "failed" | "unavailable";
const wait = (ms: number) => new Promise<void>(resolve => window.setTimeout(resolve, ms));
function seconds(value: number) { const safe = Math.max(0, Math.round(value)); return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`; }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, { credentials: "same-origin", ...init, signal: controller.signal, headers: { ...(init?.body ? { "content-type": "application/json" } : {}), ...init?.headers } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json() as T;
  } finally { window.clearTimeout(timer); }
}

export function AudioBriefing({ briefing }: { briefing: MorningBriefing }) {
  const text = useMemo(() => {
    const needs = briefing.needs_you.map(item => `${item.reason || item.title}. ${item.detail}.`).join(" ");
    const happening = briefing.happening_now.map(item => `${item.title}. ${item.detail}.`).join(" ");
    const later = briefing.later_today.map(item => `Um ${item.time}: ${item.title}. ${item.detail}.`).join(" ");
    return [briefing.greeting, (briefing.verlauf ?? []).join(" "), needs, happening, later].filter(Boolean).join(" ");
  }, [briefing]);
  const audio = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string | null>(null);
  const jobId = useRef<string | null>(null);
  const generation = useRef(0);
  const [status, setStatus] = useState<AudioStatus>("idle");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [rate, setRate] = useState(1);
  const [canPlay, setCanPlay] = useState(false);

  function clearAudio() {
    const element = audio.current;
    if (element) { element.pause(); element.removeAttribute("src"); element.load(); }
    if (objectUrl.current) { URL.revokeObjectURL(objectUrl.current); objectUrl.current = null; }
    setCanPlay(false); setPosition(0); setDuration(0);
  }
  function cancelJob() {
    const id = jobId.current;
    jobId.current = null;
    if (id) void fetch(`/api/v1/audio/${encodeURIComponent(id)}`, { method: "DELETE", credentials: "same-origin" }).catch(() => undefined);
  }
  function cancelRemote(id: string) { void fetch(`/api/v1/audio/${encodeURIComponent(id)}`, { method: "DELETE", credentials: "same-origin" }).catch(() => undefined); }
  function reset() { generation.current += 1; cancelJob(); clearAudio(); setStatus("idle"); setError(""); }
  useEffect(() => { let active = true; request<{available: boolean}>("/api/v1/audio/status").then(value => { if (active) setAvailable(value.available); }).catch(() => { if (active) setAvailable(false); }); return () => { active = false; reset(); }; }, [text]);
  useEffect(() => () => { cancelJob(); clearAudio(); }, []);

  async function generate() {
    if (status === "generating" || status === "processing") return;
    if (!text.trim()) { setError("Das Briefing enthält keinen Text für ein lokales Audio."); setStatus("failed"); return; }
    if (text.length > 8000) { setError("Das Briefing ist zu lang für ein lokales Audio. Die Textansicht enthält den vollständigen Inhalt."); setStatus("failed"); return; }
    const current = ++generation.current; cancelJob(); clearAudio(); setError(""); setStatus("generating");
    try {
      const ready = await request<{available: boolean}>("/api/v1/audio/status");
      if (current !== generation.current) return;
      setAvailable(ready.available);
      if (!ready.available) { setStatus("unavailable"); return; }
      const created = await request<{id: string; status: string}>("/api/v1/audio", { method: "POST", body: JSON.stringify({ text }) });
      if (current !== generation.current) { cancelRemote(created.id); return; }
      jobId.current = created.id; setStatus("processing");
      const started = Date.now();
      while (Date.now() - started < 120000 && current === generation.current) {
        const next = await request<{status: "pending" | "processing" | "ready" | "failed"}>(`/api/v1/audio/${encodeURIComponent(created.id)}`);
        if (current !== generation.current) { cancelRemote(created.id); return; }
        if (next.status === "failed") throw new Error("failed");
        if (next.status === "ready") {
          const controller = new AbortController();
          const timer = window.setTimeout(() => controller.abort(), 15000);
          let blob: Blob;
          try {
            const response = await fetch(`/api/v1/audio/${encodeURIComponent(created.id)}/content`, { credentials: "same-origin", signal: controller.signal });
            if (!response.ok) throw new Error("content");
            blob = await response.blob();
          } finally { window.clearTimeout(timer); }
          if (current !== generation.current) { cancelRemote(created.id); return; }
          objectUrl.current = URL.createObjectURL(blob); setCanPlay(true); setStatus("ready");
          const element = audio.current;
          if (element) { element.src = objectUrl.current; element.playbackRate = rate; element.load(); try { await element.play(); } catch { /* Browser autoplay policy; the ready button remains available. */ } }
          return;
        }
        await wait(1000);
      }
      if (current === generation.current) throw new Error("timeout");
    } catch { if (current === generation.current) { cancelJob(); setStatus("failed"); setError("Das lokale Audio konnte nicht erstellt werden. Bitte erneut versuchen."); } }
  }
  function toggle() { const element = audio.current; if (!element || !canPlay) return; if (element.paused) void element.play().catch(() => setError("Zum Abspielen bitte die Wiedergabe-Schaltfläche erneut drücken.")); else element.pause(); }
  function seek(delta: number) { const element = audio.current; if (element) element.currentTime = Math.max(0, Math.min(element.duration || 0, element.currentTime + delta)); }
  function changeRate() { const next = rate === 1 ? 1.25 : rate === 1.25 ? 1.5 : 1; setRate(next); if (audio.current) audio.current.playbackRate = next; }
  // Ohne lokales Audio kein Spieler (Fremdprobe, Befund 20): Vorher stand ein Pause-Zeichen da, als liefe etwas, und
  // darunter „nicht verfügbar“. Bis die Antwort da ist, ebenfalls nichts; das Briefing ist auch ohne Ton vollständig.
  if (available !== true && (status === "idle" || status === "unavailable")) return null;
  // Im Kopf von Heute ein leiser Knopf „Vorlesen“ (Paket U, H1); erst wenn etwas läuft, die kleinen Bedienknöpfe.
  const laeuft = canPlay && (status === "ready" || status === "playing" || status === "paused");
  return <span className="audio-briefing" role="group" aria-label="Vorlesen">
    <audio ref={audio} onError={event => { if (event.currentTarget.src === objectUrl.current) { setCanPlay(false); setStatus("failed"); setError("Das lokale Audio konnte nicht gelesen werden. Bitte erneut versuchen."); } }} onLoadedMetadata={event => { if (event.currentTarget.src === objectUrl.current && Number.isFinite(event.currentTarget.duration)) setDuration(event.currentTarget.duration); }} onTimeUpdate={event => { if (event.currentTarget.src === objectUrl.current) setPosition(event.currentTarget.currentTime); }} onPlay={event => { if (event.currentTarget.src === objectUrl.current) setStatus("playing"); }} onPause={event => { if (event.currentTarget.src === objectUrl.current) setStatus(current => current === "playing" ? "paused" : current); }} onEnded={event => { if (event.currentTarget.src === objectUrl.current) setStatus("ready"); }} />
    {status === "idle" ? <button className="today-text-link" type="button" onClick={() => void generate()}>Vorlesen</button> : null}
    {laeuft ? <>
      <button className="today-text-link" type="button" aria-label={status === "playing" ? "Briefing pausieren" : "Briefing vorlesen"} onClick={toggle}>{status === "playing" ? "Pause" : "Abspielen"}</button>
      <button className="today-text-link" type="button" aria-label="10 Sekunden zurück" onClick={() => seek(-10)}>−10 s</button>
      <button className="today-text-link" type="button" aria-label="10 Sekunden vor" onClick={() => seek(10)}>+10 s</button>
      <button className="today-text-link" type="button" aria-label="Wiedergabetempo ändern" onClick={changeRate}>{rate.toLocaleString("de-DE")}×</button>
      <span className="audio-time">{seconds(position)} / {seconds(duration)}</span>
    </> : null}
    {available === false && status !== "idle" ? <span className="audio-message" role="status">Lokales Audio ist derzeit nicht verfügbar. Bitte später erneut versuchen.</span> : null}
    {status === "generating" || status === "processing" ? <span className="audio-message" role="status">Wird vorbereitet … <button className="today-text-link" type="button" onClick={reset}>Abbrechen</button></span> : null}
    {status === "failed" || error ? <span className="audio-message" role="alert">{error || "Das lokale Audio ist fehlgeschlagen."} <button className="today-text-link" type="button" onClick={() => void generate()}>Erneut versuchen</button></span> : null}
  </span>;
}
