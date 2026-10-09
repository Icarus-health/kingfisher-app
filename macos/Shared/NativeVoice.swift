import Foundation

struct VoiceRequest {
    let action: String
    let id: String
    let text: String?
    init?(message: Any) {
        guard let body=message as? [String:Any], let action=body["aktion"] as? String,
              ["spracheStatus","spracheStart","spracheEnde","spracheAbbrechen","spracheVorlesen","spracheStopp"].contains(action),
              let id=body["id"] as? String, UUID(uuidString:id) != nil else { return nil }
        let speaking=action=="spracheVorlesen"
        guard Set(body.keys)==(speaking ? Set(["aktion","id","text"]) : Set(["aktion","id"])) else { return nil }
        if speaking {
            guard let text=body["text"] as? String, !text.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty, text.count<=8000 else { return nil }
            self.text=text
        } else { self.text=nil }
        self.action=action;self.id=id
    }
}

protocol NativeVoiceReading: AnyObject {
    var supportsLocal: Bool { get }
    func authorize(if allowed: @escaping () -> Bool, _ done: @escaping (Bool) -> Void)
    func start(result: @escaping (String,Bool) -> Void, failure: @escaping () -> Void) throws
    func finish()
    func cancel()
}
protocol NativeVoiceSpeaking: AnyObject {
    var available: Bool { get }
    var speaking: Bool { get }
    func speak(_ text: String) -> Bool
    func stop()
}
struct VoiceEvent {
    let id: String
    let state: String
    var text: String = ""
    var dictationAvailable: Bool = false
    var speechAvailable: Bool = false
    var dictionary: [String:Any] { ["id":id,"state":state,"text":text,"dictationAvailable":dictationAvailable,"speechAvailable":speechAvailable] }
}

/// Main-thread coordinator; no storage/network. Permission and transcription callbacks
/// are bound to one request and its still-active document. Partial results are drafts.
final class NativeVoiceEngine {
    private let reader: NativeVoiceReading
    private let speaker: NativeVoiceSpeaking
    private let clock: () -> Date
    private let emit: (VoiceEvent) -> Void
    private var generation=0
    private var id: String?
    private var allowed: () -> Bool = {false}
    private var phase="idle"
    private var text=""
    private var deadline: Date?

    init(reader:NativeVoiceReading,speaker:NativeVoiceSpeaking,clock:@escaping()->Date=Date.init,emit:@escaping(VoiceEvent)->Void) {
        self.reader=reader;self.speaker=speaker;self.clock=clock;self.emit=emit
    }
    private func report(_ state:String,_ text:String="") {
        guard let id=id else { return }
        emit(VoiceEvent(id:id,state:state,text:text,dictationAvailable:reader.supportsLocal,speechAvailable:speaker.available))
    }
    func handle(_ request: VoiceRequest,allowed:@escaping()->Bool) {
        switch request.action {
        case "spracheStatus":
            emit(VoiceEvent(id:request.id,state:"ready",dictationAvailable:reader.supportsLocal,speechAvailable:speaker.available))
        case "spracheStart":
            cancelAll();id=request.id;self.allowed=allowed
            guard allowed(),reader.supportsLocal else { report("unavailable");return }
            phase="authorizing";report(phase);let token=generation
            reader.authorize(if:{[weak self] in self?.valid(token)==true}) {[weak self] granted in
                guard let self=self,self.valid(token) else { return }
                guard granted,self.reader.supportsLocal else { self.end("unavailable");return }
                self.phase="listening";self.deadline=self.clock().addingTimeInterval(60);self.report(self.phase)
                do {
                    try self.reader.start(result:{[weak self] value,final in
                        guard let self=self,self.valid(token),["listening","finishing"].contains(self.phase) else { return }
                        guard value.count<=4000 else { self.end("failed");return }
                        self.text=value
                        if final { self.end("completed",value) }
                        else { self.report(self.phase,value) }
                    },failure:{[weak self] in guard let self=self,self.valid(token) else{return};self.end("failed")})
                }catch { self.end("failed") }
            }
        case "spracheEnde":
            guard request.id==id,allowed(),phase=="listening" else { return }
            finish()
        case "spracheAbbrechen":
            guard request.id==id else{return};report("canceled");cancelAll()
        case "spracheVorlesen":
            guard allowed(),speaker.available,let text=request.text else{return}
            cancelAll();id=request.id;self.allowed=allowed
            phase=speaker.speak(text) ? "speaking" : "idle"
            report(phase=="speaking" ? phase : "failed")
        case "spracheStopp":
            guard request.id==id else{return};report("canceled");cancelAll()
        default:break
        }
    }
    private func valid(_ token:Int)->Bool {token==generation && id != nil && allowed()}
    private func finish(){phase="finishing";deadline=clock().addingTimeInterval(5);reader.finish();report(phase,text)}
    private func end(_ state:String,_ value:String="") {
        generation+=1;deadline=nil;phase="idle";reader.cancel();report(state,value)
    }
    var hasWork:Bool {["authorizing","listening","finishing","speaking"].contains(phase)}
    func suspend(){report("canceled");cancelAll()}
    func tick() {
        guard id != nil else{return}
        guard allowed() else {report("canceled");cancelAll();return}
        if phase=="speaking",!speaker.speaking{end("completed");return}
        if let deadline=deadline,clock()>=deadline {
            if phase=="listening"{finish()}
            else if phase=="finishing"{end(text.isEmpty ? "failed" : "completed",text)}
        }
    }
    func cancelAll(){generation+=1;deadline=nil;phase="idle";text="";id=nil;allowed={false};reader.cancel();speaker.stop()}
}
