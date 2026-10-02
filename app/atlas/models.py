"""Typed records for the Atlas resolver/binding layer."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JudgmentEngine = Literal["none", "jev"]


class AtlasObject(BaseModel):
    """One component in the Atlas domain catalog."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    state: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AtlasRelationship(BaseModel):
    """A typed edge between Atlas components."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    relation: str
    target_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class AtlasBinding(BaseModel):
    """Declarative rule mapping an event/subject shape to runtime semantics.

    The binding does not decide whether a transition is legal. It only resolves
    which behavior (normally an XState machine) should receive the event and
    which Atlas components are in scope.

    ``judgment_ids`` are Atlas Judgment objects. ``judgment_engine`` says whether
    a judgment engine such as JEv is needed to evaluate them. Keeping those
    separate prevents the runtime engine from being confused with the domain
    judgment being applied.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    subject_kind: str
    behavior_id: str
    subject_ids: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=lambda: ["*"])
    states: list[str] = Field(default_factory=lambda: ["*"])
    judgment_engine: JudgmentEngine = "none"
    judgment_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    executor_ids: list[str] = Field(default_factory=list)
    playbook_ids: list[str] = Field(default_factory=list)
    method_ids: list[str] = Field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    data: dict[str, Any] = Field(default_factory=dict)


class AtlasCatalog(BaseModel):
    """Portable, machine-readable Atlas catalog used by the resolver."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    objects: list[AtlasObject] = Field(default_factory=list)
    relationships: list[AtlasRelationship] = Field(default_factory=list)
    bindings: list[AtlasBinding] = Field(default_factory=list)


class AtlasEvent(BaseModel):
    """Normalized event entering Atlas."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    subject_id: str
    source: str = "unknown"
    correlation_id: str | None = None
    payload: Any = None


class AtlasResolution(BaseModel):
    """Deterministic result of resolving one event against one Atlas subject."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    subject_id: str
    subject_kind: str
    subject_state: str | None
    event_id: str
    event_type: str
    binding_id: str
    behavior_id: str
    judgment_engine: JudgmentEngine
    judgment_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    executor_ids: list[str] = Field(default_factory=list)
    playbook_ids: list[str] = Field(default_factory=list)
    method_ids: list[str] = Field(default_factory=list)
    outgoing_relationships: dict[str, list[str]] = Field(default_factory=dict)
    incoming_relationships: dict[str, list[str]] = Field(default_factory=dict)
