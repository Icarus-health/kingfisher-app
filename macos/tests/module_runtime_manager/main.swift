import Foundation
import Darwin

// Build-only substitute; the live Docker discovery/commands are never used.
struct Docker {
    let executable: String
    static func find() -> Docker? { nil }
}
let scenario = CommandLine.arguments[1]
let root = URL(fileURLWithPath: CommandLine.arguments[2])
func expect(_ value: @autoclosure () -> Bool, _ message: String) {
    if !value() { print(message); exit(1) }
}
func refuses(_ body: () throws -> Void) {
    do { try body(); print("operation unexpectedly accepted"); exit(1) }
    catch { expect(!String(describing:error).contains("SENTINEL"), "unsafe diagnostic") }
}
let image = "sha256:" + String(repeating:"a",count:64)
let otherImage = "sha256:" + String(repeating:"b",count:64)
let mainID = String(repeating:"1",count:64), gatewayID = String(repeating:"2",count:64), workerID = String(repeating:"3",count:64)
let controlKey = String(repeating:"k",count:43)
let token = "SENTINEL-MASTER-TOKEN", passphrase = "SENTINEL-PASSPHRASE"
let runtimePath = "/public/runtime-v1-arm64-" + String(repeating:"d",count:64)
let digest = String(repeating:"e",count:64)
let preparedPathKey = "KINGFISHER_MODULE_PREPARED_RUNTIME", preparedManifestKey = "KINGFISHER_MODULE_PREPARED_MANIFEST_SHA256"
let newRuntimePath = "/public/runtime-v1-arm64-" + String(repeating:"c",count:64), newDigest = String(repeating:"b",count:64)
let publicRuntime = VerifiedRuntime(hostPath:runtimePath,manifestDigest:digest,architecture:"arm64")
let baseline = ["PATH=/usr/local/bin:/usr/bin:/bin", "PYTHON_VERSION=3.12.12", "ICARUS_DATA_DIR=/data"]
func encoded(_ value: Any) -> Data { try! JSONSerialization.data(withJSONObject:value, options:[.sortedKeys]) }
func imageRecord() -> [String:Any] {
    ["Id":image,"Os":"linux","Architecture":"arm64", "Config":["Env":baseline,"Entrypoint":["icarus-sidecar"],"Cmd":NSNull(),"User":"kingfisher"]]
}
func mainRecord(_ id: String = mainID, enabled: Bool = true) -> [String:Any] {
    var env = baseline + ["ICARUS_SIDECAR_TOKEN=\(token)","ICARUS_SECRETS_PASSPHRASE=\(passphrase)","KINGFISHER_VOLLER_NAME=SENTINEL-NAME"]
    if enabled { env += ["KF_HARNESS_MODE=controlled-local-readonly-v1","KF_GATEWAY_CONTROL_KEY=\(controlKey)"] }
    return ["Id":id,"Name":"/kingfisher-kingfisher-1","Image":image,"State":["Running":true],
        "Config":["Image":"ghcr.io/icarus-health/kingfisher-app:1.0.43","Env":env,"Entrypoint":["icarus-sidecar"],"Cmd":NSNull(),"User":"kingfisher",
            "Labels":["com.docker.compose.project":"kingfisher","com.docker.compose.service":"kingfisher"]],
        "HostConfig":["Privileged":false,"NetworkMode":"kingfisher_default","PortBindings":["8890/tcp":[["HostIp":"127.0.0.1","HostPort":"8890"]]]],
        "Mounts":[["Type":"volume","Name":"kingfisher_kingfisher-data","Source":"/private-volume","Destination":"/data","RW":true]],
        "NetworkSettings":["Ports":["8890/tcp":[["HostIp":"127.0.0.1","HostPort":"8890"]]],
            "Networks":["kingfisher_default":["Aliases":["kingfisher"],"IPAddress":"172.20.0.2"],
                "kingfisher-modules-control":["Aliases":["kingfisher-controller"],"IPAddress":"172.21.0.2"]]]]
}
func roleRecord(_ role: String, id: String? = nil, key: String = controlKey) -> [String:Any] {
    let worker = role == "worker", identifier = id ?? (worker ? workerID : gatewayID)
    let aliases = worker ? ["kingfisher-modules-worker":["kingfisher-worker"]] :
        ["kingfisher-modules-control":["kingfisher-gateway-control"],"kingfisher-modules-worker":["kingfisher-gateway"]]
    var networks: [String:Any] = [:]
    for (name,values) in aliases { networks[name] = ["Aliases":values,"IPAddress":name.hasSuffix("control") ? "172.21.0.3" : (worker ? "172.22.0.3" : "172.22.0.2")] }
    return ["Id":identifier,"Name":"/kingfisher-modules-\(role)-1","Image":image,"State":["Running":true],
        "Config":["Image":image,"Env":baseline + (worker ? [] : ["KF_GATEWAY_CONTROL_KEY=\(key)"]),
            "Entrypoint":worker ? ["/runtime/bin/node","/runtime/harness_service.mjs","--controlled-local-readonly-v1"] : ["python","/runtime/harness_gateway.py","--controlled-local-readonly-v1"],
            "Cmd":NSNull(),"User":"1000:1000","Labels":["com.docker.compose.project":"kingfisher-modules","com.docker.compose.service":role],"Healthcheck":["Test":["NONE"]]],
        "HostConfig":["ReadonlyRootfs":true,"Privileged":false,"CapDrop":["ALL"],"CapAdd":[],"SecurityOpt":["no-new-privileges:true"],
            "Memory":worker ? 536870912 : 100663296,"NanoCpus":worker ? 750000000 : 250000000,"PidsLimit":worker ? 64 : 32,
            "Dns":["127.0.0.1"],"Tmpfs":["/tmp":"rw,noexec,nosuid,size=\(worker ? "64m" : "16m"),uid=1000,gid=1000,mode=700","/data":"rw,noexec,nosuid,size=64k,mode=000"],
            "NetworkMode":worker ? "kingfisher-modules-worker" : "kingfisher-modules-control","PortBindings":[:],"PidMode":"","IpcMode":"private","Devices":[],"ExtraHosts":[],"Links":[],"VolumesFrom":[]],
        "Mounts":[["Type":"bind","Source":runtimePath,"Destination":"/runtime","RW":false]],
        "NetworkSettings":["Ports":["8890/tcp":NSNull()],"Networks":networks]]
}
func networkRecord(_ role: String, main: String = mainID, gateway: String = gatewayID, worker: String = workerID) -> [String:Any] {
    ["Name":"kingfisher-modules-\(role)","Id":String(repeating:role == "control" ? "4" : "5",count:64),"Internal":true,"Driver":"bridge",
     "Labels":["com.docker.compose.project":"kingfisher-modules","com.docker.compose.network":role],
     "Containers":Dictionary(uniqueKeysWithValues:(role == "control" ? [main,gateway] : [gateway,worker]).map { ($0,["Name":"owned"]) })]
}
func set(_ dictionary: inout [String:Any], _ group: String, _ key: String, _ value: Any) {
    var nested = dictionary[group] as! [String:Any]; nested[key] = value; dictionary[group] = nested
}
func statusData(_ paired: Bool, busy: Bool = false, stopping: Bool = false, broker: Bool? = nil) -> Data {
    encoded(["model":"kingfisher-qwen3.5:9b-8k","mode":"controlled-local-readonly-v1","configured":true,"paired":paired,
        "broker_running":broker ?? paired,"jobs_busy":busy,"stopping":stopping,"restart_needed":false])
}
if scenario == "probe-scripts" { print(String(data:encoded(["sandbox":ModuleIsolation.sandboxProbe,"broker":ModuleIsolation.brokerProbe]),encoding:.utf8)!); exit(0) }
let paths = AppPaths(support:root.appendingPathComponent("support"), envFile:root.appendingPathComponent("support/kingfisher.env"), composeFile:root.appendingPathComponent("bundle/compose.yaml"))

