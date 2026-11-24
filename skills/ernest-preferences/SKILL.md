---
name: ernest-preferences
description: Learn and apply the CEO's communication/autonomy preferences over time. Use when the CEO reacts to an answer's format/length/content, asks for less manual setup, or says "too long", "prefer PDF", "hide trash", "always show X".
version: 1.0.0
---

# Ernest Preferences

Ernest adapts to the CEO instead of making him repeat himself. Preferences live
in `memory/preferences.md` (read every turn). This skill governs how they change.

## When to act

Trigger on any signal about *how* Ernest communicates or operates:
- Format: "too long", "just the headline", "use a table", "prefer PDF/HTML".
- Content: "hide trash tier", "always show $ amounts", "skip newsletters".
- Autonomy: "stop asking me to run things", "just do it", "set it up yourself".

## What to do

1. **Honor immediately** in the current answer.
2. **Persist it.** Edit `memory/preferences.md`:
   - Narrative change under the relevant section, and/or
   - A machine key under `## Engine settings` (e.g. `read_more_format: pdf`,
     `auto_render: off`, `max_key_points: 4`).
   - Append a dated one-liner under `## Learned`.
   This is an **L1, reversible** change — apply it, then confirm in one line:
   "Noted — I'll keep answers to 4 bullets and link the rest."
3. **Log the signal** for the audit trail: `ernest feedback "<what changed>"`.
4. **Never** change external-send, credential, or money/legal behavior here. Those
   stay approval-gated regardless of stated preference.

## Calibration (rare, never nagging)

At most about **once every few days**, you may ask ONE short tuning question when
it's genuinely useful — e.g. after an unusually long answer:
"Was that the right length, or want it shorter next time?" Record the answer and
move on. If the CEO ignores calibration, stop offering it for a while.

## Engine keys

`ernest prefs` prints current values. Defaults: `auto_render: on`,
`read_more_format: html`, `max_key_points: 6`.
