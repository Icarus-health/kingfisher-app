"""Artificial-only acceptance fixture for the actual managed source controller.

There are no application settings, personal stores, connectors or cloud models.
Only the trusted controller has the positively verified local Ollama transport.
"""
from pathlib import Path
import os
import tempfile
import threading

from fastapi import Depends, FastAPI, Header, HTTPException

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.local_module_controller import MODEL
from icarus_memory.local_module_model import VerifiedModuleModel
from icarus_memory.local_module_routes import register
from icarus_memory.local_module_lifecycle_routes import register as lifecycle
from icarus_memory.local_module_runtime import ManagedLocalSourceRuntime
from icarus_memory.model import Provenance, SourceType
from icarus_memory.procedures import ProcedureStore
from icarus_memory.providers import OpenAICompatible


CASES = [
    dict(id='requester-versus-owner', text='Künstliche Prüfquelle KF-Modulprobe43. '
         'Vera König bittet Sören Kube: Bitte sende den Entwurf für Nordstern bis '
         '7. November 2026, 17 Uhr. Matthias Braun liefert seine Unterlagen bis '
         '6. November 2026, 12 Uhr. Das Treffen ist am 9. November 2026, 10 Uhr. '
         'Der Termin ist keine Abgabefrist.',
         question='Wer soll laut dieser Quelle was erledigen und bis wann? Trenne Abgabefristen vom Treffen.'),
    dict(id='requester-owner-reversed', text='Sören Kube bittet Vera König: Bitte sende '
         'den Entwurf für Nordstern bis 7. November 2026, 17 Uhr. Matthias Braun '
         'liefert seine Unterlagen bis 6. November 2026, 12 Uhr. '
         'Das Treffen ist am 9. November 2026, 10 Uhr. Sören übernimmt keine Lieferung.',
         question='Wer hat welche Aufgabe und bis wann? Unterscheide Auftraggeber und ausführende Person.'),
    dict(id='person-task-deadline', text='Von: Vera König <vera.koenig@example.invalid>\n'
         'Datum: 2. November 2026\nHallo Sören, bitte sende mir den Entwurf für das Projekt '
         'Birke bis zum 7. November 2026. Viele Grüße, Vera König',
         question='Wer bittet um welche Aufgabe und bis wann? Nenne nur belegte Angaben.'),
    dict(id='appointment-versus-deadline', text='Von: Matthias Braun <matthias.braun@example.invalid>\n'
         'Datum: 2. November 2026\nDie Besprechung ist am 9. November 2026 um 10 Uhr. '
         'Ich, Matthias Braun, sende die Unterlagen bis zum 6. November 2026 um 17 Uhr. '
         'Sören hat keine eigene Aufgabe zugesagt.',
         question='Welche Aufgabe hat wer, welche Abgabefrist gilt und was ist nur ein Termin?'),
    dict(id='ambiguous-name', text='Projekt Birke: Alexander Meier und Alexander Wolf arbeiten mit. '
         'Beide werden gelegentlich Alex genannt. Alex soll den Entwurf senden. '
         'Welcher der beiden gemeint ist und bis wann, steht nicht in der Nachricht.',
         question='Welcher Alex muss den Entwurf bis wann senden? Frage nach, wenn es nicht eindeutig ist.'),
    dict(id='ambiguous-other-name', text='Im Projekt Fjord arbeiten Jana Neumann und Jana Peters. '
         'Beide werden Jana genannt. Die Nachricht lautet: Jana kümmert sich um das Protokoll. '
         'Weder der Nachname noch eine Abgabefrist sind in der Nachricht angegeben.',
         question='Welche Jana übernimmt das Protokoll und wann ist es fällig?'),
    dict(id='meeting-as-deadline', text='Vera König bittet Sören Kube: Sende den Entwurf '
         'spätestens bis zum Treffen am 9. November 2026 um 10 Uhr. Dies ist der späteste '
         'Abgabezeitpunkt. Wer am Treffen teilnimmt, steht nicht in der Nachricht.',
         question='Wer soll was bis wann abgeben? Gibt es eine belegte Abgabefrist?'),
    dict(id='three-name-candidates', text='Alexander Meier, Alexander Wolf und Alexander Braun '
         'werden im Projekt alle Alex genannt. Alex soll den Entwurf senden. Welche der drei '
         'Personen gemeint ist, steht nicht dabei; auch keine Frist.',
         question='Welcher Alex soll den Entwurf senden?'),
    dict(id='delegated-request', text='Vera König bittet Sören Kube: Frage bitte Matthias Braun, '
         'ob er die Unterlagen bis zum 6. November 2026 um 12 Uhr liefern kann. '
         'Matthias hat noch nicht geantwortet. Eine Frist für Sörens Nachfrage ist nicht genannt.',
         question='Was soll Sören tun, was hat Matthias zugesagt, und welche Fristen sind verbindlich belegt?'),
]

temporary = tempfile.TemporaryDirectory(prefix='kf-artificial-local-source-')
root = Path(temporary.name)
episodes = EpisodeStore(root / 'episodes.sqlite3')
procedures = ProcedureStore(root / 'procedures.sqlite3')
sources = {case['id']: episodes.record(EpisodeKind.DOCUMENT, case['id'], case['text'],
    Provenance(source_type=SourceType.DOCUMENT))[0] for case in CASES}
originals = {key: source.to_dict() for key, source in sources.items()}
calls = []
provider = OpenAICompatible(MODEL, 'artificial-local', 'http://host.docker.internal:11434/v1',
                            trusted_local_hosts=('host.docker.internal',))


class TrackedModel(VerifiedModuleModel):
    def infer(self, identity, messages, tools, permitted):
        row = dict(model=identity.model, local=identity.local,
                   source_safety='Quellen' in messages[0].get('content', ''))
        calls.append(row)
        try:
            reply = super().infer(identity, messages, tools, permitted)
            # Artificial fixture only: actual tool choices explain bounded
            # loop failures without collecting headers, grants or credentials.
            row['tool_choices'] = [dict(name=tool.name, arguments=tool.arguments)
                                   for tool in reply.tool_calls]
            row['returned_text'] = bool(reply.text)
            return reply
        except Exception as error:
            row['failure_type'] = type(error).__name__
            raise


model = TrackedModel(lambda: provider, threading.Lock())
runtime = ManagedLocalSourceRuntime(episodes, procedures, model, os.environ['KF_GATEWAY_CONTROL_KEY'])
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def auth(x_icarus_token: str | None = Header(default=None)):
    import secrets
    if not secrets.compare_digest(x_icarus_token or '', os.environ['ICARUS_SIDECAR_TOKEN']):
        raise HTTPException(401, 'Unauthorized artificial fixture')


guard = [Depends(auth)]
register(app, guard, controller_factory=runtime.controller_for_request)
lifecycle(app, guard, runtime_factory=lambda: runtime)


@app.get('/fixture/readiness', dependencies=guard)
def readiness():
    return dict(artificial_only=True, cases=[dict(id=case['id'], source_id=sources[case['id']].id,
        fingerprint=episodes.belegbarer_snapshot(sources[case['id']].id).support_fingerprint(),
        question=case['question'], original=case['text']) for case in CASES])


@app.get('/fixture/receipt', dependencies=guard)
def receipt():
    return dict(artificial_only=True, calls=calls, originals_unchanged=all(
        episodes.get(source.id).to_dict() == originals[key] for key, source in sources.items()),
        runtime=runtime.status())
