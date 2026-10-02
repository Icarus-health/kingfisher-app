"""Ephemeral local audio-worker queue; no persistence or external I/O."""
from __future__ import annotations

import base64
import binascii
import io
import threading
import time
import uuid
import wave
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import Response

TTL = 300.0
PROCESSING_TIMEOUT = 120.0
MAX_AUDIO = 10 * 1024 * 1024


class AudioIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)

    @field_validator("text")
    @classmethod
    def usable_text(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Text ist leer oder ungültig.")
        return value


class WorkerResult(BaseModel):
    id: str
    success: bool
    audio_base64: str | None = Field(default=None, max_length=14 * 1024 * 1024)


def _purge(state: dict[str, Any], now: float) -> None:
    for key, job in list(state["jobs"].items()):
        if job["status"] == "processing" and now - job["claimed_at"] > PROCESSING_TIMEOUT:
            job["status"] = "failed"
            job.pop("audio", None)
            job.pop("text", None)
        if now - job["created_at"] > TTL:
            del state["jobs"][key]
    active = state.get("active")
    if active and active not in state["jobs"]:
        state["active"] = None


def _validate_wav(raw: bytes) -> None:
    if len(raw) > MAX_AUDIO:
        raise ValueError("Audiodatei ist zu groß.")
    try:
        with wave.open(io.BytesIO(raw), "rb") as wav:
            if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2:
                raise ValueError("Nur PCM16-WAV wird unterstützt.")
            if wav.getnchannels() not in (1, 2) or wav.getframerate() <= 0 or wav.getnframes() <= 0:
                raise ValueError("Ungültige WAV-Parameter.")
            if wav.getnframes() / wav.getframerate() > 1200:
                raise ValueError("Audiodatei ist zu lang.")
            expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            if len(wav.readframes(wav.getnframes())) != expected:
                raise ValueError("Ungültige WAV-Datei.")
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("Ungültige WAV-Datei.") from exc


def register_local_audio_routes(app, guard):
    state = {"lock": threading.RLock(), "jobs": {}, "active": None, "heartbeat": None}
    app.state.local_audio = state

    def available(now: float) -> bool:
        heartbeat = state["heartbeat"]
        return heartbeat is not None and now - heartbeat < 15.0

    @app.get("/api/v1/audio/status", dependencies=guard)
    def status():
        with state["lock"]:
            _purge(state, time.monotonic())
            return {"available": available(time.monotonic())}

    @app.post("/api/v1/audio", dependencies=guard)
    def create(body: AudioIn):
        with state["lock"]:
            now = time.monotonic(); _purge(state, now)
            if not available(now):
                raise HTTPException(503, "Lokaler Audioworker ist nicht verfügbar.")
            if state["active"]:
                state["jobs"].pop(state["active"], None)
            job_id = uuid.uuid4().hex
            state["jobs"][job_id] = {"id": job_id, "text": body.text, "status": "pending", "created_at": now}
            state["active"] = job_id
            return {"id": job_id, "status": "pending"}

    @app.get("/api/v1/audio-worker", dependencies=guard)
    def worker_get():
        with state["lock"]:
            now = time.monotonic(); state["heartbeat"] = now; _purge(state, now)
            job = state["jobs"].get(state["active"])
            if not job or job["status"] != "pending":
                return {"job": None}
            job["status"] = "processing"; job["claimed_at"] = now
            result = {"job": {"id": job["id"], "text": job["text"]}}
            job.pop("text", None)
            return result

    @app.post("/api/v1/audio-worker", dependencies=guard)
    def worker_result(body: WorkerResult):
        with state["lock"]:
            _purge(state, time.monotonic())
            job = state["jobs"].get(body.id)
            if not job or job["status"] != "processing":
                raise HTTPException(404, "Audiolauf nicht gefunden.")
            if not body.success:
                job["status"] = "failed"; job.pop("audio", None); job.pop("text", None)
                return {"status": "failed"}
            try:
                if not body.audio_base64: raise ValueError("Audiodatei fehlt.")
                raw = base64.b64decode(body.audio_base64, validate=True)
                _validate_wav(raw)
            except (ValueError, binascii.Error) as exc:
                job["status"] = "failed"; job.pop("audio", None); job.pop("text", None)
                raise HTTPException(422, "Ungültige WAV-Datei.") from exc
            job["audio"] = raw; job["status"] = "ready"
            return {"status": "ready"}

    @app.get("/api/v1/audio/{job_id}", dependencies=guard)
    def get_job(job_id: str):
        with state["lock"]:
            now = time.monotonic(); _purge(state, now)
            job = state["jobs"].get(job_id)
            if not job: raise HTTPException(404, "Audiolauf nicht gefunden.")
            if job["status"] == "processing" and now - job["claimed_at"] > PROCESSING_TIMEOUT:
                job["status"] = "failed"; job.pop("audio", None)
            return {"id": job_id, "status": job["status"]}

    @app.get("/api/v1/audio/{job_id}/content", dependencies=guard)
    def content(job_id: str):
        with state["lock"]:
            now = time.monotonic(); _purge(state, now)
            job = state["jobs"].get(job_id)
            if not job: raise HTTPException(404, "Audiolauf nicht gefunden.")
            if job["status"] != "ready": raise HTTPException(409, "Audio ist noch nicht bereit.")
            return Response(job["audio"], media_type="audio/wav", headers={"Cache-Control": "no-store"})

    @app.delete("/api/v1/audio/{job_id}", dependencies=guard)
    def cancel(job_id: str):
        with state["lock"]:
            _purge(state, time.monotonic()); job = state["jobs"].get(job_id)
            if not job: raise HTTPException(404, "Audiolauf nicht gefunden.")
            job["status"] = "failed"; job.pop("audio", None); job.pop("text", None)
            return {"id": job_id, "status": "failed"}
