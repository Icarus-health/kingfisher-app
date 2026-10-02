import AppKit

// Die native Ansicht, solange die Seite nicht da ist: ein Satz, wenn nötig ein Fortschritt und höchstens
// zwei Knöpfe. Ruhig wie docs/16-gestaltung.md: kühles Leinen, Tinte, ein gedeckter Akzent.

enum Theme {
    static let ground = dynamic(light: 0xf4f4f1, dark: 0x16191a)
    static let ink = dynamic(light: 0x171a1a, dark: 0xe9ecea)
    static let quiet = dynamic(light: 0x5b6163, dark: 0xa9b0b2)
    static let accent = dynamic(light: 0x2f5069, dark: 0x7ba7c4)
    static let surface = dynamic(light: 0xfcfcfa, dark: 0x212527)

    private static func dynamic(light: Int, dark: Int) -> NSColor {
        NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            return Theme.color(isDark ? dark : light)
        }
    }

    private static func color(_ hex: Int) -> NSColor {
        NSColor(srgbRed: CGFloat((hex >> 16) & 0xff) / 255, green: CGFloat((hex >> 8) & 0xff) / 255,
                blue: CGFloat(hex & 0xff) / 255, alpha: 1)
    }
}

/// Ein Knopf der Ansicht: Beschriftung und was er tut.
struct StatusAction {
    let title: String
    let perform: () -> Void
}

/// Was die Ansicht zeigt.
struct StatusContent {
    var title: String?
    var sentence: String
    var busy: Bool
    var actions: [StatusAction]

    /// Ein Satz mit Fortschritt, ohne Knöpfe.
    static func working(_ sentence: String, title: String? = nil) -> StatusContent {
        StatusContent(title: title, sentence: sentence, busy: true, actions: [])
    }
}

final class StatusView: NSView {
    private let titleLabel = NSTextField(labelWithString: "")
    private let sentenceLabel = NSTextField(wrappingLabelWithString: "")
    private let spinner = NSProgressIndicator()
    private let buttons = NSStackView()
    private var actions: [StatusAction] = []

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        titleLabel.font = NSFont.systemFont(ofSize: 22, weight: .semibold)
        titleLabel.textColor = Theme.ink
        titleLabel.alignment = .center
        sentenceLabel.font = NSFont.systemFont(ofSize: 16)
        sentenceLabel.textColor = Theme.ink
        sentenceLabel.alignment = .center
        sentenceLabel.preferredMaxLayoutWidth = 520
        spinner.style = .spinning
        spinner.controlSize = .regular
        buttons.orientation = .horizontal
        buttons.spacing = 12
        let stack = NSStackView(views: [titleLabel, sentenceLabel, spinner, buttons])
        stack.orientation = .vertical
        stack.alignment = .centerX
        stack.spacing = 20
        stack.translatesAutoresizingMaskIntoConstraints = false
        addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: centerYAnchor),
            stack.widthAnchor.constraint(lessThanOrEqualToConstant: 560),
            stack.leadingAnchor.constraint(greaterThanOrEqualTo: leadingAnchor, constant: 32),
            sentenceLabel.widthAnchor.constraint(lessThanOrEqualToConstant: 560),
        ])
    }

    required init?(coder: NSCoder) { return nil }

    override var wantsUpdateLayer: Bool { true }

    override func updateLayer() { layer?.backgroundColor = Theme.ground.cgColor }

    func show(_ content: StatusContent) {
        isHidden = false
        titleLabel.stringValue = content.title ?? ""
        titleLabel.isHidden = content.title == nil
        sentenceLabel.stringValue = content.sentence
        spinner.isHidden = !content.busy
        if content.busy { spinner.startAnimation(nil) } else { spinner.stopAnimation(nil) }
        actions = content.actions
        buttons.arrangedSubviews.forEach { $0.removeFromSuperview() }
        for (index, action) in content.actions.enumerated() {
            let button = NSButton(title: action.title, target: self, action: #selector(pressed(_:)))
            button.tag = index
            button.bezelStyle = .rounded
            button.controlSize = .large
            if index == 0 {
                button.keyEquivalent = "\r"
                button.bezelColor = Theme.accent
            }
            buttons.addArrangedSubview(button)
        }
        buttons.isHidden = content.actions.isEmpty
        needsDisplay = true
    }

    @objc private func pressed(_ sender: NSButton) {
        guard actions.indices.contains(sender.tag) else { return }
        actions[sender.tag].perform()
    }
}

/// Eine schmale Zeile unter der Seite für einen Hinweis, der nicht aufhält (etwa: Ollama fehlt).
final class HintBar: NSView {
    private let label = NSTextField(wrappingLabelWithString: "")
    private let link = NSButton(title: "", target: nil, action: nil)
    private let close = NSButton(title: "Ausblenden", target: nil, action: nil)
    private var url: URL?

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        label.font = NSFont.systemFont(ofSize: 13)
        label.textColor = Theme.ink
        label.preferredMaxLayoutWidth = 640
        link.bezelStyle = .rounded
        link.target = self
        link.action = #selector(openLink)
        close.bezelStyle = .inline
        close.isBordered = false
        close.contentTintColor = Theme.quiet
        close.target = self
        close.action = #selector(dismiss)
        let row = NSStackView(views: [label, link, close])
        row.orientation = .horizontal
        row.spacing = 12
        row.edgeInsets = NSEdgeInsets(top: 10, left: 20, bottom: 10, right: 20)
        row.translatesAutoresizingMaskIntoConstraints = false
        label.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        addSubview(row)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: leadingAnchor),
            row.trailingAnchor.constraint(equalTo: trailingAnchor),
            row.topAnchor.constraint(equalTo: topAnchor),
            row.bottomAnchor.constraint(equalTo: bottomAnchor),
        ])
        isHidden = true
    }

    required init?(coder: NSCoder) { return nil }

    override var wantsUpdateLayer: Bool { true }

    override func updateLayer() { layer?.backgroundColor = Theme.surface.cgColor }

    func show(_ sentence: String, linkTitle: String, url: URL) {
        label.stringValue = sentence
        link.title = linkTitle
        self.url = url
        isHidden = false
    }

    @objc private func openLink() { if let url = url { _ = NSWorkspace.shared.open(url) } }
    @objc private func dismiss() { isHidden = true }
}
