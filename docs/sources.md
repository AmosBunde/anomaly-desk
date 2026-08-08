# Event sources

Every source Anomaly Desk triages is pinned here: where it came from, under what license, at which snapshot, and
whether its committed demo slice may be redistributed. `configs/sources.yaml` is the machine-readable copy that
`scripts/fetch_sources.py` reads and the tests assert against, so the two cannot drift.

Why this exists before any labeling. A10 labels 100 or more of these events and the judge scores every later
variant against those labels. If a source changes underneath, every comparison made against it becomes
meaningless, and the change would be invisible without a recorded hash. `make data` verifies each snapshot and
fails loudly rather than accepting a silent substitution.

## Selection

Three sources from the loghub collection, chosen for failure-mode diversity rather than volume. The triage
system has to classify severity and category, so a corpus of one failure type would produce a labeled set that
cannot distinguish a working classifier from a constant one.

| Source | Domain | Failure modes it supplies |
| --- | --- | --- |
| `loghub-hdfs` | Hadoop Distributed File System | Capacity and dependency: block replication, datanode loss, namenode pressure |
| `loghub-openstack` | OpenStack Nova compute | Configuration and dependency: instance lifecycle, API errors, quota and scheduling |
| `loghub-bgl` | Blue Gene/L supercomputer | Hardware: memory, cache, interconnect, and card failures |

`loghub-bgl` carries an upstream alert or non-alert flag. It is a useful sanity check while labeling and is
never used as a gold label, for the same reason `severity_hint` in the event envelope is never trusted: a label
derived from the source is not an independent measurement of the system that reads the source.

## Provenance

| Field | `loghub-hdfs` | `loghub-openstack` | `loghub-bgl` |
| --- | --- | --- | --- |
| Origin | `logpai/loghub` `HDFS/HDFS_2k.log` | `logpai/loghub` `OpenStack/OpenStack_2k.log` | `logpai/loghub` `BGL/BGL_2k.log` |
| Upstream | github.com/logpai/loghub | github.com/logpai/loghub | github.com/logpai/loghub |
| License | loghub dataset license | loghub dataset license | loghub dataset license |
| Redistributable | Yes, with conditions | Yes, with conditions | Yes, with conditions |
| Retrieved | 2026-08-08 | 2026-08-08 | 2026-08-08 |
| Records | 2000 | 2000 | 2000 |
| Snapshot sha256 | `7c967000980c086e...bbb635035` | `025a1bc64ff5b2ef...625629f2f` | `2a819ea540909db6...704825496` |
| Redactions | None | None | None |
| Demo slice | First 120 records | First 120 records | First 120 records |

Full hashes are in `configs/sources.yaml`. They are quoted there deliberately: an unquoted all-digit hash is
parsed by YAML as an integer and would then never compare equal to the hex digest computed at runtime, which
would make the verification silently always fail. That was found by testing the mismatch path rather than by
reading the file.

## License and the conditions on redistribution

The loghub datasets are freely available for research or academic work. Redistribution is permitted subject to
three conditions, all of which this repository meets:

1. **Attribution to the upstream repository.** Recorded per source in `configs/sources.yaml` and in the table
   above.
2. **Citation of the loghub paper.** Reproduced below and written into `data/demo/LICENSE` beside the
   redistributed slice.
3. **The license notice included in all copies.** `scripts/fetch_sources.py` writes `data/demo/LICENSE`
   whenever it cuts the slice, and a test asserts that file exists, so the slice cannot be committed without it.

> Jieming Zhu, Shilin He, Pinjia He, Jinyang Liu, Michael R. Lyu. Loghub: A Large Collection of System Log
> Datasets for AI-driven Log Analytics. In ISSRE, 2023.

License text: <https://github.com/logpai/loghub/blob/master/LICENSE>

All three sources are redistributable, so no source here is restricted to local use. Had one been, it would be
recorded as `redistributable: false` and nothing from it would be committed; `make data` would still fetch it
into gitignored `data/raw/` for local runs. The distinction is enforced by a test rather than by remembering.

Upstream states the logs are not sanitized, anonymized, or otherwise modified. These are production and lab
logs from other people's systems, which is the point: they are messy in ways a synthetic corpus is not. It also
means host names, paths, and identifiers in them are real, and no redaction has been applied because none is
required by the license and inventing one would change the data the labels were written against.

## What is committed and what is not

| Path | Tracked | Contents |
| --- | --- | --- |
| `configs/sources.yaml` | Yes | The pins: origin, license, hash, record count |
| `docs/sources.md` | Yes | This document |
| `data/demo/*.log` | Yes | 120 records per source, 360 total |
| `data/demo/LICENSE` | Yes | The upstream notice and citation |
| `data/raw/*.log` | No | Full 2000-record snapshots, fetched by `make data` |
| `data/normalized/` | No | Envelope output, produced by A9 |

The demo slice is committed so that `docker compose up --build` followed by `make eval` works from a clean
checkout with no fetch, which the definition of done requires.

## Running it

```
make data             # fetch, verify hashes, cut the demo slice; safe to run twice
make verify-sources   # verify cached snapshots without fetching
```

A hash mismatch is a hard failure naming both digests and stating why it matters. A fetch failure exits with a
distinct code and says that substituting a mirror changes provenance and is therefore an owner decision rather
than something to fix silently.
