from __future__ import annotations

import pytest

from icarus_memory.model_routing import Candidate, RoutingError
from icarus_memory.providers import ProviderError, Reply
from icarus_memory.routing_provider import RoutedProvider


class P:
    name = "test"
    is_local = True

    def __init__(self, model="m", error=False):
        self.model, self.error, self.seen = model, error, []

    def complete(self, messages, tools):
        self.seen.append((messages, tools))
        if self.error:
            raise ProviderError("down")
        return Reply(text="ok")


def c(id, **kw):
    values = dict(model=id, is_local=True, capabilities=frozenset({"text", "tools"}), quality=80, cost=1, latency=1)
    values.update(kw)
    return Candidate(id, **values)


def test_local_boundary_and_trace_have_no_payload():
    local, cloud = P("local"), P("cloud")
    cloud.is_local = False
    routed = RoutedProvider(local, [(c("local"), local), (c("cloud", is_local=False), cloud)])
    routed.complete([{"role": "user", "content": "secret"}], [])
    assert not cloud.seen
    assert all("secret" not in str(item) for item in routed.trace)


def test_tools_require_tools_capability():
    provider = P()
    routed = RoutedProvider(provider, [(c("text", model="m", capabilities=frozenset({"text"})), provider)])
    with pytest.raises(ProviderError):
        routed.complete([], [{"name": "x"}])


def test_failure_falls_back_within_same_boundary():
    first, second = P("first", True), P("second")
    routed = RoutedProvider(first, [(c("first"), first), (c("second", cost=2), second)])
    assert routed.complete([], []).model == "second"
    assert not any(item[0] for item in second.seen[0][0])
    assert [item["outcome"] for item in routed.trace] == ["chosen", "failed", "chosen", "success"]


def test_remote_wrapper_rejects_local_candidates():
    with pytest.raises(RoutingError):
        RoutedProvider(P(), [(c("local"), P())], local_only=False)


def test_default_is_explicit_single_candidate():
    provider = P("default")
    assert RoutedProvider(provider, []).complete([], []).model == "default"


def test_exhaustion_with_one_candidate_is_provider_error():
    provider = P("only", True)
    routed = RoutedProvider(provider, [(c("only"), provider)])
    with pytest.raises(ProviderError, match="failed|eligible"):
        routed.complete([], [])


def test_duplicate_ids_and_model_mismatch_fail_closed():
    first, second = P("same"), P("same")
    with pytest.raises(RoutingError, match="unique"):
        RoutedProvider(first, [(c("same"), first), (c("same"), second)])
    with pytest.raises(RoutingError, match="match"):
        RoutedProvider(first, [(c("declared"), first)])
