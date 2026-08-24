# The cloud rung (PhantomBuster) — optional

## Why you would turn this on

You do not need it. The tool is complete without it, and the LinkedIn data
export handles the thing that matters most — a backlog of thousands of pending
invitations — in a single download with no automation against your account.

Turn it on for two things the export cannot do:

1. **Archived, unread, InMail and spam DM folders.** The export flattens your
   messages and does not carry folder state. A request that got dropped is very
   often sitting in one of those folders, which is the whole reason this rung
   exists.
2. **Accepting invitations from someone else's infrastructure** rather than from
   your own laptop and IP, paced at their documented ceiling of 50 per launch.

## What it does not do

It does not read your pending received invitations. No third-party service does,
and none needs to — one export download returns the entire queue. Anyone selling
you invitation scraping is selling you the risky version of a free, safe thing.

## Turning it on

```bash
export PHANTOMBUSTER_API_KEY=your-key
python3 adapters/linkedin/ingest.py --doctor    # cloud_rung: PhantomBuster configured
```

Or, to keep it with the install instead of in your shell profile, write
`phantombuster.json` next to `linkedin_triage.py`:

```json
{
  "api_key": "your-key",
  "org": "",
  "agents": {
    "inbox_scraper": "532696507966746",
    "invitation_accepter": ""
  }
}
```

The `agents` ids are per-account: you duplicate an automation from PhantomBuster's
store and get your own id. The store id for the Inbox Scraper is the default and
works on a fresh account. There is deliberately **no default for the accepter** —
that one mutates your account, and a wrong id there should fail loudly rather
than do something surprising.

## The session cookie

Every LinkedIn automation guide opens with "paste your `li_at` cookie". This one
does not ask. `adapters/linkedin/browser.py:session_cookie` reads it out of the
browser you already signed in to, over the DevTools protocol, and caches it
`0600` in this folder. It expires itself after 25 days, because a stale cookie
fails in a way that looks like a scraping error rather than an auth error.

It is a credential. It grants full access to your LinkedIn account. It never
leaves this folder except in the request to PhantomBuster, and deleting the
folder removes it.

## Cost and rate

PhantomBuster bills by execution time. The inbox scraper on a large mailbox is
minutes, not seconds. The accepter is capped at 50 per launch by them and at 25
per day by this tool — the tighter of the two wins, and it is ours.

## What happens when it fails

Nothing dramatic. It is a rung, not a dependency: a failure is logged, the ladder
moves on, and the report is produced from whatever else answered. The `source:`
line on the report always says which rung actually provided the data.
