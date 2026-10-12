"""Human-readable intake status, derived from the current original and index."""
from .working_memory_store import WorkingMemoryStore

LABELS = {
    'complete': 'Automatisch eingeordnet',
    'empty': 'Eingeordnet · keine verwertbaren Angaben erkannt',
    'pending': 'Gespeichert · Einordnung ausstehend oder wird aktualisiert',
    'queued': 'Gespeichert · zur Einordnung vorgemerkt',
    'processing': 'Wird gerade automatisch eingeordnet',
    'paused': 'Gespeichert · automatische Einordnung pausiert',
    # Fremdprobe 3, Befund 9: „erneuter Versuch bei aktiver Automatik“ las sich bei laufender Automatik wie ein
    # Widerspruch. Jetzt je nach Stand ein Satz, der stimmt.
    'failed': 'Einordnung fehlgeschlagen · erneuter Versuch ausstehend',
    'failed_paused': 'Einordnung fehlgeschlagen · Kingfisher versucht es wieder, sobald das automatische Sortieren läuft',
    'deferred': 'Nicht eingeordnet · Quelle zu umfangreich oder unvollständig',
    'dismissed': 'Automatische Einordnung von dir verworfen',
    'excluded': 'Nicht für das Arbeitsgedächtnis verfügbar',
}


def _automatik_vorgesehen(app):
    plan = app.state.settings.schedule
    # Das Gesprächsmodell ist nicht die Hintergrundrolle. Die Anzeige liest
    # nur den Zeitplan; Modellbereitschaft und Ausführung prüft der Worker.
    return bool(plan.enabled and plan.with_model)


def source_status(app, episode_id):
    state = WorkingMemoryStore(app.state.episodes).source_state(episode_id)
    if state in {'pending', 'failed'}:
        scheduler = getattr(app.state, 'scheduler', None)
        observed = scheduler.memory_state(episode_id) if scheduler is not None else None
        if observed == 'processing':
            # Ein schon laufender Aufruf kann die geänderte Freigabe erst
            # beim nächsten Worker-Prüfpunkt sehen; er ist noch nicht beendet.
            state = 'processing'
        elif not _automatik_vorgesehen(app):
            state = 'failed_paused' if state == 'failed' else 'paused'
        elif observed == 'queued':
            state = 'queued'
    return {'state': state, 'label': LABELS[state]}
