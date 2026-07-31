# Reference code catalog

`references/` contains shallow clones of the codebases analyzed when
`docs/DESIGN.md` was written (recreate with `scripts/clone_references.sh` if
absent). They are **read-only**: never modify them, and never copy code from
them verbatim — they are inspiration and a source of constants/algorithms, and
they carry assorted licenses (GPL-era code among them). Reimplement ideas
cleanly.

What each is for:

- `references/twclone` — architecture reference: server/engine process split,
  durable event log + cron-task scheduling, market-driven port economy
  (docs/GALACTIC_ECONOMY.md, docs/ENGINE.md), tunnel/FedSpace universe gen,
  full TW command catalog in docs/PROTOCOL.v3/.
- `references/terminal-space` — closest Python cousin: clean domain model,
  PortClass enum (8 buy/sell triples), port type distribution
  (20/20/20/10/10/10/5/5), stock-ratio pricing, `to_public(context)`
  fog-of-war DTO pattern, embedded-server single-player.
- `references/blacknovatraders` — tuned economy constants (config.php),
  linear pricing `base ± delta * stock/limit`, planet/colonist production
  math (sched_planets.php), combat baseline (attack.php).
- `references/tradewars/tw2bas/` — the original 1986 BASIC source +
  TWINSTR.DOC rulebook: turn costs, sector-fighter rules, retreat costs one
  fighter, Cabal NPCs, 500-sector scale. Authenticity reference.
- `references/SectorWars` — contains "TW Sector Algorithm.txt": the
  cluster-and-bridge universe generation algorithm we use.
- `references/ExchangeConflict2016` — networkx generation motifs (deadends,
  rings), uniview-style map inspector idea, config-driven ship data.
- `references/aatraders` — sysop/admin feature catalog only (Phase 5).
