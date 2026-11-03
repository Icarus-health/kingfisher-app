import Foundation
import CoreFoundation

// Pure validation of actual Docker/HTTP receipts. No command, environment or filesystem access.
enum ModuleIsolationError: Error { case invalid }
enum ModuleRole: String { case gateway, worker }

enum ModuleJSON {
    static func object(_ data: Data) throws -> [String: Any] {
        guard data.count <= 8 * 1024 * 1024,
              let value = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { throw ModuleIsolationError.invalid }
        return value
    }
    static func inspect(_ data: Data) throws -> [String: Any] {
        guard data.count <= 8 * 1024 * 1024,
              let rows = try JSONSerialization.jsonObject(with: data) as? [[String: Any]], rows.count == 1 else { throw ModuleIsolationError.invalid }
        return rows[0]
    }
    static func boolean(_ value: Any?) -> Bool? {
        guard let value = value as? NSNumber, CFGetTypeID(value) == CFBooleanGetTypeID() else { return nil }
        return value.boolValue
    }
    static func integer(_ value: Any?) -> Int64? {
        guard let value = value as? NSNumber, CFGetTypeID(value) != CFBooleanGetTypeID(),
              value.doubleValue == Double(value.int64Value) else { return nil }
        return value.int64Value
    }
    static func environment(_ value: Any?) throws -> [String: String] {
        guard let rows = value as? [String] else { throw ModuleIsolationError.invalid }
        var result: [String: String] = [:]
        for row in rows {
            let parts = row.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
            guard parts.count == 2, !parts[0].isEmpty, parts[0].utf8.allSatisfy({ $0 == 95 || (48...57).contains($0) || (65...90).contains($0) || (97...122).contains($0) }),
                  !row.contains("\n"), !row.contains("\r"), !row.contains("\0"), result[String(parts[0])] == nil else { throw ModuleIsolationError.invalid }
            result[String(parts[0])] = String(parts[1])
        }
        return result
    }
    static func dictionary(_ value: Any?) -> [String: Any] { value as? [String: Any] ?? [:] }
}

struct ModuleRuntimeStatus {
    static let model = "kingfisher-qwen3.5:9b-8k"
    static let mode = "controlled-local-readonly-v1"
    let configured, paired, brokerRunning, jobsBusy, stopping, restartNeeded: Bool
    var quiescent: Bool { !paired && !brokerRunning && !jobsBusy && !stopping }
    var ready: Bool { configured && paired && brokerRunning && !stopping && !restartNeeded }
    static func decode(_ data: Data) throws -> ModuleRuntimeStatus {
        let value = try ModuleJSON.object(data)
        guard Set(value.keys) == Set(["model", "mode", "configured", "paired", "broker_running", "jobs_busy", "stopping", "restart_needed"]),
              value["model"] as? String == model, value["mode"] as? String == mode,
              let configured = ModuleJSON.boolean(value["configured"]), let paired = ModuleJSON.boolean(value["paired"]),
              let broker = ModuleJSON.boolean(value["broker_running"]), let busy = ModuleJSON.boolean(value["jobs_busy"]),
              let stopping = ModuleJSON.boolean(value["stopping"]), let restart = ModuleJSON.boolean(value["restart_needed"]) else { throw ModuleIsolationError.invalid }
        return ModuleRuntimeStatus(configured: configured, paired: paired, brokerRunning: broker, jobsBusy: busy, stopping: stopping, restartNeeded: restart)
    }
}

struct ModuleContainer {
    let raw: [String: Any]
    let id, image, name: String
    let config, host, networks: [String: Any]
    let environment: [String: String]
    var running: Bool { ModuleJSON.boolean(ModuleJSON.dictionary(raw["State"])["Running"]) == true }
    init(_ data: Data) throws {
        raw = try ModuleJSON.inspect(data)
        guard let id = raw["Id"] as? String, ModuleRuntimeContract.validDigest(id), let image = raw["Image"] as? String,
              ModuleRuntimeContract.validImage(image), let name = raw["Name"] as? String else { throw ModuleIsolationError.invalid }
        self.id = id; self.image = image; self.name = String(name.drop(while: { $0 == "/" }))
        config = ModuleJSON.dictionary(raw["Config"]); host = ModuleJSON.dictionary(raw["HostConfig"])
        networks = ModuleJSON.dictionary(ModuleJSON.dictionary(raw["NetworkSettings"])["Networks"])
        environment = try ModuleJSON.environment(config["Env"])
    }
    func owned(project: String, service: String) -> Bool {
        let labels = config["Labels"] as? [String: String] ?? [:]
        return labels["com.docker.compose.project"] == project && labels["com.docker.compose.service"] == service
    }
    func address(_ network: String) throws -> String {
        guard let value = ModuleJSON.dictionary(networks[network])["IPAddress"] as? String, ModuleIsolation.privateIPv4(value) else { throw ModuleIsolationError.invalid }
        return value
    }
}

