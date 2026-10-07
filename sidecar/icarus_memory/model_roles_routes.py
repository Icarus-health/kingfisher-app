"""Routen für „Lokale KI“: Empfehlung je Rolle, Modell je Rolle, Einrichten mit einem Klick.

* `GET  /api/v1/models/recommendation`  Gerät, Empfehlung je Rolle, Status
* `GET  /api/v1/models/stand`           die eine Aussage zur lokalen KI (`lokale_ki.py`)
* `GET  /api/v1/models/roles`           gewählte Modelle und Cloud-Einwilligungen
* `PUT  /api/v1/models/roles/{rolle}`   Modell wählen, Cloud mit Einwilligung zuschalten
* `PUT  /api/v1/models/saetze`           Sätze an oder aus (Vorgabe an; aus = Zitatmodus)
* `PUT  /api/v1/models/satzpruefung`     zweites Tor an oder aus (Vorgabe an; wirkt nur mit Modell der Rolle `pruefung`)
* `GET  /api/v1/antwortzeiten`           Protokoll der Antwortzeiten (`zeiten_routes.py`)
* `POST /api/v1/models/pull`            empfohlenes Modell laden und prüfen (nur bestätigt)
* `GET  /api/v1/models/pull[/{id}]`     Fortschritt
* `POST /api/v1/models/laden`           alle offenen Aufgaben nacheinander im Hintergrund laden (nur bestätigt)
* `GET  /api/v1/models/laden`           wie weit das ist, in Prozent nach Größe, und was am Ende fehlt

Regeln: Es wird nur geladen, was der Katalog für dieses Gerät empfiehlt, und nur
nach ausdrücklicher Bestätigung. Cloud braucht die Einwilligung je Rolle
(`model_roles.py`). Nichts davon sendet Inhalte des Nutzers.
"""
from __future__ import annotations

import re
import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from . import config, logbuch
from . import device_profile
from .agent_verdrahtung import satzpruefung_stand
from .model_pull import Fehlergrund, Fehlschlag, PullBelegt, PullManager, bestaetigungssatz
from .model_recommendation import (
    KATALOG_STAND, ROLLEN as ROLLEN_NAMEN, STUFEN, Empfehlung, Geraet, KatalogEintrag, ausweichwahl, empfehle_alle,
    festplatte_reicht, gb_text, geraet_aus_profil, kleinere_wahl, normalisiere, orchester_bedarf, orchester_hinweise,
    stufe_fuer,
)
from .model_roles import (
    CLOUD_ANBIETER, OLLAMA_CLOUD, OLLAMA_CLOUD_SATZ, ROLLEN, RollenWahl, einwilligung_gueltig, lese_wahlen,
    lokaler_endpunkt, ollama_wurzel, rollen_von,
)
from .ollama_inventar import CLOUD, HINWEIS_CLOUD, LOKAL, inventar_von
from .providers import OpenAICompatible

_MODELLNAME = re.compile(r"[A-Za-z0-9._:/-]{1,128}")
_ANBIETER_LABEL = {"anthropic": "Anthropic", "openai": "OpenAI", "mistral": "Mistral (EU-Endpunkt)", "openrouter": "OpenRouter (EU-Endpunkt)"}


class RolleIn(BaseModel):
    modell: str | None = None
    cloud: bool | None = None
    anbieter: str | None = None
    einwilligung: bool | None = None  # ausdrückliche Bestätigung des Satzes zur Rolle


class SaetzeIn(BaseModel):
    saetze: Literal["an", "aus"]


class SatzpruefungIn(BaseModel):
    satzpruefung: Literal["an", "aus"]


class LadenIn(BaseModel):
    bestaetigt: bool = False


class PullIn(BaseModel):
    rolle: str
    modell: str | None = None  # nur ein Modell aus Vorauswahl oder Alternativen dieser Rolle
    bestaetigt: bool = False


