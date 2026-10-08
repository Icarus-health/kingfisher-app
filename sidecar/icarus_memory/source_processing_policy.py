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