// Production parser/validator is exercised directly with complete synthetic inspect envelopes.
if ["host-network","oversized-tmpfs","dto-strict","topology","foreign-image","private-mount","external-network","ports","root-user","caps","writable-root","dns","resources","bad-tmpfs","worker-authority","gateway-authority","wrong-mode","foreign-alias","network-members","negative-receipt"].contains(scenario) {
    if scenario == "dto-strict" {
        expect(try! ModuleRuntimeStatus.decode(statusData(true)).paired, "valid status")
        var invalid = try! JSONSerialization.jsonObject(with:statusData(true)) as! [String:Any]
        invalid["jobs_busy"] = 1; refuses { _ = try ModuleRuntimeStatus.decode(encoded(invalid)) }
        invalid["jobs_busy"] = false; invalid["control_key"] = token
        refuses { _ = try ModuleRuntimeStatus.decode(encoded(invalid)) }
    } else if scenario == "negative-receipt" {
        let good = Dictionary(uniqueKeysWithValues:ModuleIsolation.workerChecks.map { ($0,true) })
        try ModuleIsolation.validateProbe(encoded(good), role:.worker)
        var bad: [String:Any] = good; bad["main_ip_denied"] = false
        refuses { try ModuleIsolation.validateProbe(encoded(bad), role:.worker) }
        bad = good; bad["root_read_only"] = 1
        refuses { try ModuleIsolation.validateProbe(encoded(bad), role:.worker) }
    } else {
        var worker = roleRecord("worker"), gateway = roleRecord("gateway"), main = mainRecord()
        var control = networkRecord("control"), network = networkRecord("worker")
        switch scenario {
        case "host-network": set(&worker,"HostConfig","NetworkMode","host")
        case "oversized-tmpfs": set(&worker,"HostConfig","Tmpfs",["/tmp":"rw,noexec,nosuid,size=9223372036854775807m,uid=1000,gid=1000,mode=700","/data":"rw,noexec,nosuid,size=64k,mode=000"])
        case "foreign-image": worker["Image"] = otherImage
        case "private-mount": worker["Mounts"] = [["Type":"volume","Source":"private","Destination":"/data","RW":true]]
        case "external-network": var n = (worker["NetworkSettings"] as! [String:Any])["Networks"] as! [String:Any]; n["bridge"] = ["Aliases":[],"IPAddress":"172.17.0.2"]; set(&worker,"NetworkSettings","Networks",n)
        case "ports": set(&worker,"NetworkSettings","Ports",["3001/tcp":[["HostIp":"0.0.0.0","HostPort":"3001"]]])
        case "root-user": set(&worker,"Config","User","0:0")
        case "caps": set(&worker,"HostConfig","CapAdd",["NET_ADMIN"])
        case "writable-root": set(&worker,"HostConfig","ReadonlyRootfs",false)
        case "dns": set(&worker,"HostConfig","Dns",["8.8.8.8"])
        case "resources": set(&worker,"HostConfig","PidsLimit",128)
        case "bad-tmpfs": set(&worker,"HostConfig","Tmpfs",["/tmp":"rw,exec,size=64m,mode=777","/data":"rw,mode=700"])
        case "worker-authority": set(&worker,"Config","Env",baseline + ["KF_GATEWAY_CONTROL_KEY=\(controlKey)"])
        case "gateway-authority": set(&gateway,"Config","Env",baseline + ["KF_GATEWAY_CONTROL_KEY=\(controlKey)","ICARUS_SIDECAR_TOKEN=\(token)"])
        case "wrong-mode": set(&worker,"Config","Entrypoint",["/runtime/bin/node","/runtime/harness_service.mjs"])
        case "foreign-alias": var n = (worker["NetworkSettings"] as! [String:Any])["Networks"] as! [String:Any]; n["kingfisher-modules-worker"] = ["Aliases":["kingfisher-worker","kingfisher-controller"],"IPAddress":"172.22.0.3"]; set(&worker,"NetworkSettings","Networks",n)
        case "network-members": var c = control["Containers"] as! [String:Any]; c[String(repeating:"f",count:64)] = ["Name":"foreign"]; control["Containers"] = c
        default: break
        }
        let validate = { try ModuleIsolation.validate(imageData:encoded([imageRecord()]),mainData:encoded([main]),gatewayData:encoded([gateway]),workerData:encoded([worker]),controlData:encoded([control]),workerNetworkData:encoded([network]),runtime:publicRuntime,controlKey:controlKey) }
        if scenario == "topology" { let proof = try validate(); expect(proof.mainID == mainID && proof.workerID == workerID, "ownership") }
        else { refuses { _ = try validate() } }
    }
    print(String(data:encoded(["passed":scenario]),encoding:.utf8)!); exit(0)
}