struct ModuleIsolationProof: Equatable {
    let mainID, gatewayID, workerID, imageID, runtimePath, manifestDigest, controlID, workerNetworkID, mainControlIP: String
}

enum ModuleIsolation {
    static let project = "kingfisher-modules"
    static let control = "kingfisher-modules-control", workerNetwork = "kingfisher-modules-worker"
    static let modeKey = "KF_HARNESS_MODE", controlKey = "KF_GATEWAY_CONTROL_KEY"
    static let pathKey = "KINGFISHER_MODULE_RUNTIME", imageKey = "KINGFISHER_MODULE_IMAGE", manifestKey = "KINGFISHER_MODULE_MANIFEST_SHA256"
    static let preparedPathKey = "KINGFISHER_MODULE_PREPARED_RUNTIME", preparedManifestKey = "KINGFISHER_MODULE_PREPARED_MANIFEST_SHA256"
    static func validKey(_ value: String) -> Bool {
        value.utf8.count == 43 && value.utf8.allSatisfy { (65...90).contains($0) || (97...122).contains($0) || (48...57).contains($0) || $0 == 45 || $0 == 95 }
    }
    static func privateIPv4(_ value: String) -> Bool {
        let parts = value.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 4, parts.allSatisfy({ Int($0).map { (0...255).contains($0) } ?? false }), let first = Int(parts[0]), let second = Int(parts[1]) else { return false }
        return first == 10 || (first == 172 && (16...31).contains(second)) || (first == 192 && second == 168)
    }
    static func noPublishedPorts(_ value: Any?) -> Bool {
        guard let ports = value as? [String: Any] else { return false }
        return ports.values.allSatisfy { $0 is NSNull || ($0 as? [Any])?.isEmpty == true }
    }
    static func baseline(_ image: [String: Any]) throws -> [String: String] {
        let env = try ModuleJSON.environment(ModuleJSON.dictionary(image["Config"])["Env"])
        guard env.keys.allSatisfy({ name in
            name == "GPG_KEY" || (!name.hasPrefix("KF_") && !name.hasSuffix("_KEY") && !name.hasSuffix("_TOKEN") && !name.contains("PASSWORD") && !name.contains("PASSPHRASE") && !name.contains("SECRET"))
        }) else { throw ModuleIsolationError.invalid }
        return env
    }
    static func main(_ value: ModuleContainer, image: [String: Any], requireControl: Bool) throws {
        let imageConfig = ModuleJSON.dictionary(image["Config"])
        guard value.running, value.owned(project: Installation.project, service: "kingfisher"), value.image == image["Id"] as? String,
              ModuleJSON.boolean(value.host["Privileged"]) == false,
              value.config["User"] as? String == imageConfig["User"] as? String,
              !["", "root", "0", "0:0"].contains(imageConfig["User"] as? String ?? ""),
              value.config["Entrypoint"] as? [String] == imageConfig["Entrypoint"] as? [String],
              commands(value.config["Cmd"]) == commands(imageConfig["Cmd"]),
              let mounts = value.raw["Mounts"] as? [[String: Any]], mounts.count == 1,
              mounts[0]["Type"] as? String == "volume", mounts[0]["Name"] as? String == Installation.dataVolume,
              mounts[0]["Destination"] as? String == "/data", ModuleJSON.boolean(mounts[0]["RW"]) == true,
              Set(value.networks.keys).isSubset(of: Set(["kingfisher_default", control])), value.networks["kingfisher_default"] != nil,
              !requireControl || value.networks[control] != nil else { throw ModuleIsolationError.invalid }
        let ports = ModuleJSON.dictionary(ModuleJSON.dictionary(value.raw["NetworkSettings"])["Ports"])
        let bindings = ModuleJSON.dictionary(value.host["PortBindings"])
        for mapping in [ports, bindings] {
            guard Set(mapping.keys) == ["8890/tcp"], let rows = mapping["8890/tcp"] as? [[String: String]], rows.count == 1,
                  rows[0]["HostIp"] == "127.0.0.1", rows[0]["HostPort"] == "8890" else { throw ModuleIsolationError.invalid }
        }
        if requireControl { try aliases(value, network: control, required: "kingfisher-controller", service: "kingfisher") }
    }
    static func commands(_ value: Any?) -> [String] { value as? [String] ?? [] }
    static func aliases(_ container: ModuleContainer, network: String, required: String, service: String) throws {
        let endpoint = ModuleJSON.dictionary(container.networks[network])
        guard let values = endpoint["Aliases"] as? [String], values.contains(required) else { throw ModuleIsolationError.invalid }
        let allowed = Set([required, service, container.name, container.id, String(container.id.prefix(12))])
        guard Set(values).isSubset(of: allowed) else { throw ModuleIsolationError.invalid }
    }
    static func bytes(_ value: String) -> Int64? {
        let lower = value.lowercased(), suffix = lower.last
        let scale: Int64 = suffix == "m" ? 1024 * 1024 : suffix == "k" ? 1024 : 1
        guard let amount = Int64(scale == 1 ? lower : String(lower.dropLast())), amount >= 0 else { return nil }
        let (bytes, overflow) = amount.multipliedReportingOverflow(by: scale)
        return overflow ? nil : bytes
    }
    static func tmpfs(_ value: Any?, worker: Bool) -> Bool {
        guard let values = value as? [String: String], Set(values.keys) == ["/tmp", "/data"] else { return false }
        for (path, text) in values {
            let parts = text.split(separator: ",").map(String.init)
            var entries: [String: String] = [:]
            for part in parts {
                let fields = part.split(separator: "=", maxSplits: 1).map(String.init)
                guard let key = fields.first, entries[key] == nil else { return false }
                entries[key] = fields.count == 2 ? fields[1] : ""
            }
            let allowed: Set<String> = path == "/tmp" ? ["rw", "noexec", "nosuid", "size", "uid", "gid", "mode"] : ["rw", "noexec", "nosuid", "size", "mode"]
            guard Set(entries.keys) == allowed, entries["rw"] == "", entries["noexec"] == "", entries["nosuid"] == "",
                  bytes(entries["size"] ?? "") == (path == "/tmp" ? (worker ? 64 : 16) * 1024 * 1024 : 64 * 1024),
                  Int(entries["mode"] ?? "", radix: 8) == (path == "/tmp" ? 0o700 : 0) else { return false }
            if path == "/tmp" && (entries["uid"] != "1000" || entries["gid"] != "1000") { return false }
        }
        return true
    }
    static func role(_ value: ModuleContainer, role: ModuleRole, image: [String: Any], runtime: VerifiedRuntime, key: String, requireRunning: Bool = true) throws {
        let worker = role == .worker
        var env = try baseline(image)
        if !worker { env[controlKey] = key }
        let entrypoint = worker ? ["/runtime/bin/node", "/runtime/harness_service.mjs", "--" + ModuleRuntimeStatus.mode] : ["python", "/runtime/harness_gateway.py", "--" + ModuleRuntimeStatus.mode]
        guard (!requireRunning || value.running), value.owned(project: project, service: role.rawValue), value.image == image["Id"] as? String,
              value.config["Image"] as? String == value.image, value.config["User"] as? String == "1000:1000", value.environment == env,
              value.config["Entrypoint"] as? [String] == entrypoint, commands(value.config["Cmd"]).isEmpty,
              ModuleJSON.dictionary(value.config["Healthcheck"])["Test"] as? [String] == ["NONE"],
              ModuleJSON.boolean(value.host["ReadonlyRootfs"]) == true, ModuleJSON.boolean(value.host["Privileged"]) == false,
              value.host["CapDrop"] as? [String] == ["ALL"], commands(value.host["CapAdd"]).isEmpty,
              value.host["SecurityOpt"] as? [String] == ["no-new-privileges:true"],
              ModuleJSON.integer(value.host["Memory"]) == (worker ? 536870912 : 100663296),
              ModuleJSON.integer(value.host["NanoCpus"]) == (worker ? 750000000 : 250000000),
              ModuleJSON.integer(value.host["PidsLimit"]) == (worker ? 64 : 32), value.host["Dns"] as? [String] == ["127.0.0.1"],
              tmpfs(value.host["Tmpfs"], worker: worker), noPublishedPorts(value.host["PortBindings"]),
              noPublishedPorts(ModuleJSON.dictionary(value.raw["NetworkSettings"])["Ports"]),
              value.host["NetworkMode"] as? String == (worker ? workerNetwork : control),
              (value.host["PidMode"] as? String ?? "").isEmpty, ["", "private"].contains(value.host["IpcMode"] as? String ?? ""),
              ["Devices", "DeviceRequests", "ExtraHosts", "Links", "VolumesFrom"].allSatisfy({ value.host[$0] == nil || value.host[$0] is NSNull || (value.host[$0] as? [Any])?.isEmpty == true }),
              let mounts = value.raw["Mounts"] as? [[String: Any]], mounts.count == 1,
              mounts[0]["Type"] as? String == "bind", mounts[0]["Source"] as? String == runtime.hostPath,
              mounts[0]["Destination"] as? String == "/runtime", ModuleJSON.boolean(mounts[0]["RW"]) == false,
              Set(value.networks.keys) == (worker ? [workerNetwork] : [control, workerNetwork]) else { throw ModuleIsolationError.invalid }
        try aliases(value, network: workerNetwork, required: worker ? "kingfisher-worker" : "kingfisher-gateway", service: role.rawValue)
        if !worker { try aliases(value, network: control, required: "kingfisher-gateway-control", service: role.rawValue) }
    }
    static func network(_ value: [String: Any], role: String, members: Set<String>) throws -> String {
        let name = project + "-" + role, labels = value["Labels"] as? [String: String] ?? [:]
        guard value["Name"] as? String == name, let id = value["Id"] as? String, ModuleRuntimeContract.validDigest(id),
              ModuleJSON.boolean(value["Internal"]) == true, value["Driver"] as? String == "bridge",
              labels["com.docker.compose.project"] == project, labels["com.docker.compose.network"] == role,
              Set(ModuleJSON.dictionary(value["Containers"]).keys) == members else { throw ModuleIsolationError.invalid }
        return id
    }
    static func validate(imageData: Data, mainData: Data, gatewayData: Data, workerData: Data, controlData: Data, workerNetworkData: Data,
                         runtime: VerifiedRuntime, controlKey: String) throws -> ModuleIsolationProof {
        let image = try ModuleJSON.inspect(imageData)
        guard image["Os"] as? String == "linux", let id = image["Id"] as? String, ModuleRuntimeContract.validImage(id),
              let arch = image["Architecture"] as? String, ModuleRuntimeArchitecture(engine: arch)?.rawValue == runtime.architecture,
              validKey(controlKey), ModuleRuntimeContract.validDigest(runtime.manifestDigest) else { throw ModuleIsolationError.invalid }
        let mainValue = try ModuleContainer(mainData), gateway = try ModuleContainer(gatewayData), worker = try ModuleContainer(workerData)
        try main(mainValue, image: image, requireControl: true)
        guard mainValue.environment[modeKey] == ModuleRuntimeStatus.mode, mainValue.environment[self.controlKey] == controlKey else { throw ModuleIsolationError.invalid }
        try role(gateway, role: .gateway, image: image, runtime: runtime, key: controlKey)
        try role(worker, role: .worker, image: image, runtime: runtime, key: controlKey)
        let controlID = try network(ModuleJSON.inspect(controlData), role: "control", members: [mainValue.id, gateway.id])
        let workerNetworkID = try network(ModuleJSON.inspect(workerNetworkData), role: "worker", members: [gateway.id, worker.id])
        return ModuleIsolationProof(mainID: mainValue.id, gatewayID: gateway.id, workerID: worker.id, imageID: id,
            runtimePath: runtime.hostPath, manifestDigest: runtime.manifestDigest, controlID: controlID,
            workerNetworkID: workerNetworkID, mainControlIP: try mainValue.address(control))
    }
    static let workerChecks = ["uid", "no_capabilities", "no_new_privileges", "root_read_only", "tmp_noexec", "private_data_denied", "no_authority_env", "gateway_reachable", "main_dns_denied", "main_ip_denied", "model_denied", "egress_denied", "ui_denied", "controller_denied"]
    static let gatewayChecks = ["uid", "no_capabilities", "no_new_privileges", "root_read_only", "tmp_noexec", "private_data_denied"]
    static func validateProbe(_ data: Data, role: ModuleRole) throws {
        let value = try ModuleJSON.object(data), fields = role == .worker ? workerChecks : gatewayChecks
        guard Set(value.keys) == Set(fields), fields.allSatisfy({ ModuleJSON.boolean(value[$0]) == true }) else { throw ModuleIsolationError.invalid }
    }
}

