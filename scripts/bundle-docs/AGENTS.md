# Read this first — you are an agent, and this folder is now your job

Someone unzipped `linkedin-inbound-__VERSION__` and pointed you at it. They may
have said nothing else. This file is the whole brief: what it is, how to install
it, how it works internally, and how to repair it when it breaks. You should
never need to ask them a question you can answer by reading or running something.

**Start here:**

```bash
./install.sh
```

That verifies the environment, produces the first report, runs the bundled
tests, and installs a daily schedule. Then read what it printed and act on it.
Everything below is for when that is not enough.

---

## 1. What this is, in one paragraph

Standalone LinkedIn inbound triage for one person. It reads their pending
connection invitations and their DM threads, grades both against a rubric, and
writes one report saying who is worth accepting, who is waiting on a reply, what
the principal promised and never sent, and what is spam. It **reports**.
Accepting, ignoring and archiving happen only through a batch that names every
person in it and that the principal approved.

Python 3.9+, **standard library only**. Never add a dependency — no pip, no npm,
no vendor SDK. The one optional external service (PhantomBuster) is reached over
plain `urllib` and is off unless a key is configured.

## 2. The map

```
linkedin_triage.py            entry point — the only thing anyone has to run
install.sh                    idempotent setup; verifies, never asserts
BUILD.txt                     version + commit. Read it before debugging.

adapters/linkedin/            OUTSIDE the grading engine, on purpose
  ingest.py                   the ladder: cache -> export -> live -> CRM -> none
  browser.py                  Chromium over CDP, hand-rolled WebSocket
  cloud.py                    PhantomBuster rung (optional, off by default)
  act.py                      accept / ignore, capped and audited
  report.py                   markdown -> HTML -> PDF
  drafts.py                   reply briefs
  references/dom-notes.md     the selectors, and every trap already found

ernest/                       the grading engine subset. DO NOT EDIT.
  sources.py                  CSV -> Invitation / Conversation objects
  grading.py                  the decision order and the tiers
  li_insight.py               value, commitments, deadlines, campaigns, diffs
  grade_run.py                orchestration + the two report cards

data/grading/linkedin-rubric.json   the scoring brain. Lists only.
data/linkedin/                      the ingested CSVs live here
memory/                             who the principal is; pins message direction
reports/  .state/  logs/            output and run state
```

## 3. How a run actually flows

```
  linkedin_triage.py
        |
        |-- adapters/linkedin/ingest.py            (a separate process)
        |     rung 1  data/linkedin/*.csv fresh?          -> use it
        |     rung 2  drive the browser: request the           writes
        |             export, wait, download, unpack      -> data/linkedin/
        |     rung 2b cloud.py, if a key is configured:       invitations.csv
        |             archived / spam / InMail threads        messages.csv
        |     rung 3  read the invitation manager live         .ingest.json
        |             (CAPPED at 200 — see §7)
        |     rung 4  a HubSpot export, if one is present
        |     rung 5  nothing. Says so. Invents nothing.
        |
        |-- ernest/sources.py       CSV -> objects, owner detection
        |-- ernest/grading.py       tier + lane + one-line summary per person
        |-- ernest/li_insight.py    value, promises, deadlines, campaigns
        |-- ernest/grade_run.py     -> .state/Ernest/00-Watch/*.md + *.csv
        |
        |-- copies them to ~/Documents/LinkedIn-Inbound/<date>/
        |-- drafts.py    -> reply-briefs.md
        `-- report.py    -> report.html, then report.pdf via headless Chrome