// Manager scenarios will use only injected fake command/HTTP/cache/env boundaries.

// Independent small quoted-value decoder for the fake command boundary. The
// exported exact bytes are also checked with the real, offline Compose parser.
func composeValue(_ env: EnvFile, _ name: String) -> String? {
    guard let raw = env.lines.last(where: { $0.hasPrefix(name + "=") }).map({ String($0.dropFirst(name.count + 1)) }) else { return nil }
    if raw.hasPrefix("'"), raw.hasSuffix("'") { return String(raw.dropFirst().dropLast()).replacingOccurrences(of: "\\'", with: "'") }
    guard raw.hasPrefix("\""), raw.hasSuffix("\"") else { return env.value(name) }
    let input = Array(raw.dropFirst().dropLast()); var result = "", index = 0
    let escapes: [Character: String] = ["n":"\n", "r":"\r", "t":"\t", "b":"\u{8}", "f":"\u{c}", "a":"\u{7}", "v":"\u{b}", "\\":"\\", "\"":"\"", "$":"\u{e000}"]
    while index < input.count {
        if input[index] == "\\", index + 1 < input.count, let escaped = escapes[input[index + 1]] { result += escaped; index += 2 }
        else { result.append(input[index]); index += 1 }
    }
    return result.replacingOccurrences(of: "\u{e000}", with: "$")
}

