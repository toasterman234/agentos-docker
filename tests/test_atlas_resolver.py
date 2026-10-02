"""Deterministic checks for the Atlas resolver/binding layer."""

import unittest

from app.atlas.catalog import AtlasCatalogError, validate_catalog
from app.atlas.models import (
    AtlasBinding,
    AtlasCatalog,
    AtlasEvent,
    AtlasObject,
    AtlasRelationship,
)
from app.atlas.resolver import AtlasResolverError, resolve_event


def base_objects() -> list[AtlasObject]:
    return [
        AtlasObject(id="gap:GAP-001", kind="gap", state="reported"),
        AtlasObject(id="behavior:gap-lifecycle", kind="behavior"),
        AtlasObject(id="behavior:special-gap", kind="behavior"),
        AtlasObject(id="policy:evidence-required", kind="policy"),
        AtlasObject(id="capability:investigate", kind="capability"),
        AtlasObject(id="agent:pi", kind="agent"),
        AtlasObject(id="playbook:root-cause", kind="playbook"),
        AtlasObject(id="method:investigate", kind="method"),
    ]


def event(event_type: str = "gap.reported") -> AtlasEvent:
    return AtlasEvent(
        id="event:001",
        type=event_type,
        subject_id="gap:GAP-001",
        source="test",
    )


class ResolverTests(unittest.TestCase):
    def test_exact_event_and_state_binding_beats_wildcard(self) -> None:
        catalog = AtlasCatalog(
            objects=base_objects(),
            bindings=[
                AtlasBinding(
                    id="binding:generic-gap",
                    subject_kind="gap",
                    behavior_id="behavior:gap-lifecycle",
                ),
                AtlasBinding(
                    id="binding:reported-gap",
                    subject_kind="gap",
                    event_types=["gap.reported"],
                    states=["reported"],
                    behavior_id="behavior:special-gap",
                ),
            ],
        )

        result = resolve_event(catalog, event())

        self.assertEqual(result.binding_id, "binding:reported-gap")
        self.assertEqual(result.behavior_id, "behavior:special-gap")

    def test_subject_specific_binding_beats_kind_binding(self) -> None:
        catalog = AtlasCatalog(
            objects=base_objects(),
            bindings=[
                AtlasBinding(
                    id="binding:all-gaps",
                    subject_kind="gap",
                    event_types=["gap.reported"],
                    states=["reported"],
                    behavior_id="behavior:gap-lifecycle",
                ),
                AtlasBinding(
                    id="binding:this-gap",
                    subject_kind="gap",
                    subject_ids=["gap:GAP-001"],
                    event_types=["*"],
                    states=["*"],
                    behavior_id="behavior:special-gap",
                ),
            ],
        )

        result = resolve_event(catalog, event())

        self.assertEqual(result.binding_id, "binding:this-gap")

    def test_resolution_carries_binding_and_relationship_context(self) -> None:
        catalog = AtlasCatalog(
            objects=base_objects(),
            relationships=[
                AtlasRelationship(
                    source_id="gap:GAP-001",
                    relation="governed_by",
                    target_id="policy:evidence-required",
                ),
                AtlasRelationship(
                    source_id="playbook:root-cause",
                    relation="addresses",
                    target_id="gap:GAP-001",
                ),
            ],
            bindings=[
                AtlasBinding(
                    id="binding:gap",
                    subject_kind="gap",
                    behavior_id="behavior:gap-lifecycle",
                    capability_ids=["capability:investigate"],
                    policy_ids=["policy:evidence-required"],
                    executor_ids=["agent:pi"],
                    playbook_ids=["playbook:root-cause"],
                    method_ids=["method:investigate"],
                )
            ],
        )

        result = resolve_event(catalog, event())

        self.assertEqual(result.capability_ids, ["capability:investigate"])
        self.assertEqual(result.executor_ids, ["agent:pi"])
        self.assertEqual(
            result.outgoing_relationships,
            {"governed_by": ["policy:evidence-required"]},
        )
        self.assertEqual(
            result.incoming_relationships,
            {"addresses": ["playbook:root-cause"]},
        )

    def test_equal_specificity_is_ambiguous_and_fails_closed(self) -> None:
        catalog = AtlasCatalog(
            objects=base_objects(),
            bindings=[
                AtlasBinding(
                    id="binding:a",
                    subject_kind="gap",
                    event_types=["gap.reported"],
                    states=["reported"],
                    behavior_id="behavior:gap-lifecycle",
                ),
                AtlasBinding(
                    id="binding:b",
                    subject_kind="gap",
                    event_types=["gap.reported"],
                    states=["reported"],
                    behavior_id="behavior:special-gap",
                ),
            ],
        )

        with self.assertRaises(AtlasResolverError) as caught:
            resolve_event(catalog, event())

        self.assertEqual(caught.exception.code, "ambiguous_binding")

    def test_no_binding_fails_closed(self) -> None:
        catalog = AtlasCatalog(objects=base_objects(), bindings=[])

        with self.assertRaises(AtlasResolverError) as caught:
            resolve_event(catalog, event())

        self.assertEqual(caught.exception.code, "no_binding")

    def test_dangling_binding_reference_is_rejected(self) -> None:
        catalog = AtlasCatalog(
            objects=base_objects(),
            bindings=[
                AtlasBinding(
                    id="binding:bad",
                    subject_kind="gap",
                    behavior_id="behavior:missing",
                )
            ],
        )

        with self.assertRaises(AtlasCatalogError):
            validate_catalog(catalog)


if __name__ == "__main__":
    unittest.main()
