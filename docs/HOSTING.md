# Hosting Edge of the Unknown (multiplayer) — WP68

Edge is single-player-first; multiplayer is a **delivery mechanism** for the same game
(DESIGN §2, §14). One authoritative process owns the universe and every client — terminal or
browser — talks to it over a websocket. This doc is the operator's guide: run a server, let
people connect, and keep the saves safe.

## The pieces

- **`edge-server`** — the authoritative game host. In *lobby mode* (`--accounts`) it owns
  accounts, hosts many games, and runs one single-writer command queue + engine ticker **per
  open game** (H14: every command applies in arrival order, so a hosted game rebuilds to the
  same `state_hash` as its command log). With no storage arguments it uses
  `~/.edge/server/accounts.db` and `~/.edge/server/games/`.
- **`edge --connect ws://host:port`** — the remote client. A normal terminal player runs this;
  it opens the lobby turnstile (register / log in / join a game), then plays through all the
  ordinary screens over the wire. No optimistic prediction: commands round-trip and views
  re-read (correctness over snappiness at LAN scales).
- **`edge --serve --connect ws://host:port`** — the *browser* client: `textual-serve` runs the
  remote client as a served subprocess, so a player only needs a browser.

The wire is JSON-RPC 2.0 with a versioned codec (`server/wire.py`); client and server refuse a
build mismatch at the `hello` fingerprint handshake, so a stale client fails loudly rather than
corrupting a game.

## Live sysop administration

Do not intervene in a running hosted game by opening its SQLite file as a second writer. The
server owns the authoritative in-memory universe and its single-writer command queue; a direct
DB edit is durable but cannot update that live state safely.

Run the dashboard with the server connection and the game's lobby name. After sysop
authentication, the server resolves the backing DB used for trusted, fog-bypassing reports;
mutations still go through the server queue:

```bash
EDGE_SYSOP_PASSWORD='operator-secret' edge-sysop \
  --connect ws://localhost:8765 \
  --game alpha
```

The sysop secret is independent of every player account, including the first account registered.
That first account retains only its lobby-host role for creating games; its login password grants
no sysop authority.
Set it when launching the server with `--sysop-password`, `EDGE_SYSOP_PASSWORD`, or an
`EDGE_SYSOP_PASSWORD=…` entry in `./.env`. The sysop tool uses the same precedence
(`--password`, environment, then `./.env`), so when both commands run from the same directory a
local `.env` works for both without repeating the secret on their command lines. Do not commit
that file. If the commands run from different directories, pass the same file explicitly with
`--env-file PATH`. For live administration, the authenticated server resolves `--game NAME`
and supplies the authoritative save location; the operator does not provide a numeric game ID,
accounts-registry path, or save path.

Every intervention is sent as a `DevPatch` through the running game's command queue, persisted
in arrival order, broadcast normally, and visible to connected players and bots on their next
view read. The local DB is replayed for each dashboard refresh so reports follow the live command
log. Offline `edge-sysop --save …` remains available only when that game is not being served.

## Quick start (localhost)

Create a local operator secret once, then use two terminals from that directory:

```bash
# local-only operator configuration (.env is ignored by this repository)
printf '%s\n' 'EDGE_SYSOP_PASSWORD=replace-with-a-long-secret' > .env

# 1) host a lobby (~/.edge/server is created on first run)
pixi run host                     # → edge-server, listening on ws://localhost:8765

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

A game is a single SQLite file under `--games-dir` (default `~/.edge/server/games/`), plus the
accounts database (default `~/.edge/server/accounts.db`).
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
EnvironmentFile=/etc/edge/server.env
ExecStart=/opt/edge/.pixi/envs/default/bin/edge-server \
    --accounts /var/lib/edge/accounts.db --games-dir /var/lib/edge/games --host 0.0.0.0
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`/etc/edge/server.env` should contain `EDGE_SYSOP_PASSWORD=…` and be readable only by the
service account.

Back up `/var/lib/edge/` on a timer; that directory is the whole galaxy.

## Reconnecting

A dropped socket is not a lost game. The client surfaces it as a retryable link state and
`reconnect()` re-authenticates, re-binds the same seat, and replays every event missed via the
durable event rail (`events_since`) — so a blip costs no events and no progress.

## Scale

Tens of players on SQLite-behind-one-writer is within the design load (DESIGN §2). The
repository seam (`store/repo.py`) is the swap point if a deployment ever outgrows it; Postgres is
explicitly out of scope for now.