```

Seven files land per run: `invitations.md`, `invitations.csv`, `messages.md`,
`messages.csv`, `reply-briefs.md`, `report.html`, `report.pdf`. If any is
missing, §8 says which stage owns it.

## 4. Where every number on the report comes from

| On the report | Produced by | If it looks wrong |
|---|---|---|
| tier (accept / your call / spam) | `grading.py:grade_linkedin_inbound` | the rubric lists — §6 |
| the one-line summary under a name | `grading.py`, field `summary` | same |
| "2 investors, 1 creator" in the TL;DR | `grade_run.py:_lane_phrase` off `grade.lane` | same |
| "You promised …" | `li_insight.py:commitments` | needs a named subject; vague promises are dropped on purpose |
| "Deadlines they set" | `li_insight.py:deadlines` | resolved against the message date, not today |
| "N of these are one sequence" | `li_insight.py:campaigns`, Jaccard ≥ 0.45 | raise the threshold if genuine messages cluster |
| "Since the last run" | `li_insight.py:diff_runs` vs `.state/` | delete the state file to reset |
| `source:` | whichever rung answered | never edit this by hand |
| "Reading as: X" | `sources.py:last_owner` | if X is not the principal, EVERY direction is inverted — §8 |

## 5. Decide yourself. Do not ask.

Decide without asking: which rung to use (the ladder picks, you report which
answered), the daily schedule, where reports go, running the tests, installing a
browser if none is present, re-running after a transient failure.

Ask only: for approval before the first batch of accepts or ignores, and for the
principal to sign in to LinkedIn once if no rung can reach it — that one cannot
be automated, because it needs their password and second factor.

Never ask them to: export their data by hand, find a zip, paste a cookie, edit a
config file, install Python packages, or "let you know when it's done". Every one
of those is something this bundle does itself.

## 6. Tuning without breaking it

`data/grading/linkedin-rubric.json` is the whole scoring brain. It **replaces**
the code defaults wholesale, so:

- **Edit lists. Never delete a key.** A missing key silently turns that entire
  check off, and nothing will tell you.
- `investor.current_investors` — the principal's own cap table. Names here are
  treated as fact, not inference.
- `tier1.companies` — companies big enough that a decision-maker there is tier-1
  on the logo alone. Every name added promotes everyone who works there; keep it
  short.
- `spam.threshold` — points of independent evidence before something is proposed
  for Ignore. **Raise it** when real people land in spam. Lower it only with
  evidence.
- `hold.competitor_keywords` — the principal's competitors. A competitor with a
  perfect buyer profile must still land in hold; the branch order guarantees it.

The decision order is fixed in code and is the safety mechanism:

```
suppression -> hold -> CRM tier -> tier-1 lanes -> ICP score
            -> partnership -> job seeker -> spam -> default tier-2