final class FixtureManagerSystem: ModuleManagerSystem {
    var clock = Date(timeIntervalSince1970: 1000)
    var env = EnvFile.generated(token: token, passphrase: passphrase)
    var initialEnv: EnvFile!
    var currentMain = mainRecord(enabled: false)
    var modules = false, connected = false, running = true, paired = false
    var prepareCalls = 0, verifyCalls = 0, initializes = 0, shutdowns = 0, workerProbes = 0, gatewayProbes = 0, brokerProbes = 0
    var commands: [[String]] = [], writes: [EnvFile] = [], temporary: [String: EnvFile] = [:], temporaryHistory: [EnvFile] = []
    var fresh = true, forged = false, badRecipe = false, failProbe = false, failPair = false, raced = false, changedImage = false
    var busyShutdown = false, unknownShutdown = false, missingShutdown = false, cancelNow = false
    var blockPrepare = false, reuseKey = false, cancelOnEnable = false, cancelOnProbe = false
    var cancelAfterPrepare = false, corruptRollback = false, corruptRollbackMode = false, corruptRollbackKey = false, generationRace = false
    var currentGateway = gatewayID, currentWorker = workerID, roleImage = image
    var cachePath = runtimePath, cacheDigest = digest, roleRuntimePath = runtimePath
    let prepareEntered = DispatchSemaphore(value: 0), prepareRelease = DispatchSemaphore(value: 0)
    var mainChanges = 0
    init(approved: Bool = false) {
        env.set(EnvKey.image, "ghcr.io/icarus-health/kingfisher-app:1.0.43")
        env.set("UNRELATED_SETTING", "SENTINEL-KEEP")
        if approved {
            env.set(ModuleIsolation.modeKey, ModuleRuntimeStatus.mode); env.set(ModuleIsolation.controlKey, controlKey)
            env.set(ModuleIsolation.pathKey, runtimePath); env.set(ModuleIsolation.manifestKey, digest); env.set(ModuleIsolation.imageKey, image)
            currentMain = mainRecord(enabled: true)
        }
        initialEnv = env
    }
    func docker() -> Docker? { Docker(executable: "/fixture/docker") }
    func now() -> Date { clock }
    func pause(_ seconds: TimeInterval) { clock.addTimeInterval(seconds) }
    func readEnvironment(_ paths: AppPaths) throws -> EnvFile { env }
    func writeEnvironment(_ value: EnvFile, paths: AppPaths) throws { env = value; writes.append(value); if cancelOnEnable && value.value(ModuleIsolation.controlKey) == String(repeating:"n",count:43) { cancelNow = true } }
    func acquire(_ paths: AppPaths) throws -> ModuleManagerLease { ModuleManagerLease({}) }
    func temporaryEnvironment(_ value: EnvFile, paths: AppPaths) throws -> URL {
        let file = paths.support.appendingPathComponent("fixture-\(temporaryHistory.count).env"); temporary[file.path] = value; temporaryHistory.append(value); return file
    }
    func removeTemporary(_ file: URL) { temporary[file.path] = nil }
    func newControlKey() throws -> String { reuseKey ? controlKey : String(repeating: "n", count: 43) }
    func cacheMetadata(path: String, digest: String) throws -> VerifiedRuntime {
        guard [runtimePath,newRuntimePath].contains(path), ModuleRuntimeContract.validDigest(digest) else { throw ModuleRuntimeCacheError.integrityFailed }
        return VerifiedRuntime(hostPath:path,manifestDigest:digest,architecture:"arm64")
    }
    func prepareCache(paths: AppPaths, docker: Docker, image: String, progress: (ModuleSetupPhase) -> Void, cancelled: @escaping () -> Bool) throws -> VerifiedRuntime {
        prepareCalls += 1; prepareEntered.signal()
        if blockPrepare { _ = prepareRelease.wait(timeout: .now() + 3) }
        if fresh { progress(.downloading); progress(.installing) }; progress(.ready)
        if cancelAfterPrepare { cancelNow = true }
        return VerifiedRuntime(hostPath: cachePath, manifestDigest: forged ? String(repeating: "f", count: 64) : cacheDigest, architecture: "arm64", builtFresh: fresh)
    }
    func verifiedCache(paths: AppPaths, docker: Docker, image: String, path: String, digest: String, cancelled: @escaping () -> Bool) throws -> VerifiedRuntime {
        verifyCalls += 1
        if cancelled() { throw ModuleRuntimeCacheError.cancelled }
        if badRecipe || forged || path != cachePath || digest != cacheDigest { throw ModuleRuntimeCacheError.integrityFailed }
        return VerifiedRuntime(hostPath:path,manifestDigest:digest,architecture:"arm64")
    }
    func request(_ action: ModuleHTTPAction, token: String, deadline: Date, cancelled: @escaping () -> Bool) throws -> ModuleHTTPResponse {
        expect(token == self.env.value(EnvKey.token), "changed main token")
        switch action {
        case .health: return ModuleHTTPResponse(status: 200, data: encoded(["status": "ok"]))
        case .version: return ModuleHTTPResponse(status: 200, data: encoded(["fassung": "1.0.43"]))
        case .initialize:
            initializes += 1
            expect(workerProbes > 0 && gatewayProbes > 0, "initialize before active OS probes")
            paired = true
            return ModuleHTTPResponse(status: failPair ? 503 : 200, data: failPair ? encoded(["detail": "SENTINEL-PRIVATE"]) : statusData(true))
        case .shutdown:
            shutdowns += 1
            if missingShutdown { return ModuleHTTPResponse(status: 404, data: Data()) }
            if unknownShutdown { return ModuleHTTPResponse(status: 500, data: encoded(["detail": "SENTINEL-PRIVATE"])) }
            paired = false
            return ModuleHTTPResponse(status: 200, data: statusData(false, busy: busyShutdown, stopping: busyShutdown, broker: busyShutdown))
        case .status:
            return ModuleHTTPResponse(status: 200, data: statusData(paired, busy: busyShutdown, stopping: busyShutdown, broker: paired || busyShutdown))
        }
    }
    func command(_ docker: Docker, _ args: [String], deadline: Date, cancelled: @escaping () -> Bool) throws -> String {
        if cancelled() { throw ModuleRuntimeCacheError.cancelled }
        commands.append(args)
        func json(_ value: Any) -> String { String(data: encoded(value), encoding: .utf8)! }
        if args.first == "ps" {
            let full = args.contains("--no-trunc")
            if args.contains("label=com.docker.compose.project=kingfisher") { return full ? currentMain["Id"] as! String : String((currentMain["Id"] as! String).prefix(12)) }
            return modules ? (full ? currentGateway : String(currentGateway.prefix(12))) + "\n" + (full ? currentWorker : String(currentWorker.prefix(12))) + "\n" : ""
        }
        if args.prefix(2) == ["image", "inspect"] {
            var record = imageRecord(); if args.last == otherImage { record["Id"] = otherImage }
            return json([record])
        }
        if args.first == "inspect" {
            let identifier = args.last!
            if identifier == mainID || identifier == String(repeating: "6", count: 64) {
                var main = currentMain
                var n = (main["NetworkSettings"] as! [String: Any])["Networks"] as! [String: Any]
                if !connected { n[ModuleIsolation.control] = nil }
                set(&main, "NetworkSettings", "Networks", n)
                if changedImage { main["Image"] = otherImage }
                return json([main])
            }
            guard modules else { throw ModuleRuntimeCacheError.unavailable }
            var role = roleRecord(identifier == currentGateway ? "gateway" : "worker", id: identifier, key: env.value(ModuleIsolation.controlKey) ?? controlKey)
            role["Mounts"] = [["Type":"bind","Source":roleRuntimePath,"Destination":"/runtime","RW":false]]
            role["Image"] = roleImage; set(&role,"Config","Image",roleImage)
            role["State"] = ["Running": running]
            return json([role])
        }
        if args.prefix(2) == ["network", "ls"] { return modules || connected ? ModuleIsolation.control + "\n" + ModuleIsolation.workerNetwork + "\n" : "" }
        if args.prefix(2) == ["network", "inspect"] {
            let control = args.last == ModuleIsolation.control
            var net = networkRecord(control ? "control" : "worker", main: currentMain["Id"] as! String, gateway:currentGateway, worker:currentWorker)
            if !modules { net["Containers"] = control && connected ? [(currentMain["Id"] as! String): ["Name": "main"]] : [:] }
            return json([net])
        }
        if args.prefix(2) == ["network", "connect"] { connected = true; return "" }
        if args.prefix(2) == ["network", "disconnect"] { connected = false; return "" }
        if args.first == "compose" {
            if args.contains("up") && args.last == "kingfisher" {
                mainChanges += 1
                var main = mainRecord(String(repeating: "6", count: 64), enabled: env.value(ModuleIsolation.modeKey) == ModuleRuntimeStatus.mode)
                let file = args[args.firstIndex(of: "--env-file")! + 1], values = temporary[file] ?? env
                var entries = baseline + ["ICARUS_SIDECAR_TOKEN=\(token)", "ICARUS_SECRETS_PASSPHRASE=\(passphrase)", "KINGFISHER_VOLLER_NAME=\(composeValue(values, EnvKey.vollerName) ?? "")"]
                if corruptRollback && mainChanges > 1 { entries.removeAll { $0.hasPrefix("KINGFISHER_VOLLER_NAME=") }; entries.append("KINGFISHER_VOLLER_NAME=CORRUPTED") }
                if let mode = values.value(ModuleIsolation.modeKey), !mode.isEmpty { entries += ["KF_HARNESS_MODE=\(mode)", "KF_GATEWAY_CONTROL_KEY=\(values.value(ModuleIsolation.controlKey) ?? "")"] }
                if mainChanges > 1 && corruptRollbackMode { entries.removeAll { $0.hasPrefix(ModuleIsolation.modeKey + "=") }; entries.append(ModuleIsolation.modeKey + "=unexpected") }
                if mainChanges > 1 && corruptRollbackKey { entries.removeAll { $0.hasPrefix(ModuleIsolation.controlKey + "=") }; entries.append(ModuleIsolation.controlKey + "=" + String(repeating:"z",count:43)) }
                set(&main, "Config", "Env", entries); currentMain = main; connected = false
                changedImage = raced && mainChanges == 1
                return ""
            }
            if args.contains("up") && args.suffix(2) == ["gateway", "worker"] { modules = true; running = true; currentGateway = String(repeating:"7",count:64); currentWorker = String(repeating:"8",count:64); roleImage = image; roleRuntimePath = env.value(ModuleIsolation.pathKey) ?? runtimePath; return "" }
            throw ModuleRuntimeCacheError.builderFailed
        }
        if args.first == "stop" { running = false; return "" }
        if args.first == "rm" { modules = false; return "" }
        if args.first == "exec" {
            let code = args[4]
            expect(!args.contains(token) && !args.contains(passphrase) && !args.contains(controlKey) && !args.contains(String(repeating:"n",count:43)), "credential in process arguments")
            if code == ModuleIsolation.hostModelAddressProbe { return json(["address": "172.20.0.1"]) }
            if code == ModuleIsolation.brokerProbe { brokerProbes += 1; return json(["missing_grant_denied": true, "master_token_denied": true]) }
            if code == ModuleIsolation.sandboxProbe {
                let worker = args[1] == currentWorker
                if worker { workerProbes += 1; if cancelOnProbe { cancelNow = true } } else { gatewayProbes += 1 }
                if worker && generationRace { currentWorker = String(repeating:"9",count:64) }
                var result = Dictionary(uniqueKeysWithValues: (worker ? ModuleIsolation.workerChecks : ModuleIsolation.gatewayChecks).map { ($0, true) })
                if failProbe && worker { result["main_ip_denied"] = false }
                return json(result)
            }
            throw ModuleRuntimeCacheError.builderFailed
        }
        throw ModuleRuntimeCacheError.builderFailed
    }
}
let approved = ["recipe-cache-rollback","recipe-cache-cancel-retry","prepared-reconcile","prepared-stale-active-fallback","backend-cache-drain-retry","recipe-cache-drain-retry","rollback-mode-drift","rollback-key-drift","rollback-old-authority","reused-control-key","backend-update-cache","cache-reuse", "self-signed-cache", "shutdown", "shutdown-busy", "shutdown-unknown", "shutdown-404-enabled", "reconcile-approved", "reconcile-changed-recipe", "status-no-adopt"].contains(scenario)
let system = FixtureManagerSystem(approved: approved)
let manager = ModuleRuntimeManager(paths: paths, system: system)
var progress: [ModuleSetupPhase] = []
func prepare() throws {
    try manager.prepareAndStart(progress: { value in
        if value == .ready { expect(system.paired && system.brokerProbes > 0, "ready before full pairing/authorization check") }
        progress.append(value)
    }, cancelled: { system.cancelNow })
}
let specialValues = ["one\\backslash", "two\\\\slashes", "trailing\\", "single'quote", "double\"quote", "both'\"\\", "dollar$HOME ${MISSING:-evil} #hash", "slash\\$HOME", "Grüße\t東京", " leading and trailing ", "literal\\n\\t"]
if scenario == "dotenv-roundtrip" {
    var fixtures: [[String: String]] = []
    for original in specialValues {
        let fixture = FixtureManagerSystem(), subject = ModuleRuntimeManager(paths: paths, system: fixture)
        var config = fixture.currentMain["Config"] as! [String: Any]
        config["Env"] = (config["Env"] as! [String]).filter { !$0.hasPrefix(EnvKey.vollerName + "=") } + [EnvKey.vollerName + "=" + original]
        fixture.currentMain["Config"] = config
        // Capture setup and rollback encodings; the public test then passes each
        // through Compose's real config-only parser without a daemon.
        fixture.failProbe = true
        try? subject.prepareAndStart(progress: { _ in }, cancelled: { false })
        for captured in fixture.temporaryHistory where captured.value(EnvKey.vollerName) != nil { fixtures.append(["original":original, "env":captured.text]) }
    }
    print(String(data:encoded(fixtures),encoding:.utf8)!); exit(0)
}
switch scenario {
case "recipe-cache-rollback", "recipe-cache-cancel-retry":
    system.modules = true; system.connected = true; system.cachePath = newRuntimePath; system.cacheDigest = newDigest
    let bindingKeys = [ModuleIsolation.pathKey,ModuleIsolation.manifestKey,ModuleIsolation.imageKey,ModuleIsolation.modeKey,ModuleIsolation.controlKey]
    let originalBinding = bindingKeys.map { system.env.value($0) }
    if scenario == "recipe-cache-rollback" { system.failProbe = true } else { system.cancelAfterPrepare = true }
    refuses { try prepare() }
    expect(bindingKeys.map { system.env.value($0) } == originalBinding && system.env.value(preparedPathKey) == newRuntimePath && system.env.value(preparedManifestKey) == newDigest, "rollback/cancel lost old active binding or new prepared provenance")
    expect(system.initializes == 0, "failed setup initialized")
    system.failProbe = false; system.cancelAfterPrepare = false; system.cancelNow = false; system.fresh = false
    try prepare(); expect(manager.status() == .ready, "prepared recipe retry failed after rollback/cancel")
case "prepared-reconcile", "prepared-stale-active-fallback":
    system.modules = true; system.connected = true; system.fresh = false
    system.env.set(preparedPathKey,newRuntimePath); system.env.set(preparedManifestKey,newDigest)
    if scenario == "prepared-reconcile" { system.cachePath = newRuntimePath; system.cacheDigest = newDigest }
    manager.reconcileIfEnabled()
    expect(system.prepareCalls == 0 && system.initializes == 1 && manager.status() == .ready, "prepared/legacy exact approval reconcile failed or downloaded")
case "backend-cache-drain-retry", "recipe-cache-drain-retry":
    system.modules = true; system.connected = true; system.paired = true
    if scenario == "backend-cache-drain-retry" { system.roleImage = otherImage; system.env.set(ModuleIsolation.imageKey,otherImage) }
    else { system.cachePath = newRuntimePath; system.cacheDigest = newDigest }
    let originalBinding = [ModuleIsolation.pathKey,ModuleIsolation.manifestKey,ModuleIsolation.imageKey,ModuleIsolation.modeKey,ModuleIsolation.controlKey].map { system.env.value($0) }
    system.unknownShutdown = true; refuses { try prepare() }
    expect([ModuleIsolation.pathKey,ModuleIsolation.manifestKey,ModuleIsolation.imageKey,ModuleIsolation.modeKey,ModuleIsolation.controlKey].map { system.env.value($0) } == originalBinding, "active role binding changed before drain")
    expect(system.env.value(preparedPathKey) == system.cachePath && system.env.value(preparedManifestKey) == system.cacheDigest, "prepared cache provenance lost")
    expect(system.mainChanges == 0 && system.initializes == 0 && system.modules, "failed drain mutated active services")
    system.unknownShutdown = false
    expect(manager.stopBeforeMaintenance(), "old roles became unmaintainable")
    system.fresh = false; try prepare()
    expect(manager.status() == .ready && system.env.value(ModuleIsolation.pathKey) == system.cachePath && system.env.value(ModuleIsolation.imageKey) == image, "prepared retry stranded old roles")
case "env-backslash", "env-trailing-slash", "env-quotes", "env-dollar", "env-unicode-tab":
    let originals = ["env-backslash":specialValues[0], "env-trailing-slash":specialValues[2], "env-quotes":specialValues[5], "env-dollar":specialValues[6], "env-unicode-tab":specialValues[8]]
    let original = originals[scenario]!
    var config = system.currentMain["Config"] as! [String: Any]
    config["Env"] = (config["Env"] as! [String]).filter { !$0.hasPrefix(EnvKey.vollerName + "=") } + [EnvKey.vollerName + "=" + original]
    system.currentMain["Config"] = config
    try prepare()
    let actual = try ModuleJSON.environment((system.currentMain["Config"] as! [String:Any])["Env"])[EnvKey.vollerName]
    expect(actual == original, "existing value corrupted")
    expect(manager.status() == .ready, "special existing value rejected")
case "rollback-env-drift", "rollback-mode-drift", "rollback-key-drift":
    system.failProbe = true; system.corruptRollback = scenario == "rollback-env-drift"
    system.corruptRollbackMode = scenario == "rollback-mode-drift"; system.corruptRollbackKey = scenario == "rollback-key-drift"
    do { try prepare(); expect(false,"setup unexpectedly passed") }
    catch { expect(error as? ModuleManagerError == .cleanupRequired, "corrupted rollback accepted") }
    expect(progress.last == .failed, "rollback failure hidden")
case "rollback-old-authority":
    system.failProbe = true; refuses { try prepare() }
    let actual = try ModuleJSON.environment((system.currentMain["Config"] as! [String:Any])["Env"])
    expect(actual[ModuleIsolation.modeKey] == ModuleRuntimeStatus.mode && actual[ModuleIsolation.controlKey] == controlKey, "prior authority not restored")
case "fresh-cache-drain-retry", "fresh-cache-cancel-retry":
    if scenario == "fresh-cache-drain-retry" { system.unknownShutdown = true } else { system.cancelAfterPrepare = true }
    refuses { try prepare() }
    expect(system.env.value(preparedPathKey) == runtimePath && system.env.value(preparedManifestKey) == digest, "fully verified fresh cache provenance lost")
    expect(system.env.value(ModuleIsolation.pathKey) == nil && system.env.value(ModuleIsolation.manifestKey) == nil && system.env.value(ModuleIsolation.imageKey) == nil, "cache-only approval changed active binding")
    expect(system.env.value(ModuleIsolation.modeKey) == nil && system.env.value(ModuleIsolation.controlKey) == nil && system.mainChanges == 0, "cache-only approval enabled runtime")
    system.unknownShutdown = false; system.cancelAfterPrepare = false; system.cancelNow = false; system.fresh = false
    try prepare(); expect(manager.status() == .ready, "approved fresh cache could not be retried")
case "shutdown-absent-no-work": expect(manager.stopBeforeMaintenance() && system.commands.isEmpty && system.shutdowns == 0 && system.initializes == 0, "unconfigured maintenance performed HTTP/Docker work")
case "shutdown-partial": system.env.set(ModuleIsolation.modeKey,ModuleRuntimeStatus.mode); expect(!manager.stopBeforeMaintenance() && system.commands.isEmpty && system.shutdowns == 0, "partial authority accepted or contacted backend")
case "reused-control-key": system.reuseKey = true; refuses { try prepare() }; expect(system.initializes == 0, "old control credential reused")
case "cancel-before-main": system.cancelOnEnable = true; refuses { try prepare() }; expect(system.mainChanges == 0 && system.initializes == 0 && system.env.value(ModuleIsolation.modeKey) == nil, "cancel caused unnecessary main restart")
case "cancel-after-probe": system.cancelOnProbe = true; refuses { try prepare() }; expect(system.initializes == 0 && !system.modules && system.env.value(ModuleIsolation.modeKey) == nil, "cancelled setup retained active roles")
case "backend-update-cache": system.fresh = false; system.modules = true; system.connected = true; system.roleImage = otherImage; system.env.set(ModuleIsolation.imageKey,otherImage); try prepare(); expect(manager.status() == .ready && system.env.value(ModuleIsolation.imageKey) == image, "approved public cache tied to old backend image")
case "initial-idle": expect(manager.status() == .unavailable && system.commands.isEmpty && system.initializes == 0 && system.prepareCalls == 0, "implicit activation")
case "setup", "cache-ready-not-ready", "preserve-env":
    try prepare(); expect(manager.status() == .ready, "not ready")
    expect(progress.last == .ready && progress.filter { $0 == .ready }.count == 1, "cache ready leaked before pair")
    expect(system.env.value(EnvKey.token) == token && system.env.value(EnvKey.passphrase) == passphrase && system.env.value("UNRELATED_SETTING") == "SENTINEL-KEEP", "original environment lost")
    expect(system.env.value(EnvKey.image) == system.initialEnv.value(EnvKey.image), "main image tag changed")
case "cache-reuse": system.fresh = false; try prepare(); expect(manager.status() == .ready, "approved cache rejected")
case "unknown-cache": system.fresh = false; refuses { try prepare() }; expect(system.writes.isEmpty && system.initializes == 0, "unknown cache enrolled")
case "self-signed-cache": system.fresh = false; system.forged = true; refuses { try prepare() }; expect(system.writes.isEmpty && system.initializes == 0, "regenerated public manifest approved")
case "cancelled": system.cancelNow = true; refuses { try prepare() }; expect(system.commands.isEmpty && system.initializes == 0, "cancelled setup did work")
case "probe-failure": system.failProbe = true; refuses { try prepare() }; expect(system.initializes == 0 && manager.status() != .ready, "unsafe runtime paired")
case "pair-failure": system.failPair = true; refuses { try prepare() }; expect(system.initializes == 1 && manager.status() != .ready, "pair retried/adopted")
case "generation-race": system.generationRace = true; refuses { try prepare() }; expect(system.workerProbes == 1 && system.initializes == 0 && manager.status() != .ready, "changed worker generation paired")
case "image-race": system.raced = true; refuses { try prepare() }; expect(system.initializes == 0 && manager.status() != .ready, "changed main image paired")
case "foreign-existing": system.modules = true; refuses { try prepare() }; expect(system.writes.isEmpty && system.initializes == 0 && !system.commands.contains { $0.first == "stop" || $0.first == "rm" }, "foreign resources changed")
case "repeat": try prepare(); let count = system.initializes; try prepare(); expect(system.initializes == count, "repeated setup initialized again")
case "shutdown": system.modules = true; system.connected = true; system.paired = true; expect(manager.stopBeforeMaintenance(), "clean shutdown failed"); expect(!system.running && system.shutdowns > 0, "services stopped before backend drain")
case "shutdown-busy": system.modules = true; system.busyShutdown = true; expect(!manager.stopBeforeMaintenance(), "busy callback treated as stopped"); expect(!system.commands.contains { $0.first == "stop" }, "stopped role before physical callback drain")
case "shutdown-unknown": system.modules = true; system.unknownShutdown = true; expect(!manager.stopBeforeMaintenance(), "unknown shutdown accepted"); expect(!system.commands.contains { $0.first == "stop" }, "unknown callback teardown")
case "shutdown-404": system.missingShutdown = true; expect(manager.stopBeforeMaintenance(), "legacy absence blocked ordinary app")
case "shutdown-404-enabled": system.missingShutdown = true; expect(!manager.stopBeforeMaintenance(), "enabled runtime 404 accepted")
case "reconcile-absent": manager.reconcileIfEnabled(); expect(system.prepareCalls == 0 && system.commands.isEmpty && system.initializes == 0, "ordinary startup activated modules")
case "reconcile-approved": manager.reconcileIfEnabled(); expect(system.prepareCalls == 0 && system.verifyCalls > 0 && system.initializes == 1, "reconcile downloaded/adopted old pair")
case "reconcile-changed-recipe": system.badRecipe = true; manager.reconcileIfEnabled(); expect(system.prepareCalls == 0 && system.initializes == 0, "unknown recipe downloaded/adopted")
case "status-no-adopt": system.modules = true; system.connected = true; system.paired = true; expect(manager.status() == .unavailable && system.initializes == 0 && system.prepareCalls == 0, "status adopted old healthy pair")
case "restore-env": system.failProbe = true; refuses { try prepare() }; expect(system.env.value(EnvKey.token) == token && system.env.value(EnvKey.passphrase) == passphrase && system.env.value(EnvKey.image) == system.initialEnv.value(EnvKey.image), "rollback lost original keys/image"); expect(system.env.value(ModuleIsolation.modeKey) == nil && system.env.value(ModuleIsolation.controlKey) == nil && system.env.value(ModuleIsolation.pathKey) == nil, "failed activation stayed enabled"); expect(system.env.value(preparedManifestKey) == digest, "fresh cache provenance lost on failed pair")
case "admission":
    system.blockPrepare = true
    let finished = DispatchSemaphore(value: 0)
    DispatchQueue.global().async { try? manager.prepareAndStart(progress: { _ in }, cancelled: { false }); finished.signal() }
    expect(system.prepareEntered.wait(timeout: .now() + 2) == .success, "setup did not enter cache")
    refuses { try prepare() }; system.prepareRelease.signal(); expect(finished.wait(timeout: .now() + 5) == .success, "first setup did not complete")
default: print("unknown scenario"); exit(1)
}
print(String(data: encoded(["passed": scenario]), encoding: .utf8)!)
