"""AgentOS workflow functions exposing the Atlas resolver."""

import json
from os import getenv
from pathlib import Path
from typing import Any

from agno.workflow import StepInput
from pydantic import BaseModel, ValidationError

from app.atlas.catalog import AtlasCatalogError, load_catalog
from app.atlas.models import AtlasEvent
from app.atlas.resolver import AtlasResolverError, resolve_event

_ERROR_PREFIX = "Error: "
_DEFAULT_CATALOG_PATH = Path("atlas/catalog.json")


def _error(message: str) -> str:
    return f"{_ERROR_PREFIX}{message}"


def _step_text(step_input: StepInput) -> str:
    content = step_input.previous_step_content
    if content is None:
        return step_input.get_input_as_string() or ""
    if isinstance(content, BaseModel):
        return content.model_dump_json(exclude_none=True)
    if isinstance(content, (dict, list)):
        return json.dumps(content, default=str, ensure_ascii=False)
    return str(content)


def _catalog_path() -> Path:
    return Path(getenv("ATLAS_CATALOG_PATH", str(_DEFAULT_CATALOG_PATH)))


def resolve_atlas_event(step_input: StepInput) -> str:
    """Resolve a normalized Atlas event into behavior + runtime bindings.

    Input must be one JSON object matching AtlasEvent. The function performs no
    model call and no side effect; failures return `Error: ...` so a Studio
    workflow can branch or hold rather than accidentally advancing.
    """

    text = _step_text(step_input)
    if text.startswith(_ERROR_PREFIX):
        return text

    try:
        raw: Any = json.loads(text)
        event = AtlasEvent.model_validate(raw)
        catalog = load_catalog(_catalog_path())
        resolution = resolve_event(catalog, event)
    except json.JSONDecodeError:
        return _error("Atlas resolver expected one JSON event object")
    except ValidationError as exc:
        return _error(f"invalid Atlas event: {exc}")
    except AtlasCatalogError as exc:
        return _error(f"invalid Atlas catalog: {exc}")
    except AtlasResolverError as exc:
        details = json.dumps(exc.details, sort_keys=True, ensure_ascii=False)
        return _error(f"{exc.code}: {exc}; details={details}")

    return resolution.model_dump_json(exclude_none=True)


def validate_atlas_catalog(step_input: StepInput) -> str:
    """Validate the configured Atlas catalog and return a compact inventory."""

    _ = step_input
    try:
        catalog = load_catalog(_catalog_path())
    except AtlasCatalogError as exc:
        return _error(f"invalid Atlas catalog: {exc}")

    return json.dumps(
        {
            "schema_version": catalog.schema_version,
            "objects": len(catalog.objects),
            "relationships": len(catalog.relationships),
            "bindings": len(catalog.bindings),
            "catalog_path": str(_catalog_path()),
        },
        sort_keys=True,
    )
