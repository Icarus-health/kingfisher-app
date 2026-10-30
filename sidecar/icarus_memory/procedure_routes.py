"""Geschützte Prüfung expliziter Lernvorschläge, getrennt von Wissensaussagen."""
import hashlib
import json
import re

from fastapi import HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from .procedures import CORE, ProcedureError, ProcedureStore, Spec, episode_dependency
from .providers import ProviderError
from .procedure_model import draft as draft_procedure


def connect(app, directory):
    app.state.procedures = ProcedureStore(directory / 'procedures.sqlite3',
        dependency=lambda identifier: episode_dependency(app.state.episodes, identifier))


def explicit_learning(message):
    if re.match(r'^(?:bitte\s+)?(?:lerne|merke dir)\s+(?:diesen|folgenden|den)\s+ablauf\s*:', message.strip(), re.I):
        return True
    # Nur die direkte eigene Bitte, keine Suche nach Anweisungen in Zitaten,
    # Mails oder nachfolgenden Zeilen. Stil und biografische Fakten sind kein Ablauf.
    line = message.strip().partition('\n')[0][:600]
    if '?' in line:
        return False
    context = r'(?P<scope>[^:!?;\n]{3,120}?)'
    request = re.match(r'^(?:bitte\s+)?(?:merke dir|lerne)\s+(?:für|bei)\s+' + context + r'\s*:\s*(?P<steps>.+)$', line, re.I)
    if request is None:
        request = re.match(r'^(?:bitte\s+)?(?:bei|für)\s+' + context
            + r'\s+(?:bitte\s+)?(?:künftig|in zukunft|ab jetzt|immer)\s+(?P<steps>.+)$', line, re.I)
        if request and not (line.lower().startswith('bitte ') or
                re.search(r'\bbitte\s+(?:künftig|in zukunft|ab jetzt|immer)\b',line,re.I)):
            return False
    if request is None:
        return False
    # Beschreibungen wie „laut Handbuch gilt …“ und erzählte Handlungen
    # bleiben normale Inhalte, auch wenn sie Tätigkeitswörter enthalten.
    narrative = (r'\b(?:laut|steht|gilt|sagt|schreibt|berichtet|heißt|ich|wir|er|sie|du|ihr|es|'
                 r'lernen|lernt|war|waren|wurde|ist|sind|hat|haben)\b')
    if re.search(narrative,request.group('scope')+' '+request.group('steps'),re.I):
        return False
    steps = re.fullmatch(r'(?:zuerst|erst)\s+(.+?)\b(?:dann|danach|anschließend)\s+(.+)', request.group('steps'), re.I)
    action = (r'\b(?:prüfen|prüfe|klären|kläre|suchen|suche|zuordnen|vergleichen|entwerfen|'
              r'zusammenfassen|auflisten|öffnen|lesen|gegenlesen|festhalten|nachfragen|'
              r'bestätigen|sortieren|verknüpfen|abgleichen)\b')
    return bool(steps and all(re.search(action+r'\s*[,.;]?\s*(?:und\s*)?$',step,re.I) for step in steps.groups()))