```

Reordering those branches is a behaviour change, not a refactor. Checking tier
before suppression is how a competitor or a journalist ends up accepted.

## 7. The rules that are not negotiable

- **Never fabricate a population.** If no rung reached LinkedIn, say so and give
  the remedy. "Nothing pending" and "I could not look" are different answers and
  must never be rendered the same way.
- **Missing is not zero.** A field a rung could not see stays blank and scores
  nothing. The export carries no mutual-connection count, so it under-detects
  spam by design. That is the correct trade.
- **Provenance rides through.** A month-old export is never presented as live.
- **Never act on a category.** Batches name people. A batch with no names is
  refused, and so is anything that landed in `hold`.
- **Reporting spam is irreversible** and affects the other person's account. It
  never becomes automatic, at any autonomy level, ever.
- **Do not over-trash.** An ambiguous stranger is tier-2 with a flag. Missing a
  spammer costs a scroll; wrongly reporting a customer cannot be undone.
- **The live rung is capped at 200 invitations** and refuses more. Reading 6,000
  through the browser is ~600 automated page loads against a signed-in session,
  which is exactly what gets accounts restricted. The export returns the whole
  queue in one download; use it.
- **Write nothing outside this folder** except `~/Documents/LinkedIn-Inbound/`.
  Deleting this folder must remove every trace of the tool.

## 8. When it breaks — diagnosis by symptom

Run this first; it answers most of them:

```bash
python3 adapters/linkedin/ingest.py --doctor
```

**"Could not reach LinkedIn, and there is no cached data"**
Every rung failed. `--doctor` prints `rungs_reachable`. Empty means no browser
and no cached export. Re-run `python3 linkedin_triage.py` in a terminal someone
is watching: a browser window opens on the sign-in page and the run continues by
itself once they are in. Under cron there is nobody to sign in, so the ladder
skips that rung rather than hanging — that is intended.

**"Reading as: <the wrong person>"**
Every inbound/outbound direction in the DM report is inverted, and the report
will otherwise look completely normal. `sources.py` infers the account owner from
the export and cross-checks it against `memory/ceo-persona.md`. Fix the `Name:`
line in that file to exactly the name LinkedIn uses. A configured name that
appears nowhere in the export is discarded on purpose — trusting it inverts
everything.

**A report is missing**
- `invitations.md` missing but `messages.md` present → no invitation rows;
  check `data/linkedin/invitations.csv` exists and is non-empty.
- `messages.*` missing → the export had no messages (that box was not ticked),
  and no cloud rung is configured. Re-run the ingest, or configure §9.
- `report.pdf` missing but `report.html` present → no Chromium could print it.
  `browser.find_chromium()` returns the path it looked for; `download_chromium()`
  fetches one.
- Everything missing → the grade stage found no rows at all. Run
  `python3 linkedin_triage.py --demo`; if the demo works, it is a data problem,
  not a code problem.

**Everyone is spam / nobody is**
`spam.threshold` in the rubric. The card prints the score behind each decision in
`invitations.csv` — sort by it before changing anything.

**A real customer graded as spam, or a stranger as tier-1**
That is a rubric bug, and it is worth fixing rather than working around:

```bash
python3 adapters/linkedin/act.py --rescue slug:their-name --actual tier-1 --why "real customer"
```

Three corrections of the same shape and it proposes a scoring change that can be
reviewed and undone. It never edits its own scoring silently.

**The DOM changed and a selector misses**
`adapters/linkedin/references/dom-notes.md` holds every selector and every trap
already found — the curly apostrophe in the Accept label, the premium cards that
render Accept as an `<a>` no click will fire, the invitation manager loading ten
cards and ignoring scroll. Read it before changing a selector, and **append what
you learn**. That file is the memory this has instead of a test against a live
site.

**A test fails**
```bash
for t in tests/test_*.py; do PYTHONPATH=$PWD python3 "$t"; done
```
They are plain scripts and print `[FAIL]` with the actual value. The rubric tests
fail when a rubric key is deleted, which is the most common self-inflicted break.

**Reproducing someone else's bug**
`cat BUILD.txt` first. A commit ending in `+uncommitted` was built from a dirty
tree and is not reproducible from git.

## 9. The optional cloud rung

Off unless configured, and the tool is complete without it. It adds two things
the export cannot do: DM threads from the archived / unread / InMail / spam
folders, and accepting invitations from someone else's infrastructure instead of
the principal's laptop.

```bash
export PHANTOMBUSTER_API_KEY=...        # or write phantombuster.json, see docs/
python3 adapters/linkedin/ingest.py --doctor   # cloud_rung should say configured
```

The LinkedIn session cookie it needs is read out of the browser the principal
already signed in to and cached `0600` in this folder. **Never ask anyone to
paste a cookie.** It is a credential; treat it like one.

The invitation queue does not come from here. No third-party service reads
pending received invitations, and none needs to — one export download does.

## 10. Exit codes and the machine contract

Both CLIs answer the same way:

`0` ok · `2` usage · `3` nothing to work on · `4` unreachable · `5` upstream ·
`6` refused by policy · `7` rate limited · `10` config.

`--agent` implies `--json --compact` and never prompts. JSON comes back in a
provenance envelope:

```json
{"meta": {"source": "...", "rung": 2, "synced_at": "..."}, "results": {}}
```

## 11. Before you tell anyone it is done

```bash
python3 adapters/linkedin/ingest.py --doctor         # rungs_reachable non-empty
python3 linkedin_triage.py                           # 7 files in ~/Documents/...
ls ~/Documents/LinkedIn-Inbound/latest/
for t in tests/test_*.py; do PYTHONPATH=$PWD python3 "$t"; done
```

Say which rung answered and how many people were graded. If a rung failed, say
which one and why. Do not report success on a run that produced a report from
the shipped sample rows — the card says so in a banner at the top, and so should
you.
