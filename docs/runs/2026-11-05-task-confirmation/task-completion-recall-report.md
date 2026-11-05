# P1 confirmed task completion in memory recall

**NEEDS_CONTEXT** · Base `b906d43956abee9caf33fee5a0602eb60fa0d3d9`

The strict evidence route still sees only an older mail after an explicit task completion. The current task history cannot establish which `completed` events were explicitly confirmed. The same event can be produced by a model tool call without a corresponding user instruction or approval. Only this report was written in the worktree.

## Reproduction and observations

The appendix is a runnable characterization test. It opens a real `create_app` with the default agent/store wiring and exercises authenticated HTTP routes through the in-process FastAPI test client. The provider is synthetic at every model call. The test sets a synthetic sidecar token, blocks outgoing socket connections, disables sentence generation and leaves the MCP door shut. The normal test fixtures isolate stores and disable Keychain and update-server access. No frozen heldout inputs are used.

1. Ingest two original synthetic mails for `LINDENBOGEN-46` through `mail_ingestion.remember`. The first requests the material-list check. The older status report states that only the first page is checked and approval remains outstanding. Run the production `TaskDetector` over the request mail using synthetic extraction and review outputs. Read the actual candidate from `GET /api/v1/task-candidates` and accept it through the candidate route. The accepted open task identifies its originating request episode. For the report mail, store the literal section as a synthetic historical classification via `WorkingMemoryStore.commit`; this deliberately isolates retrieval from classification quality.
2. At `2026-09-24T16:05:00+02:00`, use `POST /api/v1/tasks/{id}/done` twice. The same task reads back as `done` with the action time and one `completed` transition. History gives `recorded_at=2026-09-24T14:05:00+00:00`, `business_at=null` and `actor_id=null`. Replaying identical report mail under the same transport identity returns the existing source.
3. At `16:10+02:00`, send `Wurde „LINDENBOGEN-46 Materialliste prüfen“ erledigt?` with `answer_mode=memory_evidence` through the conversation-message route. The provider's entire candidate list is one historical source row. The saved and newly returned answer is a `working_reports` source report with an episode link and no task ID, completion timestamp or current saved decision. The selected older wording is attributed as a report with an uncertain time relationship. The defect is the absence of the task state, with no observed assertion that the older report is current or authoritative.
4. Reopen, then drop the same task through the authenticated routes. Readback distinguishes `open` with no `done_at` from `dropped` with a non-null `done_at`. The original saved source-only answer is unchanged across both task transitions. Withdrawing the report episode through the ignore route removes its text from the conversation view while preserving its original. The subsequent chat's provider input contains no copy of the withdrawn report. Withdrawing the original request episode also preserves the saved task and its original. No task completion evidence was ever presented, so these checks establish current source invalidation behavior only.
5. Before importing the mails, create a similarly named task, `LINDENBOGEN-46 Materialliste archivieren`. In a fresh ordinary chat whose only user message is `Sag nur Hallo.`, have the synthetic provider return `aufgabe_erledigt` for that task. The actual tool executes with no approval and audit `(notify, executed, approved_by=null)`. The recorded completion fields, transition and times match the direct route's shape after allowing for different IDs, sequences and creation fields. This is a forced counterexample to using the event as proof of user intent. A model can also invoke the tool in response to a legitimate user request, and an explicit approval may be collected on a tainted turn. Neither route origin nor affirmative approval is part of the task event, so the counterexample does not classify real past tool executions.

The positive assertions describe existing behavior and pass. There is no implementation or green regression for the desired product behavior. The reproduction exercises no external model, makes no claim about real extraction or recall quality, and tests the configured closed MCP door rather than a new task-answer egress boundary.

## Wiring and design decision

- `server.py` sends explicit evidence-mode conversation turns through `_memory_conversation_turn` to `Agent.answer_memory`. That method tries literal original lookup and specialized open/coming, identity, and calendar paths, then working memory and a knowledge-claim fallback. `working_memory_answers.prepare` assembles source/claim inputs. `EvidenceAnswer` accepts only `knowledge` items backed by claim lineage. The normal task list tool reads open tasks. The forthcoming view also reads open tasks, and the open-points view uses dossiers. These routes cannot supply the missing completion evidence to the strict answer.
- The direct/legacy done routes and the ordinary model tool all call `TaskStore.complete`. In `tasks.py`, it appends `completed` only when the state changes. History is append-only, and the returned `actor_id` is always null. The automated mail completion path has the distinct `post_completed` event; that is a source-related change, not proof of a confirmed user decision. The audit record is stored separately, has no task-event sequence, and absence of an audit row cannot prove that a task event originated from the user interface.
- Stored source answers already use neutral text and reproject a bounded set of references at readback. Ordinary model history excludes those assistant answers in `Agent.load_history`. Task changes currently neither change the claim revision nor appear in those references. An episode source stamp can validate a mail report, but it cannot validate a task transition.
- The public task/history interfaces already exist. The UI opens the specific task using `/vorhaben?view=done&task=<id>` and exposes its history in the task detail. Chat source links currently represent episodes and are rendered as episode controls. Faking an episode or accepted claim for a saved task would misstate the evidence and create a second record of the decision.

