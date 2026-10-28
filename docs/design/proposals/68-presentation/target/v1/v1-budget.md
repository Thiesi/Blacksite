Host: Linux x86_64, Python 3.12.15, 4 CPUs

Picture time per step (the lit renderer's share; p95 / max). Cold: first visit. Warm: the route again. Full: a whole new screen: the scene view cuts to another place's camera, danger hands the screen to the map, or the server sends a whole view (at 80x24 when the viewport scrolls; the door then redraws everything, in every view).

| Case | Steps | Step cold | Step warm | Stop cold | Stop warm | Full cold | Full warm |
|---|---|---|---|---|---|---|---|
| street, modern, truecolor, 132x50 | 25 | 31.1 ms / 31.6 ms | 1.5 ms / 6.2 ms | 147.0 ms / 147.0 ms | 0.4 ms / 0.4 ms | - / - | - / - |
| scene, modern, truecolor, 132x50 | 72 | 2.7 ms / 13.3 ms | 2.6 ms / 16.5 ms | 3.6 ms / 3.6 ms | 3.6 ms / 3.6 ms | 67.5 ms / 67.5 ms | 4.4 ms / 4.4 ms |
| street, cp437, 256, 132x50 | 25 | 66.7 ms / 69.4 ms | 1.4 ms / 1.7 ms | 73.9 ms / 73.9 ms | 0.4 ms / 0.4 ms | - / - | - / - |
| scene, cp437, 256, 132x50 | 72 | 2.0 ms / 15.3 ms | 1.2 ms / 2.5 ms | 1.3 ms / 1.3 ms | 1.4 ms / 1.4 ms | 62.6 ms / 62.6 ms | 1.6 ms / 1.6 ms |
| street, cp437, 16, 132x50 | 25 | 47.9 ms / 57.0 ms | 8.2 ms / 9.4 ms | 0.5 ms / 0.5 ms | 7.7 ms / 7.7 ms | - / - | - / - |
| scene, cp437, 16, 132x50 | 72 | 1.3 ms / 4.1 ms | 1.2 ms / 2.9 ms | 1.4 ms / 1.4 ms | 1.4 ms / 1.4 ms | 37.5 ms / 37.5 ms | 1.6 ms / 1.6 ms |
| street, modern, truecolor, 80x24 | 25 | 9.1 ms / 25.3 ms | 0.7 ms / 0.8 ms | 36.2 ms / 36.2 ms | 0.4 ms / 0.4 ms | - / - | - / - |
| scene, modern, truecolor, 80x24 | 66 | 1.1 ms / 3.5 ms | 1.2 ms / 1.7 ms | 1.1 ms / 1.1 ms | 1.1 ms / 1.1 ms | 17.2 ms / 18.0 ms | 1.0 ms / 1.3 ms |
| street, cp437, 256, 80x24 | 25 | 18.0 ms / 21.7 ms | 0.7 ms / 0.8 ms | 18.4 ms / 18.4 ms | 0.6 ms / 0.6 ms | - / - | - / - |
| scene, cp437, 256, 80x24 | 66 | 0.7 ms / 2.8 ms | 0.7 ms / 0.8 ms | 0.6 ms / 0.6 ms | 0.7 ms / 0.7 ms | 11.7 ms / 17.0 ms | 0.7 ms / 0.7 ms |
| street, cp437, 16, 80x24 | 25 | 14.4 ms / 15.3 ms | 2.3 ms / 2.7 ms | 0.4 ms / 0.4 ms | 2.1 ms / 2.1 ms | - / - | - / - |
| scene, cp437, 16, 80x24 | 66 | 0.7 ms / 1.2 ms | 0.6 ms / 0.9 ms | 0.6 ms / 0.6 ms | 0.6 ms / 0.6 ms | 7.0 ms / 7.5 ms | 0.6 ms / 0.7 ms |

Bytes (p95 / max) against 16 KiB per delta, and the cache:

| Case | Step | Stop | Full | Cache peak (cap) |
|---|---|---|---|---|
| street, modern, truecolor, 132x50 | 31.9 KiB / 32.8 KiB | 105.3 KiB / 105.3 KiB | - / - | 2.3 MiB (24 MiB) |
| scene, modern, truecolor, 132x50 | 7.8 KiB / 51.2 KiB | 0.0 KiB / 0.0 KiB | 57.8 KiB / 57.8 KiB | 0.5 MiB (24 MiB) |
| street, cp437, 256, 132x50 | 17.5 KiB / 17.9 KiB | 39.4 KiB / 39.4 KiB | - / - | 2.6 MiB (24 MiB) |
| scene, cp437, 256, 132x50 | 3.8 KiB / 22.3 KiB | 0.0 KiB / 0.0 KiB | 22.2 KiB / 22.2 KiB | 0.3 MiB (24 MiB) |
| street, cp437, 16, 132x50 | 15.3 KiB / 17.5 KiB | 12.0 KiB / 12.0 KiB | - / - | 2.1 MiB (24 MiB) |
| scene, cp437, 16, 132x50 | 2.0 KiB / 8.0 KiB | 0.0 KiB / 0.0 KiB | 10.8 KiB / 10.8 KiB | 0.3 MiB (24 MiB) |
| street, modern, truecolor, 80x24 | 14.9 KiB / 15.2 KiB | 27.3 KiB / 27.3 KiB | - / - | 0.7 MiB (24 MiB) |
| scene, modern, truecolor, 80x24 | 2.4 KiB / 12.2 KiB | 0.0 KiB / 0.0 KiB | 19.4 KiB / 19.9 KiB | 0.1 MiB (24 MiB) |
| street, cp437, 256, 80x24 | 9.8 KiB / 10.1 KiB | 9.4 KiB / 9.4 KiB | - / - | 0.6 MiB (24 MiB) |
| scene, cp437, 256, 80x24 | 1.5 KiB / 6.7 KiB | 0.0 KiB / 0.0 KiB | 12.5 KiB / 12.7 KiB | 0.1 MiB (24 MiB) |
| street, cp437, 16, 80x24 | 4.7 KiB / 5.0 KiB | 3.6 KiB / 3.6 KiB | - / - | 0.5 MiB (24 MiB) |
| scene, cp437, 16, 80x24 | 0.9 KiB / 2.5 KiB | 0.0 KiB / 0.0 KiB | 6.4 KiB / 6.4 KiB | 0.1 MiB (24 MiB) |

How long a key can wait for the door while four sharp pictures are painted (the loop held between turns):

| Case | Painting | Key wait p95 | Key wait max | Busy | Turns |
|---|---|---|---|---|---|
| modern, truecolor, 132x50 | idle | 0.0 ms | 0.0 ms | 300 ms | 119361 |
| modern, truecolor, 132x50 | in slices (V1) | 9.1 ms | 9.5 ms | 61 ms | 13 |
| modern, truecolor, 132x50 | on the spot (V0) | 143.5 ms | 143.5 ms | 229 ms | 5 |
| cp437, 256, 132x50 | idle | 0.0 ms | 0.0 ms | 300 ms | 120070 |
| cp437, 256, 132x50 | in slices (V1) | 8.5 ms | 8.7 ms | 53 ms | 12 |
| cp437, 256, 132x50 | on the spot (V0) | 55.3 ms | 55.3 ms | 144 ms | 5 |
| modern, truecolor, 80x24 | idle | 0.0 ms | 0.0 ms | 300 ms | 120075 |
| modern, truecolor, 80x24 | in slices (V1) | 6.4 ms | 6.4 ms | 20 ms | 6 |
| modern, truecolor, 80x24 | on the spot (V0) | 40.7 ms | 40.7 ms | 69 ms | 5 |
| cp437, 256, 80x24 | idle | 0.0 ms | 0.0 ms | 300 ms | 121564 |
| cp437, 256, 80x24 | in slices (V1) | 6.5 ms | 6.5 ms | 20 ms | 6 |
| cp437, 256, 80x24 | on the spot (V0) | 17.7 ms | 17.7 ms | 51 ms | 5 |

Walking in real time (a step every 200 ms, painting in slices, the walk's budget 64 KiB/s). Lag: from a step until a picture of it, or of a later step, is up.

| Case | Steps | Shown within the step | Lag p95 | Lag max | Bytes/s walking | Pictures/s | Picture CPU s per walking minute | Painted (prepared) |
|---|---|---|---|---|---|---|---|---|
| modern, truecolor, 132x50 | 25 | 14 | 341 ms | 468 ms | 70.1 KiB/s | 2.7 | 7.8 | 34 (28) |
| cp437, 256, 132x50 | 25 | 25 | 120 ms | 121 ms | 54.8 KiB/s | 4.6 | 8.4 | 34 (28) |
| modern, truecolor, 80x24 | 25 | 25 | 109 ms | 111 ms | 57.8 KiB/s | 4.8 | 2.7 | 34 (28) |
| cp437, 256, 80x24 | 25 | 25 | 108 ms | 109 ms | 34.2 KiB/s | 4.8 | 2.7 | 34 (28) |
