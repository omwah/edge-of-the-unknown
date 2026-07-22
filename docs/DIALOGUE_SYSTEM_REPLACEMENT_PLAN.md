# Dialogue system replacement — proposed plan

> Companion to `DESIGN.md` §6.2/§6.7/§10/§13 and
> `DIALOGUE_GAME_STATE.md`. `DESIGN.md` remains authoritative until the spec
> delta in DR-WP01 is accepted and landed.
>
> **Status: alternative proposal — replace the current salience/fact-map
> dialogue system with a small declarative dialogue-program interpreter.** It
> sits alongside the lower-risk incremental proposal in
> `DIALOGUE_RUNTIME_SIMPLIFICATION_PLAN.md`; neither alternative is selected
> until the project explicitly chooses between them.

## Decision summary

Replace the current system rather than refactor it in place.

The replacement is an explicit directed graph of authored dialogue nodes. A
node contains ordered speech alternatives, visible choices, and transitions.
Conditions read a typed view of game state. Choices may set scoped narrative
variables or invoke a registered game action. The reducer advances the graph
and persists the resolved turn; the server only projects it.

```text
authoring YAML
    |
    v
compile + validate at config load
    |
    v
flat DialogueProgram per species
    |
    v
DialogueRuntime.start(entrypoint) / choose(choice_id)
    |
    +-- read typed game context
    +-- read/write scoped narrative variables
    +-- preview/dispatch registered domain actions
    +-- persist current resolved turn
    |
    v
server DTO -> TUI
```

The replacement removes these live concepts:

- salience/specificity scoring;
- `DialogueWhen` and the arbitrary `criteria` fact dictionary;
- runtime species → persona → generic pack walking;
- choices attached to whichever `DialogueLine` happens to win;
- the closed intent list as the set of all legal conversation nodes;
- magic `branch.*` and `sig.*` context prefixes;
- client-supplied context plus positional choice index;
- projection/reducer reselection “lockstep”;
- feature-specific dialogue binding and gating branches;
- signature-mechanic stage aliases hidden in `species_arcs`.

The replacement keeps these product requirements:

- deterministic replay from `(seed, command log, dialogue program)`;
- authored per-species voice and reusable persona/base material;
- variants and grammar-backed realization;
- visit-local and cross-visit memory;
- game-state-aware speech and choices;
- combat and automatic encounter speech;
- intel, contracts, trade, barter, attack, and signature mechanics;
- reducer authority, fog of war, config validation, and offline authoring;
- no runtime LLM and no I/O in core/dialogue execution.

---

## Why replacement is simpler

The current implementation has several independently reasonable layers, but
their composition is difficult to extend:

1. A flat fact map is assembled from situation, callbacks, arcs, session, and
   caller extras.
2. Dedicated `standing`/`treaty` fields coexist with arbitrary criteria and
   inert `posture`/`stage` fields.
3. Salience chooses a line entry; that winning prose entry may also determine
   the reply menu.
4. Runtime fallback walks species, persona, and generic packs separately for
   every resolution.
5. The server reconstructs offers and disabled reasons, while the reducer
   reconstructs the menu and applies effects.
6. Intel, contracts, dossier subjects, combat, and signature mechanics each
   introduce special context handling.

This yields the worst combination: the author cannot express ordinary boolean
conditions or arbitrary graph structure directly, while maintainers must keep
several implicit resolution systems synchronized.

The replacement makes control flow explicit. There is no “winning rule” to
infer and no magic context behavior to remember. At a node:

1. evaluate speech alternatives from top to bottom;
2. use the first whose condition is true;
3. preview the node's choices through registered actions;
4. persist exactly what was selected;
5. apply a stable choice ID and follow its explicit transition.

Ordered first-match selection is intentionally less clever than salience. It
is easier to author, debug, validate, and explain.

---

## Goals

1. A writer can understand a conversation by reading one explicit graph.
2. Adding an ordinary branch requires dialogue data, not a new Python context
   constant or reducer/projection switch.
3. Conditions support `and`, `or`, `not`, membership, comparisons, and scoped
   narrative variables without an open-ended fact bag.
4. Adding a mechanical integration requires one registered domain action,
   reusable from any node or species.