def _eintrag_dict(e: KatalogEintrag, passt: bool) -> dict[str, Any]:
    return {"name": e.name, "groesse_gb": e.groesse_gb, "speicher_gb": e.speicher_gb, "art": e.art,
            "begruendung": e.begruendung, "passt": passt, "bestaetigung": bestaetigungssatz(e.name, e.groesse_gb)}


def register(app, guard, data_dir, rebuild):
    """`rebuild()` baut den Agenten neu (Modelle wirken erst danach)."""

    def standard():
        return rollen_von(app).standard()

    def endpunkt() -> str:
        return lokaler_endpunkt(standard())

    def ollama_client(timeout: float = 4.0) -> httpx.Client:
        # `ollama_transport` ist nur für Tests gesetzt; im Betrieb spricht das direkt mit dem lokalen Ollama.
        return httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False,
                            transport=getattr(app.state, "ollama_transport", None))

    def inventar() -> dict[str, str] | None:
        """Installierte Modelle mit ihrer Art (lokal oder Cloud über Ollama); None, wenn Ollama nicht antwortet."""
        return inventar_von(app).installiert(ollama_wurzel(endpunkt()))

    def installierte() -> list[str] | None:
        """Namen der belegt lokalen Modelle. Cloud über Ollama gehört nicht in die lokale Vorauswahl."""
        gefunden = inventar()
        return None if gefunden is None else sorted(n for n, art in gefunden.items() if art == LOKAL)

    def cloud_installierte() -> list[str]:
        return sorted(n for n, art in (inventar() or {}).items() if art == CLOUD)

    def ausstattung() -> tuple[Geraet, str]:
        """Das Gerät und woher die Angabe stammt: `bericht` (Helfer), `eigene` (Sidecar), `untergrenze` (Sidecar im
        Container: der Rechner hat mindestens so viel) oder `unbekannt`. Gefragt wird der Mensch nie (Befund 10)."""
        g = geraet_aus_profil(device_profile.load_device_profile(data_dir()))
        quelle = 'bericht' if g.bekannt else 'unbekannt'
        if not g.bekannt:
            eigen = device_profile.eigene_ausstattung()
            if eigen is not None:
                g = replace(g, arbeitsspeicher_gb=float(eigen['memory_gb']),
                            plattform=eigen['platform'] if eigen['platform'] in {'macos', 'windows', 'linux'} else g.plattform)
                quelle = 'untergrenze' if eigen.get('untergrenze') else 'eigene'
        if g.festplatte_frei_gb is None:  # der Helfer auf dem Rechner hat es nicht gemeldet: dort messen, wo es etwas besagt
            g = replace(g, festplatte_frei_gb=device_profile.freier_platz_gb())
        return g, quelle

    def geraet() -> Geraet:
        return ausstattung()[0]

    def blockiert_satz(cloud_moeglich: bool, modell: str | None) -> str | None:
        """Warum ein gewähltes Modell nicht genutzt wird: es läuft in Ollamas Cloud, und dafür fehlt die Einwilligung."""
        if not modell:
            return None
        if cloud_moeglich:
            return f"{modell} {HINWEIS_CLOUD} Es wird ohne deine Einwilligung nicht genutzt."
        return (f"{modell} {HINWEIS_CLOUD} Diese Aufgabe liest alle deine Quellen und bleibt auf diesem Rechner; "
                "sie ruht, bis ein lokales Modell gewählt ist.")

    # -- Zustand je Rolle -------------------------------------------------------------------
    def rollen_zustand() -> list[dict[str, Any]]:
        rollen = rollen_von(app)
        zeilen = []
        for name, spec in ROLLEN.items():
            wahl = rollen.wahlen.get(name, RollenWahl())
            provider = rollen.provider(name) if name != "einbettung" else None
            im_weg = rollen.cloud_modell_im_weg(name)
            if name == "einbettung":
                wirksam = {"modell": rollen.einbettung_modell(), "lokal": True,
                           "quelle": "eigene_wahl" if wahl.modell and not im_weg else "standard"}
            elif provider is None:
                wirksam = {"modell": None, "lokal": None, "quelle": "keins"}
            else:
                cloud = wahl.cloud and einwilligung_gueltig(name, wahl) and not getattr(provider, "is_local", False)
                wirksam = {"modell": getattr(provider, "model", None), "lokal": bool(getattr(provider, "is_local", False)),
                           "quelle": "cloud" if cloud else "eigene_wahl" if wahl.modell else "standard",
                           "cloud_ueber_ollama": bool(getattr(provider, "ueber_ollama_cloud", False))}
            zeilen.append({
                "rolle": name, "titel": spec.titel, "beschreibung": spec.beschreibung,
                "cloud_moeglich": spec.cloud_moeglich, "cloud_satz": spec.cloud_satz,
                "wahl": {**wahl.als_dict(), "einwilligung_gueltig": einwilligung_gueltig(name, wahl)},
                "wirksam": wirksam,
                "blockiert": blockiert_satz(spec.cloud_moeglich, im_weg),
            })
        return zeilen

    def _schluessel_da(anbieter: str) -> bool:
        import os
        name = CLOUD_ANBIETER[anbieter][0]
        return bool(os.environ.get(name) or (anbieter == "openai" and os.environ.get("LLM_API_KEY")))

    def anbieter_liste() -> list[dict[str, Any]]:
        return [{"id": k, "label": _ANBIETER_LABEL[k], "schluessel_da": _schluessel_da(k),
                 "standardmodell": app.state.settings.cloud_models.get(k, v[1])} for k, v in CLOUD_ANBIETER.items() if k != OLLAMA_CLOUD]

    def saetze_stand() -> str:
        return "aus" if getattr(app.state.settings, "antwort_saetze", "an") == "aus" else "an"

    @app.get("/api/v1/models/stand", dependencies=guard)
    def get_stand():
        """Die eine Aussage zur lokalen KI samt den Modellen, die Ollama hat (`lokale_ki.py`)."""
        from .lokale_ki import stand
        return stand(app)

    @app.get("/api/v1/models/roles", dependencies=guard)
    def get_roles():
        return {"rollen": rollen_zustand(), "anbieter": anbieter_liste(), "saetze": saetze_stand(),
                "satzpruefung": satzpruefung_stand(app),
                "ollama_cloud": {"modelle": cloud_installierte(), "hinweis": OLLAMA_CLOUD_SATZ}}

    @app.put("/api/v1/models/saetze", dependencies=guard)
    def put_saetze(body: SaetzeIn):
        """Sätze an oder aus (zweiter Modellaufruf der Antwort); wirkt nach dem Neubau des Agenten, ohne Rückfrage."""
        settings = app.state.settings
        with app.state.conversation_lock:
            settings.antwort_saetze = body.saetze
            config.save(data_dir(), settings)
        rebuild()
        return {"saetze": saetze_stand()}

    @app.put("/api/v1/models/satzpruefung", dependencies=guard)
    def put_satzpruefung(body: SatzpruefungIn):
        """Zweites Tor an oder aus. Wirkt ab der nächsten Frage (je Antwort frisch gelesen), ohne Rückfrage."""
        settings = app.state.settings
        with app.state.conversation_lock:
            settings.satzpruefung_modell = body.satzpruefung
            config.save(data_dir(), settings)
        return satzpruefung_stand(app)

    @app.put("/api/v1/models/roles/{rolle}", dependencies=guard)
    def put_role(rolle: str, body: RolleIn):
        spec = ROLLEN.get(rolle)
        if spec is None:
            raise HTTPException(404, "Unbekannte Aufgabe.")
        settings = app.state.settings
        aktuell = lese_wahlen(settings.model_roles).get(rolle, RollenWahl())
        modell = aktuell.modell if body.modell is None else body.modell.strip()
        if modell and not _MODELLNAME.fullmatch(modell):
            raise HTTPException(422, "Der Modellname enthält nicht unterstützte Zeichen.")
        cloud = aktuell.cloud if body.cloud is None else body.cloud
        anbieter, einwilligung = aktuell.anbieter, aktuell.cloud_einwilligung
        art = inventar_von(app).art(modell, ollama_wurzel(endpunkt())) if modell else None
        ueber_ollama = (body.modell is not None and art == CLOUD) or (body.anbieter == OLLAMA_CLOUD and bool(cloud))
        if ueber_ollama:
            # Ein Modell, das Ollama an seinen Server weiterreicht, ist Cloud, auch wenn es „bei Ollama liegt“.
            if art != CLOUD:
                raise HTTPException(422, "Bitte ein Modell wählen, das in Ollamas Cloud läuft.")
            if not spec.cloud_moeglich:
                raise HTTPException(422, f"{modell} {HINWEIS_CLOUD} {spec.cloud_satz} Bitte ein lokales Modell wählen.")
            cloud, body.anbieter = True, OLLAMA_CLOUD
        if cloud:
            if not spec.cloud_moeglich:
                raise HTTPException(422, spec.cloud_satz)
            anbieter = body.anbieter if body.anbieter is not None else anbieter
            if anbieter not in CLOUD_ANBIETER:
                raise HTTPException(422, "Bitte einen Cloudanbieter wählen.")
            wechsel = not (aktuell.cloud and aktuell.anbieter == anbieter and einwilligung_gueltig(rolle, aktuell))
            if wechsel:
                # Ohne ausdrückliches Ja kein Zeitstempel, also keine Cloud.
                if body.einwilligung is not True:
                    satz = spec.cloud_satz + (" " + OLLAMA_CLOUD_SATZ if anbieter == OLLAMA_CLOUD else "")
                    raise HTTPException(422, "Für die Cloud ist deine ausdrückliche Einwilligung nötig: " + satz)
                einwilligung = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if body.cloud is True and body.modell is None and not aktuell.cloud:
                modell = ""  # ein lokaler Modellname passt nicht zum Cloudanbieter
            if anbieter in {'mistral', 'openrouter'}:
                modell = body.modell if body.modell is not None else settings.cloud_models.get(anbieter, '')
                if not modell or not _MODELLNAME.fullmatch(modell):
                    raise HTTPException(422, 'Bitte unter KI & Modelle zuerst einen Modellnamen hinterlegen.')
                if not _schluessel_da(anbieter):
                    raise HTTPException(422, 'Bitte unter KI & Modelle zuerst einen API-Schlüssel hinterlegen.')
        else:
            anbieter, einwilligung = "", ""  # Cloud aus: Einwilligung erlischt
            if aktuell.cloud and body.modell is None:
                modell = ""
        neu = RollenWahl(modell=modell, cloud=bool(cloud), anbieter=anbieter, cloud_einwilligung=einwilligung,
                        local_only=not bool(cloud) and (aktuell.local_only or aktuell.anbieter in {'mistral', 'openrouter'}))
        with app.state.conversation_lock:
            if neu.ist_leer:
                settings.model_roles.pop(rolle, None)
            else:
                settings.model_roles[rolle] = neu.als_dict()
            config.save(data_dir(), settings)
        rebuild()
        if neu != aktuell:
            logbuch.vermerke("modellwechsel", rolle=rolle, wofuer=spec.titel, lokal=not neu.cloud, modell=neu.modell)
        return get_roles()

    # -- Empfehlung -------------------------------------------------------------------------
    def status_der_rolle(rec: Empfehlung, zeile: dict[str, Any], installiert: list[str] | None) -> str:
        wirksam = zeile["wirksam"]
        norm = {normalisiere(n) for n in (installiert or [])}
        ziel = normalisiere(rec.modell.name)
        # Die Standardeinbettung (bge-m3) ist nur ein Vorgabename, kein Beleg: Ohne Antwort von
        # Ollama lässt sich nicht sagen, ob sie da ist.
        nur_vorgabe = zeile["rolle"] == "einbettung" and wirksam["quelle"] == "standard"
        if wirksam["modell"] and wirksam["lokal"] and normalisiere(wirksam["modell"]) == ziel \
                and (ziel in norm if installiert is not None or nur_vorgabe else True):
            return "eingerichtet"
        return "installiert" if ziel in norm else "fehlt"

    @app.get("/api/v1/models/recommendation", dependencies=guard)
    def recommendation():
        g, quelle = ausstattung()
        inventar_von(app).vergiss()  # die Karte zeigt den Stand jetzt, nicht den von vor 30 Sekunden
        installiert = installierte()
        zustand = {z["rolle"]: z for z in rollen_zustand()}
        zeilen = []
        alle = empfehle_alle(g)  # tagsüber und nachts zusammen passend, nicht nur je Rolle
        da = installiert or []
        orchester = {**orchester_bedarf(alle, g, da),
                     "hinweise": orchester_hinweise(alle, g, {n: s.titel for n, s in ROLLEN.items()}, da)}
        nutzbar = orchester["nutzbar_gb"]
        for name in ROLLEN_NAMEN:
            rec = alle[name]
            z = zustand[name]
            zeilen.append({
                "rolle": name, "titel": z["titel"], "beschreibung": z["beschreibung"],
                "empfohlen": _eintrag_dict(rec.modell, rec.passt_vermutlich),
                "alternativen": [_eintrag_dict(a, nutzbar is None or a.speicher_gb <= nutzbar) for a in rec.alternativen],
                "status": status_der_rolle(rec, z, installiert),
                # Was „Anderes Modell nehmen“ versucht, wenn die Prüfung scheitert (Befund 11).
                "ausweich": [_eintrag_dict(a, True) for a in ausweichwahl(name, g, (rec.modell.name,))],
                "wirksam": z["wirksam"], "blockiert": z["blockiert"], "orchester_hinweis": rec.orchester_hinweis,
            })
        return {
            "stand": KATALOG_STAND,
            "geraet": {"plattform": g.plattform, "chip": g.chip, "arbeitsspeicher_gb": g.arbeitsspeicher_gb,
                       "bekannt": g.bekannt, "stufe_gb": stufe_fuer(g), "stufen": list(STUFEN), "quelle": quelle,
                       "festplatte_frei_gb": g.festplatte_frei_gb},
            "ollama": {"erreichbar": installiert is not None, "installiert": installiert or [],
                       "cloud_ueber_ollama": cloud_installierte()},
            "rollen": zeilen, "orchester": orchester,
            "hinweis": "Das ist eine Vorauswahl nach Arbeitsspeicher. Ob ein Modell für deine Aufgaben taugt, "
                       "zeigt erst die Messlatte auf diesem Rechner.",
        }

    # -- Einrichten: laden, prüfen, übernehmen ----------------------------------------------
    def pruefe_modell(modell: str, rolle: str) -> dict[str, Any]:
        """Die vorhandene Qualifikationsprüfung (Werkzeugfähigkeit) bzw. eine Einbettungsprobe."""
        wurzel = ollama_wurzel(endpunkt())
        start = time.monotonic()
        if rolle == "einbettung":
            try:
                with ollama_client(30.0) as client:
                    antwort = client.post(wurzel + "/api/embed", json={"model": modell, "input": ["Bereitschaft"]})
                    antwort.raise_for_status()
                    vektoren = antwort.json().get("embeddings")
                ok = isinstance(vektoren, list) and bool(vektoren) and bool(vektoren[0])
            except (httpx.HTTPError, ValueError, TypeError):
                ok = False
            return {"verifiziert": ok, "latenz_ms": int((time.monotonic() - start) * 1000), "profil": None}
        from .routing_runtime import qualify_local_models
        provider = OpenAICompatible(modell, api_key="ollama", base_url=endpunkt(),
                                    trusted_local_hosts=[httpx.URL(endpunkt()).host])
        try:
            profile = qualify_local_models(provider, nur=modell)
        except (ValueError, httpx.HTTPError):
            return {"verifiziert": False, "latenz_ms": 0, "profil": None}
        profil = profile[0] if profile else None
        return {"verifiziert": bool(profil and profil.get("verified")),
                "latenz_ms": int((time.monotonic() - start) * 1000), "profil": profil}

    def nachher(modell: str, rolle: str) -> dict[str, Any]:
        inventar_von(app).vergiss()  # das Modell ist eben gekommen
        probe = app.state.modell_pruefung(modell, rolle) if hasattr(app.state, "modell_pruefung") \
            else pruefe_modell(modell, rolle)
        if not probe["verifiziert"]:
            raise Fehlschlag(Fehlergrund(
                "Das Modell ist geladen, hat die Prüfung aber nicht bestanden. Es wurde nicht übernommen.",
                "Nimm ein anderes Modell für diese Aufgabe; Kingfisher schlägt eines vor.", art="pruefung"))
        settings = app.state.settings
        with app.state.conversation_lock:
            settings.model_roles[rolle] = RollenWahl(modell=modell).als_dict()  # lokal, Cloud aus
            if probe["profil"] is not None:
                rest = [p for p in settings.routing_profiles
                        if not (p.get("model") == modell and p.get("endpoint") == probe["profil"].get("endpoint"))]
                settings.routing_profiles = [*rest, probe["profil"]]
            config.save(data_dir(), settings)
        rebuild()
        return {"modell": modell, "rolle": rolle, "geprueft": True, "latenz_ms": probe["latenz_ms"],
                "uebernommen": True}

    manager = PullManager(lambda: ollama_wurzel(endpunkt()), nachher,
                          client=lambda: httpx.Client(
                              timeout=httpx.Timeout(None, connect=5.0, read=120.0), trust_env=False,
                              follow_redirects=False, transport=getattr(app.state, "ollama_transport", None)))
    app.state.pull_manager = manager

    @app.post("/api/v1/models/pull", dependencies=guard, status_code=202)
    def start_pull(body: PullIn):
        if body.rolle not in ROLLEN:
            raise HTTPException(404, "Unbekannte Aufgabe.")
        g = geraet()
        rec = empfehle_alle(g)[body.rolle]
        erlaubt = {e.name: e for e in (rec.modell, *rec.alternativen, *ausweichwahl(body.rolle, g, (rec.modell.name,)))}
        wahl = erlaubt.get(body.modell) if body.modell else rec.modell
        if wahl is None:
            raise HTTPException(422, "Dieses Modell gehört nicht zur Empfehlung für diesen Rechner.")
        if not body.bestaetigt:
            raise HTTPException(422, "Bitte zuerst bestätigen: " + bestaetigungssatz(wahl.name, wahl.groesse_gb))
        if g.bekannt and wahl.speicher_gb > (g.modellspeicher_gb or 0) * 0.85:
            raise HTTPException(422, f"{wahl.name} braucht etwa {wahl.speicher_gb:g} GB Arbeitsspeicher und passt "
                                     "vermutlich nicht auf diesen Rechner. Bitte ein kleineres Modell wählen.")
        # Was schon auf der Festplatte liegt, braucht keinen neuen Platz (Übernehmen statt Laden).
        if normalisiere(wahl.name) not in {normalisiere(n) for n in installierte() or []} \
                and festplatte_reicht(wahl.groesse_gb, g) is False:
            kleiner = kleinere_wahl(body.rolle, wahl, g, "groesse_gb")
            raise HTTPException(422, f"{wahl.name} braucht etwa {gb_text(wahl.groesse_gb)} GB Festplatte, frei sind etwa "
                                     f"{gb_text(g.festplatte_frei_gb)} GB (zwei bleiben für das System frei). Bitte Platz schaffen"
                                     + (f" oder {kleiner.name} ({gb_text(kleiner.groesse_gb)} GB) wählen." if kleiner else "."))
        try:
            return manager.starte(wahl.name, body.rolle).als_dict()
        except PullBelegt as exc:
            raise HTTPException(409, str(exc) + " Bitte warten, bis es fertig ist.") from None

    @app.post("/api/v1/models/laden", dependencies=guard, status_code=202)
    def alles_laden(body: LadenIn):
        """Alle noch nicht eingerichteten Aufgaben mit einem Klick, nacheinander im Hintergrund (Fremdprobe 2, Befunde
        6 und 7). Der Lauf hängt an keiner Seite: Der Mensch richtet weiter ein, Heute zeigt den Fortschritt. Geladen
        wird nur die Empfehlung für diesen Rechner, nur nach ausdrücklicher Bestätigung."""
        g = geraet()
        alle = empfehle_alle(g)
        installiert = installierte()
        if installiert is None:
            raise HTTPException(503, "Das Programm, mit dem Kingfisher auf diesem Rechner denkt (Ollama), antwortet "
                                     "gerade nicht. Starte es und versuche es dann noch einmal.")
        zustand = {z["rolle"]: z for z in rollen_zustand()}
        da = {normalisiere(n) for n in installiert}
        auftraege, gezaehlt = [], set()
        for name in ROLLEN_NAMEN:
            rec = alle[name]
            if status_der_rolle(rec, zustand[name], installiert) == "eingerichtet":
                continue
            ziel = normalisiere(rec.modell.name)
            if g.bekannt and rec.modell.speicher_gb > (g.modellspeicher_gb or 0) * 0.85:
                continue  # passt nicht auf diesen Rechner; die Karte sagt das je Aufgabe
            groesse = 0.0 if ziel in da or ziel in gezaehlt else rec.modell.groesse_gb
            gezaehlt.add(ziel)
            auftraege.append((rec.modell.name, name, groesse))
        if not auftraege:
            return manager.reihe_stand() or {"laeuft": False, "prozent": 100, "auftraege": [], "eingerichtet": [],
                                               "fehlgeschlagen": [], "gesamt_gb": 0.0, "satz": ""}
        noch = sum(a[2] for a in auftraege)
        if not body.bestaetigt:
            raise HTTPException(422, f"Bitte zuerst bestätigen: Es werden etwa {gb_text(noch)} GB geladen.")
        if noch > 0 and festplatte_reicht(noch, g) is False:
            raise HTTPException(422, f"Das Laden braucht etwa {gb_text(noch)} GB Festplatte, frei sind etwa "
                                     f"{gb_text(g.festplatte_frei_gb)} GB (zwei bleiben für das System frei). Bitte Platz schaffen.")
        try:
            return manager.starte_reihe(auftraege)
        except PullBelegt as exc:
            raise HTTPException(409, str(exc) + " Bitte warten, bis es fertig ist.") from None

    @app.get("/api/v1/models/laden", dependencies=guard)
    def laden_stand():
        return manager.reihe_stand() or {"laeuft": False, "prozent": 0, "auftraege": [], "eingerichtet": [],
                                         "fehlgeschlagen": [], "gesamt_gb": 0.0, "satz": ""}

    @app.get("/api/v1/models/pull", dependencies=guard)
    def current_pull():
        stand = manager.aktuell()
        return {"aktuell": stand.als_dict() if stand else None}

    @app.get("/api/v1/models/pull/{job_id}", dependencies=guard)
    def pull_state(job_id: str):
        stand = manager.stand(job_id)
        if stand is None:
            raise HTTPException(404, "Dieser Ladevorgang ist unbekannt.")
        return stand.als_dict()

    from .zeiten_routes import register as register_zeiten
    register_zeiten(app, guard)
