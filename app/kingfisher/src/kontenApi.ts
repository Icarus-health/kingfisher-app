// Die Routen zu Konten und Bereichen (sidecar: konten_routes.py). Eigene Datei, damit `api.ts` klein bleibt.
import { request } from "./api";
import type { Konten } from "./kontenBereiche";

const put = (body: unknown) => ({ method: "PUT", body: JSON.stringify(body) });

export const kontenApi = {
  konten: () => request<Konten>("/api/v1/konten"),
  umbenennen: (id: string, name: string) => request<Konten & { vorher: string }>("/api/v1/konten/name", put({ id, name })),
  bereich: (zuordnung: Record<string, string | null>) =>
    request<Konten & { vorher: Record<string, string | null> }>("/api/v1/konten/bereich", put({ zuordnung })),
  bereichAnlegen: (name: string) =>
    request<Konten & { neu: string }>("/api/v1/bereiche", { method: "POST", body: JSON.stringify({ name }) }),
  ausblenden: (ids: string[]) => request<{ ausgeblendet: string[] }>("/api/v1/kalender/ausgeblendet", put({ ids })),
};
