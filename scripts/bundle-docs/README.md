# LinkedIn inbound triage — v__VERSION__

## If you only read one line

Open Claude Code in this folder and say:

> **"Read AGENTS.md and set this up."**

It installs itself, works out how to reach LinkedIn, produces your first report,
runs its own tests, and schedules a daily run. If a browser window opens asking
you to sign in to LinkedIn, sign in — that is the only thing anyone can ask of
you, and it is asked once. Everything below is detail you can skip.

Prefer a terminal?

```bash
./install.sh
```

---

## What you get

One page you act on in two minutes, out of thousands of pending invitations and
unread messages.

**A TL;DR at the top**, then, in the order they cost you something:

- **Accept** — investors, decision-makers at companies big enough to write a real
  cheque, current customers, large audiences, and people who fit what you sell.
  Each with one line saying who they are and what they want.
- **Your call** — press, competitors, legal, and anyone claiming they already
  spoke to you. Never auto-accepted, never auto-ignored.
- **You promised, and it never went out** — commitments buried in threads you
  already replied to. Nothing else surfaces these.
- **Deadlines they set**, resolved against the day they wrote, not today.
- **Waiting on you** — they wrote last and got nothing back.
- **Talent lane** — people applying who actually have something behind them.
- **Spam** — sellers, consultants, cold applicants, and mass sequences collapsed
  so one campaign is one decision instead of forty.

**It reports. It does not act.** Accepting, ignoring and archiving happen only
after you approve a list that names every person on it.

## Where the reports land

`~/Documents/LinkedIn-Inbound/<date>/`, with a `latest` pointing at the newest:

| File | What |
|---|---|
| `report.pdf` | the whole thing, designed to be read |
| `report.html` | the same, in a browser |
| `invitations.md` / `messages.md` | the text versions |
| `invitations.csv` / `messages.csv` | everyone, with the scoring behind each call |
| `reply-briefs.md` | draft replies for whoever is actually waiting |

## How it gets your data

It tries, in order, and tells you which one worked. You do not choose.

1. Data already fetched and still fresh.
2. **LinkedIn's own data export** — it requests it through the browser, waits,
   downloads it and unpacks it. One download, no automation against your account,
   no risk. This is the path that handles a six-thousand-invitation backlog.
3. Reading the live invitation pages — **capped at 200 on purpose**. Reading
   6,000 that way is roughly 600 automated page loads against your signed-in
   session, and that is exactly what gets LinkedIn accounts restricted. It
   refuses, and points at the export instead.
4. A HubSpot export, if you have one. Partial, and it says so.
5. Nothing — in which case it says so and invents no one.

If the export mail has already landed and you would rather just hand it over:

```bash
python3 linkedin_triage.py --from-archive ~/Downloads/<the-export>.zip
```

**Browsers:** Chrome, Edge, Brave, Arc and Chromium all work, and it can start
one itself. If the machine has none, it downloads Google's Chrome for Testing
build into this folder. Safari and Firefox cannot be driven this way.

## Will this get my account restricted?

Reading the export: no. It is a file LinkedIn offers you.

Acting: capped and paced on purpose — 25 accepts and 100 ignores a day, spread
out. Sudden bulk activity triggers restrictions; steady activity does not.
Reporting someone as spam is never automatic, because it cannot be undone and it
affects their account.

## Clearing the spam

Say **"clean up the spam"** to Claude, or:

```bash
python3 adapters/linkedin/act.py --plan --tier trash    # writes a named list
# open it, delete anyone who does not belong, then:
python3 adapters/linkedin/act.py --execute <that-file>
```

Nothing happens until `--execute`, and even then it is a dry run until you set
`dry_run: false` and `approved: true` in `ernest.yaml`.

## When it gets someone wrong

```bash
python3 adapters/linkedin/act.py --rescue slug:their-name --actual tier-1 --why "real customer"
```

Three corrections of the same shape and it proposes a scoring change you can
review and undo. It never changes its own scoring silently.

## Making it yours

`data/grading/linkedin-rubric.json` is the whole scoring brain — who counts as an
investor, which companies are big enough to matter, who your competitors are,
what spam looks like. Edit the lists; **never delete a key** — a missing key
silently switches that whole check off.

The two worth setting first:

- `investor.current_investors` — your own cap table. Names here are treated as
  fact rather than guessed at.
- `hold.competitor_keywords` — your competitors. A competitor with a perfect
  buyer profile still lands in "your call", never in Accept.

`docs/linkedin-spec.md` documents every list, weight and threshold, and every
reason something gets dropped. If a report ever surprises you, the answer is
there.

## Optional: the cloud rung

Off by default and not needed. With a PhantomBuster API key it adds DM threads
from your archived / unread / InMail / spam folders — the folders the export
flattens, and where a dropped request hides — and can accept invitations from
their infrastructure instead of your laptop.

```bash
export PHANTOMBUSTER_API_KEY=...
```

It never asks you for a session cookie. It reads one from the browser you already
signed in to. See `docs/cloud-rung.md`.

## Trust

- Reports first; acts only on a list you approved that names each person.
- Never invents a number — it says which source answered, or that none did.
- Blank is not zero: a field it could not see never counts as evidence.
- Runs on your machine, Python standard library only. No accounts, no
  subscriptions, nothing installed system-wide.
- Writes nothing outside this folder except your reports. Delete the folder and
  every trace is gone.
- `tests/` asserts all of the above, and `./install.sh` runs them.

For agents: read `AGENTS.md`.
