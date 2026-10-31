"""Katalog und echte Aufnahme-/Aufgaben-/Abrufkette; keine Modellbewertung vortäuschen."""
from dataclasses import asdict
from contextlib import ExitStack
import os
from datetime import datetime
from email import policy
from email.parser import BytesParser
import json
from pathlib import Path
from unittest.mock import patch

CATALOG = Path(__file__).resolve().parents[1] / 'docs/evaluations/memory-quality/intake/catalog.json'


def _address(value):
    if not isinstance(value, str) or '@' not in value or not value.rsplit('@', 1)[1].endswith('.example'):
        raise ValueError('Nur reservierte künstliche .example-Adressen sind erlaubt.')


def load_catalog(path=CATALOG):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('synthetic_only') is not True or data.get('version') != 1:
        raise ValueError('Kein freigegebener synthetischer Katalog.')
    clock = datetime.fromisoformat(data['clock'])
    if clock.tzinfo is None: raise ValueError('Stichtag braucht Zeitzone.')
    _address(data['owner']['address'])
    ids = [s['id'] for s in data['mails']]
    if not ids or len(ids) != len(set(ids)): raise ValueError('Quellen-IDs fehlen oder sind doppelt.')
    for s in data['mails']:
        _address(s['sender']['address'])
        for recipient in s['recipients']: _address(recipient['address'])
        at = datetime.fromisoformat(s['at'])
        if at.tzinfo is None or at > clock: raise ValueError('Unzulässige Quellenzeit.')
        if s.get('reply_to') and s['reply_to'] not in ids: raise ValueError('Unbekannte Antwortquelle.')
        if not s['body'].strip() or s['expect']['tasks'] not in {'none','required','review'}:
            raise ValueError('Ungültiger Quelleninhalt oder Sollwert.')
    question_ids = [q['id'] for q in data['questions']]
    if len(question_ids) != len(set(question_ids)): raise ValueError('Doppelte Fragen-ID.')
    for q in data['questions']:
        if (not set(q['required']) <= set(q['allowed']) or not set(q['allowed']) <= set(ids)
                or not q['status']): raise ValueError('Unbekannte oder widersprüchliche Sollbelege.')
    return data


def to_mail(source, owner):
    """Explizites Feldmapping: Erwartungen sind keine Eingabe an Produkt oder Modell."""
    from messlatte.daten import Adresse, Mail
    address = lambda a: Adresse(a['name'], a['address'])
    return Mail(id=source['id'], zeit=datetime.fromisoformat(source['at']), szenario='aufnahme',
                von=address(source['sender']), an=tuple(address(a) for a in source['recipients']),
                betreff=source['title'], text=source['body'], ordner=source.get('folder','INBOX'),
                antwort_auf=source.get('reply_to'))


def omit_dates(mailbox, identifiers):
    """Datum nur im künstlichen RFC-822-Transport entfernen, niemals nach der Aufnahme."""
    for folder, rows in mailbox.ordner.items():
        for i, (uid, raw) in enumerate(rows):
            if mailbox.welt_id[(folder, uid)] in identifiers:
                message = BytesParser(policy=policy.default).parsebytes(raw)
                if 'Date' in message: del message['Date']
                rows[i] = (uid, message.as_bytes())


def _required_text_body(text):
    # Die gerenderte Belegliste enthält auch Quelltitel. Deren Wörter dürfen
    # eine fehlende eigentliche Antwort nicht als bestanden erscheinen lassen.
    body, separator, footer = text.partition('\n\nBelege\n')
    label, closing, _ = footer.partition('] ')
    citation_footer = separator and closing and label.startswith('[') and label[1:].isdigit()
    return body if citation_footer else text


def grade_question(case, observed):
    selected = set(observed.get('sources', []))
    text = observed.get('text', '').casefold()
    body = _required_text_body(observed.get('text', '')).casefold()
    return {'required_sources':set(case['required']) <= selected,
            'only_allowed_sources':selected <= set(case['allowed']),
            'status':observed.get('status') in case['status'],
            'required_text':all(t.casefold() in body for t in case.get('contains',[])),
            'forbidden_text_absent':all(t.casefold() not in text for t in case.get('excludes',[])),
            'choice_count':len(observed.get('choices',[])) >= case.get('minimum_choices',0)}


def _same_time(left, right):
    if left is None or right is None: return left is right
    try: return datetime.fromisoformat(left) == datetime.fromisoformat(right)
    except (ValueError, TypeError): return False


def grade_tasks(expect, observed):
    if expect['tasks'] == 'none': return {'no_own_task':not observed}
    checks = {'candidate_present':bool(observed), 'at_most_one':len(observed) <= 1}
    if not observed: return checks
    checks['action_anchor'] = all(expect.get('anchor','').casefold() in
        (r.get('statement','')+' '+r.get('quote','')).casefold() for r in observed)
    if 'person' in expect:
        checks['person'] = all((r.get('person_vorschlag') or {}).get('adresse') == expect['person'] for r in observed)
    if 'due' in expect:
        checks['due'] = all(_same_time(r.get('frist_vorschlag'), expect['due']) for r in observed)
    if 'temporal' in expect:
        checks['temporal'] = all(r.get('temporal_status') in expect['temporal'] for r in observed)
    if expect.get('not_recent'):
        checks['not_current'] = all(r.get('temporal_status') != 'recent' for r in observed)
    return checks


