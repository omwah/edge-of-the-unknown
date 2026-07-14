# Hosting Edge of the Unknown (multiplayer) — WP68

Edge is single-player-first; multiplayer is a **delivery mechanism** for the same game
(DESIGN §2, §14). One authoritative process owns the universe and every client — terminal or
browser — talks to it over a websocket. This doc is the operator's guide: run a server, let
people connect, and keep the saves safe.

## The pieces

- **`edge-server`** — the authoritative game host. In *lobby mode* (`--accounts`) it owns
  accounts, hosts many games, and runs one single-writer command queue + engine ticker **per
  open game** (H14: every command applies in arrival order, so a hosted game rebuilds to the
  same `state_hash` as its command log).
- **`edge --connect ws://host:port`** — the remote client. A normal terminal player runs this;
  it opens the lobby turnstile (register / log in / join a game), then plays through all the
  ordinary screens over the wire. No optimistic prediction: commands round-trip and views
  re-read (correctness over snappiness at LAN scales).
- **`edge --serve --connect ws://host:port`** — the *browser* client: `textual-serve` runs the
  remote client as a served subprocess, so a player only needs a browser.

The wire is JSON-RPC 2.0 with a versioned codec (`server/wire.py`); client and server refuse a
build mismatch at the `hello` fingerprint handshake, so a stale client fails loudly rather than
corrupting a game.

## Quick start (localhost)

Two terminals:

```bash
# 1) host a lobby (accounts.db + games/ are created on first run)
pixi run host                     # → edge-server --accounts accounts.db --games-dir games
                                  #    listening on ws://localhost:8765

# 2a) connect a terminal player
pixi run edge -- --connect ws://localhost:8765

# 2b) …or serve the client in a browser (visit http://localhost:8000)
pixi run serve-remote             # → edge --serve --connect ws://localhost:8765
```

In the lobby: pick a username/password and a game name. **Register + Join** creates the account
(and, if you are the configured host, the game) and drops you into it; **Log in + Join** does the
same for a returning player. The first game must be created by a host account (create-game is
host-gated server-side); other players **Join** it by name.

## Serving the browser client off-box (`--public-url`)

`--serve` bakes the session websocket URL **into the page** from the address it was told to
serve on — it does not derive it from the incoming request. So the default
(`--host localhost`) only works when the browser is on the *same machine*. Point any other
browser at it — a LAN IP, a WSL or container host, an SSH port-forward — and the page it
receives tells that browser to open `ws://localhost:8000/ws` against **itself**, which connects
to nothing. The symptom is the textual-serve splash (the game title on a dark page) sitting
there forever: the splash only clears when the app's first output arrives over that websocket.
There is no button to click — the `Start` button in the markup is `display: none` by design.

Bind wide and declare the address players actually type:

```bash
edge --serve --host 0.0.0.0 --port 8000 --public-url http://192.168.1.50:8000
```

Behind a TLS-terminating reverse proxy, `--public-url` is the **public** origin
(`https://edge.example.com`), and textual-serve derives the `wss://` session URL from it.

## Ports

- `8765` — the game server websocket (`edge-server`, change with `--port`).
- `8000` — the browser server for the served client (`--serve --port`).

Open only what you need. For play beyond localhost put the server behind a TLS-terminating
reverse proxy (nginx/caddy) and hand players a `wss://` URL — the client accepts any
`ws://`/`wss://` URL.

## Saves and backup

A game is a single SQLite file under `--games-dir` (default `games/`), plus the `accounts.db`.
The save is the durable `(seed, command log, maintenance log)` — **back it up by copying the
`.db` file** (do it while the server is stopped, or use SQLite's online backup). A restored file
replays to the identical state on next open. Accounts (password hashes, tokens, seat bindings)
live in `accounts.db`, deliberately **outside** game state (H15) — never in `state_hash`.

### systemd sketch

```ini
# /etc/systemd/system/edge-server.service
[Unit]
Description=Edge of the Unknown game server
After=network.target

[Service]
WorkingDirectory=/opt/edge
ExecStart=/opt/edge/.pixi/envs/default/bin/edge-server \
    --accounts /var/lib/edge/accounts.db --games-dir /var/lib/edge/games --host 0.0.0.0
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Back up `/var/lib/edge/` on a timer; that directory is the whole galaxy.

## Reconnecting

A dropped socket is not a lost game. The client surfaces it as a retryable link state and
`reconnect()` re-authenticates, re-binds the same seat, and replays every event missed via the
durable event rail (`events_since`) — so a blip costs no events and no progress.

## Scale

Tens of players on SQLite-behind-one-writer is within the design load (DESIGN §2). The
repository seam (`store/repo.py`) is the swap point if a deployment ever outgrows it; Postgres is
explicitly out of scope for now.
