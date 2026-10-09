import Foundation

func check(_ value: @autoclosure () -> Bool, _ label: String) { if !value() { fatalError(label) } }
let first = UUID().uuidString, second = UUID().uuidString
check(VoiceRequest(message:["aktion":"spracheStart","id":first]) != nil,"valid request")
for bad: [String:Any] in [[:],["aktion":"spracheStart","id":"bad"],["aktion":"spracheStart","id":first,"text":"injected"],["aktion":"spracheVorlesen","id":first,"text":"   "],["aktion":"spracheVorlesen","id":first,"text":String(repeating:"x",count:8001)]] {
 check(VoiceRequest(message:bad)==nil,"strict request")
}
final class Reader: NativeVoiceReading {
 var supportsLocal = true
 var permission: (() -> Bool, (Bool) -> Void)?
 var result: ((String,Bool) -> Void)?
 var failure: (() -> Void)?
 var starts=0, finishes=0, cancels=0
 func authorize(if allowed: @escaping () -> Bool, _ done:@escaping(Bool)->Void){permission=(allowed,done)}
 func start(result:@escaping(String,Bool)->Void, failure:@escaping()->Void) throws { starts+=1;self.result=result;self.failure=failure }
 func finish(){finishes+=1}
 func cancel(){cancels+=1}
}
final class Speaker: NativeVoiceSpeaking {
 var available=true;var speaking=false;var texts:[String]=[];var stops=0
 func speak(_ text:String)->Bool{texts.append(text);return true}
 func stop(){stops+=1}
}
let reader=Reader(), speaker=Speaker();var active=true,events:[VoiceEvent]=[],now=Date(timeIntervalSince1970:0)
let engine=NativeVoiceEngine(reader:reader,speaker:speaker,clock:{now},emit:{events.append($0)})
func command(_ action:String,_ id:String=first,_ text:String?=nil) {
 var value:[String:Any]=["aktion":action,"id":id];if let text=text{value["text"]=text}
 engine.handle(VoiceRequest(message:value)!,allowed:{active})
}
command("spracheStatus");check(events.last?.dictationAvailable==true,"local capability")
command("spracheStart");check(reader.starts==0,"no capture before consent")
let late=reader.permission!
active=false;late.1(true);check(reader.starts==0,"no late permission after hidden")
active=true;command("spracheStart",second);reader.permission!.1(true);check(reader.starts==1,"consent starts")
reader.result!("Hallo",false);check(events.last?.text=="Hallo" && events.last?.state=="listening","partial remains draft")
command("spracheEnde",first);check(reader.finishes==0,"wrong session cannot stop")
command("spracheEnde",second);check(reader.finishes==1,"finish capture")
reader.result!("Hallo Welt",true);check(events.last?.state=="completed" && events.last?.text=="Hallo Welt","final draft")
let obsolete=reader.result!
command("spracheStart",first);reader.permission!.1(true)
let count=events.count;obsolete("wrong old result",true);check(events.count==count,"ignore old callback")
command("spracheAbbrechen");let canceledCount=events.count;reader.result!("late",true);check(events.count==canceledCount,"cancel ignores late result")
command("spracheStart",second);reader.permission!.1(true);reader.result!("Begrenzter Entwurf",false)
now=now.addingTimeInterval(61);engine.tick();check(reader.finishes==2,"bounded recording")
now=now.addingTimeInterval(6);engine.tick();check(events.last?.state=="completed" && events.last?.text=="Begrenzter Entwurf","bounded finalization")
reader.supportsLocal=false;let before=reader.starts;command("spracheStart");check(reader.starts==before && events.last?.state=="unavailable","no remote fallback")
command("spracheVorlesen",first,"Nur geprüfter Text");check(speaker.texts==["Nur geprüfter Text"],"explicit speaking")
active=false;command("spracheVorlesen",second,"hidden");check(speaker.texts.count==1,"no hidden voice start")
engine.cancelAll();check(speaker.stops>0,"stop speaker on exit")
print("Native voice contract passed")