5. The runtime has one selection path and one transition path.
6. Shared persona/generic content is resolved at load time, leaving a flat and
   inspectable program at runtime.
7. Automatic encounter/combat beats use named entrypoints into the same graph,
   not a separate dialogue mechanism.
8. The new implementation is materially smaller and has fewer extension
   points than the system it deletes.

## Non-goals

- No natural-language parser or free-text player input.
- No runtime generative AI.
- No general-purpose scripting language in YAML.
- No arbitrary Python calls or arbitrary `Player` mutation from authored data.
- No attempt to model combat, trade, contracts, or discoveries inside the
  dialogue engine.
- No permanent compatibility layer for the old runtime.
- No exact preservation of which randomized variant old development saves
  would have spoken next.
- No visual redesign of the contact screen in the replacement milestone.

---

## Replacement format: Dialogue Program v2

### Program structure

Each species resolves to one compiled `DialogueProgram`:

```yaml
version: 2

programs:
  generic_contact:
    entrypoints:
      contact: greeting
      farewell: farewell
      combat.open: combat.open
      combat.round: combat.taunt
      combat.surrender: combat.surrender
      combat.fled: combat.flee_scorn

    nodes:
      greeting:
        say:
          - when: "relationship.allied"
            variants:
              - "Welcome home, {player}."
          - when: "relationship.standing == 'hostile'"
            variants:
              - "State your purpose and keep your batteries cold."
          - variants:
              - "We receive you, {player}."

        choices:
          - id: ask_self
            text: "Tell me about your people."
            goto: dossier.self
          - id: ask_coordinates
            text: "What lies beyond this sector?"
            action: intel.preview
            goto:
              success: intel.offer
              unavailable: intel.none
          - id: trade
            text: "Show me what you trade."
            action: trade.open
            goto:
              success: trade.open
              unavailable: trade.refuse
          - id: leave
            text: "Until next transmission."
            action: conversation.leave

      dossier.self:
        say:
          - variants:
              - "We crossed the old dark before your charts had names."
        choices:
          - id: back
            text: "Let us speak of something else."
            goto: $back

      intel.offer:
        say:
          - variants:
              - "Search {target} at {coords}; the trail is {distance} jumps."
        choices:
          - id: accept
            text: "Put those coordinates in my computer."
            action: intel.accept
            goto: greeting
          - id: decline
            text: "Not now."
            goto: greeting

      intel.none:
        say:
          - variants:
              - "We know of nothing your charts do not already hold."
        choices:
          - id: back
            text: "Then another subject."
            goto: greeting

      farewell:
        say:
          - variants:
              - "May the lanes open before you."
        end: true
```

The example is illustrative rather than the final corpus schema. The following
properties are normative.

### Nodes are arbitrary stable IDs

A node ID is unique within its compiled program. It has no semantics based on
its spelling. `branch.*`, `sig.*`, and the current closed intent catalogue are
not runtime namespaces.

Game systems enter dialogue through a small, closed entrypoint vocabulary:

```text
contact
farewell
combat.open
combat.betrayal
combat.round
combat.surrender
combat.fled
```

Future systems add an entrypoint only when the game initiates speech without a
player transition. Writers may add any number of internal nodes without a code
change.

### Speech selection is ordered first-match

`say` is an ordered list. The first alternative with a true `when` is used; an
alternative without `when` is the required fallback and must be last.

An alternative contains exactly one realization form:

- `variants`: a list of authored strings; or
- `grammar`: the existing deterministic grammar form.

There is no salience score, specificity weight, or weighted competition among
different conditions. Randomness only realizes variation *inside* the chosen
alternative.

### Choices belong to nodes

Choices are not stored on speech alternatives. Every choice has a stable ID
unique within its node and may contain:

```yaml
- id: stable_choice_id
  text: "Player-facing reply"
  when: "optional condition"
  action: optional.registered_action
  with:
    optional: validated parameters
  set:
    relationship.promised_help: true
  goto: next_node
```

`goto` may be:

- one node ID;
- `$back`;
- omitted when the action ends or leaves the conversation; or
- a mapping from registered action result keys to node IDs.

Hidden choices fail their `when`. Mechanically impossible choices remain
visible but disabled when their action preview returns a reason. This keeps
narrative branching distinct from domain authorization.

