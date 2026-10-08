from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from email.message import EmailMessage
from io import BytesIO
from dataclasses import replace
from datetime import datetime, timezone
import json
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from icarus_memory import anhaenge, source_index
from icarus_memory.episodes import EpisodeStore
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_ingestion import remember
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.proposals import ProposalStore, Evidence
from icarus_memory.knowledge_render import KnowledgeInputBuild
from icarus_memory.source_versions import invalidate_with_corrections

def document(blank=False):
    writer=PdfWriter()
    font=writer._add_object(DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')}))
    page=writer.add_blank_page(width=595,height=842)
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 11 Tf 50 790 Td (Aurorabeleg 4711) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    if blank:writer.add_blank_page(width=595,height=842)
    out=BytesIO();writer.write(out);return out.getvalue()

def envelope(data):
    mail=EmailMessage();mail.set_content('Synthetic cover')
    mail.add_attachment(data,maintype='application',subtype='pdf',filename='Vertrag.pdf')
    return mail

with TemporaryDirectory() as tmp, ExitStack() as stack:
    stores=[]
    for cls,name in ((EpisodeStore,'episodes'),(ClaimStore,'claims'),(ProposalStore,'proposals')):
        store=cls(Path(tmp)/(name+'.sqlite3'));stack.callback(store.close);stores.append(store)
    episodes,claims,proposals=stores
    report={};items=anhaenge.aus_mail(envelope(document()),bericht=report)
    assert report['vollstaendig'] and items[0].vollstaendig
    original=Message('qa:1','Synthetic','QA <qa@example.test>',datetime(2026,10,8,tzinfo=timezone.utc),'',False,body='Synthetic cover',account_id='qa',anhaenge=items,anhang_bericht=report)
    captured=remember(episodes,original,claims=claims);parent=captured['episode']['id'];child_id=captured['anhaenge'][0];child=episodes.get(child_id)
    claims.entities.create('person','Synthetic QA',explicit_id='person:qa')
    service=KnowledgeService(episodes=episodes,claims=claims,proposals=proposals)
    proposal,_=service.propose(subject_ref='person:qa',predicate='qa_fact',value='Aurorabeleg 4711',statement='Aurorabeleg 4711',rationale='Synthetic explicit acceptance',evidence=[Evidence(child_id,'Aurorabeleg 4711',child.digest)])
    claim=service.accept(proposal.id,supersedes=[])
    assert KnowledgeInputBuild(claims,episodes.support_snapshot).capture(claim.id)
    partial_report={};partial=anhaenge.aus_mail(envelope(document()),abgeschnitten=True,bericht=partial_report)
    updated=remember(episodes,replace(original,body='Synthetic',truncated=True,anhaenge=partial,anhang_bericht=partial_report),claims=claims)
    assert updated['episode']['id']==parent
    assert episodes.support_snapshot(child_id).current()
    assert KnowledgeInputBuild(claims,episodes.support_snapshot).capture(claim.id)
    mixed_report={};mixed,=anhaenge.aus_mail(envelope(document(blank=True)),bericht=mixed_report)
    assert not mixed.vollstaendig and mixed.ungelesene_seiten==[2]
    assert 'Seite 2' in anhaenge.text(mixed,'Synthetic',None)
    long=anhaenge.Anhang('Long.pdf','pdf',anhaenge.GELESEN,('START '+('x'*60000),'y\n'*100000),2)
    rendered=anhaenge.text(long,'Synthetic',None)
    assert 'START ' in rendered and len(rendered)<60400 and not long.vollstaendig
    invalidate_with_corrections(episodes,claims,parent);episodes.ignore(parent,grund='qa-withdrawal')
    assert not episodes.support_snapshot(child_id).current()
    assert KnowledgeInputBuild(claims,episodes.support_snapshot).capture(claim.id) is None
    assert child_id not in source_index.suchen(episodes._conn,'Aurorabeleg').episoden
    assert claims.get(claim.id).status.value=='disputed'
    assert 'Aurorabeleg 4711' in episodes.get(child_id).body
print(json.dumps({'synthetic_only':True,'real_pdf_worker':True,'parent_withdrawal_claim_and_search_verified':True,'partial_refresh_preserves_complete_evidence':True,'mixed_pdf_gap_visible':True,'character_budget_verified':True,'model_calls':0,'network':False}))
