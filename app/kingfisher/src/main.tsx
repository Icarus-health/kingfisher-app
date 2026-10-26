import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { HinweisAnzeige } from "./grundlage";
import { api } from "./api";
import { eingabenMelden } from "./aktivitaet";
import "./LeafletPlaces";
import "./theme.css";
import "./styles.css";
import "./CalmUI.css";
import "./WorkspaceTasks.css";
import "./Messages.css";
import "./SavedMailWorkflow.css";
import "./Workspace.css";
import "./NordicWorkspace.css";
// Die Gestaltungsgrundlage (Werte, Bausteine, globale Abbildung der vorhandenen Klassen), direkt vor den Breitenregeln.
import "./Grundlage.css";
// Zuletzt: die Breitenregeln für alle Seiten (keine Seite breiter als das Fenster).
import "./Seitenbreite.css";

// Wer tippt oder klickt, arbeitet: Der Hintergrund tritt dann kurz zurück.
eingabenMelden(api.hintergrundAktiv);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    {/* Der eine Hinweis mit „Rückgängig“ für alle Seiten (grundlage/hinweisOrt.ts). */}
    <HinweisAnzeige />
  </StrictMode>,
);
