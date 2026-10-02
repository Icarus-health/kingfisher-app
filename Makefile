# Icarus — Entwicklungskommandos
#
# `make help` listet alle Ziele. Wer Icarus nur benutzen will, braucht davon
# genau eines: `make start`.

PY      ?= python3
VENV    := .venv
BIN     := $(VENV)/bin
SCHEMA  := schema/self-model.schema.json
EXAMPLE := schema/beispiel-profil.json

# Erzeugte Datei mit Token und Passphrase. Liegt neben dem Repo, nie darin —
# siehe .gitignore.
ENVDATEI := .kingfisher.env
QUELLENDATEI := .kingfisher.sources
COMPOSE  := docker compose -p kingfisher --env-file $(ENVDATEI)
ADRESSE  := http://127.0.0.1:8890

.DEFAULT_GOAL := help
.PHONY: help start stop logs url modell-lokal lokal quellen backups backup-auslagern aktualisieren zurueck-vor-update \
        quelle-freigeben quelle-entziehen notizen-importieren \
        venv sidecar-dev sidecar-run mcp-config container \
        test validate-schema check ci-lokal clean

help: ## Diese Übersicht anzeigen
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# -- Loslegen ---------------------------------------------------------------
#
# `make start` ist der einzige Befehl, den jemand kennen muss, der Icarus
# benutzen und nicht bauen will. compose.yaml allein verlangt vier Schritte und
# drei Dinge, die man wissen muss — Token erzeugen, Passphrase erzeugen, einen
# Bind-Mount einkommentieren und ICARUS_FILE_ROOTS dazu passend setzen. Nichts
# davon kann ein Mensch besser als das Programm. Also macht es das Programm.
#
# Was es NICHT macht: die Sicherheitszusagen aufweichen. Das Token wird erzeugt,
# nicht auf einen Vorgabewert gesetzt; das `:?` in compose.yaml bleibt scharf.
# Der Notizordner wird nur eingebunden, wenn er ausdrücklich genannt wurde, und
# dann nur lesend.

# Token und Passphrase werden einmal erzeugt und danach wiederverwendet.
#
# Das Wiederverwenden ist keine Bequemlichkeit: Die Passphrase entschlüsselt
# schluessel.icarus im Datenvolume (siehe secrets.py). Ein zweiter Start mit
# einer neuen Passphrase macht jeden dort hinterlegten API-Schlüssel unlesbar —
# der Nutzer sähe eine leere Einrichtung und keinen Grund dafür.
$(ENVDATEI):
	@umask 077; { \
	  echo "# Von 'make start' erzeugt — nicht ins Git, nicht weitergeben."; \
	  echo "#"; \
	  echo "# Beide Werte müssen erhalten bleiben. Die Passphrase entschlüsselt"; \
	  echo "# die Schlüsseldatei im Datenvolume; ist sie weg, sind die dort"; \
	  echo "# hinterlegten API- und Mailpasswörter unlesbar."; \
	  echo "ICARUS_SIDECAR_TOKEN=$$(openssl rand -hex 32)"; \
	  echo "ICARUS_SECRETS_PASSPHRASE=$$(openssl rand -hex 32)"; \
	} > $@
	@chmod 600 $@
	@echo "Token und Passphrase erzeugt und in $@ abgelegt (nur für dich lesbar)."

# Der freigegebene Pfad steht lokal in einer einzelnen, nicht versionierten
# Zeile. Die Datei wird nie als Shell-Code eingelesen: Ein Notizordner darf
# Leerzeichen und Apostrophe enthalten, aber niemals Teil eines Befehls werden.
# Ohne eine aktive Freigabe wird kein Host-Pfad in den Container eingebunden.
quellen: ## Zeigt die lokal freigegebene Notizquelle
	@if [ -s "$(QUELLENDATEI)" ]; then \
	  printf 'Freigegebener Notizordner (nur lesend): '; \
	  sed -n '1p' "$(QUELLENDATEI)"; \
	else \
	  echo 'Kein Notizordner freigegeben.'; \
	  echo 'Freigeben: make quelle-freigeben NOTIZEN=~/Documents/Obsidian'; \
	fi

