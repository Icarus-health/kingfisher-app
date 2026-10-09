import type { AktenArt, ArtStand, KreisArt, KreisStand, KreisUebersicht } from "./kreis";
import type { WkStand } from "./wiederkehrendes";
import type { SuchindexStand } from "./suchindex";
import type { SystemAngabe } from "./system";
import type { BelegQuelle } from "./quellenWeg";
import type { FassungStand } from "./fassungsAngebot";
export type Attention = {
  occurred_at?: string | null;
  recorded_at?: string | null;
  project_id?: string | null;
  id: string;
  title: string;
  detail: string;
  priority?: string;
  icon?: string;
  source?: string;
  source_ref?: string | null;
  episode_id?: string | null;
  reason?: string;
  action?: string | null;
  review_required?: boolean;
};

export type CalendarItem = Attention & { time: string };

export type MorningBriefing = {
  fixture?: boolean;
  /** Ohne Posteingang zusammengestellt; die Post kommt mit dem zweiten Abruf (Befund 22). */
  post_ausstehend?: boolean;
  generated_at: string;
  timezone: string;
  greeting: string;
  verlauf?: string[];
  relevance_count: number;
  historical_task_reviews?: number;
  needs_you: Attention[];
  happening_now: Attention[];
  working_memory_more?: boolean;
  later_today: CalendarItem[];
  timeline: Array<{ id: string; label: string; icon: string; tone: string }>;
  weather: null | {
    location: string;
    temperature_c: number;
    condition: string;
    attribution?: string;
    attribution_url?: string;
  };
  partial_failures: Array<{ section: string; message: string }>;
};

/** Ein Beleg der Satzantwort. `kennzeichen` trägt die Arten `andere_person` und `ausserhalb_zeitraum` (kennzeichnung.py). */
export type SatzBeleg = { nummer: number; episode_id: string; titel: string; kopf: string; rolle: string; zitat: string; datum: string;
  ueberholt?: { text: string; durch: number | null; grund: string; alt: string; neu: string };
  kennzeichen?: Array<{ art: "andere_person" | "ausserhalb_zeitraum"; text: string }> };

/** Eine belegte Antwort in Sätzen (E3): Sätze mit Belegnummern, die Belege im Wortlaut, „Aus der Akte“. */
export type SatzAntwortDaten = {
  version: number;
  /** Vom Programm geprüfte Hinweise zur Suchabdeckung, auch bei geschlossenen Belegen sichtbar. */
  hinweise?: string[];
  /** `verlaesslichkeit` (gut, einfach, duenn) und `hinweis` (Nebensatz) kommen aus verlaesslichkeit.py. */
  saetze: Array<{ text: string; belege: number[]; vom_programm: boolean; verlaesslichkeit?: "gut" | "einfach" | "duenn"; hinweis?: string }>;
  belege: SatzBeleg[];
  akte: Array<{ rolle: string; sache: string; name: string; datum: string; episode_id: string; text: string }>;
  verworfen: number;
  /** Sätze, die das zweite Tor (Prüfmodell, satzpruefung_modell.py) verworfen hat; getrennt von `verworfen`. */
  verworfen_pruefmodell?: number;
  pruefung?: { zustand: "an" | "aus" | "kein_modell"; modell: string };
  modell: string;
  stichtag: string;
};

/** Wie lange eine Antwort brauchte, in Sekunden je Abschnitt (sidecar: zeitmessung.py). Abschnitte, die nicht liefen, fehlen. */
export type AntwortZeiten = {
  gesamt: number; frage?: number; suche?: number; antwort_modell?: number; saetze_modell?: number; satzpruefung?: number;
  pruefung_modell?: number;
};

/** Das zweite Tor der Satzprüfung: Schalter, Zustand (ohne Modell still aus) und das Prüfmodell. */
export type SatzpruefungStand = { schalter: "an" | "aus"; zustand: "an" | "aus" | "kein_modell"; modell: string | null };

/** Das Protokoll der letzten Antworten (GET /api/v1/antwortzeiten): Median und 90-Prozent-Wert je Abschnitt. */
export type AntwortZeitenProtokoll = {
  antworten: number; ziel_s: number;
  abschnitte: Partial<Record<keyof AntwortZeiten, {median: number; p90: number; anzahl: number}>>;
  modelle: {frage: string | null; antwort: string | null};
  saetze: "an" | "aus";
  pruefung?: SatzpruefungStand;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "complete" | "error";
  created_at: string;
  metadata?: { resolved_approval_id?: string; context?: { satzantwort?: SatzAntwortDaten; zeiten?: AntwortZeiten; quellen?: BelegQuelle[]; source_links?: Array<{episode_id: string; label: string; automatic_memory?: boolean}>; clarification_choices?: Array<{label: string}>; clarification_date?: boolean; original_question?: string; refresh_available?: boolean; routing?: { from: string; to: string; reason: string; allowed_tools: string[]; history_shared: boolean; trace: Array<{model: string; outcome: string}> } } };
};

export type KnowledgeProjection = {
  format: "knowledge-context-v3";
  assertion_id: string;
  statement: string;
  subject_ref: string;
  target_ref: string | null;
  scope_ref: string | null;
  predicate: string;
  value: string;
  claim_created_at: string;
  valid_from: string | null;
  valid_until: string | null;
  primary_evidence: {
    episode_id: string; digest: string; source_type: string; source_ref: string | null;
    occurred_at: string | null; recorded_at: string;
  };
  reason: string;
};

export type ContextItem = {
  knowledge_projection?: KnowledgeProjection;
  knowledge_input?: { version: 1; claim_id: string; primary_episode_id: string;
    projection_sha256: string; source_generations: Record<string, number> };
  evidence_at_basis?: "occurred_at" | "recorded_at";
  basis?: { version: 1; state: "none" | "supported" | "review"; reason: string | null };
  assertion_id: string;
  statement: string;
  kind: string;
  state: "current" | "outdated" | "disputed";
  reason: string;
  source_type: string;
  source_ref: string | null;
  evidence_at: string;
  confidence: number | null;
};

export type ContextPacket = {
  query: string;
  generated_at: string | null;
  items: ContextItem[];
  withheld_count: number;
  source_links?: Array<{episode_id: string; label: string; automatic_memory?: boolean}>;
};

export type MemoryCandidate = {
  id: string;
  statement: string;
  rationale: string;
  state: "pending" | "accepted" | "rejected" | "superseded";
  subject_ref: string;
  predicate: string;
  value: string;
  scope_ref: string | null;
  evidence: Array<{ episode_id: string; quote: string; digest: string }>;
};

export type MemoryCandidateCard = {
  message_id: string;
  candidate: MemoryCandidate;
  conflicts: Array<{ id: string; statement: string }>;
  competing_count: number;
  source_message_id: string | null;
  claim: {
    id: string;
    status: string;
    superseded_by: string | null;
  } | null;
  claim_usable: boolean;
};

export type ActionRequest = {
  id: string; message_id: string; tool: string; dry_run: string; action_class: string;
  state: "pending" | "expired" | "approved" | "rejected" | "unknown";
  confirmation_phrase: string | null; expires_at: string; reasons: string[];
};

export type ConversationPayload = {
  action_requests?: ActionRequest[];
  conversation: { id: string; title: string; created_at: string; updated_at: string };
  messages: Message[];
  context: ContextPacket;
  memory_candidates: MemoryCandidateCard[];
};

export type ConversationSummary = {
  id: string;
  title: string;
  updated_at: string;
  preview: string;
  message_count: number;
};

export type Schedule = {
  enabled: boolean; interval_minutes: number; with_model: boolean; backup: boolean;
  mail_accounts: string[]; sources: Record<string, string>;
  mail_status: Record<string, {last_attempt?: string; last_success?: string; last_failure?: "unavailable" | "credentials_missing" | "cancelled"; consecutive_failures?: number; last_report?: {recorded?: number; duplicates?: number}}>;
  last_run: null | {finished_at: string | null; ok: boolean; jobs: Array<{name: string; ok: boolean; detail: string}>};
  /** Je Postfach die eine Aussage, dieselbe wie auf Heute und in der Einrichtung (sidecar: mail_stand.py). */
  mail_stand?: Array<MailStand & {account_id: string; label: string}>;
  /** Welches Modell beim Abruf Kosten verursachen kann; null, wenn nur ein Modell auf diesem Rechner arbeitet. */
  kosten_modell?: string | null;
};

/** Der Stand eines Postfachs in einem Satz (Fremdprobe 2, Befund 17). */
export type MailStand = {
  zustand: "liest" | "wartet" | "leer" | "aktuell" | "pausiert" | "nicht_abgerufen" | "fehler" | "gescheitert";
  satz: string; gelesen: number | null; gesamt: number | null; zuletzt: string | null;
  /** Nur für „Für Techniker“: Ordner, Grund je Anzahl und Fehlerklasse (Fremdprobe 3, Befund 2). */
  technik?: string | null;
};

export type MailAccount = {
  id: string;
  label: string;
  user: string;
  enabled: boolean;
  configured: boolean;
  secret_present: boolean;
  can_send: boolean;
};

export type MailIntakeFolder = {
  folder: string;
  inventory_complete: boolean;
  total: number | null;
  captured: number;
  duplicates: number;
  failed: number;
  /** Gescheiterte beider Wege je Grund (`mail_intake_grund.py`). */
  failed_by?: Record<string, number>;
  /** Bewusst ausgefiltert (Newsletter, Spam): gelesen, aber nicht ins Gedächtnis übernommen. */
  filtered?: number;
  pending: number;
  live_pending: number;
  live_failed?: number;
  live_filtered?: number;
  live_filtered_by?: Record<string, number>;
  analyzed: number;
  analysis_failed: number;
  deferred: number;
  excluded: number;
  categorized?: number;
  categories_pending?: number;
  categories_failed?: number;
  categories_deferred?: number;
  categories_failed_by?: Record<string, number>;
  /** Failed category records beyond the per-status freshness-check budget. */
  categories_unverified?: number;
};

export type MailIntakeAccount = {
  account_id: string;
  label: string;
  connected: boolean;
  started: boolean;
  attachments_supported?: boolean;
  attachments_description?: string;
  paused: boolean;
  folders: MailIntakeFolder[];
  step: string;
  /** History capture yields to classification; new mail has a separate lane. */
  history_waiting_for_analysis?: boolean;
  error: string | null;
  scope: string;
  empfaengernachtrag?: { offen: number; ergaenzt: number; ohne_kopfzeilen: number; gedrosselt: boolean; fertig: boolean } | null;
  stand?: MailStand | null;
};

export type MailIntakeStatus = {
  analysis_active?: boolean;
  /** Explicit global pause, independent of a mailbox's own paused flag. */
  background_paused?: boolean;
  accounts: MailIntakeAccount[];
  attachments_supported: boolean;
};

export type MailIntakePreview = {folders: string[]; description: string; attachments_supported: boolean; attachments_description?: string};

export type CategoryTaxonomyEntry = {id: string; label: string; description: string; version: number};
export type SourceCategoriesResult = {
  episode_id: string;
  status: string;
  failure_code?: string | null;
  categories: Array<{id: string; label: string; origin: string;
    evidence: Array<{start: number; end: number; quote: string}>; taxonomy_version: number}>;
  entities: Array<{kind: string; name: string; role: string; start: number; end: number; quote: string; origin: string}>;
  correction: null | {categories: string[]; fingerprint: string; stale: boolean};
  automatic: boolean;
};

export type MemoryAreaCategory = {
  id: string;
  label: string;
  origin: "automatic" | "user";
  evidence: Array<{start: number; end: number; quote: string; quote_truncated: boolean}>;
};
export type MemoryAreaSource = {
  episode_id: string;
  title: string;
  occurred_at: string | null;
  status: string;
  categories: MemoryAreaCategory[];
};
export type MemoryAreasPage = {
  areas: Array<{id: "work" | "personal" | "health" | "finance"; label: string; available: boolean}>;
  sources: MemoryAreaSource[];
  taxonomy_version: number;
  scanned_count: number;
  counts_scope: "page";
  area: "work" | "personal" | "health" | "finance" | "other" | null;
  selection_scope: "corpus" | "page";
  scan_limited: boolean;
  candidates_checked: number;
  next_cursor: number | null;
  truncated: boolean;
};

export type CalendarSource = {
  id: string;
  label: string;
  kind: "caldav" | "ical" | "google" | "microsoft";
  enabled: boolean;
  configured: boolean;
  secret_present: boolean;
};

export type IntegrationOverview = {
  mail_accounts: MailAccount[];
  calendar_sources: CalendarSource[];
};

export type MailProvider = {
  id: string;
  label: string;
  imap_host: string;
  smtp_host: string;
  imap_port: number;
  smtp_port: number;
  app_password: boolean;
  hint: string;
  help_url: string;
  domains?: string[];
  /** Wo der Kalender dieses Anbieters liegt (Startpunkt der Suche); leer, wenn der Katalog es nicht weiß. */
  caldav_url?: string;
  /** Warum es keinen Kalenderzugang mit Passwort gibt (Google, Microsoft); sonst leer. */
  caldav_note?: string;
  /** Text des Verweises auf `help_url` (etwa „Zur Google-Seite „App-Passwörter““); sonst „So bekommst du es“. */
  help_label?: string;
  /** Der Kalender geht ohne Passwort über seine geheime iCal-Adresse (Google, Fremdprobe Befund 2). */
  kalender_ical?: boolean;
  /** Womit man sich anmeldet: die ganze Adresse oder nur der Teil vor dem @ (aus der Autoconfig der Domain). */
  benutzer?: "adresse" | "lokalteil";
};

