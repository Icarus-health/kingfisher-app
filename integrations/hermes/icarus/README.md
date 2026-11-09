# Kingfisher memory for Hermes Agent

A read-only memory provider for [Hermes Agent](https://github.com/NousResearch/hermes-agent).
Before every reply, Hermes pulls the statements from Kingfisher that fit the message — each
with its source — and gets two tools to look things up on purpose. Everything goes through
Kingfisher's MCP door, so the same policy and the same audit log apply as for any other
assistant on this computer (`docs/07-mcp-tuer.md`, German).

What it deliberately does **not** do:

- **Write into Kingfisher.** No `sync_turn`, no `on_memory_write`. In Kingfisher a fact only
  becomes a fact when a person accepts a proposal; an outside assistant does not get a shortcut.
  Hermes keeps its own built-in memory (MEMORY.md, USER.md) alongside.
- **Show protected data.** The door only hands out statements with protection level `normal`.
- **Keep a second store.** No database of its own; every request goes to the running app.

## Setup

1. Turn the door on in Kingfisher. In the Mac app, add this line to
   `~/Library/Application Support/Kingfisher/kingfisher.env` and restart Kingfisher:

   ```
   KINGFISHER_MCP_TUER=1
   ```

2. Copy this directory into your Hermes profile and select it:

   ```bash
   mkdir -p "${HERMES_HOME:-$HOME/.hermes}/plugins"
   ```

   ```bash
   cp -R integrations/hermes/icarus "${HERMES_HOME:-$HOME/.hermes}/plugins/icarus"
   ```

   ```bash
   hermes config set memory.provider icarus
   ```

3. Check that it works:

   ```bash
   hermes icarus pruefen
   ```

   It answers with one sentence: connected, or what is missing and where to change it.

With the Mac app nothing else is needed: the plugin reads the token from `kingfisher.env` (only
that one line) and talks to `127.0.0.1:8890`. A sidecar started by hand is found through its
`verbindung.json` in `~/Library/Application Support/Icarus`.

## Other setups

Optional `$HERMES_HOME/icarus.json`:

| Key | Meaning |
|---|---|
| `adresse` | Sidecar address, e.g. `http://127.0.0.1:8890`. The token then comes from the Hermes secret `ICARUS_SIDECAR_TOKEN` (`$HERMES_HOME/.env`). |
| `daten_ordner` | Folder with `verbindung.json` of a sidecar started by hand (e.g. a working copy's `.icarus-data`). |

## Tools

| Tool | What it returns |
|---|---|
| `icarus_gedaechtnis_suchen` | Statements matching `query` (up to `limit`, default 5), with source and selection reason |
| `icarus_kontext` | Everything Kingfisher shows an outside assistant, verbatim, with sources |

Results are JSON: `{"ergebnis": "…"}` or `{"fehler": "…"}` with a sentence saying what to do.

## Limits

- Hermes must run on the same computer as Kingfisher (the sidecar only listens on loopback).
- The token reaches every sidecar route, not only the door's — the same trade-off as for the
  MCP door. Only use it with assistants you already trust with this computer.
- Every recall shows up in Kingfisher's audit log, one entry per non-trivial message.
- Tested against the real Kingfisher sidecar; the Hermes side against Hermes' `MemoryProvider`
  interface as of November 2026. Set `HERMES_AGENT_SRC` to a Hermes checkout to run
  `sidecar/tests/test_hermes_plugin.py` against the real interface.
