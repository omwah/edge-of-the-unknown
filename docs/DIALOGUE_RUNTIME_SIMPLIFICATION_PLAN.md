# Dialogue runtime simplification — alternative proposed plan

> Companion to `DESIGN.md` §6.2/§6.7/§10/§13 and
> `DIALOGUE_GAME_STATE.md`. `DESIGN.md` remains authoritative until an accepted
> spec delta is landed.
>
> **Status: alternative proposal — simplify the current system incrementally
> while preserving its config model and behavior.** The full replacement
> alternative is documented in `DIALOGUE_SYSTEM_REPLACEMENT_PLAN.md`; neither
> alternative is selected yet.

## Decision summary

This alternative keeps the recognizable shape of the current dialogue system:

- config-driven species/persona/generic content;
- conditional line selection;
- variants and grammar realization;
- visit-local facts and cross-visit story state;
- authored choices and registered mechanical actions;
- deterministic replay.

It simplifies the implementation around that model by establishing one contact
runtime, separating node choices from line variants, replacing the mixed
condition/gating mechanisms with one predicate model, introducing stable IDs,
and consolidating dialogue-related state.

Unlike the replacement alternative, this plan deliberately preserves
salience-style conditional selection and compatibility with the existing
corpus. It is the lower-risk path when retaining shipped behavior, data, and
saves matters more than minimizing the final runtime surface.

---

## Context

The current system's guarantees are valuable:

- pure, deterministic selection;
- config-driven voice and content;
- species → persona → generic reuse;
- replay-safe recency, session facts, callbacks, and arcs;
- reducer-side authorization of mechanical effects;
- validation and offline authoring/play-testing.

Its maintenance burden comes from one conversation turn being spread across
several mechanisms:

1. `edge.dialogue.facts.contact_facts` assembles a flat fact map.
2. `edge.dialogue.select` resolves lines and choices.
3. `edge.server.session.contact_view` independently reconstructs bindings,
   offers, choice availability, and disabled reasons.
4. `edge.core.rules._converse_choice` reconstructs the same menu from a
   client-supplied context and positional index before applying effects.
5. Intel, contracts, trade, attack, dossier subjects, combat, and signature
   mechanics each introduce special paths.
6. Relationship and dialogue memory is spread across several `Player` maps and
   records.

The target is one pure contact-runtime boundary that resolves a complete turn,
plus explicit typed state and action seams. Domain systems remain independent;
dialogue consumes their projections and delegates their actions.

---

## Goals

1. Give a conversation turn one authoritative resolution path.
2. Stop projection and reducer code from independently reconstructing the same
   turn.
3. Replace positional choices with stable authored IDs.
4. Separate node choices from whichever prose rule wins selection.
5. Replace `DialogueWhen` fields, arbitrary criteria, choice gating, and
   reducer guards with one coherent predicate/capability model.
6. Give every mechanical choice the same preview/apply contract.
7. Consolidate dialogue-related relationship and narrative progress without
   moving unrelated domain state into dialogue.
8. Preserve existing corpus behavior and migrate in reversible increments.

## Non-goals

- No runtime generative AI or free-text player input.
- No transfer of combat, economy, contracts, leads, or discoveries into the
  dialogue layer.
- No YAML access to arbitrary Python functions or `Player` fields.
- No visual redesign of the contact screen.
- No treaty implementation as an accidental part of the refactor.
- No requirement to adopt the full replacement architecture described in the
  companion alternative.

---

## Target flow

```text
authoritative domain state
          |
          v
typed DialogueContext + action previews
          |
          v
ContactRuntime.resolve()
    - fallback chain
    - conditional line selection
    - deterministic realization
    - node-level choices
          |
          v
persisted ConversationState / DialogueTurnRef
          |
          v
server DTO -> TUI

ChooseDialogue(choice_id, expected_revision)
          |
          v
ContactRuntime.plan_choice()
          |
          v
core reducer applies domain action + resolves next turn
```

The reducer resolves and persists the turn once. The server renders the stored
turn; it never reselects it.

---

## Architectural decisions

### S1 — One authoritative contact runtime

Add a pure runtime with two conceptual operations:

```python
def resolve_turn(
    state: UniverseState,
    player: Player,
    speaker: AlienSpecies,
    config: GameConfig,
    request: TurnRequest,
) -> ResolvedTurn: ...

def plan_choice(
    state: UniverseState,
    player: Player,
    speaker: AlienSpecies,
    config: GameConfig,
    command: ChooseDialogue,
) -> ChoicePlan: ...
```

