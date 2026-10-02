# Atlas resolver/binding layer v0.1

**State:** implemented on `feat/atlas-resolver-binding-v0.1`  
**Scope:** deterministic resolver/binding layer only  
**Base:** `main@5d378ee3b6695b3847cac450f254cd8c9b3193e7`

## Goal

Make the AgentOS fork capable of holding Atlas components and resolving an incoming
normalized event to the one behavior/runtime binding that should receive it.

This layer is deliberately **not** the state machine, judgment engine, or executor:

- Atlas catalog: what exists and how it is related.
- Resolver/bindings: which behavior and runtime context apply.
- XState: what transitions/actions are legal.
- JEv: bounded judgment among legal choices.
- Pi: admitted execution.
- AgentOS: run lifecycle, API/MCP, approvals, persistence, tracing, scheduling.

## Added surface

`app/atlas/models.py`
: Portable typed records for Atlas objects, relationships, bindings, events, and
  resolution output.

`app/atlas/catalog.py`
: JSON catalog loading plus fail-closed integrity validation.

`app/atlas/resolver.py`
: Deterministic event-to-binding resolution.

`app/atlas/functions.py`
: Two deterministic AgentOS workflow functions:
  `validate_atlas_catalog` and `resolve_atlas_event`.

`atlas/catalog.json`
: Empty, valid catalog placeholder. It is intentionally not populated with
  synthetic Atlas records. `ATLAS_CATALOG_PATH` can point to a generated/imported
  canonical catalog later.

## Binding contract

A binding selects a behavior and the runtime context that is in scope:

```json
{
  "id": "binding:gap-reported",
  "subject_kind": "gap",
  "subject_ids": [],
  "event_types": ["gap.reported"],
  "states": ["reported"],
  "behavior_id": "behavior:gap-lifecycle",
  "judgment": "jev",
  "capability_ids": ["capability:investigate"],
  "policy_ids": ["policy:evidence-required"],
  "executor_ids": ["agent:pi"],
  "playbook_ids": ["playbook:root-cause"],
  "method_ids": ["method:investigate"],
  "priority": 0,
  "enabled": true
}
```

Every referenced ID must exist as an Atlas object. Relationships also require both
endpoints to exist.

## Resolution rules

For an event `{id, type, subject_id, ...}`:

1. Load and validate the configured Atlas catalog.
2. Resolve `subject_id`; unknown subjects fail.
3. Filter to enabled bindings matching:
   - optional explicit `subject_ids`,
   - `subject_kind` (or `*`),
   - `event_types` (or `*`),
   - current subject `state` (or `*`).
4. Rank matching bindings by specificity:
   explicit subject -> exact kind -> exact event -> exact state -> priority.
5. If exactly one top binding exists, return it.
6. If none or more than one top binding exists, fail closed.
7. Include all incoming/outgoing relationships for the subject in the result so
   downstream XState/JEv logic can inspect Atlas context without the resolver
   inventing ontology semantics.

The resolver does **not** advance state, choose an XState transition, invoke JEv,
or execute Pi.

## AgentOS integration

`app/registry.py` registers:

- `validate_atlas_catalog`
- `resolve_atlas_event`

as reviewed deterministic workflow functions. Studio-built workflows can therefore
use the resolver without granting them source mutation or arbitrary runtime powers.

`ATLAS_CATALOG_PATH` defaults to `atlas/catalog.json`.

## Verification

Deterministic unit coverage proves:

- exact event/state bindings beat wildcards;
- explicit subject bindings beat kind-level bindings;
- relationships survive into resolution context;
- equal-specificity bindings are rejected as ambiguous;
- missing bindings are rejected;
- dangling binding references are rejected.

`scripts/validate.sh` now runs these tests after format/lint/type checks, preserving
the repo rule that local and CI use the same validation gate.

## Explicitly not done yet

This commit does **not**:

- import the canonical Atlas catalog from `master-repo`;
- add Postgres Atlas tables;
- call the existing XState 6 runtime;
- call JEv;
- call Pi Durable;
- add the generic `atlas_runtime` AgentOS workflow;
- mutate Atlas lifecycle state;
- create a new operator UI.

Those are later lifecycle steps. The next useful proof is to import one real Atlas
subject plus its behavior/capability/policy bindings, resolve one event, and compare
the resolver result against the existing XState workflow before any execution is
enabled.