### Shared content is compiled, not resolved at runtime

Reuse remains important, but runtime fallback is removed. Programs may extend
one base program and optionally apply one persona overlay:

```yaml
programs:
  merchant_base:
    extends: generic_contact
    nodes: { ... }

  ruskin:
    extends: merchant_base
    overlay: persona.formal_collective
    nodes:
      greeting:
        say: [ ... ]
```

Compilation performs a deterministic merge and produces one flat program per
species. The merge rules are deliberately narrow:

- a program has at most one `extends` parent;
- an optional overlay is applied after the parent and before local nodes;
- a locally supplied node field replaces that entire inherited field;
- authors can replace `say`, `choices`, or both independently;
- there is no runtime fallback and no multiple-inheritance search.

The validator and authoring tool can print the compiled program, so writers see
exactly what will run.

---

## Conditions: a small safe expression language

Conditions are concise strings, compiled at config load:

```yaml
when: >-
  relationship.standing in ['friendly', 'allied']
  and player.hull_ratio < 0.35
  and not visit.did_trade
```

Implementation uses `ast.parse(..., mode="eval")` followed by a custom
interpreter. It must never call Python `eval`. The allowed syntax is limited to:

- `and`, `or`, `not`;
- `==`, `!=`, `<`, `<=`, `>`, `>=`;
- `in`, `not in`;
- parentheses;
- booleans, numbers, strings, and literal lists;
- dotted reads from registered context namespaces.

Calls, comprehensions, arithmetic, indexing, mutation, imports, and arbitrary
attribute access are rejected. Every dotted path is checked against a typed
registry at config load, so misspellings and invalid comparisons fail before a
game starts.

### Read-only game context

The runtime builds one typed `DialogueContext` through registered providers:

```text
speaker.*       id, kind, alliance, traits, configured posture
relationship.* effective standing, attitude, allied, grudge
player.*        hull ratio, turns, cargo summary, alignment, equipment
place.*         band, nebula, visible wrecks, public coordinates
history.*       met, last seen, accepted/followed leads, last combat
visit.*         node visits, choices taken, visit-scoped variables
story.*         persisted narrative variables for this species/player
encounter.*     round, pack size, survivors, shields
offer.*         current registered-action preview data
result.*        the immediately preceding action's typed result data
```

Providers own the mapping from authoritative state into these namespaces. The
dialogue engine does not know how a contract, lead, grudge, or combat round is
stored. Providers expose only information the conversation is allowed to use,
preserving fog of war.

Context paths replace both `DialogueWhen` and `contact_facts`. There is no
second caller-extra dictionary and no duplicate `sig_stage` alias.

---

## Narrative state

The engine owns only narrative memory, not domain state.

```python
@dataclass(frozen=True, slots=True)
class NarrativeMemory:
    species_vars: Mapping[str, Mapping[str, Scalar]]
    realization_counts: Mapping[str, int]

@dataclass(frozen=True, slots=True)
class ConversationState:
    speaker_id: int
    sector_id: int
    program_id: str
    node_id: str
    revision: int
    history: tuple[str, ...]
    visit_vars: Mapping[str, Scalar]
    node_visits: Mapping[str, int]
    choices_taken: frozenset[str]
    turn: ResolvedTurnRef
```

`Scalar` is a closed `str | int | float | bool` union with bounded key/value
sizes. Dialogue data may set only `visit.*` and `story.*` variables declared by
the compiled program. It cannot set attitude, money, cargo, contracts,
encounters, or other core fields.

Relationship state stays in its existing core domains unless a separate model
cleanup is justified. The replacement does not need to move attitudes,
grudges, leads, contracts, or `last_combat`; providers read them where they
already live. This keeps the dialogue replacement bounded.

### Resolved turn

Reducers persist a compact reference to exactly what was spoken and offered:

```python
@dataclass(frozen=True, slots=True)
class ResolvedTurnRef:
    speech_id: str
    realization: int
    bindings: Mapping[str, str]
    choices: tuple[ResolvedChoiceRef, ...]
```

The server renders/projects this reference. It does not rerun conditions,
selection, offer picking, or choice gating. A command carries the stable choice
ID and `expected_revision`; stale or fabricated input is rejected.

