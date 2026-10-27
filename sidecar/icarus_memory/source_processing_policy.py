"""Explicit, source-scoped permission for a single remote memory operation."""


class ExplicitSourcePolicy:
    """A capability for one source, provider, and current permission state.

    The normal path still requires a local provider. A remote caller must pass
    this object explicitly; its callback rechecks consent, the source snapshot,
    and the provider grant each time analysis reaches a provider boundary.
    """

    def __init__(self, provider, episode_id, authorize):
        self.provider = provider
        self.episode_id = episode_id
        self._authorize = authorize

    def permits(self, provider, episode):
        if (provider is not self.provider or getattr(provider, "is_local", True)
                or getattr(provider, "is_remote", False) is not True
                or getattr(episode, "id", None) != self.episode_id):
            return False
        return bool(self._authorize(episode))


class ScopedProvider:
    """Zählt jeden Aufruf und prüft Freigabe, Quelle und Zugang beim Senden, über `complete_json_guarded`.

    Ein eingegrenzter Cloudanbieter für genau eine Quelle (`_episode`) unter genau einer Policy (`_policy`); beide
    bindet der Aufrufer, bevor der Anbieter die Quelle sieht (`cloud_memory._scoped`, `hintergrund_cloud.Einordnung`).
    Ohne `complete_json_guarded` beim inneren Anbieter zählt `before_request` wenigstens vor dem Aufruf.
    """
    is_local = False
    is_remote = True
    category_evidence_repair = True

    #: Wofür die Anfragen hinausgehen (`nach_draussen.WOFUER`); `hintergrund_cloud.Einordnung` setzt `einordnung`.
    wofuer = "import"

    def __init__(self, provider, policy, before_request):
        self._provider = provider
        self._policy = policy
        self._before_request = before_request
        self._episode = None
        self.name = getattr(provider, "name", "chatgpt")
        self.model = getattr(provider, "model", "")
        self.grant_id = getattr(provider, "grant_id", None)
        self.credential_revision = getattr(provider, "credential_revision", None)
        self.entity_anchor_mode = getattr(provider, "entity_anchor_mode", "absolute")

    def available(self):
        pruefung = getattr(self._provider, "available", None)
        return bool(pruefung()) if callable(pruefung) else True

    def complete_json(self, messages, *, max_tokens, schema):
        guarded_call = getattr(self._provider, "complete_json_guarded", None)
        if callable(guarded_call):
            return guarded_call(
                messages, max_tokens=max_tokens, schema=schema,
                before_send=self._vor_dem_senden,
                still_permitted=lambda: self._policy is not None and self._policy.permits(self, self._episode),
            )
        self._vor_dem_senden()
        return self._provider.complete_json(messages, max_tokens=max_tokens, schema=schema)

    def _vor_dem_senden(self):
        """Prüfen und zählen (Aufrufer), danach den Versand ohne Inhalt ins Logbuch (`nach_draussen.vermerken`)."""
        self._before_request()
        from . import nach_draussen
        nach_draussen.vermerken(self._provider, self.wofuer)


#: Bisheriger Name in `cloud_memory.py`.
_ScopedProvider = ScopedProvider
