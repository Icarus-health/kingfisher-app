import AppKit
import WebKit

// Die geladene App (Kingfisher.dmg): ein Fenster mit der Seite von Kingfisher. Davor, solange nötig, eine
// native Ansicht mit einem Satz – beim Einrichten, beim Starten und während eines Updates.
// Keine Fachlogik: Die steckt im Container.

@available(macOS 11.3, *)
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var surface: WebSurface!
    private let status = StatusView()
    private let hint = HintBar()
    private var paths: AppPaths?
    private var startup: Startup?
    private var updater: Updater?
    private var powerReporter: PowerReporter?
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
        startup = Startup(paths: paths)
        updater = Updater(paths: paths)
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
        let bridge = BridgeHandler(origin: AppPaths.origin) { [weak self] request in self?.requestUpdate(request) }
        configuration.userContentController.add(bridge, name: UpdateRequest.bridgeName)
        surface = WebSurface(origin: AppPaths.origin, configuration: configuration)
        surface.window = window
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

    @objc private func reloadPage() { if !busy { surface.reload(fallbackPath: AppPaths.startPage) } }

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
        case .ready(let ollamaMissing):
            if let paths = paths, powerReporter == nil {
                let reporter = PowerReporter(origin: AppPaths.origin, tokenFile: paths.envFile)
                powerReporter = reporter
                reporter.start()
            }
            status.show(.working(Satz.starten))
            if ollamaMissing { hint.show(Satz.ollamaFehlt, linkTitle: Knopf.ollamaLaden, url: Adresse.ollamaDownload) }
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
        busy = true
        updating = true
        hint.isHidden = true
        status.show(.working(Satz.schritt(.backup), title: Satz.aktualisieren))
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
        let reload = StatusAction(title: Knopf.weiter) { [weak self] in
            guard let self = self else { return }
            self.status.show(.working(Satz.starten))
            self.surface.reload(fallbackPath: AppPaths.startPage)
        }
        switch result {
        case .updated:
            status.show(.working(Satz.starten))
            surface.reload(fallbackPath: AppPaths.startPage)
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
        guard updating else { return .terminateNow }
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
        powerReporter?.stop()
        surface?.cancelDownloads()
    }
}

/// Nimmt Nachrichten der Seite an. Nur aus dem Hauptrahmen der eigenen Adresse; alles andere wird ignoriert.
/// Hält die App nur schwach über den Rückruf: WKUserContentController hält seine Handler fest.
final class BridgeHandler: NSObject, WKScriptMessageHandler {
    private let origin: URL
    private let onUpdate: (UpdateRequest) -> Void

    init(origin: URL, onUpdate: @escaping (UpdateRequest) -> Void) {
        self.origin = origin
        self.onUpdate = onUpdate
    }

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        let source = message.frameInfo.securityOrigin
        guard message.name == UpdateRequest.bridgeName, message.frameInfo.isMainFrame,
              source.protocol == origin.scheme, source.host == origin.host, source.port == origin.port,
              let request = UpdateRequest(message: message.body) else { return }
        onUpdate(request)
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
