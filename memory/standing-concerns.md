# Standing Concerns

Ernest reads this on every ambient-watch run. The CEO adjusts it by talking:
"watch partnership threads", "stop inbound watch", "tighten follow-ups to 3
days". The CEO should never edit YAML by hand.

```yaml
concerns:
  - id: dropped-followups
    playbook: account-followup-recovery
    enabled: true
    params:
      account: "*"
      staleness: "7d"
      include: "threads,deals,promises"

  - id: inbox-prospects
    playbook: inbox-prospect-followup
    enabled: true
    params:
      profile: "inbound B2B and partnerships"
      intent: "partnership"
      window: "90d"
      min_signal: "1 real exchange"

  # Overlaps dropped-followups; enable once you track explicit promises.
  - id: open-promises
    playbook: account-followup-recovery
    enabled: false
    params:
      account: "*"
      staleness: "3d"
      include: "promises"
```
