import AppKit
import WebKit

// Die geladene App (Kingfisher.dmg): ein Fenster mit der Seite von Kingfisher. Davor, solange nötig, eine
// native Ansicht mit einem Satz – beim Einrichten, beim Starten und während eines Updates.
// Keine Fachlogik: Die steckt im Container.

@available(macOS 11.3, *)
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, NSMenuItemValidation {
    private var window: NSWindow!
    private var surface: WebSurface!
    private var voice: NativeVoiceEngine?
    private var voiceTimer: Timer?
    private let status = StatusView()
    private let hint = HintBar()
    private var paths: AppPaths?
    private var startup: Startup?
    private var updater: Updater?
    private var moduleManager: ModuleRuntimeManager?
    private var moduleSetup: ModuleSetupWork?
    private var moduleSetupTimer: Timer?
    private var moduleStatusSequence = 0
    private var moduleStatusRunning = false
    private var moduleStatusObserver: (generation: Int, sequence: Int)?
    private var moduleTerminationPending = false
    private var powerReporter: PowerReporter?
    private var calendarReporter: CalendarReporter?
    private var notificationReporter: NotificationReporter?
    private var recoveryWindows: [RecoveryWindowController] = []
    private var recoveryQuitConfirmed = false
    /// Start oder Update laufen; dann gelten weder Neu laden noch eine zweite Anfrage.
    private var busy = false
    private var updating = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        installMenu()
        buildWindow()
        guard let paths = AppPaths.standard() else {
            status.show(StatusContent(title: nil, sentence: "Diese App ist unvollständig. Lade Kingfisher bitte neu herunter.",
                                      busy: false, actions: []))
            return
        }
        self.paths = paths
        let modules = ModuleRuntimeManager(paths: paths)
        moduleManager = modules
        startup = Startup(paths: paths, modules: modules)
        updater = Updater(paths: paths, modules: modules)
        start()
    }

    // MARK: Fenster

    private func buildWindow() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Kingfisher"
        window.minSize = NSSize(width: 900, height: 620)
        window.center()
        window.setFrameAutosaveName("Kingfisher")
        window.isReleasedWhenClosed = false

        // Die Brücke: Nur die Seite von Kingfisher selbst kann ein Update anfragen (BridgeHandler prüft das).
        let configuration = WKWebViewConfiguration()
        voice = NativeVoiceEngine(reader: AppleLocalVoiceReader(), speaker: AppleLocalVoiceSpeaker(), emit: { [weak self] event in
            self?.deliverVoice(event)
        })
        let bridge = BridgeHandler(origin: AppPaths.origin, onUpdate: { [weak self] request in self?.requestUpdate(request) },
                                   onCalendar: { [weak self] request in
            guard let self = self, !self.busy else { return }
            self.calendarReporter?.requestPermission(generation: request.generation)
        }, onVoice: { [weak self] request in self?.requestVoice(request) },
           onModules: { [weak self] request in self?.requestModules(request) })
        configuration.userContentController.add(bridge, name: UpdateRequest.bridgeName)
        surface = WebSurface(origin: AppPaths.origin, configuration: configuration)
        surface.window = window
        window.delegate = self
        surface.onLeave = { [weak self] in
            self?.stopVoice()
            self?.moduleSetup?.cancellation.cancel()
            self?.moduleStatusSequence += 1
            self?.moduleStatusObserver = nil
        }
        surface.onLoaded = { [weak self] in
            guard let self = self, !self.busy else { return }
            self.status.isHidden = true
        }
        surface.onFailure = { [weak self] message in
            guard let self = self, !self.busy else { return }
            self.status.show(StatusContent(title: nil, sentence: message, busy: false,
                                           actions: [StatusAction(title: Knopf.nochmalVersuchen) { self.start() }]))
        }

        // Seite und Hinweiszeile untereinander; eine ausgeblendete Zeile nimmt im Stapel keinen Platz ein.
        let page = surface.webView
        let column = NSStackView(views: [page, hint])
        column.orientation = .vertical
        column.spacing = 0
        column.distribution = .fill
        page.setContentHuggingPriority(.defaultLow, for: .vertical)
        hint.setContentHuggingPriority(.required, for: .vertical)
        let content = NSView()
        window.contentView = content
        for view in [column, status] as [NSView] {
            view.translatesAutoresizingMaskIntoConstraints = false
            content.addSubview(view)
            NSLayoutConstraint.activate([
                view.leadingAnchor.constraint(equalTo: content.leadingAnchor),
                view.trailingAnchor.constraint(equalTo: content.trailingAnchor),
                view.topAnchor.constraint(equalTo: content.topAnchor),
                view.bottomAnchor.constraint(equalTo: content.bottomAnchor),
            ])
        }
        NSLayoutConstraint.activate([
            page.widthAnchor.constraint(equalTo: column.widthAnchor),
            hint.widthAnchor.constraint(equalTo: column.widthAnchor),
        ])
        status.show(.working(Satz.starten))
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func installMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        let restore = appMenu.addItem(withTitle: "Sicherung wiederherstellen …", action: #selector(restoreBackup), keyEquivalent: "")
        restore.target = self
        let reopen = appMenu.addItem(withTitle: "Arbeitskopie öffnen …", action: #selector(openRecoveryCopy), keyEquivalent: "")
        reopen.target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Kingfisher beenden", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let editItem = NSMenuItem()
        main.addItem(editItem)
        let edit = NSMenu(title: "Bearbeiten")
        editItem.submenu = edit
        edit.addItem(withTitle: "Rückgängig", action: Selector(("undo:")), keyEquivalent: "z")
        edit.addItem(withTitle: "Ausschneiden", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Kopieren", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Einfügen", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Alles auswählen", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        let viewItem = NSMenuItem()
        main.addItem(viewItem)
        let view = NSMenu(title: "Ansicht")
        viewItem.submenu = view
        let reload = view.addItem(withTitle: "Neu laden", action: #selector(reloadPage), keyEquivalent: "r")
        reload.target = self
        NSApp.mainMenu = main
    }

    private var activeReloadTarget: RecoveryReloadTarget {
        guard let active = NSApp.keyWindow, active.attachedSheet == nil else { return .none }
        let recovery = recoveryWindows.first { $0.window === active }
        return RecoveryReloadTarget.resolve(mainIsKey: active === window, mainBusy: busy,
            recoveryID: recovery?.identifier, recoveryReady: recovery?.canReload == true)
    }
    func validateMenuItem(_ menuItem: NSMenuItem) -> Bool {
        if menuItem.action == #selector(reloadPage) { return activeReloadTarget != .none }
        return true
    }
    @objc private func reloadPage() {
        switch activeReloadTarget {
        case .main: surface.reload(fallbackPath: AppPaths.startPage)
        case .recovery(let identifier): recoveryWindows.first { $0.identifier == identifier }?.reloadPage()
        case .none: break
        }
    }

    @objc private func restoreBackup() { beginRecovery(reopen: false) }
    @objc private func openRecoveryCopy() { beginRecovery(reopen: true) }
    private func beginRecovery(reopen: Bool) {
        guard !updating, let paths = paths else {
            let alert = NSAlert(); alert.messageText = "Wiederherstellung noch nicht möglich"
            alert.informativeText = updating ? Satz.updateLaeuft : "Bitte die Kingfisher-Installation prüfen."
            alert.beginSheetModal(for: window); return
        }
        let controller = RecoveryWindowController(paths: paths)
        let identifier = controller.identifier
        controller.onClose = { [weak self] in self?.recoveryWindows.removeAll { $0.identifier == identifier } }
        recoveryWindows.append(controller)
        controller.begin(reopen: reopen)
    }

    // MARK: Start

    private func start() {
        guard !busy, let startup = startup else { return }
        busy = true
        status.show(.working(Satz.starten))
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let outcome = startup.run { sentence in
                DispatchQueue.main.async { self?.status.show(.working(sentence)) }
            }
            DispatchQueue.main.async { self?.finishStart(outcome) }
        }
    }

    private func finishStart(_ outcome: StartOutcome) {
        busy = false
        let again = StatusAction(title: Knopf.nochmalPruefen) { [weak self] in self?.start() }
        switch outcome {
        case .ready(let ollamaHint):
            if let paths = paths, calendarReporter == nil {
                let reporter = CalendarReporter(origin: AppPaths.origin, tokenFile: paths.envFile, reader: EventKitCalendar())
                calendarReporter = reporter
                reporter.start()
            }
            if let paths = paths, powerReporter == nil {
                let reporter = PowerReporter(origin: AppPaths.origin, tokenFile: paths.envFile)
                powerReporter = reporter
                reporter.start()
            }
            if let paths = paths, notificationReporter == nil {
                // Mitteilungen (Etappe 5): fragt den Sidecar, zeigt Systemmitteilungen; „Öffnen“ führt auf die Seite.
                let reporter = NotificationReporter(origin: AppPaths.origin, tokenFile: paths.envFile,
                                                    onOpen: { [weak self] pfad in self?.openPage(pfad) })
                notificationReporter = reporter
                reporter.start()
            }
            status.show(.working(Satz.starten))
            hint.isHidden = true
            switch ollamaHint {
            case .none:
                break
            case .start:
                hint.show(Satz.ollamaStarten, linkTitle: Knopf.ollamaStarten, url: Adresse.ollamaApp)
            case .download:
                hint.show(Satz.ollamaFehlt, linkTitle: Knopf.ollamaLaden, url: Adresse.ollamaDownload)
            }
            surface.load(path: AppPaths.startPage)
        case .dockerMissing:
            status.show(StatusContent(title: nil, sentence: Satz.dockerFehlt, busy: false, actions: [
                StatusAction(title: Knopf.dockerLaden) { _ = NSWorkspace.shared.open(Adresse.dockerDownload) }, again]))
        case .dockerSilent:
            status.show(StatusContent(title: nil, sentence: Satz.dockerStumm, busy: false, actions: [again]))
        case .composeMissing:
            status.show(StatusContent(title: nil, sentence: Satz.composeFehlt, busy: false, actions: [
                StatusAction(title: Knopf.dockerLaden) { _ = NSWorkspace.shared.open(Adresse.dockerDownload) }, again]))
        case .keysMissing:
            askForKeyFile(Satz.schluesselGesucht)
        case .failed(let sentence):
            status.show(StatusContent(title: nil, sentence: sentence, busy: false, actions: [
                StatusAction(title: Knopf.nochmalVersuchen) { [weak self] in self?.start() }]))
        }
    }

    /// Eine Mitteilung wurde angeklickt: das Fenster nach vorn und die Seite dazu, nur eine der eigenen Adresse.
    private func openPage(_ pfad: String) {
        guard !busy else { return }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        surface.open(pfad: pfad)
    }

    /// Es gibt Daten, aber keinen Schlüssel: Der Mensch zeigt die Datei, statt einen Pfad zu tippen.
    private func askForKeyFile(_ sentence: String) {
        status.show(StatusContent(title: nil, sentence: sentence, busy: false, actions: [
            StatusAction(title: Knopf.dateiWaehlen) { [weak self] in self?.chooseKeyFile() }]))
    }

    private func chooseKeyFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.showsHiddenFiles = true
        panel.message = Satz.schluesselGesucht
        panel.beginSheetModal(for: window) { [weak self] result in
            guard let self = self, result == .OK, let url = panel.url else { return }
            if self.startup?.adopt(fileAt: url) == true { self.start() } else { self.askForKeyFile(Satz.schluesselUngueltig) }
        }
    }

    // MARK: Update über die Brücke

    /// Nur nach einer Nachricht der Seite, also nach einem Klick des Menschen dort. Nie von selbst.
    private func requestUpdate(_ request: UpdateRequest) {
        guard !busy, let updater = updater else { return }
        moduleSetup?.cancellation.cancel()
        moduleStatusSequence += 1
        moduleStatusObserver = nil
        busy = true
        updating = true
        calendarReporter?.stop()
        calendarReporter = nil
        hint.isHidden = true
        status.show(.working(Satz.platzPruefen, title: Satz.aktualisieren))
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let result = updater.perform(request) { sentence in
                DispatchQueue.main.async { self?.status.show(.working(sentence, title: Satz.aktualisieren)) }
            }
            DispatchQueue.main.async { self?.finishUpdate(result) }
        }
    }

    private func finishUpdate(_ result: UpdateResult) {
        busy = false
        updating = false
        let mayResume: Bool
        switch result { case .updated, .storageBlocked, .notStarted: mayResume = true
        case .rolledBack, .broken: mayResume = false }
        if mayResume, let paths = paths {
            let reporter = CalendarReporter(origin: AppPaths.origin, tokenFile: paths.envFile, reader: EventKitCalendar())
            calendarReporter = reporter
            reporter.start()
        }
        let reload = StatusAction(title: Knopf.weiter) { [weak self] in
            guard let self = self else { return }
            self.status.show(.working(Satz.starten))
            self.surface.reload(fallbackPath: AppPaths.startPage)
        }
        switch result {
        case .updated:
            status.show(.working(Satz.starten))
            surface.reload(fallbackPath: AppPaths.startPage)
        case .storageBlocked(_, let issue):
            status.show(StatusContent(title: nil, sentence: Satz.updateSpeicherBlockiert(issue), busy: false,
                                      actions: [reload]))
        case .notStarted(let old):
            status.show(StatusContent(title: nil, sentence: Satz.updateNichtBegonnen(alteFassung: old), busy: false,
                                      actions: [reload]))
        case .rolledBack(let old):
            status.show(StatusContent(title: nil, sentence: Satz.updateGescheitert(alteFassung: old), busy: false,
                                      actions: [reload]))
        case .broken:
            status.show(StatusContent(title: nil, sentence: Satz.updateKaputt, busy: false, actions: [
                StatusAction(title: Knopf.nochmalVersuchen) { [weak self] in self?.start() }]))
        }
    }

    // MARK: Programm

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if recoveryWindows.contains(where: { $0.isWorking }) {
            let alert = NSAlert(); alert.messageText = "Wiederherstellung läuft"
            alert.informativeText = "Bitte warte, bis der aktuelle Schritt beendet ist. Die angelegten Ordner bleiben erhalten."
            alert.beginSheetModal(for: window)
            return .terminateCancel
        }
        if !recoveryQuitConfirmed && recoveryWindows.contains(where: { $0.needsDraftQuitConfirmation }) {
            let alert = NSAlert(); alert.messageText = "Arbeitskopie und Kingfisher schließen?"
            alert.informativeText = "Ungesendete Gesprächsentwürfe in den Arbeitskopien können beim Beenden verloren gehen. Bereits gespeicherte Daten bleiben erhalten."
            alert.addButton(withTitle: "Offen lassen"); alert.addButton(withTitle: "Schließen")
            alert.beginSheetModal(for: window) { [weak self] response in
                if response == .alertSecondButtonReturn {
                    self?.recoveryQuitConfirmed = true
                    NSApp.terminate(nil)
                    // A different guard may cancel quitting. Do not waive a
                    // later confirmation or this window's own close warning.
                    self?.recoveryQuitConfirmed = false
                }
            }
            return .terminateCancel
        }
        guard updating else {
            guard moduleManager != nil else { return .terminateNow }
            if moduleTerminationPending { return .terminateLater }
            moduleTerminationPending = true
            moduleSetup?.cancellation.cancel()
            // Setup owns cleanup until its actual callback returns. Quitting
            // must not leave a public builder or agent process behind.
            if moduleSetup == nil { finishModuleTermination() }
            return .terminateLater
        }
        let alert = NSAlert()
        alert.messageText = "Kingfisher"
        alert.informativeText = Satz.updateLaeuft
        alert.beginSheetModal(for: window)
        return .terminateCancel
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        stopVoice()
        calendarReporter?.stop()
        powerReporter?.stop()
        notificationReporter?.stop()
        surface?.cancelDownloads()
    }

    func applicationDidResignActive(_ notification: Notification) { stopVoice() }
    func windowDidResignKey(_ notification: Notification) { stopVoice() }
    func windowWillClose(_ notification: Notification) { stopVoice() }

    private func stopVoice() {
        voice?.suspend(); voiceTimer?.invalidate(); voiceTimer = nil
    }

    private func requestVoice(_ request: VoiceRequest) {
        guard let page = surface?.webView.url, sameOrigin(page, AppPaths.origin), page.path.hasPrefix("/conversations/") else { return }
        voice?.handle(request, allowed: { [weak self] in
            guard let self = self else { return false }
            return NSApp.isActive && self.window.isKeyWindow && self.surface.webView.url == page && !self.busy
        })
        guard voice?.hasWork == true, voiceTimer == nil else { return }
        voiceTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] timer in
            self?.voice?.tick()
            if self?.voice?.hasWork != true { timer.invalidate(); self?.voiceTimer = nil }
        }
    }

    private func deliverVoice(_ event: VoiceEvent) {
        guard let data = try? JSONSerialization.data(withJSONObject: event.dictionary) else { return }
        let encoded = data.base64EncodedString()
        surface?.webView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('kingfisher:voice',{detail:JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('\(encoded)'),c=>c.charCodeAt(0))))}))")
    }

    private final class ModuleSetupWork {
        let generation: Int
        let cancellation = ModuleSetupCancellation()
        var observer: Int?
        var phase: ModuleSetupPhase = .checking
        init(generation: Int) { self.generation = generation }
        var generations: Set<Int> { Set([generation] + (observer.map { [$0] } ?? [])) }
    }

    /// Called only by the existing same-origin, main-frame native bridge.
    /// No setup starts from status, page load or ordinary app startup.
    private func requestModules(_ request: ModuleSetupRequest) {
        guard let manager = moduleManager else {
            deliverModule(generation: request.generation, phase: .unavailable)
            return
        }
        switch request.action {
        case .cancel:
            guard let work = moduleSetup, work.generations.contains(request.generation) else {
                // A cancellation of an already completed setup is reconciled
                // from actual state; it never starts a second operation.
                requestModules(ModuleSetupRequest(message: ["aktion": "lokaleWerkzeugeStatus",
                    "generation": request.generation])!)
                return
            }
            work.cancellation.cancel()
        case .status:
            if let work = moduleSetup {
                work.observer = request.generation
                deliverModule(generation: request.generation, phase: work.phase)
                return
            }
            moduleStatusObserver = (request.generation, moduleStatusSequence)
            deliverModule(generation: request.generation, phase: .checking)
            readModuleStatus(manager)
        case .setup:
            if let work = moduleSetup {
                work.observer = request.generation
                deliverModule(generation: request.generation, phase: work.phase)
                return
            }
            guard !busy, !moduleTerminationPending else {
                deliverModule(generation: request.generation, phase: .failed)
                return
            }
            moduleStatusSequence += 1
            moduleStatusObserver = nil
            let work = ModuleSetupWork(generation: request.generation)
            moduleSetup = work
            deliverModule(generation: work.generation, phase: .checking)
            // Long public downloads/builds can be quiet. Repeat only the actual
            // current phase, without extra Docker/model/status requests.
            moduleSetupTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] timer in
                guard let self = self, self.moduleSetup === work else { timer.invalidate(); return }
                guard !work.cancellation.isCancelled() else { return }
                for generation in work.generations { self.deliverModule(generation: generation, phase: work.phase) }
            }
            DispatchQueue.global(qos: .utility).async { [weak self] in
                let outcome: ModuleSetupPhase
                do {
                    try manager.prepareAndStart(progress: { phase in
                        DispatchQueue.main.async {
                            guard let self = self, self.moduleSetup === work else { return }
                            work.phase = phase
                            for generation in work.generations { self.deliverModule(generation: generation, phase: phase) }
                        }
                    }, cancelled: { work.cancellation.isCancelled() })
                    outcome = .ready
                } catch {
                    outcome = work.cancellation.isCancelled() ? .cancelled : .failed
                }
                DispatchQueue.main.async {
                    guard let self = self, self.moduleSetup === work else { return }
                    self.moduleSetupTimer?.invalidate()
                    self.moduleSetupTimer = nil
                    for generation in work.generations { self.deliverModule(generation: generation, phase: outcome) }
                    self.moduleSetup = nil
                    if self.moduleTerminationPending { self.finishModuleTermination() }
                }
            }
        }
    }

    /// Repeated status clicks share one actual metadata callback. A replaced
    /// page gets one fresh read after the former callback exits, never a queue.
    private func readModuleStatus(_ manager: ModuleRuntimeManager) {
        guard !moduleStatusRunning, let observer = moduleStatusObserver else { return }
        moduleStatusRunning = true
        let sequence = observer.sequence
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let phase = manager.status()
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.moduleStatusRunning = false
                guard self.moduleSetup == nil, let latest = self.moduleStatusObserver else { return }
                guard latest.sequence == self.moduleStatusSequence else {
                    self.moduleStatusObserver = nil
                    return
                }
                if sequence != latest.sequence {
                    self.readModuleStatus(manager)
                    return
                }
                self.moduleStatusObserver = nil
                self.deliverModule(generation: latest.generation, phase: phase)
            }
        }
    }

    private func deliverModule(generation: Int, phase: ModuleSetupPhase) {
        guard let data = try? JSONSerialization.data(withJSONObject:
            ["generation": generation, "status": phase.rawValue]) else { return }
        let encoded = data.base64EncodedString()
        surface?.webView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('kingfisher:local-modules',{detail:JSON.parse(atob('\(encoded)'))}))")
    }

    private func finishModuleTermination() {
        guard let manager = moduleManager else {
            DispatchQueue.main.async { NSApp.reply(toApplicationShouldTerminate: true) }
            return
        }
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let quiet = manager.stopBeforeMaintenance()
            DispatchQueue.main.async {
                self?.moduleTerminationPending = false
                NSApp.reply(toApplicationShouldTerminate: quiet)
                if !quiet {
                    self?.status.show(StatusContent(title: nil,
                        sentence: "Die lokale Prüfung wird noch beendet. Bitte kurz warten und erneut schließen.",
                        busy: false, actions: []))
                }
            }
        }
    }
}