/** Microsoft 365 (sidecar: microsoft_routes.py, docs/50-microsoft-365.md). Nie mit Token oder Gerätecode. */
export type MicrosoftStand = {configured: boolean; quelle: "einstellung" | "umgebung" | null; secure_storage: boolean; client_id: string | null};
/** Die eine Anbieter-Erkennung (`anbieter_erkennen.py`): Katalogeintrag für den Passwortweg und der Dienst dahinter. */
export type AnbieterErkennung = {
  provider: MailProvider | null;
  /** `srv` und `autoconfig`: den Server einer eigenen Domain hat Kingfisher selbst gefunden (`provider.id` „gefunden“). */
  erkannt_an: "domain" | "mx" | "autodiscover" | "txt" | "srv" | "autoconfig" | "";
  dienst: "google" | "microsoft" | "";
  art: "organisation" | "privat" | "";
};
export type MicrosoftAnmeldung = {
  sitzung?: string; status: "waiting" | "ready" | "connected" | "failed" | "expired" | "cancelled";
  user_code?: string; verification_uri?: string; restsekunden?: number; mitschriften?: boolean;
  grund?: string; satz?: string; hinweis?: string; email?: string; neu?: string[]; mitschriften_an?: boolean;
  ohne_mitschriften?: boolean;
};
export type MicrosoftKonten = MicrosoftStand & {konten: Array<{
  adresse: string; verbunden: boolean; post: boolean; kalender: boolean; mitschriften: boolean; satz: string | null;
  besprechungen: Array<{titel: string; beginn: string | null; stand: string; satz: string}>;
}>};

/** Antwort auf „Kalender verbinden“ (sidecar: kalender_anmeldung.py, Befund 7). */
export type KalenderAnmeldung = IntegrationOverview & { gefunden: string[]; neu: number; anbieter: string };

export type EinrichtungSchritt = "name" | "mail" | "kalender" | "modell" | "freigaben" | "autostart" | "fertig";

// Hintergrund ohne Nacht (docs/46-hintergrund.md): Zustand, Fortschritt der Einordnung, gemessene Rate, Schätzung.
export type HintergrundZustand = "aus" | "ohne_modell" | "fertig" | "pausiert" | "wartet" | "laeuft";
export type HintergrundStand = {
  zustand: HintergrundZustand;
  grund: string | null;
  pausiert: boolean;
  fortschritt: { gesamt: number; fertig: number; offen: number };
  rate_pro_stunde: number | null;
  schaetzung: { sekunden: number; fertig_um: string; text: string } | null;
  schaetzung_text: string | null;
  satz: string | null;
  schlange: Array<{ stufe: "morgen" | "neu" | "rueckstand"; text: string; offen: number }>;
};
export type AutostartStand = { gewuenscht: boolean | null; verfuegbar: boolean; eingerichtet: boolean | null; plattform: string | null };
export type EinrichtungStand = {
  name: string;
  schritte: Partial<Record<EinrichtungSchritt, "erledigt" | "uebersprungen">>;
  abgeschlossen: boolean;
  vorhanden: { mail: boolean; kalender: boolean; modell: boolean };
  zeigen: boolean;
  /** Ob dieser Rechner den Autostart einrichten kann (ein Helfer hat sich gemeldet); sonst entfällt der Schritt. */
  autostart_verfuegbar?: boolean;
  /** Name der Zeitzone, in der Uhrzeiten gelesen werden; nur zum Anzeigen. */
  zeitzone?: string;
};
export type EinrichtungAenderung = {
  name?: string; abgeschlossen?: boolean; neu_beginnen?: boolean;
  schritt?: { id: EinrichtungSchritt; stand: "erledigt" | "uebersprungen" | "offen" };
};

export type DecisionBasis = { id: string; statement: string; kind: string };
export type Decision = {
  id: string; satz: string; status: string; erschuettert: boolean; ohne_grundlage: boolean;
  getroffen_am: string; project_id: string | null;
  grundlage: Array<{ id: string; satz: string; status: string }>;
  wackler: Array<{ annahme: string; annahme_id: string; status: string; strittig: boolean; ersetzt_durch: string | null }>;
};

export type ProjectSuggestion = {
  suggestion: {project_id: string; name: string; count: number} | null;
  unassigned_peers: number;
  sender: string | null;
};

export type Project = {
  id: string;
  name: string;
  status: "idea" | "active" | "paused" | "done" | "dropped";
  priority: "high" | "medium" | "low";
  description: string | null;
  open: boolean;
};

export type Task = {
  provenance?: {source_ref?: string | null};
  id: string;
  title: string;
  status: "open" | "done" | "dropped";
  created_at: string;
  due: string | null;
  remind_at?: string | null;
  notes: string | null;
  tags: string[];
  project_id: string | null;
  goal_id?: string | null;
  wartet_auf: string | null;
  wartet_seit: string | null;
  wartet_tage: number | null;
  overdue: boolean;
};

export type MailThreadContext = {
  context_fingerprint: string;
  uid: string; source_digest: string; scope: "stored_header_links"; status: "ready" | "excluded";
  limited: boolean; detail: string;
  items: Array<{episode_id: string | null; current: boolean; title: string; sender: string;
    occurred_at: string | null; recorded_at: string | null; text: string; truncated: boolean}>;
};

export type MailThreadSummary = {
  uid: string; context_fingerprint: string; available: boolean; status: string;
  limited: boolean; warnings: string[]; detail: string; selection_review: "proposed"; semantic_validation: false;
  items: Array<{passage_id: string; kind: "agreement" | "change" | "cancellation" | "open_question";
    label: string; quote: string; interpretation: "unconfirmed"; episode_id: string | null; current: boolean;
    title: string; sender: string; occurred_at: string | null; recorded_at: string | null; truncated: boolean}>;
};

export type MailDetail = {
  uid: string; subject: string; from: string; date: string | null;
  body: string; preview: string; answer_to: string; message_id: string;
  source_digest?: string;
  account_label?: string; can_reply: boolean; sending_account: string; truncated: boolean;
};

/** `valid_until`: vorgeschlagene Fälligkeit (bei Fristen aus privaten Mails, sidecar: akten_arten.py), sonst null. */
export type TaskCandidate = { received_at?: string | null; recorded_at?: string; temporal_status?: string; temporal_reason?: string; followup_episode_id?: string | null; id: string; statement: string; evidence: Array<{episode_id: string; quote: string; digest: string}>; valid_until?: string | null };
export type TaskCandidatePage = {items: TaskCandidate[]; total: number; offset: number; limit: number; has_more: boolean; generation: string};

export type MailTaskSuggestions = {
  available: boolean;
  detail: string;
  source_digest: string | null;
  items: Array<{ title: string; quote: string }>;
};

export type MailBriefing = {
  received_at?: string | null; temporal_status?: string; temporal_reason?: string;
  uid: string;
  available: boolean;
  status: "ready" | "empty" | "unavailable" | "incomplete";
  detail: string;
  source_digest: string | null;
  quotes: string[];
  tasks: Array<{ title: string; quote: string }>;
  truncated: boolean;
  task_review?: "not_needed" | "completed" | "incomplete" | "unavailable";
};

export type InboxMessage = {
  id: string;
  account_id: string;
  sender: string;
  subject: string;
  preview: string;
  date: string | null;
  unread: boolean;
  source: string | null;
  category: "inbox" | "newsletter" | "spam" | "blocked" | "unclear";
  filter_reason: string;
};

export type InboxPayload = { abgerufen_um?: string;
  messages: InboxMessage[];
  /** `grund` und `ziel`, wenn das Postfach selbst nicht antwortet (postfach_lage.py): der Satz nennt es, `ziel` führt hin. */
  partial_failure: { code: "not_configured" | "unavailable"; section: string; message: string; grund?: string; ziel?: string } | null;
};

export type GraphNode = {
  id: string;
  kind: string;
  label: string;
  attributes: Record<string, string | number | boolean | null>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relation: string;
  scope: string | null;
  confidence: number;
  state: string;
  evidence_refs: string[];
};