extension ModuleIsolation {
    // Compiled fixed probes use only stdlib in the already verified immutable image.
    // No source text, credential or provider endpoint is passed into a worker.
    static let sandboxProbe = #"""
    import errno,json,os,socket,subprocess,sys,threading,uuid,urllib.request,urllib.error
    class ClosedRedirect(urllib.request.HTTPRedirectHandler):
     def redirect_request(self,*args,**kwargs):return None
    r={}
    r['uid']=os.getuid()==1000
    try:
     s=open('/proc/self/status').read()
     fields=dict(line.split(':',1) for line in s.splitlines() if ':' in line)
     r['no_capabilities']=int(fields['CapEff'].strip(),16)==0
     r['no_new_privileges']=fields['NoNewPrivs'].strip()=='1'
    except Exception:r['no_capabilities']=r['no_new_privileges']=False
    p='/home/kingfisher/.kf-isolation-'+uuid.uuid4().hex
    owned_home=os.stat('/home/kingfisher').st_uid==1000
    try:
     f=open(p,'xb');f.close();os.unlink(p);r['root_read_only']=False
    except OSError as e:r['root_read_only']=owned_home and e.errno==errno.EROFS
    p='/tmp/kf-isolation-'+uuid.uuid4().hex
    created=False
    try:
     with open(p,'xb') as f:f.write(b'#!/bin/sh\nexit 0\n')
     created=True;os.chmod(p,0o700)
     try:subprocess.run([p],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1);r['tmp_noexec']=False
     except PermissionError:r['tmp_noexec']=True
     except Exception:r['tmp_noexec']=False
    finally:
     if created:os.unlink(p)
    try:
     d=os.open('/data',os.O_RDONLY|os.O_DIRECTORY);os.close(d);r['private_data_denied']=False
    except OSError as e:r['private_data_denied']=e.errno==errno.EACCES
    if len(sys.argv)>1:
     def deny(host,port):
      try:
       c=socket.create_connection((host,port),timeout=.7);c.close();return False
      except socket.gaierror:return True
      except OSError as e:return isinstance(e,TimeoutError) or e.errno in (errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ETIMEDOUT)
     def get(path,port=8890):
      q=urllib.request.Request('http://kingfisher-gateway:'+str(port)+path)
      o=urllib.request.build_opener(urllib.request.ProxyHandler({}),ClosedRedirect(),urllib.request.HTTPHandler())
      try:
       v=o.open(q,timeout=1);return v.status,'set-cookie' in v.headers
      except urllib.error.HTTPError as e:return e.code,'set-cookie' in e.headers
     r['no_authority_env']=not any(k.startswith('KF_') or k.endswith('_TOKEN') or k.endswith('_API_KEY') or 'PASSPHRASE' in k or 'PASSWORD' in k for k in os.environ)
     try:r['gateway_reachable']=get('/health')==(200,False)
     except Exception:r['gateway_reachable']=False
     dns=[]
     def lookup():
      try:socket.getaddrinfo('kingfisher-controller',8890);dns.append(False)
      except socket.gaierror:dns.append(True)
     t=threading.Thread(target=lookup,daemon=True);t.start();t.join(1)
     r['main_dns_denied']=dns==[True]
     r['main_ip_denied']=deny(sys.argv[1],8890) and deny(sys.argv[1],8892)
     r['model_denied']=deny('host.docker.internal',11434) and deny(sys.argv[2],11434)
     r['egress_denied']=deny('1.1.1.1',443)
     try:r['ui_denied']=all(get(p)==(404,False) for p in ('/','/api/v1/episodes/unknown','/api/v1/modules/local-source/runtime/status'))
     except Exception:r['ui_denied']=False
     try:r['controller_denied']=get('/controller/health',8891)==(401,False)
     except Exception:r['controller_denied']=False
    print(json.dumps(r,separators=(',',':')))
    """#
    static let hostModelAddressProbe = #"""
    import json,socket
    print(json.dumps({'address':socket.gethostbyname('host.docker.internal')}))
    """#
    static let brokerProbe = #"""
    import json,os,urllib.request,urllib.error
    class ClosedRedirect(urllib.request.HTTPRedirectHandler):
     def redirect_request(self,*args,**kwargs):return None
    r=[]
    o=urllib.request.build_opener(urllib.request.ProxyHandler({}),ClosedRedirect())
    for token in ('',os.environ.get('ICARUS_SIDECAR_TOKEN','')):
     q=urllib.request.Request('http://127.0.0.1:8892/worker/mcp',data=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
     try:
      v=o.open(q,timeout=1);r.append(False)
     except urllib.error.HTTPError as e:r.append(e.code==401 and 'set-cookie' not in e.headers)
    print(json.dumps({'missing_grant_denied':r[0],'master_token_denied':r[1]}))
    """#
    static func validateBrokerProbe(_ data: Data) throws {
        let value = try ModuleJSON.object(data)
        guard Set(value.keys) == ["missing_grant_denied", "master_token_denied"],
              value.values.allSatisfy({ ModuleJSON.boolean($0) == true }) else { throw ModuleIsolationError.invalid }
    }
}
