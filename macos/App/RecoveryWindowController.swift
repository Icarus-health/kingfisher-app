import AppKit
import WebKit

@available(macOS 11.3, *)
final class RecoveryWindowController: NSWindowController, NSWindowDelegate {
    let identifier = UUID()
    var onClose: (() -> Void)?
    private(set) var isWorking = false
    private let paths: AppPaths
    private var helper: RecoveryHelperClient?
    private var folder: URL?
    private var workingFolder: URL?
    private var selection = RecoverySelection()
    private var surface: WebSurface?
    private var closeConfirmed = false
    var draftSurface: WebSurface? { surface }
    var canReload: Bool { surface != nil && !isWorking }
    func reloadPage() { if canReload { surface?.reload(fallbackPath: "today") } }
    private let titleLabel = NSTextField(labelWithString: "Sicherung wiederherstellen")
    private let summary = NSTextField(wrappingLabelWithString: "Deine laufende Kingfisher-App bleibt unverändert.")
    private let stateLabel = NSTextField(wrappingLabelWithString: "")
    private let progress = NSProgressIndicator()
    private let choice = NSPopUpButton(frame: .zero, pullsDown: false)
    private let acknowledgement = NSButton(checkboxWithTitle: "Mir ist bewusst, dass spätere Änderungen fehlen können.", target: nil, action: nil)
    private let detailsToggle = NSButton(title: "Details anzeigen", target: nil, action: nil)
    private let detailScroll = NSScrollView()
    private let detailText = NSTextView()
    private let confirm = NSButton(title: "Arbeitskopie öffnen", target: nil, action: nil)
    private let retry = NSButton(title: "Erneut prüfen", target: nil, action: nil)
    private let reveal = NSButton(title: "Ordner zeigen", target: nil, action: nil)
    private var column: NSStackView!
    private var retryAction: (() -> Void)?

