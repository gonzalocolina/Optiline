# Validated datagen corpus

Self-play bulletformat from the Release datagen binary. No GPU and no Bullet training.
Each game clears search state and is seeded by the game index, and records are written in that order, so the same command reproduces the file.
The test file is a holdout of whole game ids, not a sample of positions from the training games.

## Measured run

- Games requested: 1200. Games written: 1187.
- Positions: 103554. Bytes: 3313728.
- Nodes per move: 5000. Threads: 4. Hash: 16 MB. Seed: 20261020.
- Teacher: `nets/nnue_search_leaves40k_rw0.bin` sha256 `06e342b8ddf128ce7c8b5b9c9c2ce4b45f555871d1dab7e853a6b09bc6bd1b54`. UseExtras left at the datagen default (on).
- Wall time: 65.010 s. Throughput: 1592.90 positions/s, 18.259 games/s.
- Positions per game: 87.24 (min 5, max 362).
- Build: Release -DNSCE_LTO=OFF -DNSCE_NATIVE=ON -DNSCE_AVX2=ON.

## Cost of the confirmatory corpus

These hours use the measured rate on this machine. They are not a 14-thread estimate.

- 100,000,000 positions: 17.44 h (627.8 s per million positions).
- 1,200,000 games, the README datagen command: 18.26 h.

## Thread scaling check

- 1 thread(s): 336.53 positions/s over 20.004 s.
- Same 100,000,000 positions at that rate: 82.54 h.

## Independent split

- Train: 1128 games, 98477 positions. sha256 `167db82f99671fe129e72e76b80cdc00a9e5e2c2e1b852536156d9b33bca468b`.
- Test: 59 games, 5077 positions. sha256 `3a386627b0215be2763e880b6284a5754aca1ca6e2ae6071f03fff07c0dee669`.
- Source sha256 `a38ad2307b49578ac088a584046a80d5f5c87c97fba16b4896837cb127c2c6f3`.
- Game relation: disjoint. Every source game is in exactly one side.

Training should point `NSCE_DATASET` at the train file and `NSCE_TEST_SET` at the test file, with `NSCE_REQUIRE_TEST=1`.
This corpus is below the 100,000,000-position training gate. It is the format and cost check, not a substitute for that corpus.
