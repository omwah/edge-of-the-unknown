# Validating Alien Dialogue Sidecars

This document serves as a checklist and methodology guide for validating and auditing authored alien dialogue sidecars (e.g., `<path_to_sidecar.yaml>`) against the Edge of the Unknown game engine rules.

When authoring or modifying a species sidecar, use the following checks to ensure the dialogue trees remain unbroken, logically sound, and mechanically complete.

## 1. Dangling State-Machine Actions
**What to check:** The `action:` key (e.g., `accept_lead`, `trade`, `farewell`) hooks directly into the core engine state machine. Ensure these are only attached to the correct conversational contexts. For example, `action: accept_lead` should only exist on choices inside `offer_coordinates` or specific mechanic branches, never on generic greetings or inquiries.
**How to check:**
*   Visually audit or use a `grep` search (`grep -B 5 -A 5 'action: accept_lead'`) to verify the surrounding context of the action.
*   Ensure that choices containing state actions are genuinely fulfilling the mechanical criteria they claim to.

## 2. Missing String Placeholders
**What to check:** Certain dialogue contexts expect specific format placeholders to be present in the text (e.g., `{target}` and `{coords}` in `offer_coordinates`). If these placeholders are omitted from a Tracery string template, the engine will either fail to format the string or present incomplete information to the player.
**How to check:**
*   Write a Python script to iterate over `species_grammars` in the YAML file.
*   For specific contexts (like `offer_coordinates`), parse the string contents of the `origin` arrays (and any sub-grammars it expands into) to assert the literal presence of `{target}`, `{coords}`, etc.

## 3. Missing Standard Menu Fallbacks
**What to check:** If you do NOT provide a `choices` block in a dialogue node, the engine derives a default "Say/Do" menu based on the species' capabilities (e.g., Trade, Ask about species, Leave). **If you DO provide a `choices` block, it overrides the default menu entirely.** You must ensure your authored choices don't accidentally trap the player by failing to provide standard conversational exits (like initiating trade or leaving).
**How to check:**
*   Write a Python script that iterates over all nodes (`greeting`, `dossier_other`, `branch.*`).
*   If `choices` is present, collect a `set` of all `action` and `next_context` values.
*   Assert that `trade` (or `go_trade_open`), `go_dossier_other`, and `farewell` are present where mechanically appropriate. If they are missing, the player is trapped; you must inject them textually into the choices array.

## 4. Missing Mechanical Dialogue Contexts
**What to check:** Species have mechanical parameters in `config/alien_roster_default.yaml` that dictate behavior—like `trade_posture: refuses` or `treaty_mode: alliance_gated`. When a player trips these conditions, the engine looks for specific dialogue contexts (like `trade_refuse` or `treaty_refuse`). If the sidecar lacks these contexts, it falls back to a generic persona, losing the species' unique flavor.
**How to check:**
*   Load `alien_roster_default.yaml` and collect a list of species that block mechanics (e.g., any `trade_posture` other than `open` or `earn`).
*   Load the dialogue sidecar and verify that a `trade_refuse` dictionary exists for each of those specific species.
*   If missing, append a `trade_refuse` node with flavored `variants` (or a `grammar`) and a `farewell` choice.

## 5. Broken Tracery Grammar Rules
**What to check:** Tracery expands tags enclosed in hashes (e.g., `#opener#`). Every tag used in an `origin` string must be defined as a key in that exact same `grammar` dictionary. If a tag is undefined, or if a hash character `#` is left dangling, the grammar rule is broken.
**How to check:**
*   Write a Python script that walks through every `grammar` dictionary in the YAML.
*   For every string value in the dictionary, use Regex (`re.findall(r'#([a-zA-Z0-9_]+)#', val)`) to extract all invoked tags.
*   Perform a set subtraction: `invoked_tags - set(grammar.keys())`. If the result is not empty, you have a broken Tracery rule.

## 6. Broken Graph Links (Orphaned Contexts)
**What to check:** The `next_context` pointer on any dialogue choice dictates the next node the engine transitions to. If there is a typo (e.g., `branch.inqury` instead of `branch.inquiry`), the player will click a choice and the game will crash or trap them.
**How to check:**
*   Write a Python script that aggregates all context keys from the sidecar `species_grammars`, the specific base `persona` the species uses, and the `generic` fallback persona.
*   Iterate through every `choices` block in the sidecar and base config.
*   Assert that every `next_context` value exists in the aggregated dictionary of keys.

## 7. Grammar Variation Exhaustion
**What to check:** The dialogue engine uses a recency ring (usually of depth 2 or 3) to prevent NPCs from repeating the same line verbatim in consecutive encounters. If a dialogue node has fewer `variants` (or fewer resulting strings in its Tracery `origin`) than the recency ring size, the engine's non-repeating illusion breaks, and it may forcefully repeat.
**How to check:**
*   Write a Python script that iterates over all context arrays (like `greeting`, `trade_open`).
*   Check if `variants` is present instead of a Tracery grammar.
*   Assert that `len(variants)` >= 3. If it is 1 or 2, you must author more variations to ensure the recency ring can cycle properly.

## 8. Invalid State Machine Actions
**What to check:** The `action:` string on a choice (`trade`, `barter`, `accept_lead`, `attack`, `farewell`) is hard-bound to core engine states. A typo like `farwell` or `trade_open` (which is a context, not an action) will fail to trigger the mechanical transition.
**How to check:**
*   Write a Python script to extract a `set` of every unique `action:` value across the sidecar and base config.
*   Assert that this set is a strict subset of the valid engine actions (`trade`, `barter`, `accept_lead`, `attack`, `farewell`, `surrender`, etc.).

## 9. Missing Treaty Responses
**What to check:** If `alien_roster_default.yaml` designates a species as treaty-capable (e.g., `treaty_mode: open`, `conditional`, `alliance_gated`), they require custom lore-accurate responses for `treaty_offer`, `treaty_grant`, `treaty_condition`, and `treaty_refuse`. If these are omitted, the species falls back to generic, mechanical treaty acceptance.
**How to check:**
*   Write a script to read `treaty_mode` from the roster.
*   If `treaty_mode` is not `none` or `impossible`, check the sidecar `species_grammars` for that specific species.
*   Assert that all four treaty contexts are fully authored.

## 10. Built-in Pipeline Validation
**What to check:** The engine has a built-in authoring and validation pipeline that runs structural integrity checks against the sidecar YAML file according to the schema in `edge/core/config.py` and `edge/dialogue/select.py`.
**How to check:**
*   Run the following terminal command to validate the sidecar automatically:
    ```bash
    pixi run author-dialogue --validate <path_to_sidecar.yaml>
    ```
*   This will catch many foundational schema errors (like missing keys or invalid list structures) before you even need to run custom python scripts.
