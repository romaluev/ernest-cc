# Read this first (you are an agent setting Ernest up)

Someone dropped you a link to this repo and asked you to install it. This file
is the whole brief: what it is, how to set it up end to end, what to decide
yourself, and what to never do.

**Do not improvise a setup.** Run `scripts/bootstrap.sh` and follow what it
reports. It is idempotent — safe to re-run at any point.

## What this is

Ernest is a **draft-first CEO operations assistant** that runs on this machine.
It reads exported data and connected apps, tells the principal what needs them,
and prepares drafts **only when asked**. It never sends, posts, accepts,
ignores, or deletes anything on its own.

Three parts:

| Part | What it is | Where |
|---|---|---|
| Engine | stdlib-only Python. No model, no network needed. | `ernest/` |
| Skills | what *you* read to do a job well | `skills/` |
| Adapters | connectors for systems with no API, run outside the safety gate | `adapters/` |

Two facts that explain most of the design:

1. **This repo ships a fictional sample world.** "Northwind", "NovaLabs", and the
   sample people in `data/` are placeholders. Real identity never lives here — it
   is seeded into the *profile* (`~/.ernest-cc`), which updates never overwrite.
   If you see "Northwind" after setup, onboarding has not run.
2. **A safety gate blocks external effects by default** (`ernest/gate.py`).
   Mutating verbs on any connector are denied, web tools are off in local mode,
   and shell network egress is blocked. **Never weaken the gate, the hooks,
   `ernest.yaml`, or the tests to make an error go away.** `scope.protect` blocks
   you anyway, and doing so is the one unrecoverable mistake here.

## Setup, in one command

```bash
./scripts/bootstrap.sh                          # install + schedule + verify
./scripts/bootstrap.sh --seed <path/to/seed>    # …and install real identity
```

It runs, in order: prereqs → install → **adopt any earlier install** →
onboard/seed → daily schedule → connector check → first data pull → first brief
→ `ernest doctor`. Each step is verified before the next begins, and it prints
exactly what is still missing.

Exit `0` means ready. Exit `1` means ready with gaps — the gaps are printed and
each one names its fix. Exit `10` is unrecoverable: **stop and report it. Do not
hand-patch around a failed step.**

## If they already tried installing this before

Very likely. A previous attempt leaves a profile holding their memory, tuned
rubrics, custom skills, connector wiring, and — easiest to lose — their
**learning history** (overrides, applied proposals, feedback). That history is
what makes grading improve; losing it silently resets the system to day one
while looking like a clean install.

`bootstrap.sh` adopts it automatically. To inspect or steer it:

```bash
python3 scripts/migrate.py --discover        # what installs exist on this machine
python3 scripts/migrate.py --dry-run         # what would be adopted
./scripts/bootstrap.sh --migrate-from <dir>  # adopt a specific one
./scripts/bootstrap.sh --no-migrate          # adopt nothing
```

Rules it follows, so you can trust it unattended: it backs up first; it is
additive and never deletes from either side; **shipped sample content never
outranks real user content** (a fresh install writes the sample world with a new
timestamp, so newest-wins alone would destroy their real identity); a file they
edited in the live profile is preserved; append-only history is unioned and
deduped; secrets are copied only into an empty slot and never merged; and it is
idempotent, so re-running is free.

A git clone of this repo is **not** a profile and is never adopted from — it
ships the sample world.

## What to decide yourself vs. ask

Decide yourself (do not make the principal choose):

- Local-only mode. It is the default and the right answer unless they already
  have a server.
- Installing the daily schedule (8:00 brief, 7:30 validated auto-update, 7:45
  read-only connector refresh). All are read-only and removable with
  `ernest schedule --remove`.
- Which ingest rung to use. The ladder picks; you report which one answered.

Ask, once, in plain words — never show flags or file paths:

- Their **name and company**, if there is no seed directory.
- Their **ideal customer**, in one sentence.
- Any **hard red lines**.
- Whether to connect live apps (Gmail/HubSpot/Slack) now or stay on exports.

If a seed directory was provided, ask nothing — it already has all of that.

## Verification gates

Setup is not done until all four pass. Report the real state; do not round up.

```bash
ernest doctor                    # expect 0 broken
ernest start                     # expect a brief, and NO "SAMPLE data" warning
python3 adapters/linkedin/ingest.py --doctor   # expect rungs_reachable non-empty
ernest schedule                  # expect three jobs installed
```

If `ernest start` still says SAMPLE data, onboarding did not take — re-run
bootstrap with `--seed`, or run `ernest onboard`.

## Rules

- **Report only, then act on approval.** Anything outbound or irreversible is a
  proposal until the principal approves a batch that names every subject.
- **Never fabricate a population.** If a data source cannot be reached, say so
  and print the remedy. "We did not look" and "we looked and found nothing" are
  different answers; never collapse them.
- **Provenance always rides through.** Every report says which source produced
  it. A stale snapshot must never be presented as live.
- **Missing is not zero.** A field a source cannot see stays blank. Scoring a
  blank as `0` turns "could not check" into evidence.
- **No third-party dependencies.** Python standard library only — no pip, no
  npm, no vendor SDK. Patterns are borrowed from other tools; code is not.
- **Answer short.** Bottom line first, then what needs them, then a link to the
  full digest. Never paste long tables into chat.

## Where to look next

| You need | Read |
|---|---|
| The persona and hard rules | `CLAUDE.md` |
| What jobs exist and which skill owns each | `skills/ernest-library-index/SKILL.md` |
| Conversational first-run setup | `skills/getting-started/SKILL.md` |
| Something is broken | `skills/ernest-self-repair/SKILL.md`, then `ernest doctor` |
| Connecting real apps | `docs/connectors.md` |
| A system with no API (e.g. LinkedIn) | `docs/ingest-ladder.md` |
| Copy-paste prompts | `docs/examples.md` |
