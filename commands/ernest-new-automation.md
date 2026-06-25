# /ernest-new-automation

Use `ernest-use-case-author`.

Goal: turn a CEO's repeated workflow into a configured concern or a new reviewable skill.

Ask only what changes the automation:

1. What starts it?
2. What should Ernest read?
3. What should Ernest produce?
4. What must never happen?
5. Should it run on schedule, on demand, or both?

Fast path for the two starter playbooks: `ernest new-automation --id <id>
--playbook account-followup-recovery|inbox-prospect-followup [--staleness 5d]
[--intent partnership]` registers the concern and scaffolds a `SKILL.md`. The
watch engine picks it up on the next `ernest watch`.

Prefer configuring an existing skill. If a new skill is needed, output a proposal with:

- new `SKILL.md` content
- schedule/standing concern changes
- tools needed
- approval level
- dry-run plan
- rollback

Never auto-install unvetted connectors or credentials.
