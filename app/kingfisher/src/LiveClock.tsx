import { useEffect, useState } from "react";
import "./LiveClock.css";

/** Die Uhr der Seitenleiste: Stunden und Minuten, ohne tickende Sekunden (Paket U, H7). Sie prüft jede Sekunde, zeichnet
 * aber nur neu, wenn die Minute wechselt. */
export function LiveClock({ className = "sidebar-clock" }: { className?: string }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const refresh = () => setNow(previous => {
      const next = new Date();
      return Math.floor(next.getTime() / 60_000) === Math.floor(previous.getTime() / 60_000) ? previous : next;
    });
    const onVisible = () => { if (!document.hidden) refresh(); };
    const timer = window.setInterval(refresh, 1_000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  // Use the device timezone, as the morning briefing request does.
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const date = new Intl.DateTimeFormat("de-DE", {
    timeZone, weekday: "short", day: "2-digit", month: "long", year: "numeric",
  }).format(now);
  const time = new Intl.DateTimeFormat("de-DE", {
    timeZone, hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(now);

  return <time className={className} dateTime={now.toISOString()} title={`Aktuelle Ortszeit · ${timeZone}`}>
    <strong>{time}</strong><span>{date}</span>
  </time>;
}
