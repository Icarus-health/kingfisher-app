"""Provider adapter that applies the model-routing boundary before calling out."""

from __future__ import annotations

from typing import Any

from .audit import AuditLog
from .model_routing import Candidate, RoutingError, select_candidate
from .providers import Provider, ProviderError, Reply


class RoutedProvider:
    """Select and call explicitly registered providers, with bounded fallback."""

    def __init__(
        self,
        default: Provider,
        candidates: list[tuple[Candidate, Provider]],
        *,
        task: str = "conversation",
        local_only: bool = True,
        audit: AuditLog | None = None,
    ) -> None:
        if not isinstance(local_only, bool) or not isinstance(task, str) or not task.strip():
            raise RoutingError("invalid routing provider settings")
        self._default = default
        self._task = task
        self._local_only = local_only
        self._audit = audit
        self.trace: list[dict[str, Any]] = []
        self._model = str(getattr(default, "model", ""))
        self._candidates = list(candidates)
        if not self._candidates:
            # An explicit default is still a registered candidate; its declared
            # capability is conservative and never discovered remotely.
            self._candidates = [(
                Candidate("default", str(default.model), bool(default.is_local), frozenset({"text"}), 0, 0, 0),
                default,
            )]
        ids: set[str] = set()
        for candidate, provider in self._candidates:
            if not isinstance(candidate, Candidate) or not hasattr(provider, "complete"):
                raise RoutingError("invalid routed provider candidate")
            if candidate.id in ids:
                raise RoutingError("candidate ids must be unique")
            ids.add(candidate.id)
            if str(getattr(provider, "model", "")) != candidate.model:
                raise RoutingError("candidate model does not match provider")
            if candidate.is_local != bool(getattr(provider, "is_local", False)):
                raise RoutingError("candidate locality does not match provider")
        if not local_only and any(candidate.is_local for candidate, _ in self._candidates):
            raise RoutingError("mixed or local providers are forbidden for remote routing")

    @property
    def name(self) -> str:
        return "routed"

    @property
    def model(self) -> str:
        return self._model

    @property
    def is_local(self) -> bool:
        # A remote wrapper is never allowed to advertise local trust.
        return self._local_only

    def _record(self, outcome: str, candidate: Candidate, provider: Provider, detail: str = "") -> None:
        item = {"outcome": outcome, "task": self._task, "candidate_id": candidate.id,
                "provider": str(getattr(provider, "name", type(provider).__name__)),
                "model": str(getattr(provider, "model", candidate.model))}
        if detail:
            item["detail"] = detail
        self.trace.append(item)
        del self.trace[:-100]
        if self._audit is not None:
            self._audit.record("model_routing", "read", "auto", outcome,
                               {k: v for k, v in item.items() if k != "detail"},
                               model=item["model"], detail=detail or None)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        required = frozenset({"text", "tools"} if tools else {"text"})
        excluded: frozenset[str] = frozenset()
        attempts = 0
        while attempts < 3:
            try:
                candidate = select_candidate(
                    [item[0] for item in self._candidates], required=required,
                    local_only=self._local_only, prefer_quality=self._task == "research",
                    excluded=excluded,
                )
            except RoutingError as exc:
                raise ProviderError("no eligible routed model candidate") from exc
            provider = next(provider for item, provider in self._candidates if item.id == candidate.id)
            self._record("chosen", candidate, provider)
            attempts += 1
            try:
                reply = provider.complete(messages, tools)
            except ProviderError as exc:
                self._record("failed", candidate, provider, type(exc).__name__)
                excluded = frozenset((*excluded, candidate.id))
                continue
            self._record("success", candidate, provider)
            self._model = str(getattr(provider, "model", "") or candidate.model)
            return Reply(text=reply.text, tool_calls=reply.tool_calls,
                         model=str(getattr(provider, "model", "") or candidate.model))
        raise ProviderError("all eligible routed model candidates failed")

    def _json_candidate(self):
        if not self._local_only:
            raise ProviderError("JSON screening requires local-only routing")
        try:
            candidate = select_candidate(
                [item[0] for item in self._candidates], required=frozenset({"text"}),
                local_only=True, prefer_quality=self._task == "research",
            )
        except RoutingError as exc:
            raise ProviderError("no eligible routed local JSON model") from exc
        provider = next(provider for item, provider in self._candidates if item.id == candidate.id)
        return candidate, provider

    @property
    def supports_json(self) -> bool:
        """Capability of the selected delegate, without making a model call."""
        try:
            _, provider = self._json_candidate()
        except ProviderError:
            return False
        return (callable(getattr(provider, "complete_json", None))
                and getattr(provider, "supports_json", True))

    def complete_json(self, messages: list[dict[str, Any]], *, max_tokens: int = 256,
                      schema: dict[str, Any] | None = None) -> Reply:
        """Run bounded JSON completion through eligible local candidates only."""
        candidate, provider = self._json_candidate()
        self._record("chosen", candidate, provider)
        method = getattr(provider, "complete_json", None)
        if not callable(method):
            self._record("failed", candidate, provider, "json_capability_missing")
            raise ProviderError("selected local provider lacks JSON capability")
        try:
            reply = method(messages) if max_tokens == 256 and schema is None else method(messages, max_tokens=max_tokens, schema=schema)
        except ProviderError as exc:
            self._record("failed", candidate, provider, type(exc).__name__)
            raise
        if getattr(reply, "tool_calls", None):
            self._record("failed", candidate, provider, "tool_calls_rejected")
            raise ProviderError("JSON screening provider returned tool calls")
        self._record("success", candidate, provider)
        self._model = str(getattr(provider, "model", "") or candidate.model)
        return Reply(text=reply.text, tool_calls=[], model=self._model)


__all__ = ["RoutedProvider"]
