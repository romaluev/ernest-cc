# /ernest-call-prep

Prepare a one-page brief before a call, deal, or meeting.

Usage:

```text
/ernest-call-prep Acme
/ernest-call-prep deal 12345
/ernest-call-prep            # next calendar event that needs prep
```

Runs the `call-prep` skill. Pulls HubSpot (deal/company), Fireflies (past calls),
Clay/Apollo (attendees), Gmail/Slack (recent comms), web signals, and Notion
(positioning) — whichever connectors are available, with `data/` export fallback.

Output: short chat summary (goal + top prep points) + a rendered one-pager
(`ernest render`) you can open or forward.

Rules:

- Read-only. A pre-read is drafted for approval, never auto-sent.
- Every claim is marked CRM / call / web / enrichment; low-confidence items flagged.
- State missing data instead of guessing.