def learn(app, message, source_episode):
    """Eine ausdrückliche Lernbitte ist ein Entwurf, keine automatische Aktivierung."""
    from .agent import Turn
    from .model import SourceType
    if not explicit_learning(message) or source_episode.provenance.source_type is not SourceType.CHAT:
        raise ProcedureError('Nur eine ausdrückliche eigene Lernbitte erzeugt einen Ablaufvorschlag.')
    provider = getattr(app.state.agent, 'provider', None)
    if provider is None or not getattr(provider, 'is_local', False):
        return Turn(reply='Für persönliche Lernvorschläge verwende ich das lokale Modell. Bitte aktiviere es unter Einstellungen → KI und Zugänge. Du kannst den Ablauf auch unter Kingfisher und du → Bewährte Abläufe eintragen.')
    stamp = episode_dependency(app.state.episodes, source_episode.id)
    if not stamp:
        raise ProcedureError('Die Lernbitte ist nicht mehr verfügbar.')
    # Vor einer weiteren Modellrunde nach demselben Original und Auftrag suchen.
    key = hashlib.sha256(message.strip().encode()).hexdigest()
    prior = next((item for item in app.state.procedures.items()
                  if item.get('request_key') == key and item['state'] in {'pending','active'} and item['current']), None)
    if prior:
        candidate = prior
    else:
        messages = [dict(role='system', content='Forme die ausdrückliche Arbeitsanweisung des Nutzers in einen knappen Ablaufvorschlag um. '
            'Gib ausschließlich JSON nach diesem Schema zurück: ' + json.dumps(Spec.model_json_schema(), ensure_ascii=False)
            + '\nKeine Fakten, Namen, Empfängeradressen oder festen Termine in den Ablauf kopieren. '
            'Keine neuen Werkzeuge, Berechtigungen oder Skripte. Bereich mail, planning oder analysis. '
            'Auslöser sind ganze Wörter der ausdrücklichen Aufgabe. Das Positivbeispiel muss einen Auslöser enthalten; '
            'das Gegenbeispiel keinen. Schritte prüfen Eingaben, Vorgehen und Ergebnis. '
            'Bestehende passende Abläufe wiederverwenden; bei einer Korrektur denselben Namen verwenden. '
            'Vorhandene passende Metadaten: ' + json.dumps(app.state.procedures.learning_catalog(message), ensure_ascii=False)),
            dict(role='user', content=message[:6000])]
        try:
            app.state.agent.assert_egress_allowed(messages)
            response = draft_procedure(provider, messages, Spec.model_json_schema())
            if getattr(response, 'tool_calls', None):
                raise ProcedureError('Werkzeugaufrufe sind keine Ablaufbeschreibung.')
            candidate = app.state.procedures.propose(json.loads(response.text),
                sources={source_episode.id:stamp}, request_key=key)
        except ProviderError:
            return Turn(reply='Das lokale Modell konnte den Lernvorschlag gerade nicht erstellen. Bitte versuche es später mit einer kurzen Beschreibung. Es wurde kein Ablauf aktiviert.')
        except Exception:
            return Turn(reply='Den Ablauf konnte ich noch nicht sauber eingrenzen. Bitte nenne den Anlass, die Schritte und einen Fall, in dem er nicht gelten soll. Es wurde kein Ablauf aktiviert.')
    reply = ('Der Ablauf „' + candidate['title'] + '“ ist bereits übernommen und wird bei passenden Anfragen verwendet.'
             if candidate['state'] == 'active' else
             'Der Ablauf „' + candidate['title'] + '“ liegt zur Prüfung bereit. Unter Einstellungen → Kingfisher und du → Bewährte Abläufe kannst du Schritte und Beispiele prüfen und ihn übernehmen. Bis dahin bleibt er inaktiv.')
    return Turn(reply=reply,
        context={'procedure_proposal': {'id':candidate['id'], 'title':candidate['title'], 'state':candidate['state']}})


class ProposalIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    spec: Spec
    sources: list[str] = Field(default_factory=list, max_length=8)


def register(app, guard):
    @app.get('/api/v1/procedures', dependencies=guard)
    def list_procedures():
        return {'items':app.state.procedures.items(), 'core':[
            dict(id=name, name=name, title=value[0], category=value[1], area=value[2], description=value[3])
            for name, value in CORE.items()]}

    @app.post('/api/v1/procedures', dependencies=guard, status_code=201)
    def propose(body: ProposalIn):
        with app.state.conversation_lock:
            try:
                stamps = {identifier:episode_dependency(app.state.episodes, identifier) for identifier in body.sources}
                if any(not value for value in stamps.values()):
                    raise ProcedureError('Eine Grundlage ist nicht mehr aktuell.')
                return app.state.procedures.propose(body.spec.model_dump(), sources=stamps)
            except ProcedureError as exc:
                raise HTTPException(422, str(exc)) from exc

    @app.get('/api/v1/procedures/{identifier}', dependencies=guard)
    def get_procedure(identifier: str):
        try:
            return app.state.procedures.get(identifier)
        except ProcedureError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get('/api/v1/procedures/{identifier}/export', dependencies=guard)
    def export_procedure(identifier: str):
        try:
            return PlainTextResponse(app.state.procedures.export(identifier),
                media_type='text/markdown', headers={'Content-Disposition':'attachment; filename="SKILL.md"'})
        except ProcedureError as exc:
            raise HTTPException(404, str(exc)) from exc

    def mutate(identifier, action):
        with app.state.conversation_lock:
            try:
                item = getattr(app.state.procedures, action)(identifier)
                app.state.audit.record('procedure_' + action, 'write_local', 'confirm', 'executed',
                    {'id':item['id'], 'name':item['name'], 'version':item['version']}, approved_by='user')
                return item
            except ProcedureError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.post('/api/v1/procedures/{identifier}/accept', dependencies=guard)
    def accept(identifier: str):
        return mutate(identifier, 'accept')

    @app.post('/api/v1/procedures/{identifier}/reject', dependencies=guard)
    def reject(identifier: str):
        return mutate(identifier, 'reject')

    @app.post('/api/v1/procedures/{identifier}/revoke', dependencies=guard)
    def revoke(identifier: str):
        return mutate(identifier, 'revoke')
