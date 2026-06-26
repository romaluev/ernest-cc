# ICP — B2B Lead Grading

How Ernest sorts inbound B2B. Goal: spend Alex's reply time on Tier-1, handle
Tier-2 efficiently, and drop trash. **Grade, don't chase everyone.**

Primary ICP: **AI studios and ad/creative agencies**. Brands and others count
too, but qualify by the tiers below.

## Signal priority (how to decide a tier)

1. **CRM (HubSpot)** — if the contact/company has a tier, deal stage, or prior
   activity, trust it first.
2. **Curated lists** — `data/grading/*` reference lists (providers, known
   contacts, high-reputation people).
3. **Inference** — infer from email content + public knowledge. If a claim like
   "Fortune 500" can't be confirmed, **flag low confidence** for Alex; don't
   silently upgrade or downgrade.

## Tier 1 — Alex should see / reply personally

Any one of these qualifies:

- Fortune 500 or Forbes Global 2000 company.
- Clear market leader / large share in its market.
- AI studio or ad/creative agency (our core ICP).
- Wants to buy enterprise **now** (procurement, rollout, seats, MSA, contract).
- Top ~20 company in its country.
- Model provider or cloud provider.
- Mentions having spoken with Alex before.
- Large fund (> $2B AUM).
- Person with strong media presence or high reputation (e.g. well-known
  investors/researchers).

Action: prioritize. Draft only on Alex's ask; otherwise remind/assign fast.

## Tier 2 — handle, don't over-invest

- Small companies (legitimate, but not market leaders).
- Small funds (< $2B AUM).
- Genuine media enquiries.

Action: route to the right owner, quick acknowledgement, no deep CEO time.

## Trash — drop or auto-decline

- Cold vendor trying to sell us something + small/unknown company.
- Small media (< ~100k readers).
- Generic pitches, SEO/backlink/guest-post spam, mass outreach.

Action: do not surface to Alex. Suggest archive/decline. Never auto-reply
without approval.

## Edge cases

- Conflicting signals → take the **higher** tier and flag the conflict.
- Unknown company not on any list → default Tier-2, confidence low, flag for a
  quick human check rather than guessing Tier-1 or trash.
- A small-but-strategic account (e.g. a tiny but famous AI studio) → Tier-1 on
  the ICP-fit rule, not company size.
