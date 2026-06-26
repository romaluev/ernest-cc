# How Ernest works

A two-minute mental model. No code required.

## The one idea

Ernest **watches** your work and tells you what needs you. It **drafts** replies and
outreach **only when you ask**. It **never sends** anything on its own. You stay in
control of every word that leaves your name.

```mermaid
flowchart LR
    W["WATCH<br/>(automatic)"] -->|finds what needs you| C["Reminder cards<br/>'3 follow-ups slipping'"]
    C -->|you say 'draft these'| D["DRAFT<br/>(on request)"]
    D -->|you review & approve| S["SEND<br/>(you, in your app)"]
    style W fill:#1d3557,color:#fff
    style D fill:#2a6f4b,color:#fff
    style S fill:#7a3b1d,color:#fff
```

- **Watch** runs in the background (or when you say "what needs me?"). It only reminds.
- **Draft** happens when you ask ("draft these", "reply to Acme"). Drafts are written
  for your review — nothing is sent.
- **Send** is always you. Ernest hands you a finished draft; you press send.

## A day with Ernest

```mermaid
sequenceDiagram
    participant E as Ernest
    participant You as You
    Note over E: 8:00 — morning brief
    E->>You: "7 follow-ups need you, 2 VIPs went quiet, 1 deal stalled."
    You->>E: "Draft replies for the two VIPs."
    E->>You: 2 drafts, in your voice, for review
    You->>E: "Send the first, fix the second to mention pricing."
    Note over You: You approve the send in Gmail
```

## What's running under the hood (you never touch this)

Ernest is built in three layers, kept in separate folders so an update can never
wipe your work:

```mermaid
flowchart TB
    subgraph P["Your Ernest"]
      core["core/ — Ernest's own code & skills<br/>(updates land here)"]
      custom["custom/ — anything YOU add<br/>(never touched by updates)"]
      state["state/ + memory — what Ernest knows about you<br/>(never overwritten)"]
    end
    core -.->|composed at runtime| run["What Ernest can do"]
    custom -.->|your tweaks win| run
    state -.->|your context| run
```

- **core** is Ernest's shipped brain. Updates only replace this.
- **custom** is your own additions (a new use-case, a tweaked reply style). Updates
  never touch it; your versions win over the defaults.
- **state / memory** is everything Ernest learns about you and your company. It stays
  put through every update, and it stays **on your machine** (see [privacy.md](privacy.md)).

## The safety gate (always on)

Every action passes a deterministic safety check *before* it can run — not a polite
request to the AI, an actual gate:

- Live sends, posts, CRM changes, payments → **blocked** until you approve.
- Reading your secrets or phoning out to the internet in private mode → **blocked**.
- Reading, searching, and preparing drafts → **allowed**.

So even if a malicious email tries to trick Ernest into "send this now," the worst it
can do is prepare a draft for you. (Details: [security.md](security.md).)

## Where to go next

- Get set up by talking: run `/ernest-setup` (see [quickstart.md](quickstart.md)).
- Day-to-day prompts: [daily-use.md](daily-use.md) and [examples.md](examples.md).
- Add a new thing for Ernest to watch: [add-automation.md](add-automation.md).
- What stays private: [privacy.md](privacy.md). How updates work: [updates.md](updates.md).