export type MemoryGraph = {
  generated_at: string;
  authority: "projection";
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type SupportReviewItem = {
  id: string;
  statement: string;
  kind: string;
  factual_at: string;
  currency: string;
  support_status: string;
  eligible: boolean;
  reason: string | null;
};

export type SupportReviewPage = {
  items: SupportReviewItem[];
  next_cursor: string | null;
  truncated: boolean;
};

export type SupportReassessmentPreview = {
  item: SupportReviewItem;
  evidence: Array<{ episode_id: string; title: string; quote: string }>;
  preview_token: string | null;
  expires_at: string | null;
};

export type SupportReassessmentResult = {
  ok: true;
  item: SupportReviewItem;
  audit_warning?: string | null;
};

export type PersonMergePreview = {
  member_ids: string[];
  label: string;
  members: GraphNode[];
  evidence_count: number;
  preview_token: string;
};

export type PersonMerge = {
  id: string;
  label: string;
  members: GraphNode[];
  created_at: string;
  undone_at: string | null;
};

export type PersonDigestCitation = {
  source_id: string; quote: string; title: string;
  status: "observed" | "confirmed" | "historical";
  occurred_at: string | null; recorded_at: string; episode_ids: string[];
};
export type PersonDigestItem = { text: string; citations: PersonDigestCitation[] };
export type PersonDigest = {
  model: string; generated_at: string;
  points: PersonDigestItem[]; questions: PersonDigestItem[]; conflicts: PersonDigestItem[];
  discarded_items?: number;
  source_period?: {from: string; to: string} | null;
};
export type PersonDigestResult = {
  status: "ready" | "missing" | "stale" | "no_sources" | "unavailable";
  digest: PersonDigest | null;
  source_count: number; total_source_count: number; truncated: boolean; model: string;
};

export type PersonProfile = {
  id: string;
  authority: "projection";
  person: {
    name: string;
    episoden_anzahl: number;
    /** Quellen, an denen die Person selbst beteiligt war; Gespräche über sie zählen nicht (Fremdprobe 2, Befund 21). */
    kontakte?: number;
    letzter_kontakt: string | null;
    tage_her: number | null;
    kontakt_text: string;
    themen: string[];
    offene_aufgaben: Task[];
    aussagen: Array<Record<string, unknown>>;
    herkuenfte: string[];
    nur_von_aussen: boolean;
    /** Adressanker: `a:<adresse>` oder, ohne Adresse, `n:<name>`. */
    id?: string;
    adressen?: string[];
    /** Alle Anzeigenamen (Aliasse), häufigste zuerst. */
    namen?: string[];
    /** Name, bei gleichnamigen Menschen mit Domäne der Adresse. */
    anzeige?: string;
    unterscheidung?: string;
    rollen?: Record<string, number>;
    /** Nur bei einem Namen ohne Adresse: Adressen, zwischen denen nicht zu entscheiden war. */
    offen_mit?: string[];
    /** Womit die Person wieder aufgerufen wird: Adresse, sonst Name. */
    verweis?: string;
  };
  contexts: Array<{ project: Record<string, unknown>; evidence_refs: string[]; last_interaction: string | null }>;
  interactions: Array<{
    id: string;
    kind: string;
    title: string;
    occurred_at: string | null;
    recorded_at: string;
    project_id: string | null;
    source_type: string;
    source_ref: string;
    digest: string;
  }>;
  claims: Array<Record<string, unknown>>;
  claim_history: Array<Record<string, unknown>>;
};

export type TerminTeilnehmer = { eingabe: string; adresse: string | null; name: string; person: string | null; kontakte: number; zuletzt: string | null };
export type TerminNachbereitung = {
  uid: string;
  start: string | null;
  end: string | null;
  summary: string | null;
  begonnen: boolean;
  stand: "offen" | "festgehalten" | "nichts";
  episode_id: string | null;
  teilnehmer: string[];
  /** Schlüssel des Termins („Kennung|Beginn“), mit dem Mitschriften zugeordnet werden. */
  termin?: string | null;
  /** Mitschriften, die diesem Termin zugeordnet sind. */
  transkripte?: TranskriptEintrag[];
  /** Mitschriften ohne Termin, die der Nutzer diesem Termin zuordnen kann. */
  angebote?: TranskriptEintrag[];
};

export type TranskriptKandidat = { key: string; uid: string; start: string; ende: string; titel: string; punkte: number; gruende: string[] };
export type TranskriptEintrag = {
  id: string;
  titel: string;
  aufgenommen: string;
  status: "zugeordnet" | "vorschlag" | "allein";
  von: "auto" | "nutzer";
  termin: { key: string; uid: string; start: string; ende: string; titel: string } | null;
  gruende: string[];
  kandidaten: TranskriptKandidat[];
  sprecher: string[];
  personen: Record<string, boolean>;
};
export type TranskriptOrdner = {
  enabled: boolean;
  generation: number;
  root_id: string | null;
  folder: string | null;
  seen_at: string | null;
  synced_at: string | null;
  last_run: null | { recorded: number; duplicates: number; changed: number; removed: number; errors: string[] };
  running: boolean;
  /** Im Browser gewählt; Kingfisher liest den Ordner selbst (Befund 6). */
  lokal?: boolean;
  /** Ein Helfer am Mac hat sich in den letzten zwei Minuten gemeldet; dann gilt sein Auswahldialog. */
  helfer?: boolean;
  getrennt: boolean;
  pick_request: null | { id: string; modus: "vorgabe" | "waehlen" };
  files: Array<{ filename: string; id: string; state: string }>;
};
/** Ordner im Browser wählen (sidecar: ordner_lokal.py, Befund 6). */
export type OrdnerOrt = { pfad: string; name: string; da: boolean; vorgabe: boolean; dateien: number; cloud?: "onedrive" | "google_drive" | "icloud" | "" };
export type OrdnerOrte = { helfer: boolean; container: boolean; orte: OrdnerOrt[]; cloud_hinweis?: string };
/** Ordner durchsehen statt tippen (Fremdprobe 2, Befund 30): `oben` ist leer bei mehreren Wurzeln, `null` ganz oben. */
export type Unterordner = { pfad: string; name: string; oben: string | null; ordner: { pfad: string; name: string }[] };
export type OrdnerPrefix = "/api/v1/transcript-sync" | "/api/v1/folder-sync";

export type TranskriptUebersicht = {
  ordner: TranskriptOrdner;
  vorgabe: string;
  stand: { aufgenommen: number; zugeordnet: number; vorschlag: number; offen: number };
  eintraege: TranskriptEintrag[];
  mehr: boolean;
};

export type NachbereitungGespeichert = {
  id: string;
  created: boolean;
  einordnung: "laeuft" | "schon_festgehalten" | "aus";
  nachbereitung: TerminNachbereitung;
};

export type TerminZuordnung = {
  teilnehmer: TerminTeilnehmer[];
  vorschlag: { id: string; name: string; grund: string } | null;
  festgelegt: boolean;
  projekt: { id: string; name: string; grund?: string; herkunft: "gewaehlt" | "vorschlag" } | null;
};
export type MappeZitat = { art: string; text: string; gekuerzt: boolean; titel: string; episode_id: string; participants: string[]; occurred_at: string | null; recorded_at: string };
export type MappeListe<T> = { eintraege: T[]; gesamt: number; ungefaehr?: boolean; archiviert?: number };
export type MappeEinzelheiten = {
  stand: string;
  bitten_und_zusagen: MappeListe<MappeZitat>;
  entwicklungen: MappeListe<MappeZitat>;
  angaben: MappeListe<MappeZitat>;
  einordnung: { eingeordnet: number; offen: number; ausgeschlossen: number };
  aufgaben: MappeListe<{ id: string; title: string; due: string | null; overdue: boolean; wartet_auf: string | null }>;
  termine: MappeListe<{ uid: string | null; titel: string; ort: string; start: string; ganztags?: boolean }> & { kalender: "ok" | "nicht_erreichbar" };
};

export type AkteZeile = { art: string; text: string; gekuerzt: boolean; titel: string; episode_id: string; participants: string[]; occurred_at: string | null; recorded_at: string };
export type AkteSachenArt = "person" | "organisation" | "projekt" | "ort" | "thema";
export type AkteTermin = { episode_id: string; titel: string; start: string; ort: string; vermutlich_abgesagt: AkteZeile | null };
export type AkteFrist = AkteZeile & { datum: string; ausdruck: string; art_der_angabe: string; ersetzt_durch: { datum: string; episode_id: string; ausdruck: string } | null };
/** Ebene 3: zwei, drei Sätze zur Sache, vom Modell geschrieben und Satz für Satz gegen die Quellen geprüft. */
export type AkteLage = {
  saetze: Array<{ text: string; belege: Array<{ nummer: number; episode_id: string; titel: string }> }>;
  erstellt_am: string; quellen: number; veraltet: boolean; wird_aktualisiert: boolean; verworfen: number; modell: string;
};
export type AkteAussage = {
  id: string; text: string; angenommen: string;
  belege: Array<{ episode_id: string; titel: string; zitat: string; datum?: string }>;
  /** Eine jüngere Quelle nennt den Gegenstand anders: ein Hinweis, kein Widerruf. */
  ueberholt: { episode_id: string; titel: string; datum: string; text: string } | null;
};
export type AkteAussagen = { eintraege: AkteAussage[]; gesamt: number };
export type Akte = {
  sache: string; art: AkteSachenArt; art_text: string; name: string; stand: string; aus_zwischenspeicher: boolean;
  quellen: { gesamt: number; beruecksichtigt: number; archiviert: number; begrenzt: boolean; abschnitte_abgeschnitten: boolean };
  verlauf: { eintraege: Array<{ episode_id: string; titel: string; datum: string; grundlagen: string[]; archiviert: boolean; art: string | null; text: string | null; gekuerzt: boolean; quelle_art: string }>; gesamt: number };
  offen: { eintraege: Array<AkteZeile & { vermutlich: boolean; danach_geaendert: AkteZeile | null; aufgabe: { id: string; title: string } | null }>; gesamt: number; vermutlich: boolean;
    erledigt: { eintraege: Array<AkteZeile & { grund: string; durch: AkteZeile | null }>; gesamt: number } };
  fristen: { kommend: AkteFrist[]; verstrichen: AkteFrist[]; ersetzt: AkteFrist[]; gesamt: { kommend: number; verstrichen: number; ersetzt: number };
    ohne_datum: { eintraege: Array<{ ausdruck: string; episode_id: string; titel: string }>; gesamt: number } };
  stand_der_dinge: { aktuell: AkteZeile | null; vorher: AkteZeile[]; vorher_gesamt: number; weitere: Array<{ aktuell: AkteZeile; vorher: AkteZeile[]; vorher_gesamt: number }>; weitere_gesamt: number };
  beteiligte: { eintraege: Array<{ sache: string; art: AkteSachenArt; anzahl: number; name: string }>; gesamt: number };
  termine: { kommend: AkteTermin[]; vergangen: AkteTermin[]; gesamt: { kommend: number; vergangen: number } };
  aufgaben: MappeListe<{ id: string; title: string; due: string | null; overdue: boolean; wartet_auf: string | null }>;
  einordnung: { eingeordnet: number; offen: number; ausgeschlossen: number };
  /** Aussagen, die ein Mensch aus einer Antwort übernommen und bestätigt hat („In die Akte übernehmen“). Als Aussage, nie als Zitat. */
  aussagen?: AkteAussagen;
  berechnung: { offen: number; berechnet: number };
  /** Fehlt oder null, solange keine Lage geschrieben ist (etwa ohne lokales Modell); die Akte ist trotzdem vollständig. */
  lage?: AkteLage | null;
  lage_wird_aktualisiert?: boolean;
  /** Bestätigter Kreis einer Person (`unbestimmt`, solange niemand bestätigt hat); nur bei Personen. */
  kreis?: KreisArt | "unbestimmt";
  /** Bestätigte private Art einer Organisation, sonst leer; nur bei Organisationen. */
  akten_art?: string;
};
// Morgenbriefing, Terminvorbereitung und Wegezeit (sidecar: tag_routes.py, wegezeit_routes.py).
export type TagBeleg = { episode_id: string; titel: string; datum: string | null; art: string };
export type TagZeile = { text: string; beleg: TagBeleg | null; art: string; rolle: string; vermutlich: boolean; hinweis: string };
export type TagFrist = { datum: string; text: string; ausdruck: string; episode_id: string; titel: string; quelle_datum: string | null;
  quelle_art: string; art: string; richtung: string; status: "kommend" | "verstrichen"; tage: number; sache: string; sache_name: string;
  vermutlich: boolean; satz: string };
export type TagPerson = { name: string; adresse: string | null; sache: string | null; bekannt: boolean; organisation: string;
  letzter_kontakt: TagZeile | null; erster_kontakt: TagZeile | null; will: TagZeile[]; zuletzt: TagZeile[]; stand: TagZeile[]; fristen: TagFrist[] };
export type TagWeg = { status: "berechnet" | "aus" | "ohne_ort" | "ohne_start" | "ohne_dienst" | "fehler" | "wird_berechnet"; ort: string; satz: string;
  minuten: number | null; verkehrsmittel: string | null; quelle: string | null; start: string; start_art: string; puffer_min: number | null;
  losfahren: string | null; knapp: string; grund: string; hinweis: string };
export type TagTermin = { uid: string; episode_id: string | null; titel: string; beginn: string; ende: string | null; ort: string;
  personen: TagPerson[]; unbekannt: string[]; hintergrund: Array<{ sache: string; name: string; art: string; herkunft: string; zeilen: TagZeile[] }>;
  projekt: { id: string; name: string; herkunft: string } | null; fristen: TagFrist[];
  einpacken: Array<{ text: string; episode_id: string; titel: string; datum: string | null; art: string }>; wegezeit: TagWeg | null; bereit: boolean };
export type TagAktion = { art: "vorbereitung" | "quelle" | "fahrzeiten" | "heimat" | "akte" | "link" | "welt_quelle" | "welt_sache"; beschriftung: string; ref: string | null };
export type TagLage = { einleitung: string; tag: "heute" | "morgen"; verlauf?: string[];
  zeilen: Array<{ art: "termin" | "leute" | "einpacken" | "fristen" | "wetter" | "welt"; text: string; aktionen: TagAktion[]; vermutlich: boolean }> };
// Das Logbuch (sidecar: logbuch.py, logbuch_routes.py): was seit dem letzten Blick geschah, in Alltagssprache.
export type LogbuchAnsicht = { seit: string; bis: string; zeilen: string[]; leer: boolean;
  tage: Array<{ tag: string; titel: string; eintraege: string[] }> };
export type WegezeitStand = { aktiv: boolean; heimat: string; verkehrsmittel: "auto" | "oepnv" | "fuss"; dienst: string; puffer_min: number;
  dienste: Record<string, boolean>; schluessel_hinterlegt: Record<string, boolean>;
  /** Ob das Einschalten rechnen könnte (Startort und ein Kartendienst da); sonst was fehlt, in einem Satz (Befund 19). */
  kann_rechnen?: boolean; fehlt?: "startort" | "dienst" | null; fehlt_satz?: string };
// Wetter und Welt im Briefing (sidecar: wetter_routes.py, welt_briefing_routes.py).
export type WetterStand = { aktiv: boolean; ort: string; name: string; vorschlag: string; aus_umgebung: boolean };
// Akten als Ordner (sidecar: akten_export_routes.py). Der Ordner wird am Mac über den Auswahldialog gewählt, nie getippt.
export type AktenExport = {
  aktiv: boolean; quellen: boolean; ordner: string | null; ordnername: string; vorgabe: string;
  laeuft: boolean; running: boolean; pick_request: null | { id: string; modus: "vorgabe" | "waehlen" };
  stand: null | { erzeugt_am: string | null; dateien: number; akten: number; mit_quellen: boolean; uebersprungen: number };
  gespiegelt: null | { am: string | null; dateien: number }; angekommen: boolean; fehler: string | null;
};
export type WetterOrt = { name: string; ort: string; breite: number; laenge: number };
// Eine vorgegebene Quelle zum Anklicken (sidecar: welt_vorgaben.py); `feed_id` gibt es, sobald sie hinzugefügt ist.
export type WeltVorgabe = { id: string; label: string; url: string; beschreibung: string; gewaehlt: boolean; feed_id: string | null };
export type WeltFeed = { id: string; url: string; label: string; enabled: boolean; fehler: string };
export type WeltStand = { aktiv: boolean; feeds: WeltFeed[]; weltquellen: Array<{ id: string; label: string; gewaehlt: boolean }>;
  abbestellt: Array<{ sache: string; name: string }>; vorschlaege: WeltVorgabe[]; vorschlaege_stand: { stand: string; abgerufen: string | null }; modell: boolean };
export type TagGeburtstag = { sache: string; name: string; vorname: string; datum: string; wann: "heute" | "morgen" | "bald"; aussage_id: string; episode_id: string | null };
export type TagBriefing = { jetzt: string; tageslage: TagLage | null; termine: TagTermin[]; fristen: TagFrist[]; geburtstage?: TagGeburtstag[]; fehler: Record<string, string>; wegezeit: WegezeitStand };
export type AkteSachen = {
  gesamt: number; berechnung: { offen: number; berechnet: number };
  sachen: Array<{ sache: string; art: AkteSachenArt; art_text: string; name: string; quellen: number; letzte: string | null }>;
};
export type QuellenBezuege = {
  episode_id: string; berechnet: boolean;
  bezuege: Array<{ sache: string; art: AkteSachenArt; art_text: string; name: string; grundlagen: Array<"anker" | "modell" | "nutzer">; zitate: string[] }>;
  offen: Array<{ art: AkteSachenArt; art_text: string; zitat: string; kandidaten: Array<{ sache: string; name: string }> }>;
  abgelehnt: Array<{ sache: string; art: AkteSachenArt; name: string }>;
  veraltet: Array<{ sache: string; art: AkteSachenArt; aktion: "zu" | "nicht" }>;
};

export type ProjectProfile = {
  id: string;
  authority: "projection";
  project: Record<string, unknown>;
  people: Array<{ id: string; name: string; evidence_refs: string[]; last_interaction: string | null; identity_resolution?: string }>;
  episodes: Array<{ id: string; kind: string; title: string; occurred_at: string | null; recorded_at: string; source_type: string; source_ref: string; digest: string }>;
  tasks: Task[];
  notes: Array<Record<string, unknown>>;
  claims: Array<Record<string, unknown>>;
  claim_history: Array<Record<string, unknown>>;
};

export type IdentitySource = { source: string; account: string; native_id: string };
export type RegistryProfile = {
  related_entities: Record<string, {id: string; kind: string; label: string; workspace_project_id?: string}>;
  sources: IdentitySource[];
  same_name_entities: Array<{id: string; kind: string; label: string}>;
  entity: { id: string; kind: string; label: string };
  claims: Array<Record<string, unknown>>;
  claim_history: Array<Record<string, unknown>>;
  revision: number;
};

export type ModelSetup = {
  settings: { provider: string; model: string; endpoint: string };
  status: { provider: string | null; model: string | null; endpoint: string | null; lokale_ki?: LokaleKi | null };
};

/** Die eine Aussage zur lokalen KI (Sidecar `lokale_ki.py`, Fremdprobe Befund 9). Nirgends ein eigener Schluss daneben. */
export type LokaleKi = {
  zustand: "keins" | "cloud" | "nicht_erreichbar" | "fehlt" | "bereit";
  kurz: string; satz: string; modell: string | null; lokal: boolean; erreichbar: boolean; endpunkt: string;
  installiert: string[]; cloud: string[];
};

export class DocumentPreviewError extends Error {}
export class ApiError extends Error {
  // `detail` ist der Grund, den der Server nennt, wenn er einen nennt.
  // `grund` ist die Kennung dazu, wo der Server eine nennt (etwa `adresse_fehlt` beim Kalender).
  constructor(public status: number, public detail?: string, public grund?: string) {
    super(`HTTP ${status}`);
  }
}

async function request<T>(path: string, init?: RequestInit, previewError = false): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    if (previewError && response.status === 422) {
      const payload = await response.json().catch(() => null);
      if (typeof payload?.detail === "string") throw new DocumentPreviewError(payload.detail.slice(0, 500));
    }
    const payload = await response.json().catch(() => null);
    throw new ApiError(response.status, typeof payload?.detail === "string" ? payload.detail.slice(0, 500) : undefined,
      typeof payload?.grund === "string" ? payload.grund.slice(0, 40) : undefined);
  }
  return response.json() as Promise<T>;
}