The runtime owns context construction, conditional entry selection,
realization, choice selection, action previews, bindings, and transitions.
`core.rules` remains the only mutator. The server only converts persisted
results to DTOs.

### S2 — Persist a compact conversation cursor

Replace the untyped `ContactSession.facts` bag with explicit state:

```python
@dataclass(frozen=True, slots=True)
class ConversationState:
    speaker_id: int
    sector_id: int
    node_id: str
    revision: int
    history: tuple[str, ...]
    visit: VisitMemory
    turn: DialogueTurnRef

@dataclass(frozen=True, slots=True)
class DialogueTurnRef:
    line_id: str
    realization: int
    bindings: Mapping[str, str]
    choice_ids: tuple[str, ...]
```

The persisted state records what was actually selected rather than forcing the
projection to reconstruct it from current world state. Movement, hostile
encounter start, attack, farewell, and destroyed contacts invalidate it in
reducers.

### S3 — Stable choices and optimistic revisions

Use:

```python
ChooseDialogue(
    species_id=17,
    choice_id="accept_coordinates",
    expected_revision=4,
)
```

Stable IDs decouple behavior from authored ordering. Revisions reject stale or
duplicate input. Reducers still revalidate domain authorization.

The old `Converse(context, choice_index)` remains decodable during the
compatibility window. A bounded adapter maps its historical context and index
to stable IDs. New games and clients emit only the stable command after
cutover.

### S4 — Nodes own lines and choices independently

Replace choices embedded in `DialogueLine` with:

```yaml
greeting:
  lines:
    - id: returning_friend
      when:
        relationship.standing: {in: [friendly, allied]}
        history.met_before: {eq: true}
      variants:
        - "Again your drive-song reaches us, {player}."

  choices:
    - id: ask_coordinates
      text: "What lies beyond this sector?"
      action: request_intel
```

Species → persona → generic fallback continues, but lines and choices inherit
independently. Changing prose selection can no longer change the menu by
accident.

Stable internal node IDs replace positional branch identity. Existing
`branch.*` names may remain as data conventions, but they do not need bespoke
runtime behavior.

### S5 — One validated predicate model

Replace dedicated `standing`, `treaty`, `posture`, and `stage` fields plus
equality-only arbitrary criteria with one structured predicate:

```yaml
when:
  all:
    - relationship.standing: {in: [friendly, allied]}
    - player.hull_ratio: {lt: 0.35}
    - any:
        - history.met_before: {eq: true}
        - mechanic.stage: {eq: trusted}
```

The initial operators are deliberately small:

- `all`, `any`, `not`;
- `eq`, `in`, `exists`;
- numeric `lt`, `lte`, `gt`, `gte`.

Every path comes from a typed registry. Invalid paths, operators, and enum
values fail at config load. The undocumented `wary` value is removed unless a
separate design decision defines how it is produced. Treaty/posture/stage are
available only when a live provider supplies them; inert forward-compatible
fields are removed.

Salience is retained but made explicit: authored priority first, predicate
specificity second, and weight only among true ties. Migrated data receives
priorities that preserve current standing precedence.

### S6 — One mechanical action seam

Every mechanical choice references a registered action with a pure preview and
authorized apply path:

```python
@dataclass(frozen=True, slots=True)
class ActionPreview:
    action_id: str
    enabled: bool
    reason: str = ""
    bindings: Mapping[str, str] = field(default_factory=dict)
    offer_ref: str | None = None
```

Initial actions cover leave, trade, barter, intel, contracts, attack,
signature mechanics, and pure transitions. Preview selects deterministic
offers, supplies bindings, and explains disabled choices. Apply revalidates
through the same domain planner before returning mutations/events.

This removes server-only `_gate_choice` logic and mirrored feature-specific
bindings without moving domain mutation into dialogue.

### S7 — Signature mechanics become ordinary actions

An authored choice calls a registered mechanic action and maps result keys to
explicit next nodes. The mechanic returns bounded effects, durable progress,
transient result data, and a result key. Immediate response selection can read
the transient result; later visits read durable progress.

This removes context-name parsing and the `sig_stage`/`arc.sig_stage` alias,
while retaining the existing hook implementations and corpus content.

### S8 — Consolidate relationship and narrative progress

After the runtime cutover, replace parallel species-keyed maps with:

```python
@dataclass(frozen=True, slots=True)
class AlienRelationship:
    attitude: float = 0.0
    last_seen_sector: int | None = None
    grudge: Grudge | None = None
    story_flags: Mapping[str, Scalar] = field(default_factory=dict)
    mechanic_progress: Mapping[str, Scalar] = field(default_factory=dict)
```

