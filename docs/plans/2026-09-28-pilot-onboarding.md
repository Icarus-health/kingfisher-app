# Approved pilot onboarding improvements

User approved the bounded in-chat design: focused setup, progressive disclosure, provider defaults, app window on existing persistent local backend, modest device/model guidance, browser-based Google OAuth where configured. No reset; no silent account permissions or model downloads; no broad redesign. Existing source/evidence and action approval rules remain intact.

## Task 1: Native window
Replace browser-only launcher with small AppKit/WKWebView wrapper around existing Docker-backed local UI. Reuse scripts/start_mac_app.py lifecycle without opening Safari. Restrict in-app navigation to configured loopback origin; external HTTPS links and OAuth use system browser. Support file chooser/downloads used by current UI, startup errors/retry, single app window, Dock reopen. Preserve same volume/environment. Existing browser starter remains fallback. New Swift source/build script owns macos/KingfisherApp.swift, scripts/build_mac_window.py and optional --no-browser argument in start_mac_app.py. No backend edits.

## Task 2: Focused settings
Existing SettingsSections/App settings flow: add first Einrichtung overview, concise status and direct next actions to named tabs; separate Mail, Kalender, lokale KI, Dokumente, Automatik, Arbeitsvorlieben, Sicherung, Erweitert. Put model routing/world controls in advanced; mail sync colocated with mail setup rather than disconnected. Known provider defaults; technical host/port fields disclosed under advanced, keep required field errors accessible. Preserve existing functions/permissions and German assets/styles. Own App.tsx settings/MailSourceForm, SettingsSections.tsx/css only. Add slots/imports for root GoogleSignIn and device helper if instructed, otherwise leave files separate.

## Task 3: Device/model help
Small macOS host helper publishes chip/memory via authenticated API or static host-report file read by Docker, not container memory as Mac RAM. Read-only, no downloads/changes. Conservative estimate and installed-model suggestions; explicit unknown when hardware info unavailable. Root integrates endpoints; agent supplies module and React component with distinct own files and tests.

## Task 4: Google OAuth
Root investigates existing integration stores/connectors and adds PKCE/state/expiry flow in external browser, encrypted persistent tokens, refresh/revoke boundaries, scopes and selected accounts. Requires user's own Desktop OAuth client configuration; never invent credentials or claim live sign-in without them. Reuse working mail/calendar adapters if possible; otherwise document unimplemented capability and disable misleading controls. Focused failure-path tests, no external transmission of real user data.

## Task 5: Integration/review/acceptance
Independent review, affected tests/build, actual native window + setup UI checks on separate test volume. Update pilot image on SAME kingfisher-pilot-data volume after backup; preserve rollback. Never reset pilot. Record exact evidence and Google registration remaining if absent.