quelle-freigeben: ## Einen Notizordner dauerhaft und nur lesend freigeben
	@set -e; \
	pfad="$(NOTIZEN)"; \
	case "$$pfad" in "~"|"~/"*) pfad="$$HOME$${pfad#\~}";; esac; \
	if [ -z "$$pfad" ]; then \
	  echo 'Bitte einen Ordner angeben: make quelle-freigeben NOTIZEN=~/Documents/Obsidian'; \
	  exit 1; \
	fi; \
	aufgeloest=$$(cd "$$pfad" 2>/dev/null && pwd -P) || { \
	  echo "Den Ordner \"$$pfad\" gibt es nicht. Es wurde nichts freigegeben."; \
	  exit 1; \
	}; \
	if [ "$$aufgeloest" = "/" ]; then \
	  echo 'Der gesamte Rechner kann nicht als Notizquelle freigegeben werden.'; \
	  exit 1; \
	fi; \
	(umask 077; printf '%s\n' "$$aufgeloest" > "$(QUELLENDATEI)"); \
	echo "Notizordner freigegeben: $$aufgeloest"; \
	echo 'Beim nächsten Start wird er ausschließlich lesend als /notizen eingebunden.'

quelle-entziehen: ## Den Zugriff auf den lokal freigegebenen Notizordner entziehen
	@rm -f "$(QUELLENDATEI)"
	@echo 'Notizquellen-Freigabe entfernt. Beim nächsten Start wird kein Ordner eingebunden.'

# NOTIZEN geht über die Umgebung in die Rezeptur, nicht über `$(NOTIZEN)` im
# Text. Eingesetzt würde der Pfad zu Shell-Quelltext, und ein Ordner wie
# „Lenas Notizen“ enthält ein Apostroph — das beendet die Zeichenkette und der
# Befehl bricht mit einem Syntaxfehler ab, den niemand sich erklären kann.
start: export NOTIZEN := $(NOTIZEN)
start: $(ENVDATEI) ## Kingfisher starten. Ordner freigeben: make start NOTIZEN=~/Notizen
	@set -e; \
	bild=$$(sed -n 's/^KINGFISHER_IMAGE=//p' "$(ENVDATEI)" | tail -n 1); \
	if [ -n "$$bild" ]; then \
	  bauen=''; \
	  echo "Fertiges Bild: $$bild (von make aktualisieren). Aus dem Quelltext bauen: die Zeile KINGFISHER_IMAGE in $(ENVDATEI) löschen."; \
	else \
	  bauen='--build'; \
	fi; \
	pfad="$$NOTIZEN"; \
	if [ -z "$$pfad" ] && [ -s "$(QUELLENDATEI)" ]; then \
	  pfad=$$(sed -n '1p' "$(QUELLENDATEI)"); \
	fi; \
	case "$$pfad" in "~"|"~/"*) pfad="$$HOME$${pfad#\~}";; esac; \
	if [ -n "$$pfad" ]; then \
	  aufgeloest=$$(cd "$$pfad" 2>/dev/null && pwd -P) || { \
	    echo "Den Ordner \"$$pfad\" gibt es nicht. Es wurde nichts gestartet."; \
	    exit 1; }; \
	  if [ "$$aufgeloest" = "/" ]; then \
	    echo 'Der gesamte Rechner kann nicht als Notizquelle freigegeben werden.'; \
	    exit 1; \
	  fi; \
	  if [ -n "$$NOTIZEN" ]; then \
	    (umask 077; printf '%s\n' "$$aufgeloest" > "$(QUELLENDATEI)"); \
	  fi; \
	  echo "Notizordner: $$aufgeloest — wird nur lesend eingebunden."; \
	  echo; \
	  yaml=$$(printf '%s' "$$aufgeloest" | sed "s/'/''/g"); \
	  printf "services:\n  kingfisher:\n    environment:\n      - ICARUS_FILE_ROOTS=/notizen\n    volumes:\n      - '%s:/notizen:ro'\n" "$$yaml" \
	    | $(COMPOSE) -f compose.yaml -f - up -d $$bauen; \
	else \
	  echo "Ohne Notizordner — Kingfisher läuft, kann aber keine Dateien lesen."; \
	  echo "Mit Ordner:  make start NOTIZEN=~/Documents/Obsidian"; \
	  echo; \
	  $(COMPOSE) up -d $$bauen; \
	 fi
	@printf 'Warte darauf, dass der Sidecar antwortet '
	@bereit=nein; \
	 for _ in $$(seq 1 90); do \
	   if curl -fsS $(ADRESSE)/health >/dev/null 2>&1; then bereit=ja; break; fi; \
	   printf '.'; sleep 1; \
	 done; \
	 echo; echo; \
	 if [ "$$bereit" = nein ]; then \
	   echo "Der Sidecar hat nach 90 Sekunden nicht geantwortet."; \
	   echo "Was er selbst dazu sagt:  make logs"; \
	   exit 1; \
	 fi
	@$(MAKE) --no-print-directory _fertig