`Scalar` is a closed value union rather than `object`. Leads, contracts,
`last_combat`, the active encounter, and the live conversation stay separate
because they have different ownership or lifetime.

This work is intentionally after the runtime cutover so it can be omitted or
deferred if its whole-game impact outweighs its benefit.

### S9 — Stable realization memory

Give every line pool a stable ID. Key realization memory by
`(speaker_instance, line_pool_id)` rather than positional context indices.

The preferred implementation is a deterministic shuffle counter, which avoids
repeats until the pool is exhausted. A typed stable-ID version of the current
K-deep ring is an acceptable lower-risk fallback.

---

## Cross-cutting constraints

- **C1 — Reducer authority.** Preview never authorizes; apply revalidates in
  core.
- **C2 — One selection.** Projection never reselects a persisted turn.
- **C3 — Replay.** State, commands, events, codecs, hashes, and goldens change
  together.
- **C4 — Stable identity.** Node, line-pool, line, choice, action, and mechanic
  IDs are explicit and unique.
- **C5 — Fog of war.** Typed context and previews expose only intended facts.
- **C6 — Fingerprint.** The dialogue fingerprint covers IDs, graph shape,
  predicates, actions, realization pools, and fallback structure.
- **C7 — Compatibility.** Old commands stay replayable for the agreed
  deprecation window.
- **C8 — No runtime I/O.** Selection, rendering, predicates, and previews are
  pure and synchronous.
- **C9 — Spec synchronization.** Schema/runtime changes update `DESIGN.md`
  §6.7/§13, the header of `config/alien_dialogue_default.yaml`, and
  `edge/dialogue/authoring/pipeline.py` in the same change.
- **C10 — Behavior-first migration.** New and old resolution run in parity
  tests before each authority cutover; cleanup follows in a separate commit.

---

## Milestones and work packages

### M1 — Make the existing model explicit

#### DS-WP01 — Spec delta and parity fixtures (S/M)

- Adopt the accepted simplification decisions in DESIGN.
- Pin friendly, hostile, combat, branch, intel, contract, trade, barter,
  attack, Entity, and signature scenarios.
- Record line, choices, disabled reasons, events, state hash, and reload output.
- Add a dry-run corpus migration report.

Exit: current behavior is reviewably pinned.

#### DS-WP02 — Stable IDs and node-level choices (M)

- Add stable node/line/choice IDs and node-owned menus.
- Add a compatibility loader for the current pack schema.
- Convert the shipped corpus to explicit readable IDs.
- Validate uniqueness, reachability, references, placeholders, and actions.
- Update all synchronized dialogue authoring/spec surfaces.

Exit: prose and menu inheritance are independent with no gameplay cutover.

#### DS-WP03 — Typed context and unified predicates (M/L)

- Add typed context DTOs and path registry.
- Implement the structured predicate evaluator.
- Translate legacy `DialogueWhen` at load.
- Replace the flat fact vocabulary in selection tests.
- Preserve old precedence through explicit migrated priority.

Exit: one condition evaluator covers lines and choices.

### M2 — One authoritative turn

#### DS-WP04 — Shared action previews (M/L)

- Add action preview/apply protocols.
- Adapt trade, barter, intel, contracts, attack, leave, and transitions.
- Prove projection reasons and reducer guards share one planner.
- Keep legacy gating temporarily for shadow comparisons only.

Exit: each mechanical choice has one availability source and one mutation
owner.

#### DS-WP05 — Conversation state and stable commands (L)

- Add `ConversationState`, `DialogueTurnRef`, visit memory, and realization
  memory.
- Add stable choice command plus store/wire codecs and state hashing.
- Preserve legacy command decoding for the selected compatibility horizon.
- Test stale revisions and every structural invalidation.

Exit: the new state/protocol exists behind an epoch gate.

#### DS-WP06 — Runtime and reducer cutover (L)

- Implement the single contact runtime over migrated data.
- Route hail, branches, farewell, and combat speech through it.
- Persist selected turns before projection.
- Shadow-compare old/new resolution across corpus matrices and goldens.

Exit: reducers are sole selectors for new games.

#### DS-WP07 — Projection and TUI cutover (M)

- Project persisted turns rather than recomputing them.
- Dispatch stable choice ID + revision.
- Remove `_line`, `_contact_choices`, `_gate_choice`, and mirrored offer
  selection once unused.
- Adapt the real play-test harness.

Exit: projection contains no dialogue business rules.

### M3 — State cleanup and expressiveness

#### DS-WP08 — Relationship aggregate (optional M/L)

