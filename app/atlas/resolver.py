"""Deterministic event-to-behavior resolution for Atlas."""

from collections import defaultdict
from typing import Any

from app.atlas.catalog import validate_catalog
from app.atlas.models import (
    AtlasBinding,
    AtlasCatalog,
    AtlasEvent,
    AtlasObject,
    AtlasResolution,
)


class AtlasResolverError(ValueError):
    """A resolution failed without making a speculative choice."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


def _matches(binding: AtlasBinding, subject: AtlasObject, event: AtlasEvent) -> bool:
    if not binding.enabled:
        return False
    if binding.subject_ids and subject.id not in binding.subject_ids:
        return False
    if binding.subject_kind not in ("*", subject.kind):
        return False
    if "*" not in binding.event_types and event.type not in binding.event_types:
        return False
    if "*" not in binding.states and subject.state not in binding.states:
        return False
    return True


def _specificity(binding: AtlasBinding, subject: AtlasObject, event: AtlasEvent) -> tuple[int, ...]:
    """Prefer explicit subject/kind/event/state selectors; priority breaks like-for-like ties."""

    return (
        int(bool(binding.subject_ids) and subject.id in binding.subject_ids),
        int(binding.subject_kind == subject.kind),
        int(event.type in binding.event_types),
        int(subject.state is not None and subject.state in binding.states),
        binding.priority,
    )


def _relationship_context(
    catalog: AtlasCatalog, subject_id: str
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    outgoing: defaultdict[str, list[str]] = defaultdict(list)
    incoming: defaultdict[str, list[str]] = defaultdict(list)

    for relationship in catalog.relationships:
        if relationship.source_id == subject_id:
            outgoing[relationship.relation].append(relationship.target_id)
        if relationship.target_id == subject_id:
            incoming[relationship.relation].append(relationship.source_id)

    return (
        {key: sorted(set(values)) for key, values in sorted(outgoing.items())},
        {key: sorted(set(values)) for key, values in sorted(incoming.items())},
    )


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def resolve_event(catalog: AtlasCatalog, event: AtlasEvent) -> AtlasResolution:
    """Resolve an event to exactly one behavior binding.

    This is intentionally not a policy engine and not a state transition engine.
    It selects the behavior and context that should receive the event. XState
    remains responsible for legal transitions; JEv remains bounded judgment.
    """

    validate_catalog(catalog)
    by_id = {item.id: item for item in catalog.objects}
    subject = by_id.get(event.subject_id)
    if subject is None:
        raise AtlasResolverError(
            "unknown_subject",
            f"Atlas subject {event.subject_id!r} does not exist",
            details={"subject_id": event.subject_id},
        )

    candidates = [
        binding for binding in catalog.bindings if _matches(binding, subject, event)
    ]
    if not candidates:
        raise AtlasResolverError(
            "no_binding",
            (
                f"No enabled Atlas binding matches subject {subject.id!r} "
                f"(kind={subject.kind!r}, state={subject.state!r}) "
                f"and event {event.type!r}"
            ),
            details={
                "subject_id": subject.id,
                "subject_kind": subject.kind,
                "subject_state": subject.state,
                "event_type": event.type,
            },
        )

    scored = [(binding, _specificity(binding, subject, event)) for binding in candidates]
    top_score = max(score for _, score in scored)
    winners = [binding for binding, score in scored if score == top_score]
    if len(winners) != 1:
        raise AtlasResolverError(
            "ambiguous_binding",
            (
                "Multiple equally specific Atlas bindings match; refusing to "
                "choose implicitly"
            ),
            details={
                "binding_ids": sorted(binding.id for binding in winners),
                "score": list(top_score),
            },
        )

    binding = winners[0]
    outgoing, incoming = _relationship_context(catalog, subject.id)
    return AtlasResolution(
        subject_id=subject.id,
        subject_kind=subject.kind,
        subject_state=subject.state,
        event_id=event.id,
        event_type=event.type,
        binding_id=binding.id,
        behavior_id=binding.behavior_id,
        judgment=binding.judgment,
        capability_ids=_sorted_unique(binding.capability_ids),
        policy_ids=_sorted_unique(binding.policy_ids),
        executor_ids=_sorted_unique(binding.executor_ids),
        playbook_ids=_sorted_unique(binding.playbook_ids),
        method_ids=_sorted_unique(binding.method_ids),
        outgoing_relationships=outgoing,
        incoming_relationships=incoming,
    )