Realization variation is keyed by stable speech ID and a deterministic counter.
The counter selects a seeded shuffle cycle, avoiding repeats until the pool is
exhausted. It replaces positional recency rings keyed by context.

---

## Registered game actions

Dialogue choices integrate with game mechanics through a closed action
registry. An action has two pure/core-facing operations:

```python
class DialogueAction(Protocol):
    def preview(self, request: ActionRequest) -> ActionPreview: ...
    def apply(self, request: ActionRequest) -> ActionResult: ...
```

`preview` returns:

- enabled/disabled;
- a player-facing disabled reason;
- deterministic placeholder bindings;
- a stable offer/target reference;
- optional typed preview data exposed as `offer.*`.

`apply` revalidates authoritative state and returns domain mutations/events,
typed result data, and a result key. A preview never authorizes an action.

Initial actions replace the current special paths:

```text
conversation.leave
trade.open
barter.open
intel.preview
intel.accept
contract.preview
contract.accept
combat.attack
mechanic.run
```

Pure transitions and narrative `set` operations do not need registry entries.

### Signature mechanics

Signature mechanics are ordinary `mechanic.run` actions:

```yaml
- id: submit_to_judgment
  text: "Judge what I have done."
  action: mechanic.run
  with:
    mechanic: morality_judge
    approach: submit
  goto:
    blessed: judgment.blessed
    condemned: judgment.condemned
```

The result is available to the immediate destination node as `result.*`.
Durable mechanic progress is exposed on later turns through `story.*` or a
mechanic-owned context provider. No context-name parsing, `sig.*` namespace,
`sig_stage` alias, or transient-fact workaround remains.

---

## Runtime and layer boundaries

The new package layout is intentionally small:

```text
edge/dialogue/
    schema.py       v2 config models
    compile.py      inheritance/overlay compiler
    expression.py   safe condition compiler/interpreter
    context.py      typed context + provider registry
    actions.py      action protocol and registry metadata
    runtime.py      start/choose/transition interpreter
    render.py       variants, grammar, placeholders
    validate.py     graph/schema/context/action validation
    authoring/      offline generation and real-runtime play-test
```

After cutover, delete rather than retain renamed versions of:

```text
edge/dialogue/facts.py
edge/dialogue/intents.py
edge/dialogue/select.py
```

If a tiny compatibility converter needs their types during corpus migration,
it lives under `scripts/` or `edge/dialogue/authoring/`, never on the runtime
import path.

Dependency direction remains downward-only:

- schema/expression/render/compile/validate are independent pure modules;
- context providers may read lower `edge.core` models and pure helpers;
- runtime consumes compiled programs, context, and action previews;
- `edge.core.rules` calls runtime and applies returned domain action results;
- server projects persisted turns;
- TUI sends stable choice IDs and revisions through the service API.

---

## Save and compatibility policy

The recommended policy is a clean development epoch, not permanent dual
support:

1. Bump config/save/protocol versions at cutover.
2. Refuse old snapshots with a clear “dialogue runtime changed” message.
3. Regenerate golden command logs and fixtures against v2.
4. Provide a one-time corpus converter for authored YAML.
5. Do not ship the old selector beside the new interpreter.

If preservation of player saves is later declared mandatory, build a one-time
offline save migration before cutover. Do not add a permanent legacy reducer,
schema union, or runtime mode flag; those would recreate the maintenance burden
this replacement exists to remove.

---

## Cross-cutting invariants

- **R1 — One runtime.** There is exactly one live dialogue schema, compiler,
  condition evaluator, and interpreter after cutover.
- **R2 — Reducer authority.** Domain actions revalidate and mutate only through
  core reducers/pure domain planners.
- **R3 — One selection.** The reducer resolves and persists a turn once; the
  projection never reselects it.
- **R4 — Stable identity.** Program, node, speech, choice, action, and declared
  variable IDs are explicit and load-time unique.
- **R5 — Determinism.** Program compilation, condition evaluation, action
  previews, traversal, and realization are canonically ordered and replayable.
- **R6 — Bounded authoring.** Expressions cannot call code; narrative effects
  can write only declared narrative variables; actions come from a code
  registry.
- **R7 — Fog of war.** Context/action providers expose only intentionally
  public facts and bindings.
