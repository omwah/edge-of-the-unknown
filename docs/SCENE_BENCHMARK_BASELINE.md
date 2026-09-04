# Sector scene benchmark

**PENDING HUMAN REVIEW / APPROVAL** -- this document reports measurements only; WP-SC04's "approve one production strategy" decision is a separate, human step. Do not read any number here as an approval.

Supersedes the informal 2026-08-31 figures in plan §6.1 with a reproducible measurement. Strategy comparison numbers use a benchmark-only SceneTuning/catalog overlay -- see module docstring.

## 1. Current composer baseline (reproduces plan §6.1)

| case | size | cold ms | warm median ms | warm p95 ms | warm max ms |
|---|---|---:|---:|---:|---:|
| empty+ships | standard 67x30 | 126.5634 | 10.197299999999998 | 10.6453 | 10.6453 |
| empty+ships | wide 87x36 | 185.5074 | 13.122 | 13.2159 | 13.2159 |
| empty+ships | large 120x44 | 311.2606 | 19.940150000000003 | 20.1358 | 20.1358 |
| empty+ships | huge 150x52 | 467.1912 | 26.44895 | 27.2749 | 27.2749 |
| port+ships | standard 67x30 | 125.3704 | 9.731950000000001 | 9.9505 | 9.9505 |
| port+ships | wide 87x36 | 186.6135 | 12.44105 | 12.9303 | 12.9303 |
| port+ships | large 120x44 | 309.0626 | 22.59395 | 41.6343 | 41.6343 |
| port+ships | huge 150x52 | 449.1125 | 26.16675 | 30.7918 | 30.7918 |
| stardock+ships | standard 67x30 | 133.8174 | 12.22405 | 15.7275 | 15.7275 |
| stardock+ships | wide 87x36 | 184.2933 | 14.79675 | 16.7318 | 16.7318 |
| stardock+ships | large 120x44 | 309.2842 | 21.0059 | 39.4632 | 39.4632 |
| stardock+ships | huge 150x52 | 462.8538 | 27.7915 | 28.4808 | 28.4808 |
| starbase+ships | standard 67x30 | 130.9716 | 12.47625 | 12.8048 | 12.8048 |
| starbase+ships | wide 87x36 | 188.9053 | 14.238199999999999 | 14.2516 | 14.2516 |
| starbase+ships | large 120x44 | 335.7142 | 20.766 | 22.9332 | 22.9332 |
| starbase+ships | huge 150x52 | 455.8999 | 27.1411 | 27.3418 | 27.3418 |
| planet+ships | standard 67x30 | 164.6595 | 19.90775 | 39.6278 | 39.6278 |
| planet+ships | wide 87x36 | 242.5326 | 26.926650000000002 | 29.96 | 29.96 |
| planet+ships | large 120x44 | 405.0287 | 50.3416 | 67.924 | 67.924 |
| planet+ships | huge 150x52 | 581.0643 | 72.5293 | 85.78 | 85.78 |
| planet+port+ships | standard 67x30 | 140.1487 | 21.3926 | 21.5396 | 21.5396 |
| planet+port+ships | wide 87x36 | 199.1762 | 29.42485 | 30.8719 | 30.8719 |
| planet+port+ships | large 120x44 | 365.8092 | 49.837999999999994 | 52.972 | 52.972 |
| planet+port+ships | huge 150x52 | 525.8012 | 66.77995 | 86.0792 | 86.0792 |
| planet+stardock+ships | standard 67x30 | 141.2846 | 23.65445 | 23.9927 | 23.9927 |
| planet+stardock+ships | wide 87x36 | 205.3299 | 29.7795 | 29.9434 | 29.9434 |
| planet+stardock+ships | large 120x44 | 367.6924 | 50.78985 | 56.2568 | 56.2568 |
| planet+stardock+ships | huge 150x52 | 517.8691 | 64.99494999999999 | 88.6331 | 88.6331 |
| planet+starbase+ships | standard 67x30 | 136.8085 | 21.02355 | 21.5558 | 21.5558 |
| planet+starbase+ships | wide 87x36 | 198.3299 | 28.10055 | 49.792 | 49.792 |
| planet+starbase+ships | large 120x44 | 341.475 | 49.876050000000006 | 72.5099 | 72.5099 |
| planet+starbase+ships | huge 150x52 | 495.7673 | 66.79060000000001 | 86.2472 | 86.2472 |
| wormhole+port+ships | standard 67x30 | 130.7336 | 15.16665 | 15.4211 | 15.4211 |
| wormhole+port+ships | wide 87x36 | 198.9353 | 20.884900000000002 | 20.9869 | 20.9869 |
| wormhole+port+ships | large 120x44 | 336.1927 | 35.284800000000004 | 59.092 | 59.092 |
| wormhole+port+ships | huge 150x52 | 482.2172 | 49.10815 | 69.9319 | 69.9319 |
| blackhole+port+ships | standard 67x30 | 135.2561 | 14.793099999999999 | 14.8389 | 14.8389 |
| blackhole+port+ships | wide 87x36 | 193.3471 | 20.5212 | 20.8482 | 20.8482 |
| blackhole+port+ships | large 120x44 | 328.0231 | 33.57525 | 66.6535 | 66.6535 |
| blackhole+port+ships | huge 150x52 | 475.7713 | 44.0432 | 65.4021 | 65.4021 |
| nebula+port+ships | standard 67x30 | 946.7909 | 23.187800000000003 | 23.3612 | 23.3612 |
| nebula+port+ships | wide 87x36 | 1523.9581 | 33.5022 | 36.232 | 36.232 |
| nebula+port+ships | large 120x44 | 2650.0465 | 56.75165 | 83.2307 | 83.2307 |
| nebula+port+ships | huge 150x52 | 3974.1699 | 98.3869 | 113.5167 | 113.5167 |
| wreck+ships | standard 67x30 | 125.7159 | 10.09965 | 10.1206 | 10.1206 |
| wreck+ships | wide 87x36 | 193.7473 | 15.48795 | 15.8625 | 15.8625 |
| wreck+ships | large 120x44 | 323.7005 | 25.63215 | 25.8985 | 25.8985 |
| wreck+ships | huge 150x52 | 467.5281 | 33.9511 | 36.0654 | 36.0654 |
| wormhole+starbase+ships | standard 67x30 | 132.8023 | 16.2496 | 16.32 | 16.32 |
| wormhole+starbase+ships | wide 87x36 | 225.7078 | 23.7569 | 26.3965 | 26.3965 |
| wormhole+starbase+ships | large 120x44 | 334.6223 | 38.8507 | 42.9373 | 42.9373 |
| wormhole+starbase+ships | huge 150x52 | 508.817 | 50.73915 | 82.4519 | 82.4519 |
| belt+port+ships | standard 67x30 | 196.1625 | 22.01755 | 24.2317 | 24.2317 |
| belt+port+ships | wide 87x36 | 301.2606 | 31.3574 | 31.5236 | 31.5236 |
| belt+port+ships | large 120x44 | 513.2553 | 51.86215 | 81.52 | 81.52 |
| belt+port+ships | huge 150x52 | 732.1687 | 71.02629999999999 | 99.6953 | 99.6953 |
| planet+port+wreck+traffic | standard 67x30 | 163.0334 | 23.9754 | 25.1307 | 25.1307 |
| planet+port+wreck+traffic | wide 87x36 | 206.4662 | 33.85505 | 35.7143 | 35.7143 |
| planet+port+wreck+traffic | large 120x44 | 354.1377 | 53.89045 | 79.8643 | 79.8643 |
| planet+port+wreck+traffic | huge 150x52 | 506.5881 | 70.2191 | 95.3899 | 95.3899 |
| derelict-base+ships | standard 67x30 | 120.2342 | 9.819600000000001 | 10.0796 | 10.0796 |
| derelict-base+ships | wide 87x36 | 193.8152 | 14.1441 | 17.4049 | 17.4049 |
| derelict-base+ships | large 120x44 | 308.0988 | 21.898400000000002 | 48.409 | 48.409 |
| derelict-base+ships | huge 150x52 | 453.6792 | 26.5656 | 26.6696 | 26.6696 |

