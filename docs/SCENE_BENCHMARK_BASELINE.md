# Sector scene benchmark

**PENDING HUMAN REVIEW / APPROVAL** -- this document reports measurements only; WP-SC04's "approve one production strategy" decision is a separate, human step. Do not read any number here as an approval.

Supersedes the informal 2026-08-31 figures in plan §6.1 with a reproducible measurement. Strategy comparison numbers use a benchmark-only SceneTuning/catalog overlay -- see module docstring.

## 1. Current composer baseline (reproduces plan §6.1)

| case | size | cold ms | warm median ms | warm p95 ms | warm max ms |
|---|---|---:|---:|---:|---:|
| empty+ships | standard 67x30 | 131.2466 | 11.0937 | 13.4451 | 13.4451 |
| empty+ships | wide 87x36 | 189.7504 | 13.85425 | 15.159 | 15.159 |
| empty+ships | large 120x44 | 319.6966 | 20.2894 | 21.1911 | 21.1911 |
| empty+ships | huge 150x52 | 483.3244 | 28.727 | 42.2339 | 42.2339 |
| port+ships | standard 67x30 | 140.4105 | 9.9646 | 10.041 | 10.041 |
| port+ships | wide 87x36 | 187.7747 | 12.61365 | 12.7769 | 12.7769 |
| port+ships | large 120x44 | 322.6229 | 21.5083 | 39.1553 | 39.1553 |
| port+ships | huge 150x52 | 464.6939 | 27.90495 | 35.4614 | 35.4614 |
| stardock+ships | standard 67x30 | 133.8682 | 11.33645 | 11.7653 | 11.7653 |
| stardock+ships | wide 87x36 | 193.0857 | 13.95495 | 14.3929 | 14.3929 |
| stardock+ships | large 120x44 | 315.0645 | 19.7364 | 41.079 | 41.079 |
| stardock+ships | huge 150x52 | 465.5551 | 27.795 | 28.2013 | 28.2013 |
| starbase+ships | standard 67x30 | 133.0008 | 12.65155 | 12.7558 | 12.7558 |
| starbase+ships | wide 87x36 | 193.6175 | 13.9871 | 14.8482 | 14.8482 |
| starbase+ships | large 120x44 | 345.6178 | 23.2085 | 24.3409 | 24.3409 |
| starbase+ships | huge 150x52 | 487.6012 | 27.43445 | 29.5094 | 29.5094 |
| planet+ships | standard 67x30 | 167.7468 | 20.497 | 43.8266 | 43.8266 |
| planet+ships | wide 87x36 | 238.0375 | 25.6286 | 26.0587 | 26.0587 |
| planet+ships | large 120x44 | 426.2252 | 49.17415 | 70.5895 | 70.5895 |
| planet+ships | huge 150x52 | 592.8464 | 76.36635000000001 | 85.2888 | 85.2888 |
| planet+port+ships | standard 67x30 | 143.0112 | 21.63515 | 23.4411 | 23.4411 |
| planet+port+ships | wide 87x36 | 208.6331 | 28.96265 | 31.8602 | 31.8602 |
| planet+port+ships | large 120x44 | 373.0468 | 51.57705 | 52.5548 | 52.5548 |
| planet+port+ships | huge 150x52 | 540.9489 | 66.22815 | 85.5465 | 85.5465 |
| planet+stardock+ships | standard 67x30 | 144.309 | 23.9876 | 24.6194 | 24.6194 |
| planet+stardock+ships | wide 87x36 | 209.9316 | 29.609299999999998 | 30.2673 | 30.2673 |
| planet+stardock+ships | large 120x44 | 399.5034 | 51.07065 | 52.3259 | 52.3259 |
| planet+stardock+ships | huge 150x52 | 533.9554 | 66.8262 | 87.2733 | 87.2733 |
| planet+starbase+ships | standard 67x30 | 141.273 | 21.6982 | 22.1029 | 22.1029 |
| planet+starbase+ships | wide 87x36 | 211.0342 | 30.77735 | 53.4515 | 53.4515 |
| planet+starbase+ships | large 120x44 | 349.5276 | 57.092299999999994 | 73.9584 | 73.9584 |
| planet+starbase+ships | huge 150x52 | 524.6489 | 68.6121 | 94.9734 | 94.9734 |
| wormhole+port+ships | standard 67x30 | 137.5281 | 15.191600000000001 | 15.8616 | 15.8616 |
| wormhole+port+ships | wide 87x36 | 205.2274 | 21.0903 | 21.271 | 21.271 |
| wormhole+port+ships | large 120x44 | 349.0601 | 36.08765 | 59.6313 | 59.6313 |
| wormhole+port+ships | huge 150x52 | 506.2431 | 47.59265 | 71.6447 | 71.6447 |
| blackhole+port+ships | standard 67x30 | 134.405 | 14.39795 | 14.5681 | 14.5681 |
| blackhole+port+ships | wide 87x36 | 201.2241 | 21.92145 | 22.3257 | 22.3257 |
| blackhole+port+ships | large 120x44 | 336.5238 | 33.31485 | 58.6107 | 58.6107 |
| blackhole+port+ships | huge 150x52 | 491.7791 | 43.1434 | 71.9008 | 71.9008 |
| nebula+port+ships | standard 67x30 | 987.3625 | 22.762349999999998 | 22.8614 | 22.8614 |
| nebula+port+ships | wide 87x36 | 1599.8493 | 34.3621 | 34.6547 | 34.6547 |
| nebula+port+ships | large 120x44 | 2755.3839 | 58.1636 | 85.1383 | 85.1383 |
| nebula+port+ships | huge 150x52 | 4066.3479 | 96.5735 | 109.2404 | 109.2404 |
| wreck+ships | standard 67x30 | 125.716 | 10.1089 | 10.7369 | 10.7369 |
| wreck+ships | wide 87x36 | 191.6095 | 15.3351 | 16.1822 | 16.1822 |
| wreck+ships | large 120x44 | 323.9832 | 25.39945 | 27.1989 | 27.1989 |
| wreck+ships | huge 150x52 | 477.4335 | 33.92195 | 35.7617 | 35.7617 |
| wormhole+starbase+ships | standard 67x30 | 133.5375 | 16.4347 | 19.0189 | 19.0189 |
| wormhole+starbase+ships | wide 87x36 | 230.1623 | 23.6817 | 23.8034 | 23.8034 |
| wormhole+starbase+ships | large 120x44 | 347.6317 | 39.07955 | 39.9443 | 39.9443 |
| wormhole+starbase+ships | huge 150x52 | 511.3132 | 48.564099999999996 | 74.6688 | 74.6688 |
| belt+port+ships | standard 67x30 | 195.4688 | 21.364800000000002 | 21.5045 | 21.5045 |
| belt+port+ships | wide 87x36 | 297.4292 | 30.42905 | 31.7586 | 31.7586 |
| belt+port+ships | large 120x44 | 510.42 | 51.23655 | 77.8031 | 77.8031 |
| belt+port+ships | huge 150x52 | 741.881 | 70.3134 | 98.9063 | 98.9063 |
| planet+port+wreck+traffic | standard 67x30 | 171.4538 | 23.12265 | 23.2574 | 23.2574 |
| planet+port+wreck+traffic | wide 87x36 | 211.3208 | 33.893950000000004 | 33.9724 | 33.9724 |
| planet+port+wreck+traffic | large 120x44 | 353.2562 | 53.3741 | 80.1072 | 80.1072 |
| planet+port+wreck+traffic | huge 150x52 | 504.017 | 68.09185 | 94.0624 | 94.0624 |
| derelict-base+ships | standard 67x30 | 122.5993 | 9.97675 | 12.0439 | 12.0439 |
| derelict-base+ships | wide 87x36 | 186.8929 | 13.449300000000001 | 16.6978 | 16.6978 |
| derelict-base+ships | large 120x44 | 315.0138 | 21.2286 | 48.0782 | 48.0782 |
| derelict-base+ships | huge 150x52 | 473.3503 | 26.11945 | 29.7556 | 29.7556 |

