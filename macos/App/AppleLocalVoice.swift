import AppKit
import AVFoundation
import Speech

/// Native APIs only. The recognition request cannot fall back to remote processing.
final class AppleLocalVoiceReader: NativeVoiceReading {
    private let recognizer=SFSpeechRecognizer(locale:Locale(identifier:"de-DE"))
    private let engine=AVAudioEngine()
    private var request:SFSpeechAudioBufferRecognitionRequest?
    private var task:SFSpeechRecognitionTask?
    private var tapped=false
    var supportsLocal:Bool {
        let permission=SFSpeechRecognizer.authorizationStatus()
        return permission != .denied && permission != .restricted && recognizer?.supportsOnDeviceRecognition==true && recognizer?.isAvailable==true
    }
    func authorize(if allowed:@escaping()->Bool,_ done:@escaping(Bool)->Void) {
        guard allowed(),supportsLocal else{done(false);return}
        let microphone:()->Void={
            guard allowed(),SFSpeechRecognizer.authorizationStatus() == .authorized else{done(false);return}
            switch AVCaptureDevice.authorizationStatus(for:.audio) {
            case .authorized:done(allowed())
            case .notDetermined:
                AVCaptureDevice.requestAccess(for:.audio) { granted in DispatchQueue.main.async{done(granted && allowed())} }
            default:done(false)
            }
        }
        if SFSpeechRecognizer.authorizationStatus() == .notDetermined {
            SFSpeechRecognizer.requestAuthorization { status in DispatchQueue.main.async {
                guard status == .authorized,allowed() else{done(false);return};microphone()
            } }
        }else{microphone()}
    }
    func start(result:@escaping(String,Bool)->Void,failure:@escaping()->Void) throws {
        cancel()
        guard supportsLocal,SFSpeechRecognizer.authorizationStatus() == .authorized,
              AVCaptureDevice.authorizationStatus(for:.audio) == .authorized,let recognizer=recognizer else {throw VoiceFailure.unavailable}
        let request=SFSpeechAudioBufferRecognitionRequest()
        request.requiresOnDeviceRecognition=true
        request.shouldReportPartialResults=true
        self.request=request
        let input=engine.inputNode,format=input.outputFormat(forBus:0)
        guard format.sampleRate>0,format.channelCount>0 else{throw VoiceFailure.unavailable}
        input.installTap(onBus:0,bufferSize:1024,format:format){buffer,_ in request.append(buffer)}
        tapped=true
        task=recognizer.recognitionTask(with:request){value,error in DispatchQueue.main.async{
            if let value=value{result(value.bestTranscription.formattedString,value.isFinal)}
            else if error != nil{failure()}
        }}
        engine.prepare();try engine.start()
    }
    func finish(){engine.stop();if tapped{engine.inputNode.removeTap(onBus:0);tapped=false};request?.endAudio()}
    func cancel(){finish();task?.cancel();task=nil;request=nil}
    private enum VoiceFailure:Error{case unavailable}
}

/// Installed system voices; no synthesis requests or audio files outside this process.
final class AppleLocalVoiceSpeaker: NativeVoiceSpeaking {
    private let synthesizer=AVSpeechSynthesizer()
    private var voice:AVSpeechSynthesisVoice? {AVSpeechSynthesisVoice.speechVoices().first{$0.language=="de-DE"}}
    var available:Bool{voice != nil}
    var speaking:Bool{synthesizer.isSpeaking}
    func speak(_ text:String)->Bool {
        stop();guard let voice=voice else{return false}
        let utterance=AVSpeechUtterance(string:text);utterance.voice=voice
        synthesizer.speak(utterance);return true
    }
    func stop(){synthesizer.stopSpeaking(at:.immediate)}
}