notizen-importieren: $(ENVDATEI) ## Die freigegebene Notizquelle als belegte Rohquellen aufnehmen
	@set -e; \
	if [ ! -s "$(QUELLENDATEI)" ]; then \
	  echo 'Kein Notizordner freigegeben.'; \
	  echo 'Zuerst: make quelle-freigeben NOTIZEN=~/Documents/Obsidian'; \
	  exit 1; \
	fi; \
	adapter="$(ADAPTER)"; \
	case "$$adapter" in markdown|obsidian|notion|dateien) ;; *) \
	  echo 'Unbekannter Adapter. Erlaubt: markdown, obsidian, notion, dateien.'; \
	  exit 1;; \
	esac; \
	token=$$(sed -n 's/^ICARUS_SIDECAR_TOKEN=//p' "$(ENVDATEI)"); \
	if [ -z "$$token" ]; then \
	  echo 'Lokaler Zugriffsschlüssel fehlt. Starte Kingfisher einmal neu.'; \
	  exit 1; \
	fi; \
	curl --fail-with-body --silent --show-error -X POST "$(ADRESSE)/ingest" \
	  -H "x-icarus-token: $$token" \
	  -H 'Content-Type: application/json' \
	  --data "{\"path\":\"/notizen\",\"adapter\":\"$$adapter\"}"; \
	echo

# Abschlussmeldung. Eigenes Ziel, damit `make url` dieselbe Adresse aus
# derselben Quelle zieht — eine URL, die von Hand zusammengesetzt wird, ist die
# URL, die irgendwann nicht mehr stimmt.
.PHONY: _fertig
_fertig:
	@echo "Kingfisher läuft. Diese Adresse im Browser öffnen:"
	@echo
	@$(MAKE) --no-print-directory url
	@echo
	@echo "Das Morning Briefing funktioniert lokal; Modell, Mail und Kalender sind optional."
	@echo
	@echo "  make url     die Adresse noch einmal ausgeben"
	@echo "  make logs    mitlesen, was der Sidecar tut"
	@echo "  make stop    anhalten; Gedächtnis und Schlüssel bleiben"
	@echo
	@echo "Ausführlich: docs/15-loslegen.md"

url: $(ENVDATEI) ## Lokale Kingfisher-Adresse ausgeben
	@echo "  $(ADRESSE)/today"

# Übergabe als Daten: Modellnamen werden nie Teil des Shell-Quelltexts.
modell-lokal: export MODELL := $(MODELL)
modell-lokal: $(ENVDATEI) ## Lokales Ollama-Modell verbinden: make modell-lokal MODELL=qwen3.5:4b
	@$(PY) scripts/configure_local_model.py --env-file "$(ENVDATEI)" --base-url "$(ADRESSE)"