- **R8 — Inspectability.** The authoring tool can dump a species' fully compiled
  graph, entrypoints, conditions, variables, actions, and reachability.
- **R9 — Spec synchronization.** Every schema/runtime change updates
  `DESIGN.md` §6.7/§13, the header of
  `config/alien_dialogue_default.yaml`, and
  `edge/dialogue/authoring/pipeline.py` (`build_prompt` and
  `_structure_brief`) in the same change. `DIALOGUE_GAME_STATE.md` is rewritten
  at final cutover.
- **R10 — Smaller live surface.** The replacement is not complete until the old
  runtime files, models, helpers, projection gates, reducer branches, and tests
  of obsolete behavior are deleted.

---

## Milestones and work packages

### M1 — Prove the replacement in isolation

#### DR-WP01 — Spec delta and executable examples (S/M)

- Update DESIGN §6.7/§13 from salience packs to Dialogue Program v2.
- Record the first-match, compiled-inheritance, registered-action, scoped-state,
  and persisted-turn invariants.
- Write three complete example programs in test fixtures:
  - a generic peaceful contact with trade/intel/farewell;
  - a hostile combat speaker with automatic entrypoints;
  - a signature-mechanic conversation with result-directed branching.
- Freeze current gameplay outcome fixtures for migration comparison; exact old
  line choice is informative, not normative.

Exit: the v2 format can express every major dialogue mode before implementation
begins.

#### DR-WP02 — Schema, compiler, and graph validator (M/L)

- Implement v2 Pydantic schema models.
- Implement one-parent + one-overlay compilation into a flat immutable program.
- Validate unique IDs, entrypoints, destinations, `$back`, terminal nodes,
  declared variables, placeholders, action IDs/parameters, and result mappings.
- Compute graph reachability and reject unreachable nodes unless explicitly
  marked as an external entrypoint target.
- Add a compiled-program dump suitable for humans, tests, and authoring tools.

Exit: programs compile deterministically and invalid graphs fail with precise
source paths.

#### DR-WP03 — Safe expressions and typed context providers (M/L)

- Implement the whitelisted AST expression compiler/interpreter without
  `eval`.
- Register typed context paths and validate expressions at config load.
- Implement providers for identity, relationship, player condition, place,
  history, visit/story, and encounter facts.
- Add truth-table, fuzz, malicious-expression, fog-of-war, and missing-state
  tests.

Exit: the example programs can branch on all currently live facts without
`DialogueWhen` or a generic fact dictionary.

#### DR-WP04 — Interpreter, narrative memory, and deterministic rendering (L)

- Implement start-at-entrypoint, ordered speech selection, choice filtering,
  node transition, `$back`, terminal nodes, variable writes, and revisioning.
- Add `NarrativeMemory`, `ConversationState`, and `ResolvedTurnRef` initially in
  isolated tests.
- Reuse the existing grammar renderer behind stable speech IDs.
- Implement deterministic shuffle-cycle realization counters.
- Prove identical results across process runs, save/reload of the isolated
  state, and canonical compilation order.

Exit: a headless v2 conversation can be played completely with no dependency
on the old selector.

### M2 — Integrate every game action

#### DR-WP05 — Action registry and common preview/apply protocol (L)

- Implement the closed action registry and typed parameter/result schemas.
- Adapt leave, trade, barter, intel, contracts, attack, and signature mechanics
  behind the protocol.
- Move disabled reasons and deterministic target/offer bindings into previews.
- Ensure apply reuses the same domain planner and revalidates current state.
- Test every action for success, unavailability, state change after preview,
  and transactional failure.

Exit: no shipped interaction requires special knowledge in the dialogue
interpreter.

#### DR-WP06 — Convert the corpus and authoring pipeline (L)

- Write a one-time converter from personas/species packs into base programs,
  overlays, nodes, ordered alternatives, and stable IDs.
- Convert the shipped default corpus and signature grammar sidecars.
- Manually review ordering where salience rules overlap; make precedence
  explicit rather than emulating scores.
- Replace the authoring output schema and prompt context with v2.
- Update the play-test harness to run the v2 interpreter directly and display
  node, expression, action preview, result, and variable diagnostics.
- Add a corpus compiler report showing inherited versus overridden fields.