## Bounded decision for the next patch

### A. Completion tool approval and event provenance

The production builder passes `Policy()`. `Policy` accepts per-tool overrides, so production can set the default for `aufgabe_erledigt` to `CONFIRM` while preserving its `WRITE_LOCAL` classification and leaving other writes alone. The explicit UI done route can remain a one-click action. Existing named rules can lower the level on an untainted turn, and the existing taint escalation can raise `CONFIRM` to `CONFIRM_STRICT`. A named rule or explicit constructor override that runs the tool without a fresh grant remains delegated execution. The approval text currently shows only the opaque task ID. Show the current task title and identity in the local approval UI, with no title added to the MCP dry-run response, which currently echoes the approval dry run. Bind a pending request to the task identity and the displayed task state, and refuse a stale request after the task changes. The existing approval resolver checks knowledge, profile and procedure freshness but does not bind an approval to a task transition. The execution-side compare and change must occur together to cover concurrent direct actions.

For a user-confirmation guarantee, add an explicit origin at the existing task write boundary. The smallest candidate is a distinct append-only `user_confirmed_completion` event on the authenticated direct done action, using the existing `kind` and state fields. Leave generic legacy `completed` and mail-origin events at their known certainty. A user click on a task already marked done by a different path requires its own deduplicated confirmation for that active completion, with confirmation time separate from the existing completion time. An approval route may opt in later only if it can bind the explicit approval to this exact task and transition. Preserve old records and avoid retrospective attribution. The local route records an explicit action without claiming a verified individual identity.
### B. Typed task-status recall

Once that contract is agreed, reuse the bounded readback pattern for a local task-status response. Resolve an explicit task ID or an exact quoted task title in a narrow status-question form. Read enough exact matches to detect ambiguity regardless of status and fail closed on duplicate matches. Ordinary source questions continue on the source path. The chosen task ID, active event sequence and applicable source-support stamp form the proof for a small neutral persisted reference. Include a task detail/history link using the existing task deep link rather than an episode link. Recheck the proof at conversation readback and omit the assistant result from model history, including while it is current. A reopened or dropped task invalidates the proof, and a later completion does not revive a reference to an older event. A withdrawn source invalidates any answer relying on it while the independently saved task decision remains in its store. A title originating solely in a withdrawn episode requires an explicit disclosure policy before it can be used in recall.
If the scope is limited to current saved state and accepts unknown origin, a narrower read-only alternative can say that Kingfisher stores a task as done, with its time and history link. That would help task inspection while failing the explicit-confirmation requirement for existing generic events. Both options can use the current TaskStore and public task/history routes without general task-language matching, external model input, or MCP changes.

## Command and result

Run from the worktree. The first command extracts the exact runnable appendix into `/private/tmp/kf_task_completion_recall_repro_20261105.py`. Its SHA-256 is `d2605715ac5e064b8a11e4145f10964832c9d9eb722b945543c34353d5b4d07d`. The appendix in this report is the durable reproduction.

```sh
report=.superpowers/sdd/2026-11-04-kingfisher-product-completion/task-completion-recall-report.md
awk '/^```python$/ {copy=1; next} copy && /^```$/ {exit} copy {print}' "$report" > /private/tmp/kf_task_completion_recall_repro_20261105.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. /private/tmp/kf-core-20261104-env/bin/python -m pytest -p tests.conftest -q -s /private/tmp/kf_task_completion_recall_repro_20261105.py
```

Result for the completed characterization run was `1 passed, 1 warning`, exit 0. FastAPI's TestClient reported its existing Starlette/httpx deprecation warning. The brief limited testing to the bounded repair and ruled out a backend suite rerun. Production and tracked test files were left untouched.

## Runnable appendix

