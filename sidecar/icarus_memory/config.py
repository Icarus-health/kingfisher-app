"""Einstellungen, die einen Neustart überleben.

Bis hierher kam alles aus Umgebungsvariablen: Anbieter, Schlüssel, Mailserver,
freigegebene Ordner. Für eine Entwicklungsumgebung ist das richtig. Für eine App,
die jemand herunterlädt, ist es das Ende — niemand legt eine `.env` an, bevor er
ein Programm zum ersten Mal öffnet.

Deshalb zwei Ablagen mit klarer Trennung:

* **`einstellungen.json`** im Datenverzeichnis — alles, was kein Geheimnis ist:
  welcher Anbieter, welches Modell, welcher Mailserver, welche Ordner
  freigegeben sind.
* **Der Schlüsselbund** (`secrets.py`) — alles, was eines ist: API-Schlüssel,
  Mailpasswort, CalDAV-Passwort.

Die Trennung ist keine Förmlichkeit. Die Einstellungsdatei landet in Backups, in
Sicherungen des Datenverzeichnisses, womöglich in einem Cloud-Ordner. Ein
Schlüssel darin wäre genau der Klartext auf der Platte, den `secrets.py`
vermeiden soll.

## Vorrang

Umgebungsvariablen schlagen die Datei. Wer `ICARUS_PROVIDER=ollama` vor den
Start setzt, bekommt Ollama — auch wenn in der Datei etwas anderes steht. Das
ist der Weg, einen Testlauf zu fahren, ohne die Einstellungen des Nutzers
anzufassen, und es ist dieselbe Regel wie in `secrets.load_into_env()`.

## Warum kein Konto

Es gibt kein „Anmelden". Icarus kennt keinen Server, bei dem man sich anmelden
könnte, und das ist der Punkt des ganzen Projekts: Der Bestand liegt auf dem
Rechner der Person. Was beim Einrichten passiert, ist deshalb kein Login,
sondern die Frage, welchem Anbieter das Gespräch anvertraut wird — und die
Antwort darf „keinem" sein.
"""

from __future__ import annotations

import json
import os
import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .atomic import write_text_atomic
from .secrets import Keychain, KeychainError

DATEINAME = "einstellungen.json"

#: Schalter für die MCP-Tür in beide Richtungen (fremde Assistenten kommen
#: herein, Icarus dockt an fremde Server an). Eine Expertenfunktion: Vorgabe
#: ist AUS, und eingeschaltet wird sie bewusst vor dem Start, nicht in der
#: Oberfläche. Ein Klick, der einem Fremdprogramm Zugang gibt, wäre zu billig.
MCP_TUER_ENV = "KINGFISHER_MCP_TUER"

_MCP_TUER_AN = frozenset({"1", "true", "ja", "an", "on", "yes"})


def mcp_tuer_offen(environ: dict[str, str] | None = None) -> bool:
    """Ob die MCP-Tür eingeschaltet ist. Ohne ausdrückliches Ja: nein.

    Wird bei jedem Aufruf gelesen und nicht beim Import gemerkt, damit die
    Antwort immer zum Zustand des laufenden Prozesses passt.
    """
    environ = os.environ if environ is None else environ
    return environ.get(MCP_TUER_ENV, "").strip().lower() in _MCP_TUER_AN


MCP_TUER_ZU_TEXT = (
    "Die MCP-Anbindung ist ausgeschaltet; sie lässt sich mit "
    f"{MCP_TUER_ENV}=1 vor dem Start von Icarus einschalten."
)

#: Anbieter, die die Oberfläche anbieten darf. `""` heißt: kein Modell, und das
#: ist eine gültige Wahl — der Gedächtniskern läuft ohne.
PROVIDERS = ("", "openai", "anthropic", "ollama", "kompatibel")