export type MacCalendarState = {
  enabled: boolean; online: boolean; status: string; authorize: boolean;
  selected: string[]; calendars: Array<{id: string; name: string; source: string}>;
  synced_at: string | null; error: string; event_count: number;
};

export type CalendarOverview = {
  configured: boolean; errors: string[];
  range_start?: string; range_end?: string;
  items: Array<{uid: string; summary: string; start: string | null; end: string | null;
    location: string; all_day: boolean; source_id?: string; source_label?: string; attendees?: string[];
    /** `geburtstag`: ein bestätigter Geburtstag aus dem Gedächtnis, nur in dieser Ansicht (Fremdprobe 2, Befund 20). */
    art?: string}>;
};

export type CalendarActionSource = {id: string; label: string; user: string; calendar_id: string; can_write: boolean; reason: string | null};
export type CalendarActionInput = {kind: 'create'|'edit'|'cancel'; source_id: string; title?: string; start?: string; end?: string; event_id?: string; send_updates: 'all'|'externalOnly'|'none'};
export type CalendarActionDraft = {
  id: string; status: string; kind: CalendarActionInput['kind']; source_id: string; stand: string; provider_event_id: string;
  preview: {calendar: string; account: string; title: string | null; start: {dateTime: string} | null; end: {dateTime: string} | null;
    attendees: string[]; send_updates: CalendarActionInput['send_updates']; etag: string | null;
    current: {summary?: string; start?: {dateTime?: string; date?: string}; end?: {dateTime?: string; date?: string}; location?: string; description?: string} | null};
};

export type CalendarPreparation = {
  event: CalendarOverview["items"][number];
  project: Project | null;
  person: {id: string; label: string; kind: string} | null;
  tasks: Task[];
  decisions: Decision[];
  claims: Array<{ id: string; statement: string; evidence: Array<{ episode_id: string; quote: string }> }>;
  notes: Array<{ id: string; title: string; body: string }>;
  sources: Array<{id: string; title: string; body: string; reason: string; truncated: boolean;
    participants: string[]; recorded_at: string; occurred_at: string | null;
    provenance: {source_type: string; source_ref?: string | null}; working_kinds?: string[]}>;
  sources_more: boolean;
  working_memory_more?: boolean;
};

export type TaskSource = {quote?: string | null; state?: string; title: string; body: string; recorded_at: string; occurred_at: string | null;
  participants: string[]; truncated: boolean; provenance: {source_ref?: string | null}};

export type RecoveryJob = {id: string; status: "queued" | "running" | "completed" | "failed"; message: string; path: string | null};
export type RecoveryStatus = {online: boolean; job: RecoveryJob | null};

export type MemoryCoverage = {
  semantic_index?: {
    status: "disabled" | "unavailable" | "partial" | "indexed";
    model_key: string | null; model_name?: string | null;
    identity_checked_at: number | null;
    total: number | null; indexed: number | null; pending: number | null; failed: number | null;
    updated_at: number | null; source_pending: number | null; pause_reason?: string | null;
  };
  source_dates?: {earliest: string | null; latest: string | null; undated: number};
  working_memory?: {complete: number; pending: number; failed: number; deferred: number; dismissed: number; truncated: boolean};
  working_memory_enabled?: boolean;
  working_memory_progress?: {total: number; done: number; skipped: number; retry: number; remaining: number; estimate_seconds: number | null};
  automation?: MemoryAutomation;
  total_sources: number; sampled_sources: number; truncated: boolean;
  truncated_sources: number;
  counts: Record<"pending" | "running" | "partial" | "completed" | "failed" | "excluded", number>;
  detail: string; scope: string;
};
export type PostfachErreichbar = {account_id: string; label: string; erreichbar: boolean;
  grund: "nicht_erreichbar" | "passwort" | "imap_aus" | "app_passwort" | "unsicher" | null; satz: string | null};
export type MemoryAutomation = {state: "active" | "legacy_active" | "unverified" | "paused" | "model_missing" | "wrong_model" | "local_model_unavailable" | "cloud_ueber_ollama"; requested: boolean; pending: number; model: string | null; cloud_modell?: string | null};
export type MemoryTimeline = {
  basis: "source" | "recorded";
  next_cursor: string | null; start: string; end: string;
  items: Array<{id: string; kind: string; title: string; recorded_at: string; occurred_at: string | null; episode_id: string | null; claim_id: string | null}>;
  truncated: boolean; detail: string;
};

export type TaskHistoryEvent = {
  sequence: number; kind: string; recorded_at: string; business_at: string | null;
  before: {wartet_auf?: string | null} | null; after: {wartet_auf?: string | null};
};

export type WorkingPreference = { id: string; statement: string; status: string; expires_at: string | null; provenance: { source_type: string; source_ref: string | null }; structured: { key: string; value: string; scope: string; scope_key: string | null } };
export type WorkingProfile = { effective: { rules: Record<string, string>; ids: string[]; conflicts: string[] }; items: WorkingPreference[] };
export type WorkingMemoryCorrection = { fingerprint: string; body: string; title: string; source_time: string | null };
export type WorkingMemoryCorrectionResult = { episode_id: string; original_excluded: true };

export type DeviceProfile = {chip:string|null; memory_gb:number|null; platform:'macos'|'windows'|'linux'|'unknown'; source:'macos_host_report'|'host_report'|'eigene'|'untergrenze'|'unknown'; guidance:{capacity:string; headroom_gb:number|null; model_budget_gb:number|null; estimate:boolean; note:string}};
export type ModelEntry = {name: string; groesse_gb: number; speicher_gb: number; art: string; begruendung: string; passt: boolean; bestaetigung: string};
/** Was das Orchester zusammen braucht (sidecar: model_recommendation.orchester_bedarf); `null` heißt: nicht zu sagen. */
export type ModelOrchestra = {
  tag_gb: number; nacht_gb: number; festplatte_gb: number; festplatte_noch_gb: number;
  nutzbar_gb: number | null; festplatte_frei_gb: number | null;
  passt_tag: boolean | null; passt_nacht: boolean | null; passt_festplatte: boolean | null;
  unbekannte_modelle: string[]; hinweise: string[];
};
export type ModelRecommendationRow = {
  rolle: string; titel: string; beschreibung: string; empfohlen: ModelEntry; alternativen: ModelEntry[];
  status: "eingerichtet" | "installiert" | "fehlt";
  wirksam: {modell: string | null; lokal: boolean | null; quelle: "eigene_wahl" | "standard" | "cloud" | "keins"; cloud_ueber_ollama?: boolean};
  blockiert?: string | null;
  orchester_hinweis?: string;
  /** Was „Anderes Modell nehmen“ als Nächstes versucht, wenn die Prüfung scheitert (Befund 11). */
  ausweich?: ModelEntry[];
};
export type ModelRecommendation = {
  stand: string;
  geraet: {plattform: string; chip: string | null; arbeitsspeicher_gb: number | null; bekannt: boolean; stufe_gb: number; stufen: number[];
    /** Woher die Angabe stammt: Helfer (`bericht`), eigene Messung, im Container eine Untergrenze, oder unbekannt. */
    quelle?: "bericht" | "eigene" | "untergrenze" | "unbekannt"; festplatte_frei_gb?: number | null};
  ollama: {erreichbar: boolean; installiert: string[]; cloud_ueber_ollama?: string[]};
  rollen: ModelRecommendationRow[]; hinweis: string;
  orchester?: ModelOrchestra;
};
export type ModelRoleState = {
  rolle: string; titel: string; beschreibung: string; cloud_moeglich: boolean; cloud_satz: string;
  wahl: {modell: string; cloud: boolean; anbieter: string; cloud_einwilligung: string; einwilligung_gueltig: boolean};
  wirksam: {modell: string | null; lokal: boolean | null; quelle: "eigene_wahl" | "standard" | "cloud" | "keins"; cloud_ueber_ollama?: boolean};
  blockiert?: string | null;
};
export type ModelRoles = {saetze?: "an" | "aus"; rollen: ModelRoleState[]; anbieter: Array<{id: string; label: string; schluessel_da: boolean; standardmodell: string}>;
  ollama_cloud?: {modelle: string[]; hinweis: string}};
export type CloudProviderAccess = {id: "mistral" | "openrouter"; label: string; endpoint: string; key_present: boolean; model: string};
export type CloudAccessState = {storage_available: boolean; providers: CloudProviderAccess[]; notice: string};
export type ChatGPTState = {connected:boolean; plan_usage:boolean; available:boolean; secure_storage:boolean;
  active_account:string|null; accounts:Array<{id:string; label:string; active:boolean; plan_usage:boolean}>};
export type ChatGPTModel = {id:string; label:string};
export type CloudMemoryPurpose = "pilot"|"bulk"|"recheck";
export type CloudMemoryPreview = {preview_id:string; purpose:CloudMemoryPurpose; count:number;
  sources:Array<{id:string;title:string;occurred_at:string|null}>; expires_at:number; sampling_note?:string;
  scanned_count:number;next_cursor:number|null};
export type CloudMemoryJob = {id:string;purpose:CloudMemoryPurpose;model:string;state:"running"|"paused"|"complete"|"stopped"|"complete_with_gaps";
  selected:number;position:number;completed:number;failed:number;requests:number;request_limit:number;source_limit:number;
  stop_reason:string;updated_at:number;issue_count?:number;
  issues?:Array<{episode_id:string;stage:string;code:string;reason?:string}>};
export type ModelPullState = {
  id: string; modell: string; rolle: string; phase: "wartet" | "laedt" | "prueft" | "fertig" | "fehler";
  fortschritt: number | null; text: string; fehler: {grund: string; naechster_schritt: string; art?: string} | null;
  ergebnis: {modell: string; rolle: string; geprueft: boolean; latenz_ms: number; uebernommen: boolean} | null;
};
/** Laden im Hintergrund (Fremdprobe 2, Befunde 6 und 7): ein Lauf für alle offenen Aufgaben, Prozent nach Größe. */
export type ModellLaden = {
  laeuft: boolean; prozent: number; gesamt_gb: number; satz: string;
  eingerichtet: string[]; fehlgeschlagen: string[]; auftraege: ModelPullState[];
};
export type GoogleSession = {status: string; kind?: string; email?: string; calendars?: Array<{id:string; name:string}>};