    init(paths: AppPaths) {
        self.paths = paths
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 570),
            styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Kingfisher · Wiederherstellung"
        window.minSize = NSSize(width: 640, height: 520)
        window.isReleasedWhenClosed = false
        super.init(window: window)
        window.delegate = self
        buildReview()
        window.center()
    }
    required init?(coder: NSCoder) { nil }

    private func buildReview() {
        titleLabel.font = .systemFont(ofSize: 25, weight: .semibold)
        summary.font = .systemFont(ofSize: 14)
        summary.textColor = .secondaryLabelColor
        stateLabel.font = .systemFont(ofSize: 14)
        stateLabel.setAccessibilityRole(.staticText)
        progress.style = .spinning; progress.controlSize = .small
        choice.target = self; choice.action = #selector(choiceChanged)
        choice.setAccessibilityLabel("Datenstand für die Arbeitskopie")
        acknowledgement.target = self; acknowledgement.action = #selector(acknowledgementChanged)
        detailsToggle.target = self; detailsToggle.action = #selector(toggleDetails)
        confirm.target = self; confirm.action = #selector(prepareCopy); confirm.bezelStyle = .rounded
        confirm.keyEquivalent = "\r"
        retry.target = self; retry.action = #selector(retryStep)
        reveal.target = self; reveal.action = #selector(showFolder)
        detailText.isEditable = false; detailText.isSelectable = true
        detailText.font = .systemFont(ofSize: 13)
        detailText.textContainerInset = NSSize(width: 10, height: 10)
        detailText.isVerticallyResizable = true
        detailText.autoresizingMask = [.width]
        detailText.textContainer?.widthTracksTextView = true
        detailScroll.documentView = detailText; detailScroll.hasVerticalScroller = true
        detailScroll.borderType = .bezelBorder
        let statusRow = NSStackView(views: [progress, stateLabel]); statusRow.orientation = .horizontal
        statusRow.alignment = .centerY; statusRow.spacing = 10
        let actions = NSStackView(views: [confirm, retry, reveal]); actions.spacing = 12
        column = NSStackView(views: [titleLabel, summary, statusRow, choice, detailsToggle, detailScroll, acknowledgement, actions])
        column.orientation = .vertical; column.alignment = .leading; column.spacing = 18
        column.edgeInsets = NSEdgeInsets(top: 28, left: 28, bottom: 28, right: 28)
        column.translatesAutoresizingMaskIntoConstraints = false
        let content = NSView(); window?.contentView = content; content.addSubview(column)
        NSLayoutConstraint.activate([
            column.leadingAnchor.constraint(equalTo: content.leadingAnchor), column.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            column.topAnchor.constraint(equalTo: content.topAnchor), column.bottomAnchor.constraint(lessThanOrEqualTo: content.bottomAnchor),
            summary.widthAnchor.constraint(equalTo: column.widthAnchor, constant: -56),
            statusRow.widthAnchor.constraint(equalTo: summary.widthAnchor), choice.widthAnchor.constraint(equalTo: summary.widthAnchor),
            detailScroll.widthAnchor.constraint(equalTo: summary.widthAnchor), detailScroll.heightAnchor.constraint(equalToConstant: 180),
            acknowledgement.widthAnchor.constraint(equalTo: summary.widthAnchor),
        ])
        [choice, acknowledgement, detailsToggle, detailScroll, confirm, retry, reveal, progress].forEach { $0.isHidden = true }
    }

    func begin(reopen: Bool) {
        showWindow(nil); window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        resolveHelper(reopen: reopen) { [weak self] in
            if reopen { self?.chooseWorkingFolder() } else { self?.chooseBundle() }
        }
    }

    private func resolveHelper(reopen: Bool, _ done: @escaping () -> Void) {
        setWorking("Lokale App-Version wird geprüft …")
        let paths = self.paths
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let result: Result<RecoveryHelperClient, RecoveryFailure>
            if let docker = Docker.find(), docker.isRunning(),
               let script = Bundle.main.url(forResource: "recovery-native", withExtension: "py") {
                var image = docker.installedImage(paths: paths)?.id
                if image == nil, let saved = EnvStore(file: paths.envFile).read()?.value(EnvKey.image), !saved.isEmpty {
                    let response = docker.run(["image", "inspect", "--format", "{{.Id}}", saved])
                    if response.ok { image = response.output.trimmingCharacters(in: .whitespacesAndNewlines) }
                }
                if let image = image, RecoveryReport.matches(image, "^sha256:[a-f0-9]{64}$") {
                    result = .success(RecoveryHelperClient(script: script, docker: docker.executable, image: image))
                } else if reopen {
                    // Only open accepts an empty image: the helper must find
                    // and verify the copy's own private persisted image pin.
                    result = .success(RecoveryHelperClient(script: script, docker: docker.executable, image: ""))
                } else { result = .failure(RecoveryFailure("Keine passende lokale App-Version gefunden. Bitte zuerst Kingfisher installieren oder aktualisieren; es wird nichts heruntergeladen.")) }
            } else { result = .failure(RecoveryFailure("Bitte Docker starten und prüfen, ob Kingfisher vollständig installiert ist.")) }
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.finishWorking()
                switch result {
                case .success(let helper): self.helper = helper; done()
                case .failure(let failure): self.showError(failure.message) { [weak self] in self?.resolveHelper(reopen: reopen, done) }
                }
            }
        }
    }

    private func chooseBundle() {
        guard let window = window else { return }
        titleLabel.stringValue = "Sicherung wiederherstellen"
        let panel = NSOpenPanel(); panel.canChooseFiles = true; panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false; panel.message = "Wähle deine verschlüsselte Kingfisher-Sicherung."
        panel.prompt = "Sicherung wählen"
        panel.beginSheetModal(for: window) { [weak self] response in
            guard let self = self else { return }
            if response != .OK { self.close(); return }
            guard let bundle = panel.url else { return }
            self.chooseDestination(bundle: bundle.resolvingSymlinksInPath())
        }
    }

    private func chooseDestination(bundle: URL) {
        guard let window = window else { return }
        let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true
        panel.canCreateDirectories = true; panel.allowsMultipleSelection = false
        panel.message = "Hier entsteht ein neuer, getrennter Wiederherstellungsordner. Vorhandene Dateien bleiben erhalten."
        panel.prompt = "Ablage wählen"
        panel.beginSheetModal(for: window) { [weak self] response in
            guard let self = self else { return }
            guard response == .OK, let parent = panel.url else { self.chooseBundle(); return }
            self.askPassword(bundle: bundle, parent: parent.resolvingSymlinksInPath())
        }
    }

    private func askPassword(bundle: URL, parent: URL) {
        guard let window = window else { return }
        let alert = NSAlert(); alert.messageText = "Sicherung entsperren"
        alert.informativeText = "Gib das Passwort ein, das du beim Erstellen dieser Sicherung gewählt hast."
        let input = NSSecureTextField(frame: NSRect(x: 0, y: 0, width: 360, height: 26))
        input.placeholderString = "Sicherungspasswort"; input.setAccessibilityLabel("Sicherungspasswort")
        alert.accessoryView = input; alert.addButton(withTitle: "Entschlüsseln"); alert.addButton(withTitle: "Abbrechen")
        alert.beginSheetModal(for: window) { [weak self] response in
            guard let self = self else { return }
            guard response == .alertFirstButtonReturn else { input.stringValue = ""; self.chooseBundle(); return }
            let password = input.stringValue; input.stringValue = ""
            guard !password.isEmpty else { self.askPassword(bundle: bundle, parent: parent); return }
            let session = parent.appendingPathComponent("Kingfisher-Wiederherstellung-" + UUID().uuidString, isDirectory: true)
            do {
                try FileManager.default.createDirectory(at: session, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
            } catch { self.showError("Der neue Wiederherstellungsordner konnte nicht angelegt werden.") { [weak self] in self?.chooseDestination(bundle: bundle) }; return }
            let original = session.appendingPathComponent("Original", isDirectory: true)
            self.folder = original
            self.perform("extract", fields: ["bundle":bundle.path, "target":original.path, "password":password], sentence: "Sicherung wird entschlüsselt und geprüft …", retry: { [weak self] in self?.askPassword(bundle: bundle, parent: parent) }) { [weak self] result in
                guard let self = self, self.validFolder(result, expected: original) else { return }
                self.inspect()
            }
        }
        alert.window.initialFirstResponder = input
    }

    private func chooseWorkingFolder() {
        guard let window = window else { return }
        titleLabel.stringValue = "Arbeitskopie öffnen"
        summary.stringValue = "Wähle eine bereits vorbereitete Kingfisher-Arbeitskopie. Die Haupt-App bleibt unverändert."
        let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false; panel.prompt = "Arbeitskopie wählen"
        panel.message = "Wähle den Ordner der Arbeitskopie mit data und settings.env."
        panel.beginSheetModal(for: window) { [weak self] response in
            guard let self = self else { return }
            guard response == .OK, let folder = panel.url else { self.close(); return }
            self.workingFolder = folder.resolvingSymlinksInPath(); self.openWorkingCopy()
        }
    }

    private func inspect() {
        guard let folder = folder else { return }
        perform("inspect", fields: ["folder":folder.path], sentence: "Datenstände werden verglichen …", retry: { [weak self] in self?.inspect() }) { [weak self] result in
            guard let self = self else { return }
            guard let raw = result["report"] as? [String: Any], let report = RecoveryReport(raw) else {
                self.showError("Der Prüfbericht ist unvollständig. Es wurde keine Arbeitskopie gestartet.") { [weak self] in self?.inspect() }; return
            }
            self.selection.replace(report); self.choice.removeAllItems(); self.choice.addItem(withTitle: "Datenstand auswählen …")
            for item in report.choices { self.choice.addItem(withTitle: item.title + (item.eligible ? "" : " · ungeklärt")) }
            self.choice.selectItem(at: 0); self.acknowledgement.state = .off
            self.titleLabel.stringValue = "Datenstand auswählen"
            self.summary.stringValue = "Die Arbeitskopie übernimmt den gewählten Stand. Konten, Modelle und automatische Aktionen müssen danach neu freigegeben werden."
            self.stateLabel.stringValue = "Vergleichsstände können ältere oder spätere Änderungen enthalten. Das Datum allein entscheidet nicht."
            [self.choice, self.acknowledgement, self.detailsToggle, self.confirm, self.retry, self.reveal].forEach { $0.isHidden = false }
            self.retryAction = { [weak self] in self?.inspect() }; self.retry.title = "Erneut prüfen"
            self.updateSelection()
        }
    }

    @objc private func choiceChanged() {
        let index = choice.indexOfSelectedItem - 1
        selection.choose(index >= 0 ? selection.report?.choices[index].id : nil)
        acknowledgement.state = .off; updateSelection()
    }
    @objc private func acknowledgementChanged() { selection.acknowledged = acknowledgement.state == .on; updateSelection() }
    private func updateSelection() {
        confirm.isEnabled = selection.canPrepare && !isWorking
        acknowledgement.isEnabled = selection.selected?.eligible == true && !isWorking
        if let selected = selection.selected {
            stateLabel.stringValue = selected.summary + (selected.eligible ? "" : "\nDieser Stand ist noch nicht eindeutig lesbar und kann nicht übernommen werden.")
            detailText.string = selected.detail
        } else { detailText.string = "Wähle zuerst einen Datenstand, um die enthaltenen Bereiche zu sehen." }
    }
    @objc private func toggleDetails() {
        detailScroll.isHidden.toggle(); detailsToggle.title = detailScroll.isHidden ? "Details anzeigen" : "Details ausblenden"
        if !detailScroll.isHidden, let window = window, window.frame.height < 690 { window.setContentSize(NSSize(width: max(760, window.frame.width), height: 690)) }
    }
    @objc private func prepareCopy() {
        guard selection.canPrepare, let report = selection.report, let selected = selection.selected, let folder = folder, !isWorking else { return }
        let parent = folder.deletingLastPathComponent().appendingPathComponent("Arbeitskopien", isDirectory: true)
        do { try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700]) }
        catch {
            // A previous interrupted attempt may have created this private folder.
            var directory: ObjCBool = false
            guard FileManager.default.fileExists(atPath: parent.path, isDirectory: &directory), directory.boolValue else {
                showError("Der Arbeitsordner konnte nicht angelegt werden.") { [weak self] in self?.inspect() }; return
            }
        }
        let target = parent.appendingPathComponent("Arbeitskopie-" + UUID().uuidString, isDirectory: true)
        perform("prepare", fields: ["folder":folder.path, "target":target.path, "fingerprint":report.fingerprint,
                "selection":selected.id, "acknowledge_unknown":true], sentence: "Getrennte Arbeitskopie wird vorbereitet …", retry: { [weak self] in self?.inspect() }) { [weak self] result in
            guard let self = self, self.validFolder(result, expected: target) else { return }
            self.workingFolder = target; self.openWorkingCopy()
        }
    }

    private func openWorkingCopy() {
        guard let folder = workingFolder else { return }
        perform("open", fields: ["folder":folder.path], sentence: "Deine Arbeitskopie wird geöffnet …", retry: { [weak self] in self?.openWorkingCopy() }) { [weak self] result in
            guard let self = self else { return }
            guard let address = result["url"] as? String, let url = RecoveryLocation.loopback(address),
                  let owner = result["instance_id"] as? String, let identifier = RecoveryLocation.storeIdentifier(owner),
                  let image = result["image"] as? String, RecoveryReport.matches(image, "^sha256:[a-f0-9]{64}$") else {
                self.showError("Die Arbeitskopie hat keine gültige lokale Fensteradresse geliefert.") { [weak self] in self?.openWorkingCopy() }; return
            }
            self.presentWorkingCopy(url, identifier: identifier)
        }
    }

    private func presentWorkingCopy(_ origin: URL, identifier: UUID) {
        guard let window = window else { return }
        let configuration = WKWebViewConfiguration()
        if #available(macOS 14.0, *) { configuration.websiteDataStore = WKWebsiteDataStore(forIdentifier: identifier) }
        else { configuration.websiteDataStore = .nonPersistent() }
        // No update/calendar/voice/module bridge: those belong to a specific
        // native instance and must never fall back to the personal main service.
        let surface = WebSurface(origin: origin, configuration: configuration)
        self.surface = surface; surface.window = window
        let note = NSTextField(wrappingLabelWithString:
            "Arbeitskopie mit ihrer gespeicherten App-Version · Ungesendete Entwürfe vor dem Schließen sichern. Native Kalenderfreigabe, Sprache und App-Updates sind hier noch nicht verbunden.")
        note.font = .systemFont(ofSize: 12); note.textColor = .secondaryLabelColor
        let reveal = NSButton(title: "Ordner zeigen", target: self, action: #selector(showFolder))
        let toolbar = NSStackView(views: [note, reveal]); toolbar.spacing = 12
        toolbar.edgeInsets = NSEdgeInsets(top: 8, left: 16, bottom: 8, right: 16)
        let content = NSStackView(views: [toolbar, surface.webView]); content.orientation = .vertical; content.spacing = 0
        content.distribution = .fill; content.translatesAutoresizingMaskIntoConstraints = false
        let root = NSView(); window.contentView = root; root.addSubview(content)
        NSLayoutConstraint.activate([content.leadingAnchor.constraint(equalTo: root.leadingAnchor), content.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            content.topAnchor.constraint(equalTo: root.topAnchor), content.bottomAnchor.constraint(equalTo: root.bottomAnchor),
            toolbar.widthAnchor.constraint(equalTo: content.widthAnchor), surface.webView.widthAnchor.constraint(equalTo: content.widthAnchor)])
        surface.webView.setContentHuggingPriority(.defaultLow, for: .vertical)
        surface.onFailure = { message in note.stringValue = message + " · Erneut öffnen ist über das App-Menü möglich." }
        window.title = "Kingfisher · Arbeitskopie"
        window.minSize = NSSize(width: 900, height: 620); window.setContentSize(NSSize(width: 1280, height: 860))
        surface.load(path: "today")
    }

    private func validFolder(_ response: [String: Any], expected: URL) -> Bool {
        guard let value = response["folder"] as? String, URL(fileURLWithPath: value).standardizedFileURL == expected.standardizedFileURL else {
            showError("Der Helfer hat einen unerwarteten Zielordner gemeldet. Bitte den angelegten Ordner prüfen.") { [weak self] in self?.showFolder() }; return false
        }
        return true
    }
    private func perform(_ operation: String, fields: [String: Any], sentence: String,
                         retry: @escaping () -> Void, success: @escaping ([String: Any]) -> Void) {
        guard !isWorking, let helper = helper else { return }
        setWorking(sentence)
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let result = helper.request(operation, fields: fields)
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.finishWorking()
                switch result { case .success(let response): success(response)
                case .failure(let failure): self.showError(failure.message, retry: retry) }
            }
        }
    }
    private func setWorking(_ sentence: String) {
        isWorking = true; stateLabel.stringValue = sentence
        progress.isHidden = false; progress.startAnimation(nil)
        [choice, acknowledgement, confirm, retry, detailsToggle].forEach { $0.isEnabled = false }
        retryAction = nil
    }
    private func finishWorking() {
        isWorking = false; progress.stopAnimation(nil); progress.isHidden = true
        [choice, retry, detailsToggle].forEach { $0.isEnabled = true }; updateSelection()
    }
    private func showError(_ message: String, retry: @escaping () -> Void) {
        selection.acknowledged = false; acknowledgement.state = .off
        stateLabel.stringValue = message; retryAction = retry
        self.retry.title = "Erneut versuchen"; self.retry.isHidden = false; self.retry.isEnabled = true
        reveal.isHidden = folder == nil && workingFolder == nil
        confirm.isEnabled = false
    }
    @objc private func retryStep() { if !isWorking { retryAction?() } }
    @objc private func showFolder() {
        if let folder = workingFolder ?? folder { NSWorkspace.shared.activateFileViewerSelecting([folder]) }
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if isWorking {
            let alert = NSAlert(); alert.messageText = "Dieser Schritt läuft noch"
            alert.informativeText = "Bitte warte, bis der aktuelle Schritt beendet ist. Die laufende Haupt-App bleibt unverändert."
            alert.beginSheetModal(for: sender); return false
        }
        if let surface = surface, !closeConfirmed {
            surface.confirmLeaving { [weak self] in
                self?.closeConfirmed = true
                self?.close()
            }
            return false
        }
        return true
    }
    func windowWillClose(_ notification: Notification) { surface?.cancelDownloads(); onClose?() }
}
