# Standing Concerns

Ernest reads this on every watch run. Adjust by talking to Ernest — never edit
YAML by hand. Set `collaborator`, `assignees`, and `list_name` to match your team.

```yaml
concerns:
  - id: dropped-followups
    playbook: account-followup-recovery
    enabled: true
    params:
      account: "*"
      staleness: "7d"

  - id: important-followups
    playbook: account-followup-recovery
    enabled: true
    params:
      account: "*"
      staleness: "3d"
      priority_tiers: "investor,vip"

  - id: inbox-prospects
    playbook: inbox-prospect-followup
    enabled: true
    params:
      profile: "inbound B2B and partnerships"
      intent: "partnership"
      window: "90d"

  - id: b2b-collaborator-coverage
    playbook: add-collaborator
    enabled: true
    params:
      collaborator: "Alex"
      category: "b2b"

  - id: b2b-candidates
    playbook: candidate-followup
    enabled: true
    params:
      role: "B2B marketing/sales"
      assignees: "recruiting-lead, sales-lead"
      window: "180d"

  - id: korea-list-sync
    playbook: list-sync
    enabled: true
    params:
      category: "korea"
      match_key: "company"
      target: "data/lists/korea-hubspot.csv"
      target_key: "company"
      list_name: "Regional HubSpot list"

  - id: press-list-sync
    playbook: list-sync
    enabled: true
    params:
      category: "press"
      match_key: "company"
      target: "data/lists/press-sheet.csv"
      target_key: "outlet"
      list_name: "Press tracker sheet"

  # Partnership + ex-NovaLabs talent sourcing. Talent rows (purpose=hire) are
  # auto-graded Tier-1/2/3; run `ernest grade --talent` for a dedicated card.
  - id: partnership-sourcing
    playbook: sourcing-pipeline
    enabled: true
    params:
      source: "data/sourcing/targets.csv"
      purpose: "partnership/hire"

  - id: slack-task-tracking
    playbook: task-tracker
    enabled: true
    params:
      source: "data/slack/tasks.csv"

  - id: open-promises
    playbook: account-followup-recovery
    enabled: false
    params:
      account: "*"
      staleness: "3d"
      include: "promises"

  - id: slack-open-threads
    playbook: account-followup-recovery
    enabled: true
    params:
      account: "*"
      staleness: "1d"
      channel: "slack"

  # On-demand only — run via `ernest audit --window 365d` + /ernest-audit in Claude.
  # Not part of daily `ernest start` (too heavy for ambient watch).
  - id: mail-audit
    playbook: account-followup-recovery
    enabled: false
    params:
      account: "*"
      staleness: "7d"
      window: "365d"
```