Exit: the full shipped corpus compiles as v2 and every species is traversable in
the play-test harness.

#### DR-WP07 — Core state, commands, codecs, and replay epoch (L)

- Add authoritative narrative/conversation state to `Player`.
- Add `ChooseDialogue(species_id, choice_id, expected_revision)` and any
  start-entrypoint command/event changes.
- Add store snapshot, command/event codec, wire codec, and state-hash support.
- Bump the declared config/save/protocol epoch and regenerate goldens.
- Test stale/duplicate choice commands, speaker switching/movement/destruction,
  farewell, hostile interruption, multiplayer independence, and reload at
  every node.

Exit: v2 turns and effects survive the real service/store/replay path.

### M3 — Hard cutover and deletion

#### DR-WP08 — Reducer cutover (L)

- Route hail/contact, peaceful choices, combat open/round/surrender/flee speech,
  the Entity, dossiers, tech, intel, contracts, attack, and mechanics through
  v2 entrypoints/actions.
- Persist each resolved turn before the server projects it.
- Remove context-string and positional-index dispatch from live commands.
- Remove feature-specific `_intel_bindings`, signature context parsing, and arc
  aliases as their v2 action/provider paths take ownership.
- Run complete gameplay and replay suites before touching projection code.

Exit: every live reducer path uses v2 exclusively.

#### DR-WP09 — Projection, TUI, and hosted-client cutover (M/L)

- Make contact/encounter projections render persisted turn references only.
- Send stable choice ID + expected revision through local and remote clients.
- Preserve authored order, disabled reasons, subject/offer summaries, portraits,
  and force-enable diagnostics in the real contact screen.
- Remove `_line`, `_contact_choices`, `_gate_choice`, and projection-time offer
  selection.
- Add tests asserting the projection does not invoke selection or action
  previews.

Exit: the screen cannot disagree with what the reducer resolved.

#### DR-WP10 — Delete v1 and rewrite documentation (M)

- Delete `DialogueWhen`, `DialogueLine`, `DialogueChoice`, old dialogue packs,
  `facts.py`, `intents.py`, `select.py`, `ContactSession`, raw recency rings, and
  obsolete arc/session helpers after confirming no runtime import remains.
- Delete compatibility tests that encode salience, fallback search, positional
  indices, magic prefixes, or duplicated lockstep.
- Retain narrative/content behavior tests expressed through v2.
- Rewrite `DIALOGUE_GAME_STATE.md` around program, context, narrative state,
  actions, reducer authority, and persisted turns.
- Remove the corpus converter from runtime packaging; it may remain as an
  archived development script if useful.
- Run `ruff`, strict mypy layers, the full pytest suite, dialogue play-test
  traversal, golden replay, and graphify update.

Exit: no v1 schema, selector, fact assembler, runtime fallback, or projection
gate exists in production code.

#### DR-WP11 — Flexibility and maintenance exit criterion (M)

Prove the replacement with authored examples requiring no interpreter change:

- nested AND/OR/NOT conditions;
- numeric thresholds and membership checks;
- a visit-local branch and callback;
- a persisted cross-visit story variable;
- one species overriding prose but inheriting choices;
- one species overriding choices but inheriting prose;
- a disabled domain action with a domain-produced explanation;
- an action-result-directed branch using transient result data;
- a multi-stage signature mechanic with no magic context namespace;
- an automatic combat entrypoint using the same interpreter.

Measure maintenance surface before and after:

- runtime source files and non-comment lines;
- schema types;
- independent selection/gating paths;
- places changed to add one condition path;
- places changed to add one registered action;
- dialogue-specific branches in `core.rules` and `server.session`.

Exit criterion:

> A writer can add a multi-node, state-aware conversation using existing
> context paths and actions by editing one program and its tests. A developer
> can add a new game integration by registering one typed action/provider and
> then use it from any program. Neither change requires edits to the dialogue
> interpreter, server projection, or TUI.

---

## Suggested commits