/** „In die Akte übernehmen“ (sidecar: uebernehmen_routes.py): Rückfrage, Vorschläge und deren Stand. */
export type UebernehmenSatz = { nr: number; text: string; hinweise: string[]; steht_schon: boolean; vorgabe: boolean };
export type UebernehmenZiel = { sache: string; name: string; art_text: string };
export type UebernehmenVorschlag = {
  id: string; statement: string; state: "pending" | "accepted" | "rejected" | "superseded"; rationale: string; subject_ref: string;
  evidence: Array<{ episode_id: string; quote: string }>;
};
export type UebernehmenVorschau = { saetze: UebernehmenSatz[]; ziele: UebernehmenZiel[]; sache: string | null; bisher: UebernehmenVorschlag[] };
export type UebernehmenErgebnis = {
  nr: number; text: string; hinweise: string[]; status: "vorgeschlagen" | "steht_schon" | "liegt_vor" | "fehler"; grund?: string;
  vorschlag?: UebernehmenVorschlag;
};

/** Rückkanal für Fehler („Stimmt nicht?“, sidecar: rueckmeldung_routes.py). */
export type RueckmeldungArt = "falsch" | "unvollstaendig" | "veraltet" | "zu_langsam" | "sonstiges";
export type Rueckmeldung = { id: string; erstellt: string; frage: string; antwort: string; art: RueckmeldungArt; art_text: string;
  richtig: string; belege: string[]; status: "offen" | "erledigt"; erledigt_am: string; gespraech_id: string; nachricht_id: string };
export type RueckmeldungZaehlung = { gesamt: number; offen: number; erledigt: number };
export type RueckmeldungenListe = { meldungen: Rueckmeldung[]; zaehlung: RueckmeldungZaehlung; arten: Array<{ id: RueckmeldungArt; text: string }> };

/** Befunde des Lint über alle Akten (sidecar: lint.py, lint_routes.py). */
export type BefundArt = "widerspruch" | "aussage_gegen_quelle" | "veralteter_satz" | "waise" | "querverweis";
export type BefundStatus = "offen" | "erledigt" | "abgewiesen";
export type Befund = {
  id: string; art: BefundArt; art_text: string; unterart: string; schwere: "wichtig" | "hinweis"; text: string;
  sachen: Array<{ sache: string; name: string; art_text: string }>;
  belege: Array<{ episode_id: string; rolle: string; titel: string; datum: string | null; recorded_at: string; digest: string; zitat: string }>;
  stand: string;
  werte: Record<string, string>;
  vorschlaege: Array<{ wahl: "alt" | "neu"; id: string; zustand: string; aussage: string; wert: string }>;
  status: BefundStatus; entschieden: string; gefunden_am: string;
};
export type BefundZusammenfassung = {
  offen: number; wichtig: number; je_art: Record<BefundArt, number>; neu_seit_letztem_lauf: number; letzter_lauf: string | null;
};
export type BefundListe = { befunde: Befund[]; zusammenfassung: BefundZusammenfassung; laeuft: boolean };

export type QuestionSource = {episode_id: string; title: string; quote: string; occurred_at: string | null; recorded_at: string};
export type MemoryQuestion = {id: string; stand: string; subject_ref: string; predicate: string; scope_ref: string | null;
  candidates: Array<{id: string; statement: string; value: string; sources: QuestionSource[]}>;
  active_claims: Array<{id: string; statement: string; value: string; sources: QuestionSource[]}>};