def grade_people(expect, people):
    actual = [set(p['adressen']) for p in people]
    groups = [set(g) for g in expect['separate']]
    matches = [[i for i,p in enumerate(actual) if g <= p] for g in groups]
    return {'required_identities_present':all(len(m)==1 for m in matches),
            'identities_not_merged':len({i for m in matches for i in m}) == len(groups),
            'service_not_person':not any(set(expect['not_people']) & p for p in actual)}


def run_pipeline(catalog, provider, directory, report, save, *, embedding_factory=None):
    """Nur der Transport ist künstlich; keine vorgegebene Einordnung/Aufgabe/Antwort."""
    from messlatte.aufnahme import aufnehmen
    from messlatte.instanz import instanz_starten
    from messlatte.antwort import antwort_nachricht, lese_nachricht
    from icarus_memory import personen
    from icarus_memory.aufgaben_von_selbst import Durchlauf
    from icarus_memory.config import MailAccountSettings
    from icarus_memory.proposals import ProposalKind
    from icarus_memory.task_detection import TaskDetector, candidate_batches
    from icarus_memory.working_memory_store import WorkingMemoryStore
    clock=datetime.fromisoformat(catalog['clock']); owner=catalog['owner']['address']
    report.setdefault('mode','mechanics')
    report.update(finished=False, bulk_import_authorized=False, semantic_grade='requires_review',
                  classification=[], task_rows=[], questions=[])
    # messlatte.aufnahme ruft Intake.step ohne Relevanzfilter auf. Weder der
    # Fachbrieftext noch sein Betreff ist eine vertrauenswürdige Auswahl.
    report['newsletter_selection']={'exercised':False,'trusted_allowed_senders':[],
        'selected_source_ids':[],'reason':'intake_fixture_does_not_apply_mail_filter'}
    with patch('icarus_memory.secrets.Keychain._detect', return_value='none'):
        with instanz_starten(stichtag=clock, zeitzone=catalog['timezone'], provider=provider,
                verzeichnis=directory, eigene=(owner,)) as app, ExitStack() as cleanup:
            app.app.state.settings.mail_accounts.append(MailAccountSettings(
                id='messlatte',label='Künstliches Postfach',imap_host='imap.messlatte.example',user=owner,sender=owner))
            # Ausschließlich die aktiv gestarteten Diagnoseaufrufe; kein Scheduler-/Hintergrundmodell.
            app.app.state.scheduler.stop()
            background=getattr(app.app.state,'hintergrund',None)
            if background: background.pausieren(True)
            report['stage']='fresh_intake';save()
            result=aufnehmen(app,[to_mail(s,catalog['owner']) for s in catalog['mails']],clock,modell=provider,
                postfach_haken=lambda box:omit_dates(box,{s['id'] for s in catalog['mails'] if s.get('omit_date_header')}))
            mapping=result.episoden;reverse={v:k for k,v in mapping.items()}
            report['intake']=asdict(result);report['source_map']=mapping
            memory=WorkingMemoryStore(app.episodes)
            for source in catalog['mails']:
                eid=mapping.get(source['id'])
                state=memory.source_state(eid) if eid else 'missing'
                refs=memory.source_refs(episode_ids=[eid])['refs'] if eid else []
                ep=app.episodes.get(eid) if eid else None
                report['classification'].append({'id':source['id'],'state':state,'kinds':[r['kind'] for r in refs],
                    'original_body_preserved':ep is not None and ep.body.strip()==source['body'].strip(),
                    'occurred_at':ep.occurred_at.isoformat() if ep and ep.occurred_at else None,
                    'date_absence_preserved':not source.get('omit_date_header') or ep is not None and ep.occurred_at is None})
            save();report['stage']='fresh_task_detection';save()
            detector=TaskDetector(app.episodes,app.app.state.proposals,provider,app.app.state.conversation_lock,tasks=app.app.state.tasks)
            # Ein vollständiger, begrenzter Scan; fertige Analysen werden nicht erneut als bessere Versuche gezählt.
            report['task_scan']=[asdict(detector.run(with_model=True,limit=20)) for _ in range(2)]
            helper=Durchlauf(app.app.state.tasks,app.episodes,app.app.state.proposals,
                workspace=app.app.state.workspace,eigene=lambda:[owner],jetzt=lambda:clock)
            rows=[]
            for batch in candidate_batches(app.app.state.proposals,app.episodes,now=clock):
                for proposal,ep,timing in batch:
                    rows.append({'source':reverse.get(ep.id),'statement':proposal.statement,'quote':proposal.evidence[0].quote,
                        **timing,**helper.vorbefuellt(proposal),
                        'quote_is_exact':proposal.evidence[0].quote in ep.body})
            report['task_rows']=rows
            report['task_checks']=[{'id':s['id'],'checks':grade_tasks(s['expect'],[r for r in rows if r['source']==s['id']])} for s in catalog['mails']]
            report['tasks_created_without_confirmation']=len(app.app.state.tasks.all_tasks())
            people=personen.alle(episodes=app.episodes,tasks=app.app.state.tasks,store=app.app.state.store,
                jetzt=clock,workspace=app.app.state.workspace,eigene=[owner])
            # Die alte Teilnehmerliste bleibt sichtbar, misst aber weder die
            # Qualitätskategorie noch den tatsächlich sichtbaren Personenfilter.
            report['people_legacy']=[{'name':p.name,'adressen':p.adressen} for p in people]
            report['people_legacy_checks']=grade_people(catalog['people'],report['people_legacy'])
            graph=app.anfrage('GET','/api/v1/memory/verzeichnis')
            report['people_graph']=[node for node in graph['nodes'] if node['kind']=='person']
            report['people_projection']={'source':'/api/v1/memory/verzeichnis','filter':'people'}
            def visible_person(node):
                attributes=node['attributes'];category=attributes.get('quality_category')
                # Entspricht peopleQuality.ts: unbekannte Kategorie nur mit
                # explizit bestätigter Identität als Mensch behandeln.
                return category=='person' or category not in {'person','automated','review'} and \
                    attributes.get('identity_resolution') in {'explicit_registry','confirmed_group'}
            report['people']=[{'name':node['label'],'adressen':node['attributes'].get('addresses',[]),
                               'node_id':node['id']} for node in report['people_graph'] if visible_person(node)]
            report['people_checks']=grade_people(catalog['people'],report['people']);save()
            service=None
            if embedding_factory is not None:
                from icarus_memory.working_memory_semantic_service import SemanticService
                report['stage']='semantic_index';save()
                previous=getattr(app.app.state,'semantic_search',None)
                if previous is not None:previous.close()
                service=SemanticService(app.episodes,embedding_factory,permission_lock=app.app.state.conversation_lock)
                cleanup.callback(service.close)
                app.app.state.semantic_search=service;app.agent._working_memory_search=service
                os.environ['KINGFISHER_DURABLE_MEMORY_SEARCH']='1'  # Nur in der gekapselten Messumgebung.
                for _ in range(12):
                    step=service.index_batch();report['semantic_coverage']=service.coverage();save()
                    if not step.ok:raise RuntimeError('Semantischer Testindex nicht verfügbar.')
                    if report['semantic_coverage']['status']=='indexed':break
                if report['semantic_coverage']['status']!='indexed':raise RuntimeError('Semantischer Testindex unvollständig.')
                report['semantic_search']=True
            report['stage']='fresh_recall';save()
            report['semantic_observations']=[]
            for case in catalog['questions']:
                report['question_id']=case['id']
                tracked=('model_calls','embedding_calls','embedding_sessions','provider_refusals')
                offsets={key:len(report.get(key,[])) for key in tracked}
                cid=app.anfrage('POST','/api/v1/conversations',{})['conversation']['id']
                try:
                    answer=app.anfrage('POST',f'/api/v1/conversations/{cid}/messages',
                        {'message':case['question'],'answer_mode':'auto'})
                    message=antwort_nachricht(answer);observed=lese_nachricht(message,reverse)
                    observed={'text':observed['text'],'status':observed['status'],
                              'sources':list(observed['belege'] or []),'choices':list(observed['auswahl'])}
                    report['questions'].append({'id':case['id'],'observed':observed,'checks':grade_question(case,observed)})
                except Exception as error:
                    report['questions'].append({'id':case['id'],'error':type(error).__name__})
                    save()
                    if getattr(error,'fatal',False):raise
                finally:
                    failures=[{'kind':key,'index':i,'failure_origin':row.get('failure_origin'),
                               'failure_reason':row.get('failure_reason')}
                              for key in tracked for i,row in enumerate(report.get(key,[]))
                              if i>=offsets[key] and (key=='provider_refusals' or row.get('status')!='completed')]
                    # Ein hilfreicher Originalrückfall darf stehen bleiben, ohne
                    # den technischen Ausfall als Wissenslücke auszugeben.
                    report['questions'][-1].update(technical_status='failed' if failures or
                        report['questions'][-1].get('error') else 'no_observed_failure',technical_failures=failures)
                    save()
                if service is not None:
                    report['semantic_observations'].append({'id':case['id'],'coverage':service.coverage()})
                save()
            report.pop('question_id',None)
            if service is not None:report['semantic_after_recall']=service.coverage()
            report['originals_preserved']=all(app.episodes.get(mapping[s['id']]).body.strip()==s['body'].strip() for s in catalog['mails'])
            report['finished']=True;report['stage']='finished';save()
    return report