#: Klartext für die Auswahl. „kompatibel“ ist der Schlüssel zu allem anderen:
#: OpenRouter, Groq, Together, DeepSeek, Mistral, LM Studio, llama.cpp, vLLM —
#: sie alle sprechen dieselbe Schnittstelle. Ein Eintrag statt zwanzig.
PROVIDER_LABELS = {
    "": "Kein Modell (Gedächtnis funktioniert trotzdem)",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "ollama": "Ollama (auf diesem Rechner)",
    "kompatibel": "Anderer Anbieter (OpenAI-kompatibel)",
}

#: Wofür der Anbieter eine eigene Adresse braucht. Bei den anderen steht sie
#: fest und wird nicht gefragt.
PROVIDER_BRAUCHT_ADRESSE = ("kompatibel",)

#: Bekannte Adressen als Starthilfe. Wer eine andere hat, trägt sie ein.
BEKANNTE_ADRESSEN = {
    "OpenRouter": "https://openrouter.ai/api/v1",
    "Groq": "https://api.groq.com/openai/v1",
    "Together": "https://api.together.xyz/v1",
    "DeepSeek": "https://api.deepseek.com/v1",
    "Mistral": "https://api.mistral.ai/v1",
    "LM Studio (lokal)": "http://localhost:1234/v1",
    "llama.cpp (lokal)": "http://localhost:8080/v1",
}

#: Voreingestellte Modelle je Anbieter. Nur Vorschläge; wer ein anderes will,
#: trägt es ein.
DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-sonnet-5",
    "ollama": "llama3.1",
    "kompatibel": "",
}

#: Welcher Schlüsselbund-Eintrag zu welchem Anbieter gehört.
PROVIDER_SECRET = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    # Derselbe Eintrag wie OpenAI: es ist dieselbe Schnittstelle, und zwei
    # Schlüssel für einen Anschluss wären eine Frage zu viel.
    "kompatibel": "OPENAI_API_KEY",
}

#: Geheimnisse, die über die Einrichtung gesetzt werden können. Der Wert ist
#: der Name im Schlüsselbund; die Einstellungsdatei sieht keinen davon.
SECRET_FIELDS = {
    "api_key": None,          # hängt vom gewählten Anbieter ab
    "mail_password": "ICARUS_MAIL_PASSWORD",
    "calendar_password": "ICARUS_CALDAV_PASSWORD",
}


@dataclass
class MailSettings:
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    user: str = ""
    sender: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.imap_host and self.user)


@dataclass
class CalendarSettings:
    url: str = ""
    user: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url)


@dataclass
class MailAccountSettings:
    """Ein einzeln benanntes, lesendes Mailkonto.

    Das Kennzeichen wird ausschließlich lokal erzeugt. Es ist weder eine
    Adresse noch ein Servername und kann deshalb gefahrlos als Schlüssel für
    den zugehörigen Schlüsselbund-Eintrag dienen.
    """

    id: str = ""
    label: str = ""
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    user: str = ""
    sender: str = ""
    auth_method: str = "password"
    enabled: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.id and self.imap_host and self.user and self.enabled)


@dataclass
class CalendarSourceSettings:
    """Ein Kalenderzugang oder ein schreibgeschütztes iCalendar-Abo."""

    id: str = ""
    label: str = ""
    kind: str = "caldav"
    url: str = ""
    user: str = ""
    enabled: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.id and self.url and self.enabled)


#: Wie oft der Zeitplan läuft, wenn niemand etwas gewählt hat (Fremdprobe 3, Befund 13). Vorher alle vier Stunden: Eine
#: Bitte, die um neun kam, stand erst am Nachmittag im Gedächtnis. Mit 30 Minuten stimmt das Briefing am selben Vormittag.
VORGABE_ABSTAND_MINUTEN = 30
#: Die frühere Vorgabe. Wer sie nie selbst gewählt hat (`interval_gewaehlt` fehlt), bekommt beim Laden die neue.
FRUEHERE_VORGABE_MINUTEN = 240


