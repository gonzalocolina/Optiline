# Validated datagen corpus

Self-play bulletformat from the Release datagen binary. No GPU and no Bullet training.
Each game clears search state and is seeded by the game index, and records are written in that order, so the same command reproduces the file.
The test file is a holdout of whole game ids, not a sample of positions from the training games.

## Measured run

- Games requested: 1250000. Games written: 1239905.
- Positions: 107891804. Bytes: 3452537728.
- Nodes per move: 5000. Threads: 4. Hash: 16 MB. Seed: 20261020.
- Teacher: `nets/nnue_search_leaves40k_rw0.bin` sha256 `06e342b8ddf128ce7c8b5b9c9c2ce4b45f555871d1dab7e853a6b09bc6bd1b54`. UseExtras left at the datagen default (on).
- Wall time: 67165.022 s. Throughput: 1606.37 positions/s, 18.461 games/s.
- Positions per game: 87.02 (min 1, max 393).
- Build: Release -DNSCE_LTO=OFF -DNSCE_NATIVE=ON -DNSCE_AVX2=ON.

## Cost of the confirmatory corpus

These hours use the measured rate on this machine. They are not a 14-thread estimate.

- 100,000,000 positions: 17.29 h (622.5 s per million positions).
- 1,200,000 games, the README datagen command: 18.06 h.

## Independent split

- Train: 1177910 games, 102519658 positions. sha256 `ce5cbacc0e6be3eced544850764ddb9c1445afe35376caa9ae4d4990d53d5633`.
- Test: 61995 games, 5372146 positions. sha256 `1ffeecc9b805dfbfde580e0844681e28394e3991649ea37c0e83d404031ab31a`.
- Source sha256 `29e6750578b75ed60a4d9cbe54ba33035161a9e4fd4f41cdac6681103cd1999a`.
- Game relation: disjoint. Every source game is in exactly one side.

Training should point `NSCE_DATASET` at the train file and `NSCE_TEST_SET` at the test file, with `NSCE_REQUIRE_TEST=1`.
The training partition has 102519658 positions, above the 100000000 gate.
