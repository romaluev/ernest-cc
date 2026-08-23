# The ingest ladder

The house pattern for getting data out of a system that has no MCP, no API key,
and no intention of being automated. Built for LinkedIn; meant for every
connector after it.

The rule it exists to enforce: **a report must always be able to say where its
data came from, and must never invent a population.**

## Shape

```
rung 1  cache        already have it, still fresh          -> use it
rung 2  official     the vendor's own data export          -> request + unpack
rung 3  live         the authenticated UI                  -> read (and maybe act)
rung 4  mirror       whatever our CRM already knows         -> partial, labelled
rung 5  unavailable  nothing worked                        -> say so, write nothing
```

Every rung is optional. A rung that fails is recorded in `attempts` and the
ladder falls through — one broken rung never ends the run. Rung 5 is not an
error path, it is a **result**: "we did not look" and "we looked and found
nothing" are different answers and the ladder never collapses them.

## Non-negotiables

1. **Provenance rides through.** The rung that produced the data becomes
   `source:` on the report and `meta.source` in the JSON envelope. A month-old
   snapshot, a live read, and a partial CRM mirror must never look alike.
2. **Missing is not zero.** A field a rung cannot see stays blank. Scoring blank
   as `0` turns "we could not check" into evidence, and that is how a system
   accuses people of things.
3. **Partial sources are labelled partial.** A CRM mirror knows only the records
   that already reached the CRM. Its count is never the size of the queue.
4. **No fabrication at rung 5.** No file is written, no stale file is touched, no
   count is guessed. The remedy is printed instead.
5. **Ordering is cheapest-and-safest first.** Cache before network, official
   export before scraping, read before write.
6. **The adapter runs outside the gate.** `ernest/gate.py` blocks shell egress
   and web tools in local mode by design. Ladders are driven by cron/launchd or
   by hand; the engine only ever reads the files they write.

## CLI contract

Every adapter exposes the same surface so a scheduled job can drive any of them:

| Flag | Behavior |
|---|---|
| `--doctor` | which rungs are reachable right now, and why not |
| `--agent` | implies `--json --compact`, never prompts |
| `--deliver` | `stdout` \| `file:<path>` (atomic) \| `webhook:<url>` |
| `--profile <name>` | a saved flag set; explicit flags always win |
| `--dry-run` | show what would happen, change nothing |
| `--feedback "<note>"` | one line about what surprised you |
| `--rung N` | force one rung, for debugging |

Envelope:

```json
{"meta": {"source": "linkedin-archive", "rung": 2, "synced_at": "...", "reason": ""},
 "results": {...}}
```

Exit codes: `0` ok · `2` usage · `3` nothing to work on · `4` unreachable ·
`5` upstream · `6` refused by policy · `7` rate limited · `10` config.

## Acting

Reading and acting are separate commands, always.

- **Plan** produces a batch that names every subject by a stable identity key.
  Acting on a *category* ("all the spam") must survive being wrong about one
  member, so the approval names them.
- **Caps** come from config and are counted from the **audit log**, so a run that
  crashed halfway still consumed what it used.
- **Reversibility sets the ceiling.** Reversible actions may earn autonomy.
  Irreversible ones — anything affecting someone else's account, money, legal, or
  a public surface — never graduate past explicit per-run approval.
- **Pacing is a safety property.** Sudden mass action is what gets accounts
  restricted; steady action does not.

## Self-healing

The live rung talks to a UI that changes without notice. Each adapter keeps a
`references/dom-notes.md`: the selectors, the traps, and what to do instead.
When a run discovers something new, it gets appended. That file is the memory the
adapter has in place of a test against a live site.

Structure each entry as: what breaks → how to detect it → what to do instead.
Mark anything you cannot reproduce as `unverified` rather than deleting it.

## Self-improving

Proposals go to `logs/<connector>-decisions.jsonl`; overrides go there too. At
this volume there is no eval set, but every proposal is kept or overridden, so
**override rate is an outcome measure with N = every decision**.

Three independent signals of the same shape become a reviewable diff with its
reverse, adopted via `ernest learn --apply` and undone with `--rollback`. Nothing
edits a rubric silently — `sync.yaml` pins `max_auto_changes_per_run: 0`.

For that loop to have anything to turn, **thresholds must live in the rubric
JSON, not in code**. A constant is not a knob.

## Adding a connector

1. `adapters/<name>/` with `ingest.py`, `browser.py` (if the live rung needs
   one), `references/dom-notes.md`, `README.md`.
2. Reuse `adapters/linkedin/cli_common.py` — envelope, deliver, profiles,
   feedback, exit codes.
3. A loader in `ernest/sources.py` that reads `data/<name>/` and carries
   `source` from `.ingest.json`.
4. Doctor checks: `data.<name>` (freshness + which rung) and `<name>.ingest`
   (which rungs are reachable).
5. A scheduled refresh in `ernest schedule` and `cron/crontab.example`.
6. Tests that assert the ladder fabricates nothing, blanks stay blank, and the
   documented exit codes are the real ones.
