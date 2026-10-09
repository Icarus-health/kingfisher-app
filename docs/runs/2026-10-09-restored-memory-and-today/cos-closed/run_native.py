"""Run the frozen synthetic memory flow against an owned, isolated Ollama."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
REPO = ROOT / "repo"
MODELS = ROOT / "models"
BLOBS = MODELS / "blobs"
ORIGIN = "http://127.0.0.1:11439"
STATE = ROOT / "runtime.json"
BASELINE = ROOT / "native-source-blobs-before.json"
MANIFEST_BASELINE = ROOT / "native-source-manifests-before.json"
EXPECTED_MODELS = {"qwen3.5:4b", "bge-m3:latest"}
EXPECTED_CATALOG_SHA256 = "857965be8e845fde716e5d22d94d5310f5011058db68a4b7107abae1e10e465a"
EXPECTED_FLOW_SHA256 = "76f5139ac4cf4db3e133d62ed443b5c59ac92f06df1db3634353dfe0ad382ef4"
EXPECTED_FASSUNG = "63f707885615f63a502a37f04c5b5ff86e5488fc"
NATIVE_MODELS = Path.home() / ".ollama" / "models"
SERVER_LINK = Path("/usr/local/bin/ollama")
SERVER_BIN = Path("/Applications/Ollama.app/Contents/Resources/ollama")

if STATE.exists():
    raise SystemExit(f"Refusing to overwrite an earlier run: {STATE}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def real_regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{label} must be a regular, non-symlink file: {path}")


def real_directory(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError(f"{label} must be a real, non-symlink directory: {path}")


def verify_clone_against_source(clone: Path, source: Path, digest: str, ref: str) -> dict:
    real_regular_file(source, f"Native source blob {ref}")
    real_regular_file(clone, f"Isolated blob {ref}")
    source_stat = source.stat()
    clone_stat = clone.stat()
    if clone_stat.st_ino == source_stat.st_ino:
        raise RuntimeError(f"Isolated blob shares the native source inode: {ref}")
    if clone_stat.st_size != source_stat.st_size or sha256(clone) != digest:
        raise RuntimeError(f"Isolated blob missing, wrong size, or SHA-256 mismatch: {ref}")
    return {
        "digest": ref, "sha256": digest,
        "isolated_inode": clone_stat.st_ino, "source_inode": source_stat.st_ino,
        "distinct_inode": True, "isolated_not_symlink": True,
    }


def record_source_postcheck(state: dict, unchanged: bool | None, error: str | None = None) -> bool:
    if error is not None or unchanged is not True:
        state["completed"] = False
        message = error or "Frozen native source files changed during the run"
        state["native_source_postcheck_failed"] = message
        state["failure"] = message
        existing = state.get("runtime_error")
        if existing:
            state["runtime_error"] = existing + "; " + message
        else:
            state["runtime_error"] = message
        return False
    return True


def validate_vendor_binary() -> Path:
    if not SERVER_LINK.is_symlink():
        raise RuntimeError(f"Expected Ollama vendor symlink is unavailable: {SERVER_LINK}")
    target = SERVER_LINK.resolve(strict=True)
    if target != SERVER_BIN or not target.is_file() or target.is_symlink():
        raise RuntimeError(f"Ollama vendor symlink target changed: {SERVER_LINK} -> {target}")
    return target


def save() -> None:
    temp = STATE.with_suffix(".new")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    temp.replace(STATE)


def terminate(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def read_and_verify_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    if not REPO.is_dir() or REPO.is_symlink():
        raise RuntimeError("Snapshot repository is missing or symlinked")
    catalog = ROOT / "catalog.json"
    flow = ROOT / "closed_flow.py"
    real_regular_file(catalog, "Frozen catalog")
    real_regular_file(flow, "Frozen flow")
    if sha256(catalog) != EXPECTED_CATALOG_SHA256:
        raise RuntimeError("Frozen catalog SHA-256 changed")
    if sha256(flow) != EXPECTED_FLOW_SHA256:
        raise RuntimeError("Frozen flow SHA-256 changed")
    if not BASELINE.is_file() or BASELINE.is_symlink():
        raise RuntimeError("Native source blob freeze is missing or symlinked")
    baseline = json.loads(BASELINE.read_text())
    if not isinstance(baseline, list) or not baseline:
        raise RuntimeError("Native source blob freeze must be a nonempty list")
    by_digest = {item["digest"]: item for item in baseline}
    if len(by_digest) != len(baseline):
        raise RuntimeError("Native source blob freeze contains duplicate digests")
    if not MANIFEST_BASELINE.is_file() or MANIFEST_BASELINE.is_symlink():
        raise RuntimeError("Native source manifest freeze is missing or symlinked")
    native_manifests = json.loads(MANIFEST_BASELINE.read_text())
    if not isinstance(native_manifests, list) or not native_manifests:
        raise RuntimeError("Native source manifest freeze must be a nonempty list")
    native_manifest_paths = {item["path"] for item in native_manifests}
    if len(native_manifest_paths) != len(native_manifests):
        raise RuntimeError("Native source manifest freeze contains duplicate paths")
    expected_native_manifest_paths = {
        str(NATIVE_MODELS / "manifests" / "registry.ollama.ai" / "library" / "qwen3.5" / "4b"),
        str(NATIVE_MODELS / "manifests" / "registry.ollama.ai" / "library" / "bge-m3" / "latest"),
    }
    if native_manifest_paths != expected_native_manifest_paths:
        raise RuntimeError("Native manifest freeze must cover exactly qwen3.5:4b and bge-m3:latest")
    for item in native_manifests:
        path = Path(item["path"])
        real_regular_file(path, f"Native source manifest {path}")
        if sha256(path) != item["sha256"]:
            raise RuntimeError(f"Native source manifest SHA-256 changed: {path}")

    real_directory(MODELS, "Isolated model store")
    real_directory(BLOBS, "Isolated blob store")
    manifests = []
    refs: dict[str, str] = {}
    for name, tag in (("qwen3.5", "4b"), ("bge-m3", "latest")):
        manifest_path = MODELS / "manifests" / "registry.ollama.ai" / "library" / name / tag
        real_regular_file(manifest_path, f"Isolated {name}:{tag} manifest")
        manifest = json.loads(manifest_path.read_text())
        model_refs = [manifest["config"]["digest"], *(layer["digest"] for layer in manifest["layers"])]
        if not model_refs:
            raise RuntimeError(f"Empty manifest for {name}:{tag}")
        for ref in model_refs:
            if not ref.startswith("sha256:"):
                raise RuntimeError(f"Unexpected blob reference for {name}:{tag}: {ref}")
            refs[ref] = name + ":" + tag
        manifests.append({"name": name + ":" + tag, "path": str(manifest_path), "sha256": sha256(manifest_path)})
    frozen_manifest_hashes = {item["path"]: item["sha256"] for item in native_manifests}
    for manifest in manifests:
        model, tag = manifest["name"].split(":", 1)
        source_manifest_path = str(NATIVE_MODELS / "manifests" / "registry.ollama.ai" / "library" / model / tag)
        if manifest["sha256"] != frozen_manifest_hashes.get(source_manifest_path):
            raise RuntimeError(f"Isolated model manifest differs from frozen native manifest: {manifest['name']}")

    verified = []
    for ref, model_name in refs.items():
        digest = ref.removeprefix("sha256:")
        record = by_digest.get(ref)
        if record is None:
            raise RuntimeError(f"Native freeze does not cover required {model_name} blob {ref}")
        source = Path(record["path"])
        expected_source = NATIVE_MODELS / "blobs" / ("sha256-" + digest)
        if source != expected_source:
            raise RuntimeError(f"Frozen native path is unexpected for {ref}: {source}")
        real_regular_file(source, f"Native source blob {ref}")
        real_regular_file(source, f"Native source blob {ref}")
        source_stat = source.stat()
        if (source_stat.st_ino != record["inode"] or source_stat.st_size != record["size"]
                or source_stat.st_mtime_ns != record["mtime_ns"]
                or stat.S_IMODE(source_stat.st_mode) != record["mode"]):
            raise RuntimeError(f"Native source metadata changed since freeze for {ref}")
        if sha256(source) != digest or record.get("sha256") != digest:
            raise RuntimeError(f"Native source SHA-256 mismatch for {ref}")
        clone = BLOBS / ("sha256-" + digest)
        verified.append({"model": model_name, **verify_clone_against_source(clone, source, digest, ref)})
    return baseline, [{"manifests": manifests, "blobs": verified}], native_manifests


def inspect_native_after(baseline: list[dict]) -> tuple[list[dict], bool]:
    after = []
    for old in baseline:
        path = Path(old["path"])
        try:
            st = path.lstat()
            regular = stat.S_ISREG(st.st_mode) and not path.is_symlink()
            record = {
                "digest": old["digest"], "exists": regular, "symlink": path.is_symlink(), "size": st.st_size,
                "inode": st.st_ino, "mtime_ns": st.st_mtime_ns,
                "mode": stat.S_IMODE(st.st_mode), "sha256": sha256(path) if regular else None,
            }
        except OSError as exc:
            record = {"digest": old.get("digest"), "exists": False, "error": type(exc).__name__}
        after.append(record)
    unchanged = len(after) == len(baseline) and all(
        rec.get("exists") and rec.get("size") == old.get("size")
        and rec.get("inode") == old.get("inode") and rec.get("mtime_ns") == old.get("mtime_ns")
        and rec.get("mode") == old.get("mode") and rec.get("sha256") == old.get("sha256")
        for old, rec in zip(baseline, after, strict=True)
    )
    (ROOT / "native-source-blobs-after.json").write_text(json.dumps(after, indent=2) + "\n")
    return after, unchanged


def inspect_manifests_after(baseline: list[dict]) -> tuple[list[dict], bool]:
    after = []
    for old in baseline:
        path = Path(old["path"])
        try:
            if path.is_symlink() or not path.is_file():
                after.append({"model_name": old.get("model_name"), "tag": old.get("tag"),
                              "path": str(path), "exists": False, "symlink": path.is_symlink(), "sha256": None})
                continue
            after.append({"model_name": old.get("model_name"), "tag": old.get("tag"),
                          "path": str(path), "exists": True, "symlink": False, "sha256": sha256(path)})
        except OSError as exc:
            after.append({"model_name": old.get("model_name"), "tag": old.get("tag"),
                          "path": str(path), "exists": False, "error": type(exc).__name__})
    unchanged = len(after) == len(baseline) and all(
        item.get("exists") and not item.get("symlink") and item.get("sha256") == old.get("sha256")
        for old, item in zip(baseline, after, strict=True)
    )
    (ROOT / "native-source-manifests-after.json").write_text(json.dumps(after, indent=2) + "\n")
    return after, unchanged


state = {
    "synthetic_only": True,
    "endpoint": ORIGIN,
    "isolated_models_directory": str(MODELS),
    "ollama_no_cloud": True,
    "ollama_noprune": True,
    "production_endpoint_touched": False,
    "settings_or_private_directories_loaded": False,
    "watchdog": "900 seconds or 8 GiB sampled owned-process RSS; emergency sampler, not a hard GPU or memory cap",
    "started_at": time.time(),
    "samples": [],
    "completed": False,
    "preflight_verified": False,
}
server = client = None
baseline: list[dict] = []
native_manifests: list[dict] = []
failure: BaseException | None = None

try:
    if ROOT.resolve() != ROOT:
        raise RuntimeError("Run directory path unexpectedly resolves elsewhere")
    server_bin = validate_vendor_binary()
    if sha256(ROOT / "catalog.json") != EXPECTED_CATALOG_SHA256:
        raise RuntimeError("Frozen catalog SHA-256 changed")
    if os.environ.get("OLLAMA_HOST") == "0.0.0.0:11434":
        raise RuntimeError("Refusing a productive Ollama endpoint configuration")
    baseline, preflight, native_manifests = read_and_verify_inputs()
    state["native_source_blobs_before_sha256"] = sha256(BASELINE)
    state["native_source_manifests_before_sha256"] = sha256(MANIFEST_BASELINE)
    state["preflight"] = preflight[0]
    state["preflight_verified"] = True
    state["ollama_binary"] = str(server_bin)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 11439))

    env = dict(os.environ)
    env.update({
        "OLLAMA_HOST": "127.0.0.1:11439",
        "OLLAMA_MODELS": str(MODELS),
        "OLLAMA_NO_CLOUD": "1",
        "OLLAMA_NOPRUNE": "1",
        "OLLAMA_NUM_PARALLEL": "1",
        "OLLAMA_MAX_LOADED_MODELS": "2",
        "OLLAMA_CONTEXT_LENGTH": "4096",
        "OLLAMA_KEEP_ALIVE": "15s",
        "OLLAMA_MAX_QUEUE": "2",
        "KINGFISHER_FASSUNG": EXPECTED_FASSUNG,
        "PYTHONUNBUFFERED": "1",
    })
    env.pop("PYTHONPATH", None)
    with (ROOT / "ollama.log").open("w") as log:
        server = subprocess.Popen(
            [str(server_bin), "serve"], env=env, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        state["server_pid"] = server.pid
        save()
        with httpx.Client(trust_env=False, timeout=3) as http:
            for _ in range(80):
                if server.poll() is not None:
                    raise RuntimeError("Owned isolated Ollama exited before ready")
                try:
                    response = http.get(ORIGIN + "/api/tags")
                    response.raise_for_status()
                    break
                except httpx.HTTPError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Owned isolated Ollama did not become ready")
            tags = response.json()
            names = {item.get("name") for item in tags.get("models", [])}
            if names != EXPECTED_MODELS:
                raise RuntimeError(f"Isolated model inventory mismatch: {sorted(names)}")
            version = http.get(ORIGIN + "/api/version")
            version.raise_for_status()
            state["tags"] = tags
            state["ollama_version"] = version.json()
            save()

        with (ROOT / "probe.log").open("w") as log:
            client = subprocess.Popen(
                [sys.executable, str(ROOT / "closed_flow.py"), str(REPO)],
                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            state["client_pid"] = client.pid
            save()
            start = time.monotonic()
            while client.poll() is None:
                try:
                    ps = subprocess.run(
                        ["/bin/ps", "-axo", "pid=,pgid=,rss="],
                        text=True, capture_output=True, check=True, timeout=10,
                    )
                    rows = [list(map(int, line.split())) for line in ps.stdout.splitlines() if line.strip()]
                    if any(len(row) != 3 for row in rows):
                        raise RuntimeError("RSS sampler returned an unreadable process row")
                    owned_pgids = {server.pid, client.pid}
                    rss = sum(row[2] for row in rows if row[1] in owned_pgids)
                except BaseException as exc:
                    state["watchdog_stop"] = "RSS sampler failed; stopping owned client safely"
                    raise RuntimeError(f"Emergency RSS sampler failed: {type(exc).__name__}: {exc}") from exc
                elapsed = time.monotonic() - start
                state["samples"].append({"elapsed_seconds": round(elapsed, 2), "owned_rss_kib": rss})
                save()
                if rss > 8 * 1024 * 1024 or elapsed > 900:
                    state["watchdog_stop"] = "sampled RSS or runtime limit exceeded"
                    terminate(client)
                    break
                if server.poll() is not None:
                    raise RuntimeError("Owned isolated Ollama exited during the memory flow")
                time.sleep(2)
            state["client_exit"] = client.wait()
            state["completed"] = state["client_exit"] == 0 and state.get("watchdog_stop") is None
            save()
            if not state["completed"]:
                raise RuntimeError("Synthetic memory flow did not complete successfully")
except BaseException as exc:
    failure = exc
    state["runtime_error"] = f"{type(exc).__name__}: {exc}"
finally:
    terminate(client)
    terminate(server)
    state["server_exit"] = None if server is None else server.poll()
    state["stopped_at"] = time.time()
    if BASELINE.exists() and not BASELINE.is_symlink():
        try:
            if not baseline:
                candidate = json.loads(BASELINE.read_text())
                if isinstance(candidate, list):
                    baseline = candidate
            if baseline:
                after, unchanged = inspect_native_after(baseline)
                state["native_source_blobs_after"] = after
                state["native_source_blobs_unchanged"] = unchanged
                record_source_postcheck(state, unchanged)
        except BaseException as exc:
            state["native_source_postcheck_error"] = f"{type(exc).__name__}: {exc}"
            record_source_postcheck(state, None, state["native_source_postcheck_error"])
    else:
        record_source_postcheck(state, None, "Native source blob freeze unavailable for postcheck")
    if MANIFEST_BASELINE.exists() and not MANIFEST_BASELINE.is_symlink():
        try:
            if not native_manifests:
                candidate = json.loads(MANIFEST_BASELINE.read_text())
                if isinstance(candidate, list):
                    native_manifests = candidate
            if native_manifests:
                after, unchanged = inspect_manifests_after(native_manifests)
                state["native_source_manifests_after"] = after
                state["native_source_manifests_unchanged"] = unchanged
                record_source_postcheck(state, unchanged)
        except BaseException as exc:
            state["native_source_manifests_postcheck_error"] = f"{type(exc).__name__}: {exc}"
            record_source_postcheck(state, None, state["native_source_manifests_postcheck_error"])
    else:
        record_source_postcheck(state, None, "Native source manifest freeze unavailable for postcheck")
    try:
        save()
    except BaseException as exc:
        state["state_save_error"] = f"{type(exc).__name__}: {exc}"

print(json.dumps({k: v for k, v in state.items() if k not in {"samples", "tags"}}, indent=2))
if failure is not None or state.get("failure") or not state.get("completed"):
    raise SystemExit(1)