@dataclass
class ScheduleSettings:
    """Der mitlaufende Prozess.

    Standardmäßig aus, und die Modellnutzung darin noch einmal getrennt: Ein
    Zeitplan, der ungefragt einen Anbieter ruft, gibt fremdes Geld aus.
    """

    enabled: bool = False
    interval_minutes: int = VORGABE_ABSTAND_MINUTEN
    interval_gewaehlt: bool = False
    """Hat der Mensch den Abstand selbst gewählt? Dann bleibt er, auch wenn sich die Vorgabe ändert."""
    with_model: bool = False
    # Modellgestützte Hintergrundläufe bleiben auf lokale Anbieter begrenzt.
    # Bestehende Konfigurationen behalten ihr bisheriges Verhalten.
    local_model_only: bool = False

    mail_accounts: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)
    """Ordner, die erneut eingelesen werden — Pfad auf Adapternamen.

    Dass ein zweiter Lauf nichts doppelt anlegt, steckt im Digest der
    Episodenschicht. Ohne diese Zusicherung wäre wiederholtes Einlesen keine
    Option.
    """

    backup: bool = True
    """Snapshot bei jedem Lauf. Der billigste Schritt mit dem größten Nutzen."""


@dataclass
class Settings:
    provider: str = ""
    model: str = ""
    endpoint: str = ""
    """Eigene Adresse des Anbieters. Für Ollama oder einen Proxy."""

    file_roots: list[str] = field(default_factory=list)
    """Ordner, aus denen gelesen werden darf.

    Leer heißt: gar kein Dateizugriff. Es gibt bewusst keinen Vorgabewert wie
    das Home-Verzeichnis — das wäre die Bequemlichkeit, die den Schutz aufhebt.
    Auch der Einrichtungsassistent schlägt keinen vor.
    """

    mail: MailSettings = field(default_factory=MailSettings)
    calendar: CalendarSettings = field(default_factory=CalendarSettings)
    mail_accounts: list[MailAccountSettings] = field(default_factory=list)
    calendar_sources: list[CalendarSourceSettings] = field(default_factory=list)
    schedule: ScheduleSettings = field(default_factory=ScheduleSettings)

    mcp_server: list[dict[str, Any]] = field(default_factory=list)
    """Fremde MCP-Server, an die Icarus andockt.

    Je Eintrag ein Name, ein Befehl und optional Umgebungsvariablen — die Form
    von `mcp_client.Serverangabe`. Hier als schlichte Wörterbücher, damit die
    Einstellungsdatei kein Modul importieren muss, um lesbar zu sein.

    Leer ist der Normalfall und bleibt es: Ein angedockter Server startet ein
    fremdes Programm auf diesem Rechner. Das darf nie voreingestellt sein.
    """

    folder_sync: dict[str, Any] = field(default_factory=dict)
    transcript_sync: dict[str, Any] = field(default_factory=dict)
    """Der Eingangsordner für Mitschriften aus Meetings; gleiche Form wie `folder_sync`."""
    mail_filter: dict[str, Any] = field(default_factory=dict)
    mail_sync_status: dict[str, Any] = field(default_factory=dict)

    routing_enabled: bool = False
    routing_profiles: list[dict[str, Any]] = field(default_factory=list)
    model_roles: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Modell je Rolle (`frage`, `antwort`, `pruefung`, `hintergrund`, `einbettung`).

    Form und Regeln: `model_roles.py`. Leer heißt: ein Modell für alles, wie
    bisher. Cloud steht nur mit dem Einwilligungszeitstempel der Rolle darin.
    """
    antwort_saetze: str = "an"
    """Formuliert das Modell der Rolle `antwort` belegte Sätze (zweiter Modellaufruf)? `an` (Vorgabe) oder `aus`.

    Bei `aus` bleibt der Zitatmodus: ein Modellaufruf weniger, die Antwort zeigt die Belege wörtlich.
    Der Nutzer entscheidet das nach der Messung der Antwortzeit (`zeitmessung.py`).
    """
    satzpruefung_modell: str = "an"
    """Zweites Tor: prüft ein Modell der Rolle `pruefung` jeden Satz noch einmal gegen seine Belege? `an` (Vorgabe) oder `aus`.

    Wirkt nur, wenn der Rolle ein lokales Modell zugewiesen ist; sonst ist das Tor still aus
    (`satzpruefung_modell.py`), und die Modellkarte sagt es.
    """
    world_sources: list[dict[str, Any]] = field(default_factory=list)

    wegezeit: dict[str, Any] = field(default_factory=dict)
    """„Fahrzeiten berechnen“: Einwilligung (`aktiv`, Vorgabe aus), Heimatadresse, Verkehrsmittel, Dienst.

    Form und Regeln: `wegezeit.Einstellung`. Nur zwei Adressen verlassen den Rechner, und nur bei `aktiv`.
    Der Schlüssel eines Kartendienstes steht nie hier, sondern im Schlüsselbund.
    """

    wetter: dict[str, Any] = field(default_factory=dict)
    """„Wetter im Briefing“: Einwilligung (`aktiv`, Vorgabe aus) und der gewählte Ort mit Koordinaten.

    Form und Regeln: `wetter.Einstellung`. Nur der Ortsname und zwei gerundete Zahlen verlassen den Rechner.
    Ist nichts gespeichert, gilt die Vorbelegung aus den Umgebungsvariablen `KINGFISHER_WEATHER_*`.
    """
    welt: dict[str, Any] = field(default_factory=dict)
    """„Meldung aus der Welt im Briefing“: Schalter (Vorgabe aus), Feeds, gewählte Quellen, Abbestelltes.

    Form und Regeln: `welt_meldungen.Welt`. Gespeichert wird höchstens die gewählte Meldung des Tages.
    """

    einrichtung: dict[str, Any] = field(default_factory=dict)
    """Stand des Erststart-Assistenten: Name für den Gruß, je Schritt „erledigt“ oder „übersprungen“, Abschluss.

    Form und Regeln: `einrichtung_routes.py`. Steht hier und nicht nur im Browser, damit der Assistent nach
    einem Neustart, einem anderen Browser oder dem Mac-Fenster dort weitermacht, wo man aufgehört hat.
    """

    suchindex: dict[str, Any] = field(default_factory=dict)
    """Suchindex über die Rohquellen: `wortteile_jahre` (0 = alle Quellen mit Wortteilen, Vorgabe).

    Ältere Quellen stehen dann nur im kleineren Wortindex. Form und Regeln: `suchindex_routes.py`, `source_index.py`.
    """

    akten_export: dict[str, Any] = field(default_factory=dict)
    """„Akten als Ordner“: Schalter (Vorgabe aus), „Quellen mitschreiben“ (Vorgabe aus), der gewählte Ordner
    (`ordner`, Vorgabe keiner), Stand des letzten Schreibens und der letzten Übergabe an den Mac-Helfer.

    Form und Regeln: `akten_export_routes.py`. Der Ordner enthält Klartext und ist nur zum Lesen gedacht;
    nichts daraus fließt je zurück.
    """

    onboarded: bool = False
    """Hat jemand die Einrichtung einmal bis zum Ende durchlaufen?

    Nicht „ist alles eingerichtet": Man darf jeden Schritt überspringen. Das
    Kennzeichen sagt nur, dass die App nicht mehr beim Start in den Assistenten
    springen soll.
    """

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        """Liest Einstellungen und überliest Unbekanntes.

        Eine Datei aus einer neueren Version darf eine ältere nicht zum
        Absturz bringen — sie hat vielleicht Felder, die es hier noch nicht
        gibt. Weglassen ist richtiger als scheitern.
        """
        mail = data.get("mail") or {}
        calendar = data.get("calendar") or {}
        schedule = data.get("schedule") or {}
        mail_accounts = data.get("mail_accounts") or []
        calendar_sources = data.get("calendar_sources") or []
        return cls(
            provider=str(data.get("provider", "") or ""),
            model=str(data.get("model", "") or ""),
            endpoint=str(data.get("endpoint", "") or ""),
            file_roots=[str(p) for p in data.get("file_roots", []) if str(p).strip()],
            mcp_server=[
                d for d in (data.get("mcp_server") or [])
                if isinstance(d, dict) and str(d.get("name", "")).strip()
            ],
            mail=MailSettings(
                imap_host=str(mail.get("imap_host", "") or ""),
                imap_port=int(mail.get("imap_port") or 993),
                smtp_host=str(mail.get("smtp_host", "") or ""),
                smtp_port=int(mail.get("smtp_port") or 587),
                user=str(mail.get("user", "") or ""),
                sender=str(mail.get("sender", "") or ""),
            ),
            calendar=CalendarSettings(
                url=str(calendar.get("url", "") or ""),
                user=str(calendar.get("user", "") or ""),
            ),
            mail_accounts=[
                MailAccountSettings(
                    id=str(item.get("id", "") or ""),
                    label=str(item.get("label", "") or ""),
                    imap_host=str(item.get("imap_host", "") or ""),
                    imap_port=int(item.get("imap_port") or 993),
                    smtp_host=str(item.get("smtp_host", "") or ""),
                    smtp_port=int(item.get("smtp_port") or 587),
                    user=str(item.get("user", "") or ""),
                    sender=str(item.get("sender", "") or ""),
                    auth_method=str(item.get("auth_method", "password")),
                    enabled=bool(item.get("enabled", True)),
                )
                for item in mail_accounts
                if isinstance(item, dict) and str(item.get("id", "") or "").strip()
            ],
            calendar_sources=[
                CalendarSourceSettings(
                    id=str(item.get("id", "") or ""),
                    label=str(item.get("label", "") or ""),
                    kind=str(item.get("kind", "caldav") or "caldav"),
                    url=str(item.get("url", "") or ""),
                    user=str(item.get("user", "") or ""),
                    enabled=bool(item.get("enabled", True)),
                )
                for item in calendar_sources
                if isinstance(item, dict)
                and str(item.get("id", "") or "").strip()
                and str(item.get("kind", "caldav") or "caldav") in {"caldav", "ical", "google", "microsoft"}
            ],
            schedule=ScheduleSettings(
                enabled=bool(schedule.get("enabled", False)),
                interval_minutes=_abstand(schedule),
                interval_gewaehlt=bool(schedule.get("interval_gewaehlt", False)),
                with_model=bool(schedule.get("with_model", False)),
                local_model_only=bool(schedule.get("local_model_only", False)),
                mail_accounts=[str(item) for item in schedule.get("mail_accounts", []) if isinstance(item, str)],
                sources={str(k): str(v) for k, v in (schedule.get("sources") or {}).items()},
                backup=bool(schedule.get("backup", True)),
            ),
            folder_sync=dict(data.get("folder_sync") or {}),
            transcript_sync=dict(data.get("transcript_sync") or {}),
            mail_filter=dict(data.get("mail_filter") or {}),
            mail_sync_status=dict(data.get("mail_sync_status") or {}),
            routing_enabled=bool(data.get("routing_enabled", False)),
            routing_profiles=[dict(x) for x in data.get("routing_profiles", []) if isinstance(x, dict)],
            model_roles={str(k): dict(v) for k, v in (data.get("model_roles") or {}).items()
                         if isinstance(v, dict)} if isinstance(data.get("model_roles"), dict) else {},
            antwort_saetze="aus" if data.get("antwort_saetze") == "aus" else "an",
            satzpruefung_modell="aus" if data.get("satzpruefung_modell") == "aus" else "an",
            world_sources=[dict(x) for x in data.get("world_sources", []) if isinstance(x, dict)],
            wegezeit=dict(data.get("wegezeit") or {}) if isinstance(data.get("wegezeit"), dict) else {},
            wetter=dict(data.get("wetter") or {}) if isinstance(data.get("wetter"), dict) else {},
            welt=dict(data.get("welt") or {}) if isinstance(data.get("welt"), dict) else {},
            einrichtung=dict(data.get("einrichtung") or {}) if isinstance(data.get("einrichtung"), dict) else {},
            suchindex=dict(data.get("suchindex") or {}) if isinstance(data.get("suchindex"), dict) else {},
            akten_export=dict(data.get("akten_export") or {}) if isinstance(data.get("akten_export"), dict) else {},
            onboarded=bool(data.get("onboarded", False)),
        )


def path_for(data_dir: Path) -> Path:
    return Path(data_dir) / DATEINAME


def load(data_dir: Path) -> Settings:
    """Liest die Einstellungen. Eine kaputte Datei blockiert den Start nicht.

    Wenn hier eine Ausnahme hochginge, käme ein Nutzer mit beschädigter Datei
    nie wieder in seine App — und damit auch nicht an seinen Bestand. Ein leeres
    Formular ist reparierbar, ein Programm, das nicht startet, nicht.
    """
    target = path_for(data_dir)
    try:
        return Settings.from_dict(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return Settings()


def _abstand(schedule: dict[str, Any]) -> int:
    """Der gespeicherte Abstand; die frühere Vorgabe nur dann, wenn ihn jemand ausdrücklich gewählt hat.

    Ältere Dateien kennen `interval_gewaehlt` nicht und tragen die frühere Vorgabe, weil jedes Speichern den ganzen
    Zeitplan schreibt. Ein anderer Wert als die frühere Vorgabe war immer eine Wahl und bleibt.
    """
    wert = int(schedule.get("interval_minutes") or VORGABE_ABSTAND_MINUTEN)
    if wert == FRUEHERE_VORGABE_MINUTEN and not schedule.get("interval_gewaehlt", False):
        return VORGABE_ABSTAND_MINUTEN
    return wert


def save(data_dir: Path, settings: Settings) -> Path:
    """Schreibt die Einstellungen mit 0600.

    Keine Geheimnisse darin, aber Mailadressen und Serveradressen sind auch
    nichts, was andere Konten auf dem Rechner lesen müssen.
    """
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = path_for(directory)
    # Atomar: ein Absturz mitten im Schreiben darf Konten und Zeitplan nicht
    # zerstören. Die Rechte 0600 hat schon die Temporärdatei.
    write_text_atomic(
        target,
        json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
    )
    return target


def apply_to_env(settings: Settings, environ: dict[str, str] | None = None) -> list[str]:
    """Überträgt die Einstellungen in die Umgebung, aus der alles andere liest.

    So bleibt der bestehende Aufbau unangetastet: `providers.from_env()`,
    `MailConfig.from_env()` und `file_roots_from_env()` wissen nichts von dieser
    Datei und müssen es auch nicht.

    **Gesetzte Umgebungsvariablen gewinnen.** Wer `ICARUS_PROVIDER=ollama` vor
    den Start setzt, bekommt Ollama, egal was in der Datei steht — der Weg, einen
    Testlauf zu fahren, ohne die Einstellungen des Nutzers anzufassen.
    """
    environ = os.environ if environ is None else environ
    gesetzt: list[str] = []

    def put(name: str, value: str | None) -> None:
        if not value or environ.get(name):
            return
        environ[name] = str(value)
        gesetzt.append(name)

    put("ICARUS_PROVIDER", settings.provider)
    put("ICARUS_MODEL", settings.model)
    put("ICARUS_BASE_URL", settings.endpoint)
    put("ICARUS_FILE_ROOTS", ":".join(settings.file_roots))

    put("ICARUS_IMAP_HOST", settings.mail.imap_host)
    put("ICARUS_IMAP_PORT", str(settings.mail.imap_port) if settings.mail.imap_host else "")
    put("ICARUS_SMTP_HOST", settings.mail.smtp_host)
    put("ICARUS_SMTP_PORT", str(settings.mail.smtp_port) if settings.mail.smtp_host else "")
    put("ICARUS_MAIL_USER", settings.mail.user)
    put("ICARUS_MAIL_FROM", settings.mail.sender or settings.mail.user)

    put("ICARUS_CALDAV_URL", settings.calendar.url)
    put("ICARUS_CALDAV_USER", settings.calendar.user or settings.mail.user)
    return gesetzt


def secret_name_for_provider(provider: str) -> str | None:
    """Unter welchem Namen der Schlüssel dieses Anbieters liegt.

    Ollama braucht keinen; deshalb ist `None` eine gültige Antwort und kein
    Fehler.
    """
    return PROVIDER_SECRET.get(provider)


def integration_secret_name(kind: str, integration_id: str) -> str:
    """Liefert einen stabilen, nicht rückrechenbaren Schlüsselbund-Namen.

    Mailadressen und CalDAV-Adressen gehören nicht in Prozessumgebungen oder
    Schlüsselbund-Kontobezeichnungen. Das Kennzeichen wird daher gehasht;
    der Klartext verbleibt in der lokalen Einstellungsdatei mit Modus 0600.
    """
    if kind not in {"mail", "calendar"} or not integration_id:
        raise ValueError("Ungültige Integrationskennung.")
    digest = hashlib.sha256(integration_id.encode("utf-8")).hexdigest()[:24]
    return f"ICARUS_{kind.upper()}_PASSWORD_{digest}"


def store_secret(keychain: Keychain, name: str, value: str) -> None:
    """Legt ein Geheimnis ab — im Schlüsselbund, sonst nur in der Umgebung.

    Ohne Schlüsselspeicher (Linux ohne `secret-tool`, manche Serverumgebungen)
    wäre die Alternative, den Schlüssel in die Einstellungsdatei zu schreiben.
    Das wird hier ausdrücklich **nicht** getan: Er gilt dann nur für die
    laufende Sitzung, und die Oberfläche sagt das. Lieber unbequem als
    Klartext auf der Platte.
    """
    os.environ[name] = value
    if keychain.available:
        keychain.set(name, value)


def clear_secret(keychain: Keychain, name: str) -> None:
    os.environ.pop(name, None)
    if keychain.available:
        try:
            keychain.delete(name)
        except KeychainError:
            pass


def secret_status(keychain: Keychain) -> dict[str, bool]:
    """Welche Geheimnisse hinterlegt sind — nur ob, nie welche.

    Die Oberfläche soll „hinterlegt" anzeigen können, ohne dass ein Schlüssel je
    wieder über die Schnittstelle zurückkommt. Ein Feld, das den Wert
    zurückliefert, wäre der bequemste Weg, ihn irgendwann zu protokollieren.
    """
    status: dict[str, bool] = {}
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                 "ICARUS_MAIL_PASSWORD", "ICARUS_CALDAV_PASSWORD",
                 "ICARUS_ORS_KEY", "ICARUS_GOOGLE_ROUTES_KEY"):
        status[name] = bool(
            os.environ.get(name) or (keychain.available and keychain.get(name))
        )
    return status


__all__ = [
    "DATEINAME",
    "BEKANNTE_ADRESSEN",
    "DEFAULT_MODELS",
    "PROVIDERS",
    "PROVIDER_BRAUCHT_ADRESSE",
    "PROVIDER_LABELS",
    "PROVIDER_SECRET",
    "CalendarSettings",
    "CalendarSourceSettings",
    "MailAccountSettings",
    "MailSettings",
    "ScheduleSettings",
    "Settings",
    "apply_to_env",
    "clear_secret",
    "load",
    "integration_secret_name",
    "path_for",
    "save",
    "secret_name_for_provider",
    "secret_status",
    "store_secret",
]
