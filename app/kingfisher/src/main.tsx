import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { api } from "./api";
import { eingabenMelden } from "./aktivitaet";
import "./theme.css";
import "./styles.css";
import "./CalmUI.css";
// Zuletzt: die Breitenregeln für alle Seiten (keine Seite breiter als das Fenster).
import "./Seitenbreite.css";

// Wer tippt oder klickt, arbeitet: Der Hintergrund tritt dann kurz zurück.
eingabenMelden(api.hintergrundAktiv);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