1. `dialogue-v2: adopt replacement spec and examples`
2. `dialogue-v2: compile and validate dialogue programs`
3. `dialogue-v2: add safe expressions and typed context`
4. `dialogue-v2: interpret graphs and narrative memory`
5. `dialogue-v2: register domain action adapters`
6. `dialogue-v2: convert corpus and authoring tools`
7. `dialogue-v2: persist turns and stable choices`
8. `dialogue-v2: cut reducers over`
9. `dialogue-v2: project resolved turns`
10. `dialogue-v2: delete salience runtime`
11. `dialogue-v2: prove flexibility and maintenance exit`

Do not combine the first reducer cutover with v1 deletion. There should be one
green commit where v2 owns all live behavior and v1 remains unused, followed by
a deletion commit proving the old machinery is truly unnecessary.

---

## Verification matrix

### Compiler and validation

- Inheritance/overlay order and independent `say`/`choices` replacement.
- Duplicate IDs, cycles, missing destinations, invalid entrypoints, unreachable
  nodes, bad `$back`, terminal-node choices, and incomplete result mappings.
- Undeclared variables, invalid action parameters, unknown context paths, bad
  placeholders, and missing fallback speech.
- Compiled output stable across mapping/list construction order and processes.

### Expression safety

- Every allowed boolean/comparison/membership construct.
- Type errors detected at load.
- Rejection of calls, subscripts, comprehensions, lambdas, imports, arithmetic,
  dunder access, mutation, and oversized expressions.
- Property/fuzz tests guarantee the interpreter never escapes registered paths.

### Runtime

- Ordered first-match behavior and required fallback.
- Stable-choice dispatch, revision rejection, `$back`, terminal nodes, visit
  variables, story variables, and action-result transitions.
- Deterministic realization with no repeat until pool exhaustion.
- Save/reload displays the same persisted turn without reevaluation.

### Domain actions

- Preview/apply agreement and revalidation after state changes.
- Conservation and no-negative-balance invariants for trade/barter/mechanics.
- Fog-of-war for intel/contract targets.
- Core sanctuary and all first-strike blocks for attack.
- Immediate transient mechanic results and durable progress.

### End-to-end

- Every species/entrypoint traversed in the real play-test harness.
- Hail → branch → action → result → farewell.
- Peaceful encounter, hostile combat, surrender, flee-scorn, and betrayal.
- Entity sensor gate and codex stamp.
- Local and hosted clients, stale revisions, two simultaneous players.
- Fixed-seed command logs, state hashes, snapshots, and wire round trips.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The expression language becomes another cumbersome subsystem | Restrict it to a small AST whitelist, typed registered paths, and no functions or arithmetic. |
| Explicit ordering hides accidental precedence | Validator requires a final fallback; compiled dump and play-test show which alternative matched and why. |
| Program inheritance recreates fallback complexity | One parent, one optional overlay, deterministic whole-field replacement, and runtime sees only a flat program. |
| Persisted turns increase state size | Store IDs, counters, bindings, and previews rather than rendered prose or history transcripts. |
| Action previews become stale | Commands carry a revision and apply revalidates current domain state transactionally. |
| Corpus conversion loses nuance | Convert mechanically, report overlapping old salience rules, then manually make ordering explicit with golden scenario review. |
| Clean epoch discards development saves | Announce the epoch, preserve seed/config recipes, and provide an offline migration only if save preservation becomes a requirement. |
| Two systems linger indefinitely | Time-box parallel existence to isolated v2 construction and one green cutover commit; DR-WP10 deletes v1 before completion. |

---

## Decisions to confirm before DR-WP01

This proposal recommends all four defaults:

1. **Custom v2 interpreter rather than Ink/Yarn or another dependency.** The
   required runtime is small, deterministic, Python-native, config-integrated,
   and must call game-specific typed actions. An external narrative engine adds
   a compiler/runtime dependency and a second data model without removing the
   integration work.
2. **Ordered first-match rather than salience.** Explicit precedence is easier
   to maintain and debug; randomness remains inside the selected speech pool.
3. **Clean save/config epoch rather than permanent v1 compatibility.** This is
   a replacement intended to reduce maintenance, so the old schema and runtime
   should not remain live.
4. **One-parent + one-overlay compile-time reuse.** It preserves generic/persona
   authoring leverage while eliminating runtime fallback search and ambiguous
   multiple inheritance.

Once those defaults are accepted, DR-WP01 can turn this proposal into the
authoritative DESIGN delta and implementation work can begin.