/// Nimmt Nachrichten der Seite an. Nur aus dem Hauptrahmen der eigenen Adresse; alles andere wird ignoriert.
/// Hält die App nur schwach über den Rückruf: WKUserContentController hält seine Handler fest.
final class BridgeHandler: NSObject, WKScriptMessageHandler {
    private let origin: URL
    private let onUpdate: (UpdateRequest) -> Void
    private let onCalendar: (CalendarPermissionRequest) -> Void
    private let onVoice: (VoiceRequest) -> Void
    private let onModules: (ModuleSetupRequest) -> Void

    init(origin: URL, onUpdate: @escaping (UpdateRequest) -> Void,
         onCalendar: @escaping (CalendarPermissionRequest) -> Void = { _ in },
         onVoice: @escaping (VoiceRequest) -> Void = { _ in },
         onModules: @escaping (ModuleSetupRequest) -> Void = { _ in }) {
        self.origin = origin
        self.onUpdate = onUpdate
        self.onCalendar = onCalendar
        self.onVoice = onVoice
        self.onModules = onModules
    }

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        let source = message.frameInfo.securityOrigin
        guard message.name == UpdateRequest.bridgeName, message.frameInfo.isMainFrame,
              source.protocol == origin.scheme, source.host == origin.host, source.port == origin.port else { return }
        if let voice = VoiceRequest(message: message.body) { onVoice(voice) }
        else if let modules = ModuleSetupRequest(message: message.body) { onModules(modules) }
        else if let calendar = CalendarPermissionRequest(message: message.body) { onCalendar(calendar) }
        else if let request = UpdateRequest(message: message.body) { onUpdate(request) }
    }
}

@main
struct KingfisherDownloadApp {
    static func main() {
        if #available(macOS 11.3, *) {
            let application = NSApplication.shared
            let delegate = AppDelegate()
            application.setActivationPolicy(.regular)
            application.delegate = delegate
            withExtendedLifetime(delegate) { application.run() }
        }
    }
}