```python
import json
import socket
from datetime import datetime

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, server
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_ingestion import remember
from icarus_memory.providers import Reply, ToolCall
from icarus_memory.task_detection import TaskDetector
from icarus_memory.working_memory_store import WorkingMemoryStore
from messlatte.uhr import eingefrorene_zeit
from tests.test_conversation_retraction import _close_app

TOKEN = 'synthetic-recall-owner'
TITLE = 'LINDENBOGEN-46 Materialliste prüfen'
ASK = f'Wurde „{TITLE}“ erledigt?'
REQUEST = f'Bitte die {TITLE} und die Freigabe dokumentieren.'
OLDER = 'LINDENBOGEN-46 Materialliste prüfen: Nur die erste Seite ist geprüft; die Freigabe steht aus.'
ACTION = datetime.fromisoformat('2026-09-24T16:05:00+02:00')
QUERY = datetime.fromisoformat('2026-09-24T16:10:00+02:00')
MAILED = datetime.fromisoformat('2026-09-21T11:00:00+02:00')


class SyntheticProvider:
    name = model = 'synthetic'
    is_local = True
    is_remote = False

    def __init__(self):
        self.tool_target = None
        self.report_calls = 0
        self.chat_calls = []

    def complete_json(self, messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content']) if messages[-1]['content'].startswith('{') else {}
        if 'candidates' in data:
            assert data['body'].endswith(REQUEST)
            response = {'reviews': [{'id': 0, 'kind': 'request_to_recipient', 'title_supported': True}]}
        elif 'body' in data:
            assert REQUEST in data['body']
            response = {'items': [{'title': TITLE, 'quote': REQUEST}]}
        elif 'sources' in data:
            self.report_calls += 1
            print('SELECTOR INPUT:', data['sources'])
            matching = [row['id'] for row in data['sources'] if OLDER in str(row)]
            assert len(matching) == 1
            response = {'status': 'reports', 'ids': matching}
        else:
            response = {}
        return Reply(text=json.dumps(response))

    def complete(self, messages, tools):
        self.chat_calls.append(messages)
        if self.tool_target:
            assert 'aufgabe_erledigt' in str(tools)
            target, self.tool_target = self.tool_target, None
            return Reply(tool_calls=[ToolCall('synthetic-tool-call', 'aufgabe_erledigt', {'id': target})])
        return Reply(text='Synthetische Antwort.')


def test_missing_confirmed_task_recall(monkeypatch):
    def no_connect(*args, **kwargs):
        raise AssertionError('Synthetic proof must never connect to a socket.')

    monkeypatch.setattr(socket.socket, 'connect', no_connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', no_connect)
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', TOKEN)
    monkeypatch.setenv('KINGFISHER_MCP_TUER', '0')
    provider = SyntheticProvider()
    monkeypatch.setattr(server, 'provider_from_env', lambda: provider)
    app = server.create_app(SelfModelStore(MemoryBackend(), subject_id='synthetic'))
    app.state.agent._saetze = False
    client = TestClient(app, headers={'X-Icarus-Token': TOKEN})
    try:
        def get(path, expected=200):
            response = client.get(path)
            assert response.status_code == expected, response.text
            return response.json() if expected == 200 else None

        def post(path, body=None, expected=200):
            response = client.post(path, json=body) if body is not None else client.post(path)
            assert response.status_code == expected, response.text
            return response.json()

        def conversation():
            return post('/api/v1/conversations', {}, 201)['conversation']['id']

        def ask(conv, mode='memory_evidence', text=ASK):
            return post(f'/api/v1/conversations/{conv}/messages',
                        {'message': text, 'answer_mode': mode}, 201)['messages'][-1]

        def mail(uid, body):
            message = Message(uid=f'synthetic:8.{uid}', subject='LINDENBOGEN-46 Prüfstatus',
                              sender='Lina <lina@example.invalid>', date=MAILED,
                              preview=body, unread=False, body=body, account_id='synthetic')
            return remember(app.state.episodes, message, claims=app.state.claims)

        # No source or existing conversation context can taint this first chat.
        other = post('/api/v1/tasks', {'title': 'LINDENBOGEN-46 Materialliste archivieren'}, 201)
        other_path = f"/api/v1/tasks/{other['id']}"
        provider.tool_target = other['id']
        with eingefrorene_zeit(ACTION):
            model_turn = ask(conversation(), 'chat', 'Sag nur Hallo.')
        other_event = get(other_path + '/history')['items'][0]
        print('CHAT TOOL:', model_turn['metadata']['used_tools'], model_turn['metadata']['approvals'])
        audit = [(row['level'], row['outcome'], row['approved_by'])
                 for row in app.state.audit.entries(10) if row['tool'] == 'aufgabe_erledigt']
        print('CHAT AUDIT:', audit)
        assert audit == [('notify', 'executed', None)]
        assert model_turn['metadata']['used_tools'] == ['aufgabe_erledigt']
        assert model_turn['metadata']['approvals'] == []
        assert other_event['kind'] == 'completed' and other_event['actor_id'] is None

        request = mail(1, REQUEST)['episode']
        older = mail(2, OLDER)['episode']
        report = TaskDetector(app.state.episodes, app.state.proposals, provider,
                              app.state.conversation_lock, tasks=app.state.tasks).run(
                                  with_model=True, source_ids=[request['id']])
        assert (report.analyzed, report.proposed, report.failed) == (1, 1, 0), report
        candidate, = get('/api/v1/task-candidates')
        accepted = post(f"/api/v1/task-candidates/{candidate['id']}/accept", {'title': TITLE})
        task_path = f"/api/v1/tasks/{accepted['id']}"
        assert accepted['status'] == 'open'
        assert accepted['provenance']['source_ref'] == 'episode:' + request['id']
        working = WorkingMemoryStore(app.state.episodes)
        source = working.pending(episode_ids=[older['id']])[0]
        assert working.commit(source, [{'start': 0, 'end': len(source.episode.body), 'kind': 'historical'}],
                              model='synthetic')
        with eingefrorene_zeit(ACTION):
            completed = post(task_path + '/done')
            assert post(task_path + '/done') == completed
        event, creation = get(task_path + '/history')['items']
        print('DIRECT COMPLETION:', completed['status'], completed['done_at'], event['kind'],
              event['recorded_at'], event['business_at'], event['actor_id'])
        assert get(task_path) == completed
        assert completed['status'] == 'done' and datetime.fromisoformat(completed['done_at']) == ACTION
        assert creation['kind'] == 'from_suggestion'
        assert event['kind'] == 'completed' and event['actor_id'] is None
        for key in ('kind', 'recorded_at', 'business_at', 'actor_id'):
            assert event[key] == other_event[key]
        for key in ('before', 'after'):
            for field in ('status', 'done_at'):
                assert event[key][field] == other_event[key][field]
        assert not mail(2, OLDER)['new']

        with eingefrorene_zeit(QUERY):
            conv = conversation()
            reply = ask(conv)
            saved = get(f'/api/v1/conversations/{conv}')['messages'][-1]
            print('STRICT REPLY:', reply['content'])
            ctx = reply['metadata']['context']
            print('STRICT CONTRACT:', ctx['answer_mode'], ctx['answer_contract']['status'], ctx.get('source_links'))
            assert ctx['answer_mode'] == 'memory_evidence'
            assert ctx['answer_contract']['status'] == 'working_reports'
            assert OLDER in reply['content'] and OLDER in saved['content']
            assert ctx['source_links'][0]['episode_id'] == older['id']
            assert accepted['id'] not in str(reply)
            assert provider.report_calls == 1

            reopening = post(task_path + '/reopen')
            assert reopening['status'] == 'open' and reopening['done_at'] is None
            assert OLDER in get(f'/api/v1/conversations/{conv}')['messages'][-1]['content']
            dropping = post(task_path + '/drop')
            assert dropping['status'] == 'dropped' and dropping['done_at']
            assert OLDER in get(f'/api/v1/conversations/{conv}')['messages'][-1]['content']
            post(f"/api/v1/episodes/{older['id']}/ignore")
            withdrawn = get(f'/api/v1/conversations/{conv}')['messages'][-1]
            print('WITHDRAWN:', withdrawn['content'])
            assert OLDER not in str(withdrawn)
            assert app.state.episodes.get(older['id']).body.endswith(OLDER)
            ask(conv, 'chat', 'Sag nur Danke.')
            assert OLDER not in str(provider.chat_calls[-1])
            print('SUBSEQUENT CHAT: old mail report absent from model prompt')
            post(f"/api/v1/episodes/{request['id']}/ignore")
            assert get(task_path)['status'] == 'dropped'
            assert app.state.episodes.get(request['id']).body.endswith(REQUEST)
            assert get('/tools', 403) is None
            assert app.state.claims.all_claims() == []
    finally:
        client.close()
        _close_app(app)
```
