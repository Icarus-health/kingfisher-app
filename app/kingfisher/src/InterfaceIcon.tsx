import type { ReactNode } from "react";
import "./InterfaceIcon.css";

// Eigene geometrische Zeichen. Sichtbare Beschriftungen benennen die Aktionen.
const marks = {
  plus: <path d="M12 5v14M5 12h14" />,
  people: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 4v2" /></>,
  project: <path d="M3 7V5a1 1 0 0 1 1-1h5l3 3h8a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z" />,
  document: <><path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8m-8 4h6" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  house: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M4 10h16M10 10v10" /></>,
  "message-circle": <path d="M7 18l-3 3V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7Z" />,
  folder: <><path d="m4 7 1.5 1.5L8 6m-4 9 1.5 1.5L8 14M12 7h8M12 15h8" /></>,
  building: <><path d="M5 21V4h9v17M14 9h5v12M3 21h18M8 8h3m-3 4h3m-3 4h3" /></>,
  pin: <><path d="M12 21s-6-5.6-6-10a6 6 0 0 1 12 0c0 4.4-6 10-6 10Z" /><circle cx="12" cy="11" r="2" /></>,
  brain: <><path d="m3 8 9-5 9 5-9 5-9-5Zm0 5 9 5 9-5m-18 5 9 5 9-5" transform="translate(0 -1)" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></>,
  "calendar-days": <><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4m8-4v4M4 10h16M8 14h2m4 0h2m-8 3h2" /></>,
  settings: <><path d="M4 7h7m4 0h5M4 17h3m4 0h9" /><circle cx="13" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></>,
  "arrow-up": <path d="M12 20V4m-6 6 6-6 6 6" />,
} satisfies Record<string, ReactNode>;

export function InterfaceIcon({ name }: { name: keyof typeof marks }) {
  return <svg className="interface-icon" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{marks[name]}</svg>;
}