## 2. Real fog-safe DTO inventories (8 seeds x up to 3200 sectors sampled)

| field | median | p95 | p99 | max |
|---|---:|---:|---:|---:|
| ships | 0.0 | 1 | 1 | 3 |
| discoveries | 0.0 | 1 | 1 | 1 |
| stations (ports+starbases) | 1.0 | 2 | 2 | 2 |
| generated wrecks | 0.0 | 0 | 0 | 0 |

Synthetic multiplayer/N-ship stress (`classify_sector` only, not generated-universe data):

- 1_ships_classify_ms: 0.1166 ms
- 5_ships_classify_ms: 0.1158 ms
- 20_ships_classify_ms: 0.2701 ms
- 50_ships_classify_ms: 0.6489 ms

## 3. Replacement strategy comparison (WP-SC03 code, benchmark-only tuning)

`classify_sector` alone: median 0.0727 ms, p95 0.0756 ms, max 0.1174 ms.

| strategy | case | size | frame ms | candidates ms | candidate count | distinct quantised scenes | deterministic |
|---|---|---|---:|---:|---:|---:|---:|
| fixed_fov_perspective | empty+ships | standard 67x30 | 0.0786 | 0.2711 | 64 | 64 | True |
| depth_layered_anchor | empty+ships | standard 67x30 | 0.073 | 0.1327 | 40 | 15 | True |
| fixed_fov_perspective | empty+ships | wide 87x36 | 0.029 | 0.2378 | 64 | 59 | True |
| depth_layered_anchor | empty+ships | wide 87x36 | 0.0586 | 0.1274 | 40 | 15 | True |
| fixed_fov_perspective | empty+ships | large 120x44 | 0.0257 | 0.2526 | 64 | 59 | True |
| depth_layered_anchor | empty+ships | large 120x44 | 0.0585 | 0.1285 | 40 | 16 | True |
| fixed_fov_perspective | empty+ships | huge 150x52 | 0.0258 | 0.2451 | 64 | 64 | True |
| depth_layered_anchor | empty+ships | huge 150x52 | 0.0604 | 0.1279 | 40 | 16 | True |
| fixed_fov_perspective | port+ships | standard 67x30 | 0.0387 | 0.2377 | 64 | 7 | True |
| depth_layered_anchor | port+ships | standard 67x30 | 0.0565 | 0.1281 | 40 | 1 | True |
| fixed_fov_perspective | port+ships | wide 87x36 | 0.0251 | 0.2481 | 64 | 14 | True |
| depth_layered_anchor | port+ships | wide 87x36 | 0.0706 | 0.1298 | 40 | 1 | True |
| fixed_fov_perspective | port+ships | large 120x44 | 0.0265 | 0.2405 | 64 | 9 | True |
| depth_layered_anchor | port+ships | large 120x44 | 0.0567 | 0.1278 | 40 | 2 | True |
| fixed_fov_perspective | port+ships | huge 150x52 | 0.0263 | 0.2351 | 64 | 13 | True |
| depth_layered_anchor | port+ships | huge 150x52 | 0.0569 | 0.1283 | 40 | 2 | True |
| fixed_fov_perspective | stardock+ships | standard 67x30 | 0.0372 | 0.2851 | 64 | 7 | True |
| depth_layered_anchor | stardock+ships | standard 67x30 | 0.0575 | 0.1286 | 40 | 1 | True |
| fixed_fov_perspective | stardock+ships | wide 87x36 | 0.0298 | 0.2377 | 64 | 14 | True |
| depth_layered_anchor | stardock+ships | wide 87x36 | 0.0576 | 0.1277 | 40 | 1 | True |
| fixed_fov_perspective | stardock+ships | large 120x44 | 0.0286 | 0.2369 | 64 | 9 | True |
| depth_layered_anchor | stardock+ships | large 120x44 | 0.0568 | 0.1282 | 40 | 2 | True |
| fixed_fov_perspective | stardock+ships | huge 150x52 | 0.0252 | 0.2555 | 64 | 13 | True |
| depth_layered_anchor | stardock+ships | huge 150x52 | 0.0601 | 0.1288 | 40 | 2 | True |
| fixed_fov_perspective | starbase+ships | standard 67x30 | 0.0384 | 0.255 | 64 | 44 | True |
| depth_layered_anchor | starbase+ships | standard 67x30 | 0.0714 | 0.1296 | 40 | 11 | True |
| fixed_fov_perspective | starbase+ships | wide 87x36 | 0.0279 | 0.2457 | 64 | 44 | True |
| depth_layered_anchor | starbase+ships | wide 87x36 | 0.0572 | 0.1283 | 40 | 11 | True |
| fixed_fov_perspective | starbase+ships | large 120x44 | 0.0277 | 0.2392 | 64 | 49 | True |
| depth_layered_anchor | starbase+ships | large 120x44 | 0.0575 | 0.1269 | 40 | 10 | True |
| fixed_fov_perspective | starbase+ships | huge 150x52 | 0.0256 | 0.2548 | 64 | 58 | True |
| depth_layered_anchor | starbase+ships | huge 150x52 | 0.0582 | 0.1414 | 40 | 10 | True |
| fixed_fov_perspective | planet+ships | standard 67x30 | 0.0313 | 0.2458 | 64 | 30 | True |
| depth_layered_anchor | planet+ships | standard 67x30 | 0.0567 | 0.1287 | 40 | 1 | True |
| fixed_fov_perspective | planet+ships | wide 87x36 | 0.02 | 0.2354 | 64 | 33 | True |
| depth_layered_anchor | planet+ships | wide 87x36 | 0.0503 | 0.1283 | 40 | 1 | True |
| fixed_fov_perspective | planet+ships | large 120x44 | 0.0182 | 0.25 | 64 | 36 | True |
| depth_layered_anchor | planet+ships | large 120x44 | 0.0615 | 0.1291 | 40 | 2 | True |
| fixed_fov_perspective | planet+ships | huge 150x52 | 0.0195 | 0.2419 | 64 | 43 | True |
| depth_layered_anchor | planet+ships | huge 150x52 | 0.0538 | 0.1281 | 40 | 2 | True |
| fixed_fov_perspective | planet+port+ships | standard 67x30 | 0.0227 | 0.2377 | 64 | 30 | True |
| depth_layered_anchor | planet+port+ships | standard 67x30 | 0.0501 | 0.1285 | 40 | 1 | True |
| fixed_fov_perspective | planet+port+ships | wide 87x36 | 0.0179 | 0.2507 | 64 | 33 | True |
| depth_layered_anchor | planet+port+ships | wide 87x36 | 0.0543 | 0.1297 | 40 | 1 | True |
| fixed_fov_perspective | planet+port+ships | large 120x44 | 0.0198 | 0.2414 | 64 | 36 | True |
| depth_layered_anchor | planet+port+ships | large 120x44 | 0.0488 | 0.1278 | 40 | 2 | True |
| fixed_fov_perspective | planet+port+ships | huge 150x52 | 0.0185 | 0.2365 | 64 | 43 | True |
| depth_layered_anchor | planet+port+ships | huge 150x52 | 0.0493 | 0.1279 | 40 | 2 | True |
| fixed_fov_perspective | planet+stardock+ships | standard 67x30 | 0.0208 | 0.2534 | 64 | 30 | True |
| depth_layered_anchor | planet+stardock+ships | standard 67x30 | 0.0506 | 0.1307 | 40 | 1 | True |
| fixed_fov_perspective | planet+stardock+ships | wide 87x36 | 0.024 | 0.2355 | 64 | 33 | True |
| depth_layered_anchor | planet+stardock+ships | wide 87x36 | 0.0491 | 0.128 | 40 | 1 | True |
| fixed_fov_perspective | planet+stardock+ships | large 120x44 | 0.0205 | 0.334 | 64 | 36 | True |
| depth_layered_anchor | planet+stardock+ships | large 120x44 | 0.1662 | 0.2913 | 40 | 2 | True |
| fixed_fov_perspective | planet+stardock+ships | huge 150x52 | 0.0212 | 0.2531 | 64 | 43 | True |
| depth_layered_anchor | planet+stardock+ships | huge 150x52 | 0.0492 | 0.1414 | 40 | 2 | True |
| fixed_fov_perspective | planet+starbase+ships | standard 67x30 | 0.0219 | 0.2433 | 64 | 30 | True |
| depth_layered_anchor | planet+starbase+ships | standard 67x30 | 0.0511 | 0.1273 | 40 | 1 | True |
| fixed_fov_perspective | planet+starbase+ships | wide 87x36 | 0.0189 | 0.2361 | 64 | 33 | True |
| depth_layered_anchor | planet+starbase+ships | wide 87x36 | 0.0487 | 0.128 | 40 | 1 | True |
| fixed_fov_perspective | planet+starbase+ships | large 120x44 | 0.0179 | 0.2635 | 64 | 36 | True |
| depth_layered_anchor | planet+starbase+ships | large 120x44 | 0.0635 | 0.1292 | 40 | 2 | True |
| fixed_fov_perspective | planet+starbase+ships | huge 150x52 | 0.0198 | 0.2431 | 64 | 43 | True |
| depth_layered_anchor | planet+starbase+ships | huge 150x52 | 0.0535 | 0.1286 | 40 | 2 | True |
| fixed_fov_perspective | wormhole+port+ships | standard 67x30 | 0.0287 | 0.2385 | 64 | 49 | True |
| depth_layered_anchor | wormhole+port+ships | standard 67x30 | 0.0492 | 0.1281 | 40 | 4 | True |
| fixed_fov_perspective | wormhole+port+ships | wide 87x36 | 0.0184 | 0.2518 | 64 | 46 | True |
| depth_layered_anchor | wormhole+port+ships | wide 87x36 | 0.0503 | 0.1292 | 40 | 4 | True |
| fixed_fov_perspective | wormhole+port+ships | large 120x44 | 0.0193 | 0.2406 | 64 | 52 | True |
| depth_layered_anchor | wormhole+port+ships | large 120x44 | 0.0495 | 0.1283 | 40 | 6 | True |
| fixed_fov_perspective | wormhole+port+ships | huge 150x52 | 0.0182 | 0.2365 | 64 | 54 | True |
| depth_layered_anchor | wormhole+port+ships | huge 150x52 | 0.0488 | 0.1283 | 40 | 6 | True |
| fixed_fov_perspective | blackhole+port+ships | standard 67x30 | 0.0262 | 0.2586 | 64 | 49 | True |
| depth_layered_anchor | blackhole+port+ships | standard 67x30 | 0.0508 | 0.1302 | 40 | 4 | True |
| fixed_fov_perspective | blackhole+port+ships | wide 87x36 | 0.0408 | 0.251 | 64 | 46 | True |
| depth_layered_anchor | blackhole+port+ships | wide 87x36 | 0.0495 | 0.1291 | 40 | 4 | True |
| fixed_fov_perspective | blackhole+port+ships | large 120x44 | 0.0203 | 0.2429 | 64 | 52 | True |
| depth_layered_anchor | blackhole+port+ships | large 120x44 | 0.0513 | 0.146 | 40 | 6 | True |
| fixed_fov_perspective | blackhole+port+ships | huge 150x52 | 0.0205 | 0.2495 | 64 | 54 | True |
| depth_layered_anchor | blackhole+port+ships | huge 150x52 | 0.0512 | 0.1377 | 40 | 6 | True |
| fixed_fov_perspective | nebula+port+ships | standard 67x30 | 0.0282 | 0.2458 | 64 | 49 | True |
| depth_layered_anchor | nebula+port+ships | standard 67x30 | 0.0509 | 0.132 | 40 | 4 | True |
| fixed_fov_perspective | nebula+port+ships | wide 87x36 | 0.0218 | 0.2453 | 64 | 46 | True |
| depth_layered_anchor | nebula+port+ships | wide 87x36 | 0.0519 | 0.1378 | 40 | 4 | True |
| fixed_fov_perspective | nebula+port+ships | large 120x44 | 0.0205 | 0.2433 | 64 | 52 | True |
| depth_layered_anchor | nebula+port+ships | large 120x44 | 0.0509 | 0.132 | 40 | 6 | True |
| fixed_fov_perspective | nebula+port+ships | huge 150x52 | 0.0185 | 0.2585 | 64 | 54 | True |
| depth_layered_anchor | nebula+port+ships | huge 150x52 | 0.0539 | 0.1341 | 40 | 6 | True |
| fixed_fov_perspective | wreck+ships | standard 67x30 | 0.0308 | 0.2519 | 64 | 64 | True |
| depth_layered_anchor | wreck+ships | standard 67x30 | 0.0578 | 0.1343 | 40 | 15 | True |
| fixed_fov_perspective | wreck+ships | wide 87x36 | 0.0268 | 0.2632 | 64 | 59 | True |
| depth_layered_anchor | wreck+ships | wide 87x36 | 0.0691 | 0.1356 | 40 | 15 | True |
| fixed_fov_perspective | wreck+ships | large 120x44 | 0.0277 | 0.2554 | 64 | 59 | True |
| depth_layered_anchor | wreck+ships | large 120x44 | 0.0584 | 0.1342 | 40 | 16 | True |
| fixed_fov_perspective | wreck+ships | huge 150x52 | 0.0265 | 0.2513 | 64 | 64 | True |
| depth_layered_anchor | wreck+ships | huge 150x52 | 0.0577 | 0.1481 | 40 | 16 | True |
| fixed_fov_perspective | wormhole+starbase+ships | standard 67x30 | 0.0229 | 0.2512 | 64 | 49 | True |
| depth_layered_anchor | wormhole+starbase+ships | standard 67x30 | 0.0514 | 0.1321 | 40 | 4 | True |
| fixed_fov_perspective | wormhole+starbase+ships | wide 87x36 | 0.0192 | 0.2441 | 64 | 46 | True |
| depth_layered_anchor | wormhole+starbase+ships | wide 87x36 | 0.0508 | 0.132 | 40 | 4 | True |
| fixed_fov_perspective | wormhole+starbase+ships | large 120x44 | 0.0202 | 0.2473 | 64 | 52 | True |
| depth_layered_anchor | wormhole+starbase+ships | large 120x44 | 0.0512 | 0.1368 | 40 | 6 | True |
| fixed_fov_perspective | wormhole+starbase+ships | huge 150x52 | 0.0201 | 0.2433 | 64 | 54 | True |
| depth_layered_anchor | wormhole+starbase+ships | huge 150x52 | 0.0507 | 0.132 | 40 | 6 | True |
| fixed_fov_perspective | belt+port+ships | standard 67x30 | 0.0275 | 0.2645 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | standard 67x30 | 0.0512 | 0.1333 | 40 | 19 | True |
| fixed_fov_perspective | belt+port+ships | wide 87x36 | 0.0207 | 0.2461 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | wide 87x36 | 0.0497 | 0.1316 | 40 | 19 | True |
| fixed_fov_perspective | belt+port+ships | large 120x44 | 0.0189 | 0.2583 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | large 120x44 | 0.0491 | 0.1461 | 40 | 19 | True |
| fixed_fov_perspective | belt+port+ships | huge 150x52 | 0.0194 | 0.2486 | 64 | 64 | True |
| depth_layered_anchor | belt+port+ships | huge 150x52 | 0.0546 | 0.1322 | 40 | 19 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | standard 67x30 | 0.0233 | 0.2455 | 64 | 30 | True |
| depth_layered_anchor | planet+port+wreck+traffic | standard 67x30 | 0.0504 | 0.1325 | 40 | 1 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | wide 87x36 | 0.0202 | 0.2487 | 64 | 33 | True |
| depth_layered_anchor | planet+port+wreck+traffic | wide 87x36 | 0.052 | 0.1376 | 40 | 1 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | large 120x44 | 0.0205 | 0.244 | 64 | 36 | True |
| depth_layered_anchor | planet+port+wreck+traffic | large 120x44 | 0.0504 | 0.1324 | 40 | 2 | True |
| fixed_fov_perspective | planet+port+wreck+traffic | huge 150x52 | 0.0185 | 0.259 | 64 | 43 | True |
| depth_layered_anchor | planet+port+wreck+traffic | huge 150x52 | 0.0511 | 0.133 | 40 | 2 | True |
| fixed_fov_perspective | derelict-base+ships | standard 67x30 | 0.0309 | 0.246 | 64 | 44 | True |
| depth_layered_anchor | derelict-base+ships | standard 67x30 | 0.0593 | 0.1322 | 40 | 11 | True |
| fixed_fov_perspective | derelict-base+ships | wide 87x36 | 0.0271 | 0.3251 | 64 | 44 | True |
| depth_layered_anchor | derelict-base+ships | wide 87x36 | 0.0605 | 0.138 | 40 | 11 | True |
| fixed_fov_perspective | derelict-base+ships | large 120x44 | 0.0286 | 0.2466 | 64 | 49 | True |
| depth_layered_anchor | derelict-base+ships | large 120x44 | 0.0592 | 0.1319 | 40 | 10 | True |
| fixed_fov_perspective | derelict-base+ships | huge 150x52 | 0.027 | 0.2625 | 64 | 58 | True |
| depth_layered_anchor | derelict-base+ships | huge 150x52 | 0.0724 | 0.1335 | 40 | 10 | True |

### Fields not measurable before WP-SC06/SC07

- admitted/rejected/painted counts: n/a (pending WP-SC06 solver)
- solve-pass/occlusion/reanchor counters: n/a (pending WP-SC06 solver)
- sprite-cache hit rate: n/a (pending WP-SC07 art resolution)
- ScenePlan cache: n/a (no ScenePlan cache exists before WP-SC06/SC08)
- decision-prose gating: n/a (no Decision trace producer before WP-SC06) / n/a (no Decision trace producer before WP-SC06)
