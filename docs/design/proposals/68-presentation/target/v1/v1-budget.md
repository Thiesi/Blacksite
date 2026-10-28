Host: Linux x86_64, Python 3.12.15, 4 CPUs

Picture time per step (the lit renderer's share; p95 / max). Cold: first visit. Warm: the route again. Full: a whole new screen: the scene view cuts to another place's camera, danger hands the screen to the map, or the server sends a whole view (at 80x24 when the viewport scrolls; the door then redraws everything, in every view).

| Case | Steps | Step cold | Step warm | Stop cold | Stop warm | Full cold | Full warm |
|---|---|---|---|---|---|---|---|
| street, modern, truecolor, 132x50 | 25 | 44.6 ms / 59.5 ms | 1.8 ms / 2.3 ms | 230.4 ms / 230.4 ms | 0.6 ms / 0.6 ms | - / - | - / - |
| scene, modern, truecolor, 132x50 | 72 | 3.5 ms / 9.0 ms | 3.4 ms / 8.6 ms | 4.8 ms / 4.8 ms | 4.8 ms / 4.8 ms | 100.6 ms / 100.6 ms | 5.2 ms / 5.2 ms |
| street, cp437, 256, 132x50 | 25 | 91.1 ms / 97.7 ms | 1.7 ms / 2.1 ms | 85.6 ms / 85.6 ms | 0.5 ms / 0.5 ms | - / - | - / - |
| scene, cp437, 256, 132x50 | 72 | 2.2 ms / 4.2 ms | 1.6 ms / 3.3 ms | 1.8 ms / 1.8 ms | 1.8 ms / 1.8 ms | 81.2 ms / 81.2 ms | 2.1 ms / 2.1 ms |
| street, cp437, 16, 132x50 | 25 | 67.5 ms / 83.1 ms | 2.0 ms / 2.5 ms | 0.6 ms / 0.6 ms | 0.5 ms / 0.5 ms | - / - | - / - |
| scene, cp437, 16, 132x50 | 72 | 1.6 ms / 3.4 ms | 1.6 ms / 3.4 ms | 1.8 ms / 1.8 ms | 1.8 ms / 1.8 ms | 34.4 ms / 34.4 ms | 2.1 ms / 2.1 ms |
| street, modern, truecolor, 80x24 | 25 | 12.4 ms / 13.2 ms | 1.1 ms / 1.1 ms | 50.8 ms / 50.8 ms | 0.5 ms / 0.5 ms | - / - | - / - |
| scene, modern, truecolor, 80x24 | 66 | 1.2 ms / 2.3 ms | 1.3 ms / 2.2 ms | 1.5 ms / 1.5 ms | 1.5 ms / 1.5 ms | 24.3 ms / 25.4 ms | 1.3 ms / 1.7 ms |
| street, cp437, 256, 80x24 | 25 | 25.7 ms / 28.1 ms | 1.0 ms / 1.1 ms | 24.6 ms / 24.6 ms | 0.5 ms / 0.5 ms | - / - | - / - |
| scene, cp437, 256, 80x24 | 66 | 0.9 ms / 1.1 ms | 0.9 ms / 1.1 ms | 0.9 ms / 0.9 ms | 0.8 ms / 0.8 ms | 17.3 ms / 23.4 ms | 0.9 ms / 1.0 ms |
| street, cp437, 16, 80x24 | 25 | 21.6 ms / 21.9 ms | 1.2 ms / 1.3 ms | 0.6 ms / 0.6 ms | 0.5 ms / 0.5 ms | - / - | - / - |
| scene, cp437, 16, 80x24 | 66 | 0.8 ms / 1.2 ms | 0.9 ms / 1.2 ms | 0.8 ms / 0.8 ms | 0.8 ms / 0.8 ms | 9.8 ms / 10.3 ms | 0.8 ms / 1.0 ms |

Bytes (p95 / max) against 16 KiB per delta, and the cache:

| Case | Step | Stop | Full | Cache peak (cap) |
|---|---|---|---|---|
| street, modern, truecolor, 132x50 | 51.9 KiB / 52.2 KiB | 105.3 KiB / 105.3 KiB | - / - | 2.9 MiB (24 MiB) |
| scene, modern, truecolor, 132x50 | 4.7 KiB / 7.8 KiB | 0.0 KiB / 0.0 KiB | 57.8 KiB / 57.8 KiB | 0.5 MiB (24 MiB) |
| street, cp437, 256, 132x50 | 30.6 KiB / 31.5 KiB | 24.1 KiB / 24.1 KiB | - / - | 2.6 MiB (24 MiB) |
| scene, cp437, 256, 132x50 | 2.7 KiB / 3.8 KiB | 0.0 KiB / 0.0 KiB | 22.6 KiB / 22.6 KiB | 0.3 MiB (24 MiB) |
| street, cp437, 16, 132x50 | 15.6 KiB / 16.0 KiB | 0.0 KiB / 0.0 KiB | - / - | 3.0 MiB (24 MiB) |
| scene, cp437, 16, 132x50 | 1.7 KiB / 2.0 KiB | 0.0 KiB / 0.0 KiB | 10.8 KiB / 10.8 KiB | 0.3 MiB (24 MiB) |
| street, modern, truecolor, 80x24 | 14.9 KiB / 15.2 KiB | 27.3 KiB / 27.3 KiB | - / - | 0.7 MiB (24 MiB) |
| scene, modern, truecolor, 80x24 | 1.9 KiB / 2.4 KiB | 0.0 KiB / 0.0 KiB | 19.4 KiB / 19.9 KiB | 0.1 MiB (24 MiB) |
| street, cp437, 256, 80x24 | 9.8 KiB / 10.1 KiB | 9.4 KiB / 9.4 KiB | - / - | 0.6 MiB (24 MiB) |
| scene, cp437, 256, 80x24 | 1.2 KiB / 1.5 KiB | 0.0 KiB / 0.0 KiB | 12.5 KiB / 12.7 KiB | 0.1 MiB (24 MiB) |
| street, cp437, 16, 80x24 | 4.6 KiB / 4.7 KiB | 0.0 KiB / 0.0 KiB | - / - | 0.7 MiB (24 MiB) |
| scene, cp437, 16, 80x24 | 0.7 KiB / 0.9 KiB | 0.0 KiB / 0.0 KiB | 6.4 KiB / 6.4 KiB | 0.1 MiB (24 MiB) |

How long a key can wait for the door while four sharp pictures are painted (the loop held between turns):

| Case | Painting | Key wait p95 | Key wait max | Busy | Turns |
|---|---|---|---|---|---|
| modern, truecolor, 132x50 | idle | 0.0 ms | 0.1 ms | 300 ms | 93898 |
| modern, truecolor, 132x50 | in slices (V1) | 10.7 ms | 11.5 ms | 84 ms | 17 |
| modern, truecolor, 132x50 | on the spot (V0) | 196.0 ms | 196.0 ms | 322 ms | 5 |
| cp437, 256, 132x50 | idle | 0.0 ms | 0.1 ms | 300 ms | 94716 |
| cp437, 256, 132x50 | in slices (V1) | 9.9 ms | 10.1 ms | 70 ms | 14 |
| cp437, 256, 132x50 | on the spot (V0) | 73.8 ms | 73.8 ms | 204 ms | 5 |
| modern, truecolor, 80x24 | idle | 0.0 ms | 0.0 ms | 300 ms | 94870 |
| modern, truecolor, 80x24 | in slices (V1) | 7.4 ms | 7.4 ms | 27 ms | 7 |
| modern, truecolor, 80x24 | on the spot (V0) | 56.0 ms | 56.0 ms | 114 ms | 5 |
| cp437, 256, 80x24 | idle | 0.0 ms | 0.1 ms | 300 ms | 95688 |
| cp437, 256, 80x24 | in slices (V1) | 7.3 ms | 7.3 ms | 27 ms | 7 |
| cp437, 256, 80x24 | on the spot (V0) | 24.3 ms | 24.3 ms | 64 ms | 5 |

Walking in real time (a step every 200 ms, painting in slices):

| Case | Steps | Picture of where you stood, within the step | Lag p95 | Pictures painted | Of them prepared |
|---|---|---|---|---|---|
| modern, truecolor, 132x50 | 25 | 25 | 94 ms | 70 | 49 |
| cp437, 256, 132x50 | 25 | 25 | 36 ms | 89 | 88 |
| modern, truecolor, 80x24 | 25 | 25 | 7 ms | 89 | 88 |
| cp437, 256, 80x24 | 25 | 25 | 7 ms | 89 | 88 |