export const api = {
  deviceProfile: () => request<DeviceProfile>("/api/v1/device/profile"),
  /** Auf welchem System Kingfisher läuft (system.ts, laufumgebung.py). */
  system: () => request<SystemAngabe>("/api/v1/system"),
  modelRecommendation: () => request<ModelRecommendation>("/api/v1/models/recommendation"),
  modelRoles: () => request<ModelRoles>("/api/v1/models/roles"),
  antwortzeiten: () => request<AntwortZeitenProtokoll>("/api/v1/antwortzeiten"),
  saetzeSetzen: (saetze: "an" | "aus") =>
    request<{saetze: "an" | "aus"}>("/api/v1/models/saetze", {method: "PUT", body: JSON.stringify({saetze})}),
  satzpruefungSetzen: (satzpruefung: "an" | "aus") =>
    request<SatzpruefungStand>("/api/v1/models/satzpruefung", {method: "PUT", body: JSON.stringify({satzpruefung})}),
  saveModelRole: (rolle: string, body: {modell?: string; cloud?: boolean; anbieter?: string; einwilligung?: boolean}) =>
    request<ModelRoles>(`/api/v1/models/roles/${encodeURIComponent(rolle)}`, {method: "PUT", body: JSON.stringify(body)}),
  cloudAccess: () => request<CloudAccessState>("/api/v1/models/cloud-access"),
  chatgpt: () => request<ChatGPTState>("/api/v1/chatgpt"),
  chatgptBegin: (account_id?:string) => request<{session_id:string;url:string}>("/api/v1/chatgpt/begin",
    {method:"POST",body:JSON.stringify({origin:window.location.origin,consent:true,account_id})}),
  chatgptSession: (sid:string) => request<{status:string}>(`/api/v1/chatgpt/sessions/${encodeURIComponent(sid)}`),
  chatgptModels: () => request<{models:ChatGPTModel[]}>("/api/v1/chatgpt/models"),
  chatgptDisconnect: () => request<{remote_revoked:boolean;notice:string}>("/api/v1/chatgpt",{method:"DELETE"}),
  cloudMemoryStatus: () => request<{job:CloudMemoryJob|null}>("/api/v1/memory/cloud/status"),
  cloudMemoryPreview: (purpose:CloudMemoryPurpose,cursor?:number) => request<CloudMemoryPreview>("/api/v1/memory/cloud/preview",
    {method:"POST",body:JSON.stringify({purpose,cursor,limit:purpose === "pilot" ? 100 : 1000})}),
  cloudMemoryStart: (preview_id:string,model:string) => request<{job:CloudMemoryJob|null}>("/api/v1/memory/cloud/start",
    {method:"POST",body:JSON.stringify({preview_id,model,consent:true})}),
  cloudMemoryAction: (action:"pause"|"resume"|"revoke",job_id:string) => request<{job:CloudMemoryJob|null}>(`/api/v1/memory/cloud/${action}`,
    {method:"POST",body:JSON.stringify({job_id})}),
  saveCloudAccess: (provider: CloudProviderAccess["id"], body: {api_key?: string; model: string}) =>
    request<CloudAccessState>(`/api/v1/models/cloud-access/${encodeURIComponent(provider)}`, {method: "PUT", body: JSON.stringify(body)}),
  removeCloudAccess: (provider: CloudProviderAccess["id"]) =>
    request<CloudAccessState>(`/api/v1/models/cloud-access/${encodeURIComponent(provider)}`, {method: "DELETE"}),
  startModelPull: (rolle: string, modell?: string) =>
    request<ModelPullState>("/api/v1/models/pull", {method: "POST", body: JSON.stringify({rolle, modell, bestaetigt: true})}),
  modelPull: (id: string) => request<ModelPullState>(`/api/v1/models/pull/${encodeURIComponent(id)}`),
  currentModelPull: () => request<{aktuell: ModelPullState | null}>("/api/v1/models/pull"),
  modelleLaden: () => request<ModellLaden>("/api/v1/models/laden", {method: "POST", body: JSON.stringify({bestaetigt: true})}),
  modellLaden: () => request<ModellLaden>("/api/v1/models/laden"),
  microsoftConfig: () => request<MicrosoftStand>("/api/v1/microsoft/config"),
  microsoftConfigSetzen: (client_id: string) => request<MicrosoftStand>("/api/v1/microsoft/config", {method: "PUT", body: JSON.stringify({client_id})}),
  microsoftAnmelden: (adresse: string, mitschriften = false) => request<MicrosoftAnmeldung>("/api/v1/microsoft/anmelden", {method: "POST", body: JSON.stringify({adresse, mitschriften})}),
  microsoftNachfragen: (sitzung: string) => request<MicrosoftAnmeldung>(`/api/v1/microsoft/anmelden/${encodeURIComponent(sitzung)}`),
  microsoftAbbrechen: (sitzung: string) => request<{status: string}>(`/api/v1/microsoft/anmelden/${encodeURIComponent(sitzung)}`, {method: "DELETE"}),
  microsoftKonten: () => request<MicrosoftKonten>("/api/v1/microsoft/konten"),
  microsoftMitschriftenAbholen: () => request<MicrosoftKonten>("/api/v1/microsoft/mitschriften/abholen", {method: "POST"}),
  googleConfig: () => request<{configured:boolean; secure_storage:boolean}>("/api/v1/google/config"),
  saveGoogleConfig: (body: unknown) => request<{configured:boolean; secure_storage:boolean}>("/api/v1/google/config", {method:"PUT", body:JSON.stringify(body)}),
  googleBegin: (kind: string) => request<{session_id:string; url:string}>("/api/v1/google/begin", {method:"POST", body:JSON.stringify({kind, origin:window.location.origin})}),
  googleSession: (id:string) => request<GoogleSession>(`/api/v1/google/sessions/${encodeURIComponent(id)}`),
  googleConnect: (id:string, calendar_ids:string[]) => request<{connected:boolean}>(`/api/v1/google/sessions/${encodeURIComponent(id)}/connect`, {method:"POST", body:JSON.stringify({calendar_ids})}),
  workingProfile: (task = "") => request<WorkingProfile>(`/api/v1/working-profile${task ? `?task=${encodeURIComponent(task)}` : ""}`),
  saveWorkingPreference: (body: { key: string; value: string; scope: string; scope_key: string | null }) => request<{assertion: WorkingPreference}>("/api/v1/working-profile", { method: "PUT", body: JSON.stringify(body) }),
  retractWorkingPreference: (id: string) => request<{assertion: WorkingPreference}>(`/api/v1/working-profile/${encodeURIComponent(id)}`, {method: "DELETE"}),
  supportReview: (cursor?: string | null) => request<SupportReviewPage>(`/api/v1/assertions/support-review?${new URLSearchParams({limit: "25", ...(cursor ? {cursor} : {})})}`),
  previewSupportReassessment: (id: string) => request<SupportReassessmentPreview>(`/api/v1/assertions/${encodeURIComponent(id)}/support-reassessment/preview`, {method: "POST"}),
  submitSupportReassessment: (id: string, preview_token: string) => request<SupportReassessmentResult>(`/api/v1/assertions/${encodeURIComponent(id)}/support-reassessment`, {method: "POST", body: JSON.stringify({preview_token, confirmed: true})}),
  task: (id: string) => request<Task>(`/api/v1/tasks/${encodeURIComponent(id)}`),
  taskHistory: (id: string) => request<{items: TaskHistoryEvent[]; truncated: boolean; scope: string}>(`/api/v1/tasks/${encodeURIComponent(id)}/history`),
  memoryCoverage: () => request<MemoryCoverage>("/api/v1/memory/coverage"),
  memoryAutomation: () => request<MemoryAutomation>("/api/v1/memory/automation"),
  setMemoryAutomation: (enabled: boolean, vormerken = false) => request<MemoryAutomation>("/api/v1/memory/automation", {method: "PUT", body: JSON.stringify(vormerken ? {enabled, vormerken} : {enabled})}),
  memoryTimeline: (start: string, end: string, cursor?: string, basis: "source" | "recorded" = "recorded") => request<MemoryTimeline>(`/api/v1/memory/timeline?${new URLSearchParams({start, end, basis, ...(cursor ? {cursor} : {})})}`),
  recoveryStatus: () => request<RecoveryStatus>("/api/v1/recovery"),
  startRecovery: (password: string) => request<RecoveryJob>("/api/v1/recovery", {method:"POST", body:JSON.stringify({password})}),
  // Sicherung ohne Helfer (Befund 8): das verschlüsselte, geprüfte Archiv als Datei für den Browser.
  recoveryHerunterladen: async (password: string): Promise<{ datei: Blob; name: string }> => {
    const response = await fetch("/api/v1/recovery/herunterladen", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password }) });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new ApiError(response.status, typeof payload?.detail === "string" ? payload.detail.slice(0, 500) : undefined);
    }
    const name = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") ?? "")?.[1] ?? "Kingfisher-Sicherung.recovery";
    return { datei: await response.blob(), name };
  },
  goals: () => request<{items: Array<{id: string; satz: string; marken: string[]; beurteilbar: boolean; letzte_regung: string | null; woran: string | null; tage_still: number | null; schlaeft: boolean}>; completed: Array<{id: string; goal_id: string; statement: string; outcome: "achieved" | "stopped"; note: string; recorded_at: string}>}>("/api/v1/goals"),
  goalHistory: (id: string) => request<Array<{id: string; statement: string; kind: string; status: string; recorded_at: string; status_changed_at?: string; provenance: {source_type: string}}>>(`/api/v1/assertions/${encodeURIComponent(id)}/history`),
  saveGoal: (statement: string, tags: string[], previous?: string) => request("/api/v1/assertions", {method: "POST", body: JSON.stringify({statement, tags, kind: "goal", provenance: {source_type: "user_stated", source_ref: "ui:goals", verbatim: statement}, supersedes: previous ? [previous] : []})}),
  reopenGoal: (id: string) => request(`/api/v1/goals/${encodeURIComponent(id)}/reopen`, {method: "POST"}),
  finishGoal: (id: string, outcome: "achieved" | "stopped", note: string) => request(`/api/v1/goals/${encodeURIComponent(id)}/finish`, {method: "POST", body: JSON.stringify({outcome, note})}),
  retractGoal: (id: string) => request(`/api/v1/assertions/${encodeURIComponent(id)}/retract`, {method: "POST"}),
  uploadedDocuments: (offset = 0) => request<{items: Array<{id: string; title: string; state: string; project_id: string | null; recorded_at: string; memory_status?: {state: string; label: string}}>; next_offset: number | null}>(`/api/v1/sources/documents?offset=${offset}`),
  reopenSource: (id: string) => request(`/api/v1/episodes/${encodeURIComponent(id)}/reopen`, {method: "POST"}),
  ignoreSource: (id: string) => request(`/api/v1/episodes/${encodeURIComponent(id)}/ignore`, {method: "POST"}),
  projectSuggestion: (id: string) => request<ProjectSuggestion>(`/api/v1/episodes/${encodeURIComponent(id)}/project-suggestion`),
  linkSameSender: (id: string, projectId: string) => request<{changed: string[]}>(`/api/v1/episodes/${encodeURIComponent(id)}/project/same-sender`, {method: "POST", body: JSON.stringify({project_id: projectId})}),
  linkSourceProjects: (ids: string[], projectId: string | null, onlyIf: string | null) => request<{changed: string[]}>("/api/v1/episodes/projects", {method: "PUT", body: JSON.stringify({episode_ids: ids, project_id: projectId, only_if_project_id: onlyIf})}),
  linkSourceProject: (id: string, projectId: string | null) => request<{project_id: string | null}>(`/api/v1/episodes/${encodeURIComponent(id)}/project`, {method: "PUT", body: JSON.stringify({project_id: projectId})}),
  previewPdf: (content_base64: string) => request<{body: string; empty_pages: number[]}>("/api/v1/sources/documents/preview-pdf", {method: "POST", body: JSON.stringify({content_base64})}, true),
  previewDocx: (content_base64: string) => request<{body: string}>("/api/v1/sources/documents/preview-docx", {method: "POST", body: JSON.stringify({content_base64})}),
  routingStatus: () => request<{enabled: boolean; profiles: Array<{model: string; verified: boolean; latency_ms: number; checked_at: string}>}>("/api/v1/routing"),
  verifyRouting: () => request<{enabled: boolean; profiles: Array<{model: string; verified: boolean; latency_ms: number; checked_at: string}>}>("/api/v1/routing/verify", {method: "POST"}),
  setRouting: (enabled: boolean) => request<{enabled: boolean; profiles: Array<{model: string; verified: boolean; latency_ms: number; checked_at: string}>}>("/api/v1/routing", {method: "POST", body: JSON.stringify({enabled})}),
  previewTranscript: (text: string, format: "srt" | "vtt") => request<{body: string; segment_count: number}>("/api/v1/sources/documents/preview-transcript", {method: "POST", body: JSON.stringify({text, format})}, true),
  importDocument: (body: {filename: string; body: string; project_id: string | null}) => request<{id: string; created: boolean; title: string; project_id: string | null}>("/api/v1/sources/documents", {method: "POST", body: JSON.stringify(body)}),
  dismissWorkingMemory: (id: string) => request<{dismissed: boolean}>(`/api/v1/memory/working/${encodeURIComponent(id)}/dismiss`, {method: "POST"}),
  workingMemoryCorrection: (id: string) => request<WorkingMemoryCorrection>(`/api/v1/memory/working/${encodeURIComponent(id)}/correction`),
  saveWorkingMemoryCorrection: (id: string, body: {fingerprint: string; body: string}) => request<WorkingMemoryCorrectionResult>(`/api/v1/memory/working/${encodeURIComponent(id)}/correction`, {method: "POST", body: JSON.stringify(body)}),
  profileSource: (kind: "episode" | "note", id: string) => request<{title: string; body: string; state?: string; revision?: number; correction_id?: string; correction_current?: boolean; source_current?: boolean; source_incomplete?: boolean; attachment_check_pending?: boolean; attachment_sources?: Array<{id: string; title: string}>; attachment_coverage?: {geprueft: boolean; vollstaendig: boolean; hinweis: string} | null; project_id?: string | null; memory_status?: {state: string; label: string}; provenance?: {source_type?: string; source_ref?: string; correction_current?: boolean}}>(`/api/v1/${kind === "episode" ? "episodes" : "notes"}/${encodeURIComponent(id)}`),
  identities: () => request<{entities: Array<{id: string; label: string; kind: string}>}>("/api/v1/memory/registry"),
  correctClaim: (id: string, body: {value: string; statement: string; reason: string; scope_ref: string | null; target_ref: string | null; valid_from: string | null; valid_until: string | null}) => request(`/api/v1/memory/claims/${encodeURIComponent(id)}/correct`, {method: "POST", body: JSON.stringify(body)}),
  retractClaim: (id: string, reason: string) => request(`/api/v1/memory/claims/${encodeURIComponent(id)}/retract`, {method: "POST", body: JSON.stringify({reason})}),
  renameIdentity: (id: string, label: string) => request(`/api/v1/memory/registry/${encodeURIComponent(id)}`, {method: "PATCH", body: JSON.stringify({label})}),
  unlinkIdentitySource: (id: string, source: IdentitySource) => request(`/api/v1/memory/registry/${encodeURIComponent(id)}/sources`, {method: "DELETE", body: JSON.stringify(source)}),
  taskSource: (id: string) => request<TaskSource>(`/api/v1/tasks/${encodeURIComponent(id)}/source`),
  resolveAction: (conversationId: string, approvalId: string, granted: boolean, confirmation?: string) =>
    request<ConversationPayload>(`/api/v1/conversations/${conversationId}/approvals/${approvalId}`, {method: "POST", body: JSON.stringify({granted, confirmation})}),
  calendarActionSources: () => request<{sources: CalendarActionSource[]}>('/api/v1/calendar-actions/sources'),
  calendarActionDraft: (body: CalendarActionInput) => request<CalendarActionDraft>('/api/v1/calendar-actions/drafts', {method:'POST', body:JSON.stringify(body)}),
  calendarActionRead: (id: string) => request<CalendarActionDraft>(`/api/v1/calendar-actions/drafts/${encodeURIComponent(id)}`),
  calendarActionExecute: (draft: CalendarActionDraft) => request<CalendarActionDraft>(`/api/v1/calendar-actions/drafts/${encodeURIComponent(draft.id)}/execute`, {method:'POST', body:JSON.stringify({confirmed:true, stand:draft.stand})}),
  calendar: (from?: string, until?: string) => request<CalendarOverview>(`/api/v1/calendar?${from && until ? new URLSearchParams({from, until, tz: Intl.DateTimeFormat().resolvedOptions().timeZone}) : 'year_view=true'}`),
  calendarPreparation: (uid: string, projectId = "", personId = "", start?: string | null) => request<CalendarPreparation>(
    `/api/v1/calendar/preparation?uid=${encodeURIComponent(uid)}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}${personId ? `&person_id=${encodeURIComponent(personId)}` : ""}${start ? `&start=${encodeURIComponent(start)}` : ''}`,
  ),
  calendarAssignment: (uid: string, start?: string | null) => request<TerminZuordnung>(`/api/v1/calendar/zuordnung?${new URLSearchParams({uid, ...(start ? {start} : {})})}`),
  setCalendarAssignment: (uid: string, projectId: string | null, start?: string | null) => request<TerminZuordnung>("/api/v1/calendar/zuordnung", { method: "PUT", body: JSON.stringify({ uid, project_id: projectId, ...(start ? {start} : {}) }) }),
  calendarFollowup: (uid: string, start: string) => request<TerminNachbereitung>(`/api/v1/calendar/nachbereitung?uid=${encodeURIComponent(uid)}&start=${encodeURIComponent(start)}`),
  recordCalendarFollowup: (body: { uid: string; start: string; text: string; format: "text" | "srt" | "vtt"; notiz?: string; project_id: string | null }) => request<NachbereitungGespeichert>("/api/v1/calendar/nachbereitung", { method: "POST", body: JSON.stringify(body) }),
  transkripte: () => request<TranskriptUebersicht>("/api/v1/transkripte"),
  ordnerOrte: (prefix: OrdnerPrefix) => request<OrdnerOrte>(`${prefix}/orte`),
  unterordner: (prefix: OrdnerPrefix, pfad: string) => request<Unterordner>(`${prefix}/unterordner?pfad=${encodeURIComponent(pfad)}`),
  ordnerLokal: (prefix: OrdnerPrefix, wahl: { pfad?: string; vorgabe?: boolean }) =>
    request<TranskriptOrdner & { satz: string }>(`${prefix}/lokal`, { method: "POST", body: JSON.stringify(wahl) }),
  transkriptOrdnerWaehlen: (modus: "vorgabe" | "waehlen") => request<TranskriptOrdner>("/api/v1/transkripte/ordner", { method: "POST", body: JSON.stringify({ modus }) }),
  transkriptAuswahlAbbrechen: () => request<TranskriptOrdner>("/api/v1/transkripte/ordner/auswahl", { method: "DELETE" }),
  transkriptOrdnerTrennen: () => request<TranskriptOrdner & { entzogen: number }>("/api/v1/transkripte/ordner", { method: "DELETE" }),
  transkriptAktiv: (enabled: boolean) => request<TranskriptOrdner>("/api/v1/transcript-sync", { method: "PUT", body: JSON.stringify({ enabled }) }),
  transkriptZuordnen: (id: string, termin: string) => request<TranskriptEintrag>(`/api/v1/transkripte/${encodeURIComponent(id)}/zuordnung`, { method: "POST", body: JSON.stringify({ termin }) }),
  transkriptLoesen: (id: string) => request<TranskriptEintrag>(`/api/v1/transkripte/${encodeURIComponent(id)}/zuordnung`, { method: "DELETE" }),
  setCalendarFollowupStatus: (uid: string, start: string, nichts: boolean) => request<TerminNachbereitung>("/api/v1/calendar/nachbereitung/stand", { method: "PUT", body: JSON.stringify({ uid, start, nichts }) }),
  macCalendar: () => request<MacCalendarState>("/api/v1/mac-calendar"),
  connectMacCalendar: () => request<MacCalendarState>("/api/v1/mac-calendar/connect", {method: "POST"}),
  selectMacCalendars: (ids: string[]) => request<MacCalendarState>("/api/v1/mac-calendar/selection", {method: "PUT", body: JSON.stringify({ids})}),
  disconnectMacCalendar: () => request<MacCalendarState>("/api/v1/mac-calendar", {method: "DELETE"}),
  registryProfile: (id: string) => request<RegistryProfile>(`/api/v1/memory/registry/${encodeURIComponent(id)}`),
  modelSetup: () => request<ModelSetup>("/api/v1/setup"),
  // Was Ollama hat, von der Adresse, unter der Kingfisher es selbst findet (nicht mehr fest `host.docker.internal`).
  lokaleKi: () => request<LokaleKi>("/api/v1/models/stand"),
  localModels: () => request<LokaleKi>("/api/v1/models/stand").then(stand => {
    // Antwortet Ollama nicht, gibt es keine Liste, auch keine leere: Die Aufrufer sagen dann „Ollama antwortet nicht“.
    if (!stand.erreichbar) throw new ApiError(503, stand.satz);
    return { modelle: [...stand.installiert, ...stand.cloud] };
  }),
  // `endpoint`: wo Kingfisher Ollama selbst findet (`LokaleKi.endpunkt`); ohne Angabe die Adresse im Container.
  saveLocalModel: (model: string, endpoint = "http://host.docker.internal:11434/v1") => request<ModelSetup>("/api/v1/setup", {
    method: "PUT", body: JSON.stringify({ provider: "ollama", model, endpoint, onboarded: true }),
  }),
  testModel: () => request<{ ok: boolean }>("/api/v1/setup/test/modell", { method: "POST" }),
  /** `post: false`: ohne Posteingang, damit Heute den Gruß sofort zeigt (Befund 22); danach folgt der volle Abruf. */
  // Ohne Zeitzone des Browsers: Es gilt die eingestellte (Kingfisher und du), nicht die des Rechners (Fremdprobe 2, Befund 9).
  morning: (post = true) => request<MorningBriefing>(`/api/v1/morning-briefing${post ? "" : "?post=false"}`),
  status: () => request<{ chat: boolean }>("/api/v1/status"),
  createConversation: (title = "Neues Gespräch") =>
    request<ConversationPayload>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  getConversation: (id: string) => request<ConversationPayload>(`/api/v1/conversations/${id}`),
  listConversations: () => request<{ conversations: ConversationSummary[] }>("/api/v1/conversations"),
  integrations: () => request<IntegrationOverview>("/api/v1/integrations"),
  schedule: () => request<Schedule>("/api/v1/schedule"),
  saveSchedule: (data: {enabled: boolean; mail_accounts: string[]; interval_minutes: number}) => request<Schedule>("/api/v1/schedule", {method: "PUT", body: JSON.stringify(data)}),
  mailIntake: (signal?: AbortSignal) => request<MailIntakeStatus>("/api/v1/mail/intake", {signal}),
  geburtstag: (sache: string) => request<{geburtstag: null | {wert: string; text: string; aussage: string; aussage_id: string}}>(`/api/v1/geburtstag?sache=${encodeURIComponent(sache)}`),
  mailStand: () => request<{accounts: Array<MailStand & {account_id: string; label: string}>}>("/api/v1/mail/stand"),
  // Antwortet jedes verbundene Postfach gerade? Eine Anmeldung je Konto mit Zeitgrenze; liest nichts.
  mailErreichbar: () => request<{accounts: PostfachErreichbar[]}>("/api/v1/mail/erreichbar"),
  previewMailIntake: (accountId: string, signal?: AbortSignal) => request<MailIntakePreview>(`/api/v1/mail/intake/${encodeURIComponent(accountId)}/preview`, {signal}),
  startMailIntake: (accountId: string, folders: string[], signal?: AbortSignal) => request<MailIntakeStatus>(`/api/v1/mail/intake/${encodeURIComponent(accountId)}/start`, {method: "POST", body: JSON.stringify({folders}), signal}),
  pauseMailIntake: (accountId: string, paused: boolean, signal?: AbortSignal) => request<MailIntakeStatus>(`/api/v1/mail/intake/${encodeURIComponent(accountId)}/pause`, {method: "POST", body: JSON.stringify({paused}), signal}),
  retryMailIntake: (accountId: string, signal?: AbortSignal) => request<MailIntakeStatus>(`/api/v1/mail/intake/${encodeURIComponent(accountId)}/retry`, {method: "POST", body: JSON.stringify({}), signal}),
  categoryTaxonomy: () => request<{version: number; items: CategoryTaxonomyEntry[]}>("/api/v1/memory/categories"),
  memoryAreas: (limit = 50, cursor?: number, area?: string) => request<MemoryAreasPage>(`/api/v1/memory/areas?${new URLSearchParams({limit: String(limit), ...(cursor === undefined ? {} : {cursor: String(cursor)}), ...(area === undefined ? {} : {area})})}`),
  addCategory: (body: {id: string; label: string; description: string}) => request<CategoryTaxonomyEntry>("/api/v1/memory/categories", {method: "POST", body: JSON.stringify(body)}),
  sourceCategories: (id: string) => request<SourceCategoriesResult>(`/api/v1/episodes/${encodeURIComponent(id)}/categories`),
  correctSourceCategories: (id: string, categories: string[]) => request<SourceCategoriesResult>(`/api/v1/episodes/${encodeURIComponent(id)}/categories`, {method: "PUT", body: JSON.stringify({categories})}),
  einrichtung: () => request<EinrichtungStand>("/api/v1/einrichtung"),
  einrichtungSetzen: (aenderung: EinrichtungAenderung) => request<EinrichtungStand>("/api/v1/einrichtung", { method: "PUT", body: JSON.stringify(aenderung) }),
  calendarMemory: () => request<{ mac_termine: number; quellen: Array<{ id: string; label: string; termine: number }> }>("/api/v1/calendar-memory"),
  syncCalendarMemory: () => request<unknown>("/api/v1/calendar-memory/sync", { method: "POST" }),
  lernt: (signal?: AbortSignal) => request<{ akten: { offen: number; gesamt: number } | null }>("/api/v1/einrichtung/lernt", { signal }),
  hintergrund: () => request<HintergrundStand>("/api/v1/hintergrund"),
  hintergrundPausieren: (pause: boolean) => request<HintergrundStand>(`/api/v1/hintergrund/${pause ? "pause" : "weiter"}`, { method: "POST" }),
  // Meldet eine Eingabe (Taste, Klick); der Hintergrund tritt dann 20 s zurück. Antwortet ohne Inhalt.
  hintergrundAktiv: () => fetch("/api/v1/hintergrund/aktiv", { method: "POST", keepalive: true }).then(() => undefined, () => undefined),
  autostart: () => request<AutostartStand>("/api/v1/autostart"),
  autostartSetzen: (an: boolean) => request<AutostartStand>("/api/v1/autostart", { method: "PUT", body: JSON.stringify({ an }) }),
  mailProviders: () => request<{ providers: MailProvider[] }>("/api/v1/integrations/mail-providers"),
  addMailAccount: (data: {
    label: string; imap_host: string; imap_port: number; smtp_host: string; smtp_port: number;
    user: string; sender: string; password?: string;
  }) => request<IntegrationOverview>("/api/v1/integrations/mail", { method: "POST", body: JSON.stringify(data) }),
  addCalendarSource: (data: { label: string; kind: "caldav" | "ical"; url: string; user?: string; password?: string }) =>
    request<IntegrationOverview>("/api/v1/integrations/calendar", { method: "POST", body: JSON.stringify(data) }),
  erkenneAnbieter: (adresse: string) =>
    request<AnbieterErkennung>(`/api/v1/integrations/mail-providers/erkennen?adresse=${encodeURIComponent(adresse)}`),
  kalenderAbo: (data: { url: string; label?: string }) =>
    request<IntegrationOverview & { gefunden: string; termine: number; neu: number }>("/api/v1/integrations/calendar/abo", { method: "POST", body: JSON.stringify(data) }),
  kalenderAnmelden: (data: { adresse: string; password?: string; mail_konto?: string; url?: string }) =>
    request<KalenderAnmeldung>("/api/v1/integrations/calendar/anmelden", { method: "POST", body: JSON.stringify(data) }),
  removeIntegration: (kind: "mail" | "calendar", id: string) =>
    request<IntegrationOverview>(`/api/v1/integrations/${kind}/${id}`, { method: "DELETE" }),
  tasks: (view: "mine" | "waiting" | "done", projectId = "", options: {q?: string; cursor?: string | null; limit?: number} = {}) => request<{view: string; tasks: Task[]; total: number; next_cursor: string | null; stand: string; limit: number}>(`/api/v1/tasks?${new URLSearchParams({view, limit: String(options.limit ?? 50), ...(projectId ? {project_id: projectId} : {}), ...(options.q ? {q: options.q} : {}), ...(options.cursor ? {cursor: options.cursor} : {})})}`),
  projects: () => request<Project[]>("/api/v1/projects?all=true"),
  decisions: () => request<{items: Decision[]}>("/api/v1/decisions"),
  decisionBasis: () => request<{items: DecisionBasis[]}>("/api/v1/decision-basis"),
  addDecision: (data: {statement: string; derived_from: string[]; claim_ids: string[]; project_id?: string}) => request<Decision>("/api/v1/decisions", {method: "POST", body: JSON.stringify(data)}),
  retractDecision: (id: string) => request<Decision>(`/api/v1/decisions/${id}/retract`, {method: "POST"}),
  addProject: (data: { name: string; description?: string }) => request<Project>("/api/v1/projects", {method: "POST", body: JSON.stringify(data)}),
  updateProject: (id: string, data: { status: Project["status"] }) => request<Project>(`/api/v1/projects/${id}`, {method: "PATCH", body: JSON.stringify(data)}),
  assignTaskProject: (id: string, project_id: string | null) => request<Task>(`/api/v1/tasks/${id}/project`, {method: "PATCH", body: JSON.stringify({project_id})}),
  editTask: (id: string, data: {title?: string; due?: string | null; remind_at?: string | null; expected_remind_at?: string | null; notes?: string | null}) => request<Task>(`/api/v1/tasks/${encodeURIComponent(id)}`, {method: "PATCH", body: JSON.stringify(data)}),
  taskReminders: (limit = 100) => request<{items: Task[]; truncated: boolean}>(`/api/v1/tasks/reminders?limit=${limit}`),
  addTask: (data: { title: string; due?: string | null; project_id?: string; goal_id?: string | null }) =>
    request<Task>("/api/v1/tasks", { method: "POST", body: JSON.stringify(data) }),
  waitTask: (id: string, name: string) => request<Task>(`/api/v1/tasks/${id}/warten`, {method: "POST", body: JSON.stringify({name})}),
  unwaitTask: (id: string) => request<Task>(`/api/v1/tasks/${id}/zurueckholen`, {method: "POST"}),
  reopenTask: (id: string) => request<Task>(`/api/v1/tasks/${id}/reopen`, { method: "POST" }),
  completeTask: (id: string) => request<Task>(`/api/v1/tasks/${id}/done`, { method: "POST" }),
  messages: (accountId?: string) => request<InboxPayload>(`/api/v1/messages${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ""}`),
  mailThread: (uid: string, signal?: AbortSignal) => request<MailThreadContext>(`/api/v1/messages/${encodeURIComponent(uid)}/thread`, {signal}),
  mailThreadSummary: (uid: string, context_fingerprint: string, signal?: AbortSignal) => request<MailThreadSummary>(`/api/v1/messages/${encodeURIComponent(uid)}/thread-summary`, {method: "POST", body: JSON.stringify({context_fingerprint}), signal}),
  mailMessage: (uid: string) => request<MailDetail>(`/api/v1/messages/${encodeURIComponent(uid)}`),
  rememberMail: (uid: string) => request<{new: boolean; changed: boolean; episode: {state: string}}>(`/api/v1/messages/${encodeURIComponent(uid)}/remember`, {method: "POST"}),
  taskCandidates: () => request<TaskCandidate[]>("/api/v1/task-candidates"),
  taskCandidatePage: (limit: number, offset: number, temporal: "all" | "recent" | "review", generation?: string) => request<TaskCandidatePage>(`/api/v1/task-candidates/page?${new URLSearchParams({limit: String(limit), offset: String(offset), temporal, ...(generation ? {generation} : {})})}`),
  acceptTaskCandidate: (id: string, data: {title: string; project_id: string | null; due: string | null; waiting_for: string | null}) => request<Task>(`/api/v1/task-candidates/${encodeURIComponent(id)}/accept`, {method: "POST", body: JSON.stringify(data)}),
  rejectTaskCandidate: (id: string) => request<unknown>(`/api/v1/task-candidates/${encodeURIComponent(id)}/reject`, {method: "POST"}),
  taskSuggestions: (uid: string) => request<MailTaskSuggestions>(`/api/v1/messages/${encodeURIComponent(uid)}/task-suggestions`, {method: "POST"}),
  mailBriefing: (uid: string, signal?: AbortSignal, refresh = false) => request<MailBriefing>(`/api/v1/messages/${encodeURIComponent(uid)}/briefing`, {method: "POST", body: JSON.stringify({refresh}), signal}),
  addMailTask: (uid: string, data: {title: string; project_id: string | null; due: string | null; waiting_for: string | null; source_digest: string; source_quote?: string | null; quick_accept?: boolean}) =>
    request<Task>(`/api/v1/messages/${encodeURIComponent(uid)}/task`, {method: "POST", body: JSON.stringify(data)}),
  prepareMailReply: (uid: string, data: {body: string; context_token?: string}) => request<ConversationPayload>(`/api/v1/messages/${encodeURIComponent(uid)}/reply`, {method: "POST", body: JSON.stringify(data)}),
  validateMailReplyContext: (uid: string, contextToken: string) => request<{valid: boolean}>(`/api/v1/messages/${encodeURIComponent(uid)}/reply-suggestion/validate`, {method: "POST", body: JSON.stringify({context_token: contextToken})}),
  latestConversation: () => request<{ conversation: ConversationPayload["conversation"] | null }>(
    "/api/v1/conversations/latest",
  ),
  sendMessage: (id: string, message: string, clarification?: { choice?: number; date?: string; newQuestion?: boolean }) =>
    request<ConversationPayload>(`/api/v1/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({
        message,
        ...(clarification?.newQuestion ? { new_question: true } : {}),
        ...(clarification?.choice !== undefined ? { clarification_choice: clarification.choice } : {}),
        ...(clarification?.date ? { clarification_date: clarification.date } : {}),
      }),
    }),
  retryMessage: (conversationId: string, messageId: string) =>
    request<ConversationPayload>(
      `/api/v1/conversations/${conversationId}/messages/${messageId}/retry`,
      { method: "POST" },
    ),
  acceptMemoryCandidate: (conversationId: string, candidateId: string, replaceConflicts = false) =>
    request<ConversationPayload>(
      `/api/v1/conversations/${conversationId}/memory-candidates/${candidateId}/accept`,
      { method: "POST", body: JSON.stringify({ replace_conflicts: replaceConflicts }) },
    ),
  rejectMemoryCandidate: (conversationId: string, candidateId: string) =>
    request<ConversationPayload>(
      `/api/v1/conversations/${conversationId}/memory-candidates/${candidateId}/reject`,
      { method: "POST" },
    ),
  retractMemoryCandidate: (conversationId: string, candidateId: string) =>
    request<ConversationPayload>(
      `/api/v1/conversations/${conversationId}/memory-candidates/${candidateId}/retract`,
      { method: "POST", body: JSON.stringify({ reason: "Im Gespräch ausdrücklich als falsch widerrufen." }) },
    ),
  memoryGraph: () => request<MemoryGraph>("/api/v1/memory/graph"),
  personMerges: () => request<{merges: PersonMerge[]}>("/api/v1/memory/person-merges"),
  previewPersonMerge: (member_ids: string[], label: string) => request<PersonMergePreview>("/api/v1/memory/person-merges/preview", {
    method: "POST", body: JSON.stringify({member_ids, label}),
  }),
  confirmPersonMerge: (member_ids: string[], label: string, preview_token: string) => request<PersonMerge>("/api/v1/memory/person-merges", {
    method: "POST", body: JSON.stringify({member_ids, label, preview_token, confirmed: true}),
  }),
  undoPersonMerge: (id: string) => request<PersonMerge>(`/api/v1/memory/person-merges/${encodeURIComponent(id)}/undo`, {
    method: "POST", body: JSON.stringify({confirmed: true}),
  }),
  personDigest: (id: string) => request<PersonDigestResult>(`/api/v1/memory/person-digests/${encodeURIComponent(id)}`),
  refreshPersonDigest: (id: string) => request<PersonDigestResult>(`/api/v1/memory/person-digests/${encodeURIComponent(id)}`, {
    method: "POST", body: JSON.stringify({refresh: true}),
  }),
  personProfile: (name: string) => request<PersonProfile>(`/api/v1/memory/people/${encodeURIComponent(name)}`),
  projectProfile: (id: string) => request<ProjectProfile>(`/api/v1/memory/projects/${encodeURIComponent(id)}`),
  projectDetails: (id: string, alle = false) => request<MappeEinzelheiten>(`/api/v1/memory/projects/${encodeURIComponent(id)}/einzelheiten${alle ? "?alle=1" : ""}`),
  /** Kreis je Person (sidecar: kreis_routes.py): Vorschlag mit Begründung, Bestätigung mit einem Klick. */
  kreis: (sache: string) => request<KreisStand>(`/api/v1/kreis?sache=${encodeURIComponent(sache)}`),
  kreisBestaetigen: (sache: string, kreis: KreisArt) => request<KreisStand>("/api/v1/kreis", { method: "PUT", body: JSON.stringify({ sache, kreis }) }),
  kreisZuruecknehmen: (sache: string) => request<KreisStand>(`/api/v1/kreis?sache=${encodeURIComponent(sache)}`, { method: "DELETE" }),
  kreisUebersicht: () => request<KreisUebersicht>("/api/v1/kreis/uebersicht"),
  /** Alle offenen Vorschläge „Kollegen“ mit einem Klick (nie der innere Kreis); `anzahl` ist die Zahl aus der Rückfrage. */
  kreisSammeln: (anzahl: number) => request<{ sammlung: number | null; anzahl: number; satz: string }>("/api/v1/kreis/sammel", { method: "POST", body: JSON.stringify({ kreis: "kollegen", anzahl }) }),
  kreisSammlungZurueck: (sammlung: number) => request<{ anzahl: number; satz: string }>(`/api/v1/kreis/sammel?sammlung=${encodeURIComponent(String(sammlung))}`, { method: "DELETE" }),
  /** Geburtstag und Wiederkehrendes einer Akte (sidecar: wiederkehrendes_routes.py): Vorschläge und Angenommenes. */
  wiederkehrendes: (sache: string) => request<WkStand>(`/api/v1/wiederkehrendes?sache=${encodeURIComponent(sache)}`),
  /** Private Art einer Akte (sidecar: akten_arten_routes.py). */
  aktenArt: (sache: string) => request<ArtStand>(`/api/v1/akten/art?sache=${encodeURIComponent(sache)}`),
  aktenArtBestaetigen: (sache: string, art: AktenArt) => request<ArtStand>("/api/v1/akten/art", { method: "PUT", body: JSON.stringify({ sache, art }) }),
  akte: (sache: string, alle = false) => request<Akte>(`/api/v1/akten/akte?sache=${encodeURIComponent(sache)}${alle ? "&alle=1" : ""}`),
  akteSachen: (art: AkteSachenArt, offset = 0, suche = "") => request<AkteSachen>(`/api/v1/akten/sachen?art=${art}&limit=50&offset=${offset}${suche ? `&suche=${encodeURIComponent(suche)}` : ""}`),
  quellenBezuege: (episodeId: string) => request<QuellenBezuege>(`/api/v1/akten/quellen/${encodeURIComponent(episodeId)}`),
  bezugSetzen: (episodeId: string, sache: string, aktion: "zu" | "nicht") => request<QuellenBezuege>(`/api/v1/akten/quellen/${encodeURIComponent(episodeId)}/zuordnung`, { method: "PUT", body: JSON.stringify({ sache, aktion }) }),
  bezugEntfernen: (episodeId: string, sache: string) => request<QuellenBezuege>(`/api/v1/akten/quellen/${encodeURIComponent(episodeId)}/zuordnung?sache=${encodeURIComponent(sache)}`, { method: "DELETE" }),
  // `nachladen`: stilles Erneuern bei offenem Tab; es zählt nicht als Blick für das Logbuch.
  tagBriefing: (nachladen = false) => request<TagBriefing>(`/api/v1/tag/briefing${nachladen ? "?nachladen=true" : ""}`),
  logbuch: (seit?: string) => request<LogbuchAnsicht>(`/api/v1/logbuch${seit ? `?seit=${encodeURIComponent(seit)}` : ""}`),
  /** Laufende Fassung und Update-Angebot (sidecar: fassung_routes.py). Lesen fragt nie nach außen. */
  fassung: () => request<FassungStand>("/api/v1/fassung"),
  /** „Jetzt nachsehen“: genau eine Anfrage an die Download-Seite; `erreicht` sagt, ob ein gültiges Manifest kam. */
  fassungPruefen: () => request<FassungStand>("/api/v1/fassung/pruefen", { method: "POST" }),
  fassungSchalten: (pruefen: boolean) => request<FassungStand>("/api/v1/fassung", { method: "PUT", body: JSON.stringify({ pruefen }) }),
  wegezeit: () => request<WegezeitStand>("/api/v1/wegezeit/einstellungen"),
  wegezeitSetzen: (body: Partial<Pick<WegezeitStand, "aktiv" | "heimat" | "verkehrsmittel" | "dienst" | "puffer_min">>) =>
    request<WegezeitStand>("/api/v1/wegezeit/einstellungen", { method: "PUT", body: JSON.stringify(body) }),
  wegezeitSchluessel: (dienst: "openrouteservice" | "google", schluessel: string) =>
    request<WegezeitStand>("/api/v1/wegezeit/schluessel", { method: "PUT", body: JSON.stringify({ dienst, schluessel }) }),
  wegezeitSchluesselLoeschen: (dienst: "openrouteservice" | "google") =>
    request<WegezeitStand>(`/api/v1/wegezeit/schluessel?dienst_name=${dienst}`, { method: "DELETE" }),
  wetter: () => request<WetterStand>("/api/v1/wetter/einstellungen"),
  wetterSetzen: (body: { aktiv?: boolean; ort?: WetterOrt }) =>
    request<WetterStand>("/api/v1/wetter/einstellungen", { method: "PUT", body: JSON.stringify(body) }),
  suchindex: () => request<SuchindexStand>("/api/v1/suchindex"),
  suchindexSetzen: (wortteileJahre: number) =>
    request<SuchindexStand>("/api/v1/suchindex", { method: "PUT", body: JSON.stringify({ wortteile_jahre: wortteileJahre }) }),
  /** Bei stummem Ortsdienst 200 mit `satz` statt einer Fehlantwort (Befund 32). */
  wetterOrte: (suche: string) => request<{ orte: WetterOrt[]; grund?: string; satz?: string }>(`/api/v1/wetter/orte?suche=${encodeURIComponent(suche)}`),
  aktenExport: () => request<AktenExport>("/api/v1/akten/export"),
  aktenExportSetzen: (body: { aktiv?: boolean; quellen?: boolean }) => request<AktenExport>("/api/v1/akten/export", { method: "PUT", body: JSON.stringify(body) }),
  aktenExportSchreiben: () => request<AktenExport>("/api/v1/akten/export", { method: "POST" }),
  aktenExportOrdnerWaehlen: (modus: "vorgabe" | "waehlen") => request<AktenExport>("/api/v1/akten/export/ordner", { method: "POST", body: JSON.stringify({ modus }) }),
  aktenExportAuswahlAbbrechen: () => request<AktenExport>("/api/v1/akten/export/ordner/auswahl", { method: "DELETE" }),
  aktenExportOrdnerTrennen: () => request<AktenExport>("/api/v1/akten/export/ordner", { method: "DELETE" }),
  welt: () => request<WeltStand>("/api/v1/welt/briefing"),
  weltSetzen: (body: { aktiv?: boolean; weltquellen?: string[] }) =>
    request<WeltStand>("/api/v1/welt/briefing", { method: "PUT", body: JSON.stringify(body) }),
  weltFeedNeu: (url: string, label: string) => request<WeltStand>("/api/v1/welt/feeds", { method: "POST", body: JSON.stringify({ url, label }) }),
  weltFeedWeg: (id: string) => request<WeltStand>(`/api/v1/welt/feeds/${encodeURIComponent(id)}`, { method: "DELETE" }),
  weltFeedSchalter: (id: string, an: boolean) => request<WeltStand>(`/api/v1/welt/feeds/${encodeURIComponent(id)}/schalter`, { method: "POST", body: JSON.stringify({ an }) }),
  weltAbbestellen: (ziel: { quelle_id: string } | { sache: string }) => request<WeltStand>("/api/v1/welt/abbestellen", { method: "POST", body: JSON.stringify(ziel) }),
  weltZulassen: (sache: string) => request<WeltStand>("/api/v1/welt/zulassen", { method: "POST", body: JSON.stringify({ sache }) }),
  personDetails: (name: string, alle = false) => request<MappeEinzelheiten>(`/api/v1/memory/people/${encodeURIComponent(name)}/einzelheiten${alle ? "?alle=1" : ""}`),
  uebernehmenVorschau: (conversationId: string, messageId: string) =>
    request<UebernehmenVorschau>(`/api/v1/antworten/uebernehmen?conversation_id=${encodeURIComponent(conversationId)}&message_id=${encodeURIComponent(messageId)}`),
  uebernehmenVorschlagen: (body: { conversation_id: string; message_id: string; saetze: number[]; sache: string | null; notiz: string }) =>
    request<{ sache: string; name: string; ergebnisse: UebernehmenErgebnis[] }>("/api/v1/antworten/uebernehmen", { method: "POST", body: JSON.stringify(body) }),
  /** Die Annahme eines Vorschlags über den vorhandenen Weg des Gedächtnisses; erst sie legt die Aussage an. */
  wissenAnnehmen: (id: string) =>
    request<{ id: string; statement: string }>(`/api/v1/memory/candidates/${encodeURIComponent(id)}/accept`, { method: "POST", body: JSON.stringify({ supersedes: [] }) }),
  wissenAblehnen: (id: string) =>
    request<{ id: string }>(`/api/v1/memory/candidates/${encodeURIComponent(id)}/reject`, { method: "POST" }),
  lintBefunde: (status: BefundStatus = "offen") => request<BefundListe>(`/api/v1/lint/befunde?status=${status}`),
  lintAnstossen: () =>
    request<{ lauf: { laeuft: boolean; befunde?: number; neu?: number }; zusammenfassung: BefundZusammenfassung }>("/api/v1/lint", { method: "POST" }),
  lintStatus: (id: string, status: BefundStatus, stand?: string) =>
    request<{ befund: Befund; zusammenfassung: BefundZusammenfassung }>(`/api/v1/lint/befunde/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ status, stand }) }),
  memoryQuestions: () => request<{items: MemoryQuestion[]; truncated: boolean}>("/api/v1/memory/questions"),
  resolveMemoryQuestion: (id: string, body: {stand: string; proposal_id: string | null}) => request<unknown>(`/api/v1/memory/questions/${encodeURIComponent(id)}/resolve`, {method: "POST", body: JSON.stringify(body)}),
  lintEntscheiden: (id: string, wahl: "alt" | "neu", stand?: string) =>
    request<{ befund: Befund; aussage: { id: string; statement: string } | null; zusammenfassung: BefundZusammenfassung }>(
      `/api/v1/lint/befunde/${encodeURIComponent(id)}/entscheiden`, { method: "POST", body: JSON.stringify({ wahl, stand }) }),
  rueckmeldungen: () => request<RueckmeldungenListe>("/api/v1/rueckmeldungen"),
  rueckmeldungMelden: (body: { conversation_id: string; message_id: string; art: RueckmeldungArt; richtig: string }) =>
    request<{ meldung: Rueckmeldung } & RueckmeldungZaehlung>("/api/v1/rueckmeldungen", { method: "POST", body: JSON.stringify(body) }),
  rueckmeldungErledigt: (id: string) =>
    request<{ meldung: Rueckmeldung } & RueckmeldungZaehlung>(`/api/v1/rueckmeldungen/${encodeURIComponent(id)}/erledigt`, { method: "PATCH" }),
  /** Die Fälle als Text der Datei (Fragenformat der Messlatte). Enthält Frage- und Antworttexte, nur zum Speichern auf diesem Rechner. */
  rueckmeldungFaelle: async () => {
    const response = await fetch("/api/v1/rueckmeldungen/faelle");
    if (!response.ok) throw new ApiError(response.status);
    return response.text();
  },
};
