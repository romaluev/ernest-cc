# LinkedIn ingest adapter

Fills `data/linkedin/` so the engine can grade the CEO's inbound invitations.
**Runs outside the ernest gate on purpose** — `ernest/gate.py` blocks shell
commands containing https URLs and turns off web tools in local mode, which is
correct. This adapter is driven by cron/launchd or by hand; the engine only ever
reads the files it writes.

```
python3 adapters/linkedin/ingest.py --status --json          # what is reachable
python3 adapters/linkedin/ingest.py --from-archive ~/Downloads/*.zip
python3 adapters/linkedin/ingest.py                          # walk the ladder
python3 adapters/linkedin/ingest.py --rung 3 --limit 200     # live read only
```

## The ladder

| Rung | Mechanism | `source:` on the card | Needs |
|---|---|---|---|
| 1 | `data/linkedin/*.csv` still fresh | whatever wrote it | nothing |
| 2 | LinkedIn's "Get a copy of your data" | `linkedin-archive` | a signed-in browser, or a hand-downloaded zip |
| 3 | Live invitation-manager DOM | `linkedin-live` | a signed-in browser |
| 4 | HubSpot `linkedin_*` properties | `hubspot-mirror` | a HubSpot contacts export |
| 5 | Nothing worked | `unavailable` | — |

A failed rung never ends the run; it is recorded in `attempts` and the ladder
falls through. Rung 5 writes no data and says why. **It never fabricates a
population** — an empty answer is a real answer, a wrong one is not.

Rung 4 is always a *subset*: HubSpot only knows people who already reached the
CRM, so a count from there is not the size of the queue. The card labels it
`hubspot-mirror` for exactly that reason. Do not read the `heyreach_*` family —
those 20 properties are empty portal-wide, and reporting from them would be
technically true and completely wrong.

## Browsers

`browser.py` prefers `ego-browser` (isolated agent task space, reuses the user's
login state) and falls back to any Chrome already listening on a DevTools port:

```bash
# macOS, against the real profile that is signed in to LinkedIn
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --profile-directory=Default
```

Then `--prefer chrome`. If neither is reachable the rung raises and the ladder
moves on — it does not guess.

## When the DOM moves

LinkedIn ships UI changes without notice. `references/dom-notes.md` holds the
selectors, the three known traps, and the safety caps. Read it before changing a
selector, and **append what you learn** when a run finds something new — that
file is the memory this adapter has instead of a test against a live site.

## Acting

Ingest is read-only. Accepting, ignoring, and reporting are Phase 2 (`act.py`)
and are gated behind explicit chat approval plus the caps in
`ernest.yaml: linkedin_policy`. Reporting someone as spam is not reversible and
never graduates past L2.
