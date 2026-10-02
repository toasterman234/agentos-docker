"""Catalog loading and integrity checks for Atlas."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.atlas.models import AtlasBinding, AtlasCatalog


class AtlasCatalogError(ValueError):
    """Catalog is structurally valid JSON but not safe to resolve."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _binding_references(binding: AtlasBinding) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = [("behavior_id", binding.behavior_id)]
    for field_name in (
        "capability_ids",
        "policy_ids",
        "executor_ids",
        "playbook_ids",
        "method_ids",
    ):
        refs.extend((field_name, value) for value in getattr(binding, field_name))
    return refs


def validate_catalog(catalog: AtlasCatalog) -> AtlasCatalog:
    """Fail closed on duplicate IDs, dangling edges, or dangling binding refs."""

    issues: list[str] = []
    object_ids = [item.id for item in catalog.objects]
    binding_ids = [item.id for item in catalog.bindings]
    object_id_set = set(object_ids)

    for duplicate in _duplicates(object_ids):
        issues.append(f"duplicate object id: {duplicate}")
    for duplicate in _duplicates(binding_ids):
        issues.append(f"duplicate binding id: {duplicate}")

    for relationship in catalog.relationships:
        if relationship.source_id not in object_id_set:
            issues.append(
                f"relationship {relationship.relation!r} has unknown source "
                f"{relationship.source_id!r}"
            )
        if relationship.target_id not in object_id_set:
            issues.append(
                f"relationship {relationship.relation!r} has unknown target "
                f"{relationship.target_id!r}"
            )

    by_id = {item.id: item for item in catalog.objects}
    for binding in catalog.bindings:
        if not binding.event_types:
            issues.append(f"binding {binding.id!r} has no event_types")
        if not binding.states:
            issues.append(f"binding {binding.id!r} has no states")

        for subject_id in binding.subject_ids:
            subject = by_id.get(subject_id)
            if subject is None:
                issues.append(
                    f"binding {binding.id!r} references unknown subject {subject_id!r}"
                )
            elif binding.subject_kind != "*" and subject.kind != binding.subject_kind:
                issues.append(
                    f"binding {binding.id!r} subject {subject_id!r} has kind "
                    f"{subject.kind!r}, expected {binding.subject_kind!r}"
                )

        for field_name, ref in _binding_references(binding):
            if ref not in object_id_set:
                issues.append(
                    f"binding {binding.id!r} {field_name} references unknown object {ref!r}"
                )

    if issues:
        raise AtlasCatalogError(issues)
    return catalog


def load_catalog(path: str | Path) -> AtlasCatalog:
    """Load and validate one portable Atlas catalog JSON file."""

    catalog_path = Path(path)
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog = AtlasCatalog.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise AtlasCatalogError([f"could not load {catalog_path}: {exc}"]) from exc
    return validate_catalog(catalog)