## 2. Real fog-safe DTO inventories (8 seeds x up to 3200 sectors sampled)

| field | median | p95 | p99 | max |
|---|---:|---:|---:|---:|
| ships | 0.0 | 1 | 1 | 3 |
| discoveries | 0.0 | 1 | 1 | 1 |
| stations (ports+starbases) | 1.0 | 2 | 2 | 2 |
| generated wrecks | 0.0 | 0 | 0 | 0 |

Synthetic multiplayer/N-ship stress (`classify_sector` only, not generated-universe data):

- 1_ships_classify_ms: 0.1037 ms
- 5_ships_classify_ms: 0.1097 ms
- 20_ships_classify_ms: 0.2695 ms
- 50_ships_classify_ms: 0.6489 ms

## 3. Replacement strategy comparison (WP-SC03 code, benchmark-only tuning)

`classify_sector` alone: median 0.07165 ms, p95 0.0833 ms, max 0.1234 ms.

| strategy | case | size | frame ms | candidates ms | candidate count | distinct quantised scenes | deterministic |
|---|---|---|---:|---:|---:|---:|---:|
| fixed_fov_perspective | empty+ships | standard 67x30 | 0.0793 | 0.2758 | 64 | 64 | True |
| depth_layered_anchor | empty+ships | standard 67x30 | 0.073 | 0.1346 | 40 | 39 | True |
| fixed_fov_perspective | empty+ships | wide 87x36 | 0.0287 | 0.2381 | 64 | 64 | True |
| depth_layered_anchor | empty+ships | wide 87x36 | 0.0581 | 0.1287 | 40 | 39 | True |
| fixed_fov_perspective | empty+ships | large 120x44 | 0.04 | 0.2385 | 64 | 64 | True |
| depth_layered_anchor | empty+ships | large 120x44 | 0.057 | 0.1285 | 40 | 40 | True |
| fixed_fov_perspective | empty+ships | huge 150x52 | 0.026 | 0.2378 | 64 | 64 | True |
| depth_layered_anchor | empty+ships | huge 150x52 | 0.0571 | 0.1286 | 40 | 40 | True |
| fixed_fov_perspective | port+ships | standard 67x30 | 0.0388 | 0.241 | 64 | 64 | True |
| depth_layered_anchor | port+ships | standard 67x30 | 0.0562 | 0.1301 | 40 | 40 | True |
| fixed_fov_perspective | port+ships | wide 87x36 | 0.0249 | 0.2596 | 64 | 64 | True |
| depth_layered_anchor | port+ships | wide 87x36 | 0.0949 | 0.1322 | 40 | 40 | True |
| fixed_fov_perspective | port+ships | large 120x44 | 0.0272 | 0.239 | 64 | 64 | True |
| depth_layered_anchor | port+ships | large 120x44 | 0.0581 | 0.131 | 40 | 39 | True |
| fixed_fov_perspective | port+ships | huge 150x52 | 0.0273 | 0.2391 | 64 | 64 | True |
| depth_layered_anchor | port+ships | huge 150x52 | 0.0554 | 0.1318 | 40 | 39 | True |
| fixed_fov_perspective | stardock+ships | standard 67x30 | 0.037 | 0.2623 | 64 | 64 | True |
| depth_layered_anchor | stardock+ships | standard 67x30 | 0.0558 | 0.1482 | 40 | 40 | True |
| fixed_fov_perspective | stardock+ships | wide 87x36 | 0.0266 | 0.2395 | 64 | 64 | True |
| depth_layered_anchor | stardock+ships | wide 87x36 | 0.0563 | 0.1327 | 40 | 40 | True |
| fixed_fov_perspective | stardock+ships | large 120x44 | 0.0257 | 0.2395 | 64 | 64 | True |
| depth_layered_anchor | stardock+ships | large 120x44 | 0.0544 | 0.1298 | 40 | 39 | True |
| fixed_fov_perspective | stardock+ships | huge 150x52 | 0.0262 | 0.2392 | 64 | 64 | True |
| depth_layered_anchor | stardock+ships | huge 150x52 | 0.0548 | 0.1301 | 40 | 39 | True |
| fixed_fov_perspective | starbase+ships | standard 67x30 | 0.0374 | 0.2618 | 64 | 64 | True |
| depth_layered_anchor | starbase+ships | standard 67x30 | 0.0566 | 0.1465 | 40 | 40 | True |
| fixed_fov_perspective | starbase+ships | wide 87x36 | 0.0287 | 0.238 | 64 | 64 | True |
| depth_layered_anchor | starbase+ships | wide 87x36 | 0.0578 | 0.1291 | 40 | 40 | True |
| fixed_fov_perspective | starbase+ships | large 120x44 | 0.0269 | 0.2378 | 64 | 64 | True |
| depth_layered_anchor | starbase+ships | large 120x44 | 0.0557 | 0.129 | 40 | 39 | True |
| fixed_fov_perspective | starbase+ships | huge 150x52 | 0.0248 | 0.2386 | 64 | 64 | True |
| depth_layered_anchor | starbase+ships | huge 150x52 | 0.0554 | 0.1285 | 40 | 39 | True |
| fixed_fov_perspective | planet+ships | standard 67x30 | 0.0289 | 0.2625 | 64 | 64 | True |
| depth_layered_anchor | planet+ships | standard 67x30 | 0.1006 | 0.1312 | 40 | 40 | True |
| fixed_fov_perspective | planet+ships | wide 87x36 | 0.0205 | 0.2354 | 64 | 64 | True |
| depth_layered_anchor | planet+ships | wide 87x36 | 0.0475 | 0.132 | 40 | 40 | True |
| fixed_fov_perspective | planet+ships | large 120x44 | 0.0183 | 0.2916 | 64 | 64 | True |
| depth_layered_anchor | planet+ships | large 120x44 | 0.0475 | 0.1464 | 40 | 39 | True |
| fixed_fov_perspective | planet+ships | huge 150x52 | 0.0198 | 0.2373 | 64 | 64 | True |
| depth_layered_anchor | planet+ships | huge 150x52 | 0.0479 | 0.1305 | 40 | 39 | True |
| fixed_fov_perspective | planet+port+ships | standard 67x30 | 0.0221 | 0.2388 | 64 | 64 | True |
| depth_layered_anchor | planet+port+ships | standard 67x30 | 0.0485 | 0.1293 | 40 | 40 | True |
| fixed_fov_perspective | planet+port+ships | wide 87x36 | 0.02 | 0.2358 | 64 | 64 | True |
| depth_layered_anchor | planet+port+ships | wide 87x36 | 0.0486 | 0.1296 | 40 | 40 | True |
| fixed_fov_perspective | planet+port+ships | large 120x44 | 0.0179 | 0.2568 | 64 | 64 | True |
| depth_layered_anchor | planet+port+ships | large 120x44 | 0.0478 | 0.1339 | 40 | 39 | True |
| fixed_fov_perspective | planet+port+ships | huge 150x52 | 0.018 | 0.2414 | 64 | 64 | True |
| depth_layered_anchor | planet+port+ships | huge 150x52 | 0.061 | 0.1319 | 40 | 39 | True |
| fixed_fov_perspective | planet+stardock+ships | standard 67x30 | 0.0225 | 0.2417 | 64 | 64 | True |
| depth_layered_anchor | planet+stardock+ships | standard 67x30 | 0.0484 | 0.1296 | 40 | 40 | True |
| fixed_fov_perspective | planet+stardock+ships | wide 87x36 | 0.0194 | 0.2366 | 64 | 64 | True |
| depth_layered_anchor | planet+stardock+ships | wide 87x36 | 0.0474 | 0.1319 | 40 | 40 | True |
| fixed_fov_perspective | planet+stardock+ships | large 120x44 | 0.0178 | 0.2421 | 64 | 64 | True |
| depth_layered_anchor | planet+stardock+ships | large 120x44 | 0.0485 | 0.13 | 40 | 39 | True |
| fixed_fov_perspective | planet+stardock+ships | huge 150x52 | 0.0177 | 0.2557 | 64 | 64 | True |
| depth_layered_anchor | planet+stardock+ships | huge 150x52 | 0.0738 | 0.1313 | 40 | 39 | True |
| fixed_fov_perspective | planet+starbase+ships | standard 67x30 | 0.0223 | 0.238 | 64 | 64 | True |
| depth_layered_anchor | planet+starbase+ships | standard 67x30 | 0.0494 | 0.1292 | 40 | 40 | True |
| fixed_fov_perspective | planet+starbase+ships | wide 87x36 | 0.0204 | 0.2356 | 64 | 64 | True |
| depth_layered_anchor | planet+starbase+ships | wide 87x36 | 0.0479 | 0.1295 | 40 | 40 | True |
| fixed_fov_perspective | planet+starbase+ships | large 120x44 | 0.0399 | 0.3361 | 64 | 64 | True |
| depth_layered_anchor | planet+starbase+ships | large 120x44 | 0.0492 | 0.1294 | 40 | 39 | True |
| fixed_fov_perspective | planet+starbase+ships | huge 150x52 | 0.0181 | 0.2362 | 64 | 64 | True |
| depth_layered_anchor | planet+starbase+ships | huge 150x52 | 0.0478 | 0.1288 | 40 | 39 | True |
| fixed_fov_perspective | wormhole+port+ships | standard 67x30 | 0.031 | 0.241 | 64 | 64 | True |
| depth_layered_anchor | wormhole+port+ships | standard 67x30 | 0.0505 | 0.1292 | 40 | 40 | True |
| fixed_fov_perspective | wormhole+port+ships | wide 87x36 | 0.0202 | 0.2363 | 64 | 64 | True |
| depth_layered_anchor | wormhole+port+ships | wide 87x36 | 0.048 | 0.1287 | 40 | 40 | True |
| fixed_fov_perspective | wormhole+port+ships | large 120x44 | 0.0183 | 0.2361 | 64 | 64 | True |
| depth_layered_anchor | wormhole+port+ships | large 120x44 | 0.0479 | 0.1287 | 40 | 39 | True |
| fixed_fov_perspective | wormhole+port+ships | huge 150x52 | 0.0176 | 0.2575 | 64 | 64 | True |
| depth_layered_anchor | wormhole+port+ships | huge 150x52 | 0.0479 | 0.1454 | 40 | 39 | True |
| fixed_fov_perspective | blackhole+port+ships | standard 67x30 | 0.0278 | 0.2414 | 64 | 64 | True |
| depth_layered_anchor | blackhole+port+ships | standard 67x30 | 0.0495 | 0.1296 | 40 | 40 | True |
| fixed_fov_perspective | blackhole+port+ships | wide 87x36 | 0.0522 | 0.2621 | 64 | 64 | True |
| depth_layered_anchor | blackhole+port+ships | wide 87x36 | 0.0504 | 0.1299 | 40 | 40 | True |
| fixed_fov_perspective | blackhole+port+ships | large 120x44 | 0.0219 | 0.239 | 64 | 64 | True |
| depth_layered_anchor | blackhole+port+ships | large 120x44 | 0.0488 | 0.217 | 40 | 39 | True |
| fixed_fov_perspective | blackhole+port+ships | huge 150x52 | 0.0214 | 0.2387 | 64 | 64 | True |
| depth_layered_anchor | blackhole+port+ships | huge 150x52 | 0.0484 | 0.1294 | 40 | 39 | True |
| fixed_fov_perspective | nebula+port+ships | standard 67x30 | 0.0263 | 0.293 | 64 | 64 | True |
| depth_layered_anchor | nebula+port+ships | standard 67x30 | 0.0489 | 0.1821 | 40 | 40 | True |
| fixed_fov_perspective | nebula+port+ships | wide 87x36 | 0.0196 | 0.2377 | 64 | 64 | True |
| depth_layered_anchor | nebula+port+ships | wide 87x36 | 0.0474 | 0.1283 | 40 | 40 | True |
| fixed_fov_perspective | nebula+port+ships | large 120x44 | 0.0192 | 0.2358 | 64 | 64 | True |
| depth_layered_anchor | nebula+port+ships | large 120x44 | 0.0482 | 0.128 | 40 | 39 | True |
| fixed_fov_perspective | nebula+port+ships | huge 150x52 | 0.0177 | 0.2557 | 64 | 64 | True |
| depth_layered_anchor | nebula+port+ships | huge 150x52 | 0.047 | 0.1437 | 40 | 39 | True |
| fixed_fov_perspective | wreck+ships | standard 67x30 | 0.0316 | 0.238 | 64 | 64 | True |
| depth_layered_anchor | wreck+ships | standard 67x30 | 0.0569 | 0.1286 | 40 | 39 | True |
| fixed_fov_perspective | wreck+ships | wide 87x36 | 0.027 | 0.2375 | 64 | 64 | True |
| depth_layered_anchor | wreck+ships | wide 87x36 | 0.0551 | 0.1302 | 40 | 39 | True |
| fixed_fov_perspective | wreck+ships | large 120x44 | 0.0286 | 0.2364 | 64 | 64 | True |
| depth_layered_anchor | wreck+ships | large 120x44 | 0.0544 | 0.1278 | 40 | 40 | True |
| fixed_fov_perspective | wreck+ships | huge 150x52 | 0.0245 | 0.2578 | 64 | 64 | True |
| depth_layered_anchor | wreck+ships | huge 150x52 | 0.0597 | 0.1444 | 40 | 40 | True |
| fixed_fov_perspective | wormhole+starbase+ships | standard 67x30 | 0.0224 | 0.2403 | 64 | 64 | True |
| depth_layered_anchor | wormhole+starbase+ships | standard 67x30 | 0.0488 | 0.1292 | 40 | 40 | True |
| fixed_fov_perspective | wormhole+starbase+ships | wide 87x36 | 0.0194 | 0.2369 | 64 | 64 | True |
| depth_layered_anchor | wormhole+starbase+ships | wide 87x36 | 0.0482 | 0.1285 | 40 | 40 | True |
| fixed_fov_perspective | wormhole+starbase+ships | large 120x44 | 0.0181 | 0.2371 | 64 | 64 | True |
| depth_layered_anchor | wormhole+starbase+ships | large 120x44 | 0.0479 | 0.1285 | 40 | 39 | True |
| fixed_fov_perspective | wormhole+starbase+ships | huge 150x52 | 0.0177 | 0.2564 | 64 | 64 | True |
| depth_layered_anchor | wormhole+starbase+ships | huge 150x52 | 0.0478 | 0.147 | 40 | 39 | True |
| fixed_fov_perspective | belt+port+ships | standard 67x30 | 0.0276 | 0.2398 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | standard 67x30 | 0.0502 | 0.1288 | 40 | 40 | True |
| fixed_fov_perspective | belt+port+ships | wide 87x36 | 0.0203 | 0.2372 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | wide 87x36 | 0.0474 | 0.1285 | 40 | 40 | True |
| fixed_fov_perspective | belt+port+ships | large 120x44 | 0.0176 | 0.2379 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | large 120x44 | 0.0474 | 0.1289 | 40 | 39 | True |
| fixed_fov_perspective | belt+port+ships | huge 150x52 | 0.0177 | 0.2564 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | huge 150x52 | 0.0501 | 0.1951 | 40 | 39 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | standard 67x30 | 0.0231 | 0.3089 | 64 | 64 | True |
| depth_layered_anchor | planet+port+wreck+traffic | standard 67x30 | 0.0494 | 0.1349 | 40 | 40 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | wide 87x36 | 0.0318 | 0.238 | 64 | 64 | True |
| depth_layered_anchor | planet+port+wreck+traffic | wide 87x36 | 0.0509 | 0.1305 | 40 | 40 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | large 120x44 | 0.0198 | 0.2366 | 64 | 64 | True |
| depth_layered_anchor | planet+port+wreck+traffic | large 120x44 | 0.0492 | 0.1299 | 40 | 39 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | huge 150x52 | 0.0184 | 0.2354 | 64 | 64 | True |
| depth_layered_anchor | planet+port+wreck+traffic | huge 150x52 | 0.048 | 0.1292 | 40 | 39 | True |
| fixed_fov_perspective | derelict-base+ships | standard 67x30 | 0.0286 | 0.2642 | 64 | 64 | True |
| depth_layered_anchor | derelict-base+ships | standard 67x30 | 0.0781 | 0.1308 | 40 | 40 | True |
| fixed_fov_perspective | derelict-base+ships | wide 87x36 | 0.0279 | 0.2385 | 64 | 64 | True |
| depth_layered_anchor | derelict-base+ships | wide 87x36 | 0.0592 | 0.1293 | 40 | 40 | True |
| fixed_fov_perspective | derelict-base+ships | large 120x44 | 0.0275 | 0.2403 | 64 | 64 | True |
| depth_layered_anchor | derelict-base+ships | large 120x44 | 0.0588 | 0.129 | 40 | 39 | True |
| fixed_fov_perspective | derelict-base+ships | huge 150x52 | 0.0268 | 0.24 | 64 | 64 | True |
| depth_layered_anchor | derelict-base+ships | huge 150x52 | 0.0575 | 0.1287 | 40 | 39 | True |

### Fields not measurable before WP-SC06/SC07

- admitted/rejected/painted counts: n/a (pending WP-SC06 solver)
- solve-pass/occlusion/reanchor counters: n/a (pending WP-SC06 solver)
- sprite-cache hit rate: n/a (pending WP-SC07 art resolution)
- ScenePlan cache: n/a (no ScenePlan cache exists before WP-SC06/SC08)
- decision-prose gating: n/a (no Decision trace producer before WP-SC06) / n/a (no Decision trace producer before WP-SC06)
