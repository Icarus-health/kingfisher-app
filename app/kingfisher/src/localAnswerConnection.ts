import type {ModelRoles, ModelSetup} from './api';

type ConnectionApi = {
  saveModelRole: (role: string, body: {modell: string; cloud: boolean; local_only: boolean}) => Promise<ModelRoles>;
  saveLocalModel: (model: string, endpoint: string) => Promise<ModelSetup>;
  testModel: () => Promise<{ok: boolean}>;
};

/** Eine ausdrückliche lokale Antwortwahl ersetzt auch eine frühere Rollenwahl.
 * Erst die geprüfte lokale Rolle setzen, dann den Standard, dann den aktiven Dienst testen.
 * Das Sortieren von Quellen bleibt eine getrennte Zustimmung.
 */
export async function connectLocalAnswer(api: ConnectionApi, model: string, endpoint: string): Promise<
  {state: 'unverified'} | {state: 'different' | 'unavailable' | 'ready'; setup: ModelSetup; elapsedMs?: number}
> {
  const roles = await api.saveModelRole('antwort', {modell: model, cloud: false, local_only: true});
  const answer = roles.rollen.find(row => row.rolle === 'antwort');
  if (answer?.wirksam.modell !== model || answer.wirksam.lokal !== true) return {state: 'unverified'};
  const setup = await api.saveLocalModel(model, endpoint);
  if (setup.status.provider !== 'ollama' || setup.status.model !== model || setup.status.endpoint?.replace(/\/$/, '') !== endpoint.replace(/\/$/, '')) {
    return {state: 'different', setup};
  }
  const started = performance.now();
  const result = await api.testModel();
  return {state: result.ok === true ? 'ready' : 'unavailable', setup, elapsedMs: performance.now() - started};
}