- Introduce `AlienRelationship` and typed narrative/mechanic progress.
- Update consumers atomically in one hash/codec epoch.
- Preserve domain helper APIs for combat, alliances, law, and dossiers.

Exit: dialogue-related species state has one typed owner, or this package is
explicitly deferred if not worth its reach.

#### DS-WP09 — Signature action migration (M/L)

- Convert signature contexts to ordinary action/result transitions.
- Expose transient results to immediate response selection.
- Remove stage aliases, posture flags hidden in arcs, and prefix parsing.

Exit: adding a mechanic requires no bespoke dialogue branch.

#### DS-WP10 — Realization migration and legacy removal (M)

- Move recency to stable line-pool state.
- Strengthen the dialogue fingerprint.
- Remove legacy schema adapters and duplicate helpers after the compatibility
  window.
- Rewrite `DIALOGUE_GAME_STATE.md` around the final runtime.

Exit: one schema, resolver, condition model, and conversation state remain.

#### DS-WP11 — Flexibility exit criterion (M)

Author without runtime changes:

- nested boolean and numeric conditions;
- visit-local and cross-visit branches;
- species prose with inherited choices and vice versa;
- a disabled domain action with a domain-produced reason;
- a transient mechanic-result response;
- an automatic combat beat.

Exit criterion:

> An interaction using existing state and actions can be added through one
> dialogue node graph and tests. A new game integration requires one typed
> action/context provider, not mirrored reducer and projection switches.

---

## Verification

### Selection and validation

- Predicate truth tables, invalid paths/types/operators, explicit priority,
  specificity ties, and deterministic weight selection.
- Independent line/choice inheritance across species/persona/generic.
- Stable IDs, reachability, placeholders, action registration, and result
  transition coverage.
- Deterministic realization and no-repeat behavior.

### Reducers and domains

- Preview/apply agreement and revalidation after state changes.
- Crafted IDs, stale revisions, wrong speakers, and invalid transitions reject
  transactionally.
- Movement, encounters, attack, farewell, and destroyed contacts invalidate
  state correctly.
- Economy, combat, alliance, contract, and fog-of-war invariants remain green.

### Replay and clients

- Golden logs reproduce line IDs, realization, choices, effects, and hash.
- Save/reload at each node displays the same persisted turn.
- Legacy command logs replay during the compatibility window.
- Snapshot/store/wire codec round trips and fingerprint mismatch tests.
- Local and hosted clients send stable choice IDs and revisions.

### Tooling

- Default corpus and generated sidecars validate.
- Authoring prompts emit the new node/choice/predicate schema.
- Play-test controls use the production runtime and show selection/action
  diagnostics.
- Corpus migration is deterministic and idempotent.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Incremental migration temporarily increases code | Time-box adapters, require shadow parity, and delete each legacy seam immediately after its cutover. |
| Persisted turns add hashed state | Store compact IDs/tokens/bindings and batch one explicit epoch. |
| Predicate flexibility grows into a language | Keep a small structured operator set and typed path registry. |
| Stable-ID conversion changes positional behavior | Preserve authored order and replay representative legacy logs. |
| Fallback behavior changes subtly | Compile and compare every species/context/standing matrix before cutover. |
| Relationship aggregation becomes a whole-game rewrite | Keep DS-WP08 optional and after the contact-runtime cutover. |
| Old compatibility never disappears | Choose a deprecation horizon before DS-WP05 and make removal an exit condition. |

---

## Choosing between the alternatives

Choose this incremental simplification plan when:

- preserving current dialogue selection and save compatibility is important;
- the existing persona/generic corpus model is considered a useful foundation;
- a staged, low-risk migration is preferred;
- temporary adapters and parity machinery are acceptable.

Choose `DIALOGUE_SYSTEM_REPLACEMENT_PLAN.md` when:

- minimizing the final maintenance surface is more important than preserving
  the current runtime model;
- explicit ordered graph scripts are preferred over salience selection;
- a clean save/config epoch is acceptable;
- the old schema and runtime should be deleted rather than adapted.

The alternatives share useful foundations — stable IDs, node-level choices,
typed context, registered actions, persisted turns, and reducer authority — so
the first safe work (scenario fixtures and stable authored IDs) can begin only
after the project decides whether those artifacts should target the existing
pack model or Dialogue Program v2.

## Decisions to confirm before implementation

1. Select incremental simplification or full replacement.
2. If incremental, define the compatibility/deprecation horizon.
3. Decide whether relationship aggregation belongs in the chosen effort.
4. Choose deterministic shuffle counters or stable-ID K-deep recency.