logs: $(ENVDATEI) ## Mitlesen, was der Sidecar tut (Strg-C beendet nur das Mitlesen)
	@$(COMPOSE) logs -f

stop: $(ENVDATEI) ## Kingfisher anhalten
	@$(COMPOSE) down
	@echo
	@echo "Angehalten. Das Gedächtnis liegt weiter im Docker-Volume, die"
	@echo "Schlüssel in $(ENVDATEI). 'make start' knüpft dort wieder an."

# -- Sidecar ----------------------------------------------------------------

venv: ## Virtuelle Umgebung für den Sidecar anlegen
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@$(BIN)/pip install --quiet --upgrade pip

sidecar-dev: venv ## Sidecar samt Entwicklungsabhängigkeiten installieren (ohne cognee)
	$(BIN)/pip install -e "sidecar[dev]"
	@echo
	@echo "Installiert ohne cognee — die semantische Suche fällt auf Substringsuche"
	@echo "zurück. Für den vollen Umfang:  make sidecar-full"

sidecar-full: venv ## Sidecar mit cognee installieren (zieht ~950 MB nach)
	$(BIN)/pip install -e "sidecar[cognee,dev]"

sidecar-run: ## Sidecar roh starten, ohne Token (nur für Entwicklung)
	ICARUS_DATA_DIR=$${ICARUS_DATA_DIR:-./.icarus-data} $(BIN)/icarus-sidecar

# -- Der zweite Weg: ohne Docker --------------------------------------------
#
# `make start` braucht einen laufenden Docker-Daemon. Das ist ein halbes
# Gigabyte Fremdsoftware, die man erst installieren, starten und warten muss —
# für jemanden, der Icarus nur benutzen will, eine hohe Hürde.
#
# `make lokal` tut dasselbe ohne Docker: Python-Umgebung anlegen, Sidecar
# installieren, Token erzeugen (dasselbe wie oben, nicht schwächer), Ordner
# freigeben, starten. Ein Befehl.
#
# Der Unterschied zum Container: keine Prozessgrenze zwischen Icarus und dem
# übrigen Rechner. Wer das braucht, nimmt `make start`.
lokal: export NOTIZEN := $(NOTIZEN)
lokal: $(ENVDATEI) ## Ohne Docker starten. Ordner freigeben: make lokal NOTIZEN=~/Notizen
	@set -e; \
	test -d $(VENV) || { echo "Lege die Python-Umgebung an …"; $(PY) -m venv $(VENV); }; \
	$(BIN)/python -c "import icarus_memory" 2>/dev/null || { \
	  echo "Installiere den Sidecar (einmalig, dauert einen Moment) …"; \
	  $(BIN)/pip install --quiet --upgrade pip; \
	  $(BIN)/pip install --quiet -e "sidecar"; \
	}; \
	pfad="$$NOTIZEN"; \
	case "$$pfad" in "~"|"~/"*) pfad="$$HOME$${pfad#\~}";; esac; \
	if [ -n "$$pfad" ]; then \
	  aufgeloest=$$(cd "$$pfad" 2>/dev/null && pwd) || { \
	    echo "Den Ordner gibt es nicht: $$pfad"; exit 1; }; \
	  echo "Lese aus: $$aufgeloest"; \
	else \
	  aufgeloest=""; \
	  echo "Kein Ordner freigegeben — Icarus liest keine Dateien."; \
	  echo "Nachreichen mit:  make lokal NOTIZEN=~/Notizen"; \
	fi; \
	echo; \
	set -a; . ./$(ENVDATEI); set +a; \
	ICARUS_DATA_DIR="$${ICARUS_DATA_DIR:-$$PWD/.icarus-data}" \
	ICARUS_FILE_ROOTS="$$aufgeloest" \
	exec $(BIN)/icarus-sidecar

