# Standing Concerns

Ernest reads this on every ambient-watch run. The CEO adjusts it by talking:
"watch partnership threads", "stop inbound watch", "tighten follow-ups to 3
days", "add Manoj to B2B threads". The CEO should never edit YAML by hand.

Names like `collaborator`, `assignees`, and `priority_tiers` are parameters -
change them to fit your team.

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

  - id: add-manoj-to-b2b
    playbook: add-collaborator
    enabled: true
    params:
      collaborator: "Manoj"
      category: "b2b"

  - id: b2b-candidates
    playbook: candidate-followup
    enabled: true
    params:
      role: "B2B marketing/sales"
      assignees: "Alua, Limon"
      window: "180d"

  - id: korea-list-sync
    playbook: list-sync
    enabled: true
    params:
      category: "korea"
      match_key: "company"
      target: "data/lists/korea-hubspot.csv"
      target_key: "company"
      list_name: "Alvin's HubSpot Korea list"

  - id: press-list-sync
    playbook: list-sync
    enabled: true
    params:
      category: "press"
      match_key: "company"
      target: "data/lists/press-sheet.csv"
      target_key: "outlet"
      list_name: "press tracker sheet"

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

  # Overlaps dropped-followups; enable once you track explicit promises.
  - id: open-promises
    playbook: account-followup-recovery
    enabled: false
    params:
      account: "*"
      staleness: "3d"
      include: "promises"
```
