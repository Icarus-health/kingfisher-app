"""Source identity and withdrawal checks for individual conversation turns."""

from __future__ import annotations

from .episodes import CHAT_LOOKUP_TAG, Episode, EpisodeError, EpisodeKind, EpisodeState, EpisodeStore
from .model import Provenance, SourceType
from .working_memory_store import source_fingerprint


def source_ref(conversation_id: str, message_id: str) -> str:
    return f"conversation:{conversation_id}:message:{message_id}"


def find(episodes: EpisodeStore, conversation_id: str, message_id: str) -> Episode | None:
    ref = source_ref(conversation_id, message_id)
    head = episodes.source_head(ref)
    if head:
        return episodes.get(head)
    # Before ordinary capture, explicit memory candidates used this same
    # source reference without a source head. Keep their withdrawal intact.
    return next((episode for episode in episodes.search(ref, limit=20)
                 if episode.kind is EpisodeKind.MESSAGE
                 and episode.provenance.source_type is SourceType.CHAT
                 and episode.provenance.source_ref == ref), None)


def capture(episodes: EpisodeStore, conversation_id: str, message,
            *, lookup_only: bool = False) -> tuple[Episode, bool]:
    existing = find(episodes, conversation_id, message.id)
    if existing is not None:
        if not matches_message(existing, conversation_id, message):
            raise EpisodeError("Gesprächsquelle stimmt nicht mehr mit der Nutzerzeile überein")
        return existing, False
    ref = source_ref(conversation_id, message.id)
    episode, created = episodes.record(
        EpisodeKind.MESSAGE, "Gesprächsausschnitt", message.content,
        Provenance(source_type=SourceType.CHAT, source_ref=ref,
                   captured_at=message.created_at, verbatim=message.content),
        occurred_at=message.created_at, source_key=ref,
        tags=[CHAT_LOOKUP_TAG] if lookup_only else [],
    )
    # A crash between record and head update remains idempotent because record
    # uses both the source key and digest. The head makes future lookup cheap.
    if episodes.source_head(ref) is None:
        episodes.advance_source_head(ref, None, episode.id)
    return episode, created


def matches_message(episode: Episode, conversation_id: str, message) -> bool:
    ref = source_ref(conversation_id, message.id)
    return (episode.kind is EpisodeKind.MESSAGE
            and episode.provenance.source_type is SourceType.CHAT
            and episode.provenance.source_ref == ref
            and episode.provenance.verbatim == message.content
            and episode.body in {message.content, f"{ref}\n\n{message.content}"})


def stamp(episodes: EpisodeStore, episode_id: str) -> dict[str, str]:
    snapshot = episodes.support_snapshot(episode_id)
    return {"episode_id": episode_id, "fingerprint": source_fingerprint(snapshot)}


def usable(episodes: EpisodeStore, source: dict[str, str]) -> bool:
    try:
        episode_id = source["episode_id"]
        return (episodes.get(episode_id).state is not EpisodeState.IGNORED
                and stamp(episodes, episode_id) == source)
    except Exception:
        return False


def lineage_valid(episodes: EpisodeStore, sources: list[dict[str, str]],
                  cache: dict[tuple[str, str], bool] | None = None) -> bool:
    for source in sources:
        key = (source.get("episode_id", ""), source.get("fingerprint", ""))
        if cache is not None and key in cache:
            valid = cache[key]
        else:
            valid = usable(episodes, source)
            if cache is not None:
                cache[key] = valid
        if not valid:
            return False
    return True