container: ## Container-Bild lokal bauen
	docker build -t kingfisher:local .

# Zum Starten gibt es `make start`. Das frühere `container-run` erzeugte bei
# jedem Aufruf neue Schlüssel — damit war die verschlüsselte Schlüsseldatei nach
# dem ersten Neustart unlesbar, ohne dass irgendwo stand, warum.

mcp-config: ## Konfigurationsschnipsel für die MCP-Tür ausgeben
	@echo 'In die Konfiguration des Assistenten (Claude Desktop, Claude Code, …).'
	@echo
	@echo 'Aus dieser Arbeitskopie:'
	@echo '{ "mcpServers": { "icarus": {'
	@echo '  "command": "$(abspath $(BIN))/icarus-mcp"'
	@echo '} } }'
	@echo
	@echo 'Aus der gebündelten App — eine Binary, zwei Rollen:'
	@echo '{ "mcpServers": { "icarus": {'
	@echo '  "command": "/Applications/Icarus.app/Contents/Resources/icarus-sidecar",'
	@echo '  "args": ["--mcp"]'
	@echo '} } }'
	@echo
	@echo 'Der Sidecar muss laufen — er hinterlegt Port und Token in'
	@echo 'verbindung.json. Siehe docs/07-mcp-tuer.md.'

test: ## Tests des Selbstmodells
	$(BIN)/python -m pytest sidecar/tests -q

validate-schema: ## Beispielprofil gegen das Selbstmodell-Schema validieren
	@$(BIN)/python -c "import json,jsonschema; \
s=json.load(open('$(SCHEMA)')); d=json.load(open('$(EXAMPLE)')); \
jsonschema.Draft202012Validator.check_schema(s); \
jsonschema.Draft202012Validator(s).validate(d); \
print('$(EXAMPLE) ist gegen $(SCHEMA) valide.')"

ci-lokal: ## Dieselben Prüfungen wie GitHub-CI lokal ausführen (ohne Actions-Minuten)
	@PY=$(BIN)/python scripts/ci_lokal.sh

check: test validate-schema ## Alle Prüfungen des Sidecars

# -- Sicherheit und Sicherung ----------------------------------------------

secrets-migrate: ## Schlüssel aus .env in den Schlüsselbund übernehmen
	@$(BIN)/python -c "\
from pathlib import Path; \
from icarus_memory.secrets import Keychain, migrate_env_file; \
kc = Keychain(); \
print('Schlüsselspeicher:', kc.backend); \
migrated = migrate_env_file(Path('.env'), kc); \
print('Übernommen:', ', '.join(migrated) or 'nichts'); \
print('Die .env kann nun bereinigt werden.') if migrated else None"

backup: $(ENVDATEI) ## Vollständige lokale Kingfisher-Sicherung anlegen
	@$(COMPOSE) exec -T kingfisher python -c "\
from pathlib import Path; \
from icarus_memory.backup import snapshot_all; \
print('Sicherung:', snapshot_all(Path('/data'), Path('/data/sicherungen')))"

backups: $(ENVDATEI) ## Vorhandene vollständige Sicherungen lokal auflisten
	@token=$$(sed -n 's/^ICARUS_SIDECAR_TOKEN=//p' "$(ENVDATEI)"); \
	if [ -z "$$token" ]; then \
	  echo 'Lokaler Zugriffsschlüssel fehlt. Starte Kingfisher einmal neu.'; \
	  exit 1; \
	fi; \
	curl --fail-with-body --silent --show-error "$(ADRESSE)/backups" \
	  -H "x-icarus-token: $$token"; \
	echo

