import Foundation

/// Besitzt Timer/Requests; keine Prozesse, Ports oder Laufzeitinstallation.
final class CalendarReporter {
    private let queue = DispatchQueue(label: "local.kingfisher.calendar", qos: .utility)
    private let lock = NSLock()
    private let http: CalendarHTTP
    private let reader: NativeCalendarReading
    private var running = false
    private var timer: DispatchSourceTimer?
    private lazy var engine = NativeCalendarEngine(reader: reader, request: { [weak self] path, body in
        guard let self = self, self.isRunning else { throw NativeCalendarError.interrupted }
        return try self.http.request(path, body)
    }, active: { [weak self] in self?.isRunning == true })

    init(origin: URL, tokenFile: URL, reader: NativeCalendarReading) {
        http = CalendarHTTP(origin: origin, tokenFile: tokenFile); self.reader = reader
    }
    private var isRunning: Bool { lock.lock(); defer { lock.unlock() }; return running }
    func start() {
        lock.lock(); guard !running else { lock.unlock(); return }; running = true; lock.unlock()
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now(), repeating: .seconds(5), leeway: .seconds(1))
        timer.setEventHandler { [weak self] in
            guard let self = self, self.isRunning else { return }
            do { try self.engine.tick() }
            catch {
                // Keine Termininhalte, Kalendernamen oder Zugangsdaten in Logs.
                self.engine.recoverAfterFailure()
            }
        }
        self.timer = timer; timer.resume()
    }
    func requestPermission(generation: Int) {
        queue.async { [weak self] in self?.engine.requestPermission(generation: generation) }
    }
    func stop() {
        lock.lock(); running = false; lock.unlock()
        timer?.setEventHandler {}; timer?.cancel(); timer = nil
        http.stop()
    }
}