# Auf die neueste veröffentlichte Fassung wechseln (docs/53-download-und-updates.md): sichern (vor-update-…), das
# fertige Bild laden, KINGFISHER_IMAGE in .kingfisher.env setzen, neu starten, auf die neue Fassung warten. Geht etwas
# schief, läuft danach wieder die Fassung von vorher, und die Ausgabe nennt `make zurueck-vor-update`.
# Eine bestimmte Fassung: make aktualisieren FASSUNG=1.2.0
aktualisieren: export FASSUNG := $(FASSUNG)
aktualisieren: $(ENVDATEI) ## Auf die neueste Fassung wechseln (vorher wird gesichert): make aktualisieren [FASSUNG=1.2.0]
	@$(PY) scripts/kingfisher_aktualisieren.py

zurueck-vor-update: $(ENVDATEI) ## Neueste Sicherung vor dem Update zurückspielen; der jetzige Stand wird beiseitegelegt
	@token=$$(sed -n 's/^ICARUS_SIDECAR_TOKEN=//p' "$(ENVDATEI)"); \
	if [ -z "$$token" ]; then \
	  echo 'Lokaler Zugriffsschlüssel fehlt. Starte Kingfisher einmal neu.'; \
	  exit 1; \
	fi; \
	name=$$(curl --fail --silent --show-error "$(ADRESSE)/backups" -H "x-icarus-token: $$token" \
	  | $(PY) -c "import json, sys; names = [b['name'] for b in json.load(sys.stdin) if b.get('before_update')]; print(names[0] if names else '')"); \
	if [ -z "$$name" ]; then \
	  echo 'Es gibt keine Sicherung vor einem Update. Es wurde nichts verändert.'; \
	  exit 1; \
	fi; \
	echo "Spiele $$name zurück. Der jetzige Stand wird beiseitegelegt, nicht gelöscht."; \
	curl --fail-with-body --silent --show-error -X POST "$(ADRESSE)/backups/restore" \
	  -H "x-icarus-token: $$token" -H 'Content-Type: application/json' \
	  -d "{\"name\": \"$$name\"}"; \
	echo

backup-auslagern: $(ENVDATEI) ## Geprüfte Sicherung in eigenen Ordner kopieren: make backup-auslagern ZIEL=~/Documents/Kingfisher-Backups
	@set -e; \
	ziel="$$ZIEL"; \
	case "$$ziel" in "~"|"~/"*) ziel="$$HOME$${ziel#\~}";; esac; \
	if [ -z "$$ziel" ]; then \
	  echo 'Bitte einen lokalen Zielordner angeben, zum Beispiel:'; \
	  echo '  make backup-auslagern ZIEL=~/Documents/Kingfisher-Backups'; \
	  exit 1; \
	fi; \
	mkdir -p "$$ziel"; \
	ziel=$$(cd "$$ziel" && pwd); \
	if [ "$$ziel" = "/" ]; then \
	  echo 'Das Wurzelverzeichnis ist kein Sicherungsziel.'; \
	  exit 1; \
	fi; \
	snapshot=$$($(COMPOSE) exec -T kingfisher python -c "from pathlib import Path; from icarus_memory.backup import snapshot_all; print(snapshot_all(Path('/data'), Path('/data/sicherungen')))" ); \
	name=$$(basename "$$snapshot"); \
	case "$$name" in kingfisher-*) ;; *) \
	  echo 'Die erstellte Sicherung hat keinen gültigen Kingfisher-Namen.'; \
	  exit 1;; \
	esac; \
	container=$$($(COMPOSE) ps -q kingfisher); \
	if [ -z "$$container" ]; then \
	  echo 'Kingfisher läuft nicht. Zuerst: make start'; \
	  exit 1; \
	fi; \
	docker cp "$$container:/data/sicherungen/$$name" "$$ziel/"; \
	echo "Vollständige, geprüfte Sicherung liegt unter: $$ziel/$$name"; \
	echo 'Bewahre diesen Ordner getrennt von diesem Mac auf. .kingfisher.env bleibt getrennt und wird nicht kopiert.'

clean: ## Build-Artefakte entfernen
	rm -rf build $(VENV) app/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
