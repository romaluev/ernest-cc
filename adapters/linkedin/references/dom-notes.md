# LinkedIn DOM notes

Site-level experience for the live rungs. **Read this before inventing an
approach**, and append to it whenever a run discovers something non-obvious —
that is the whole point of the file. Each entry says what breaks, how to detect
it, and what to do instead.

Every claim here should be traceable to a real run. If you cannot reproduce it,
mark it `unverified` rather than deleting it.

---

## Surfaces

| What | URL |
|---|---|
| Received invitations (all) | `https://www.linkedin.com/mynetwork/invitation-manager/received/` |
| …filtered to mutual connections | `…/received/PEOPLE_WITH_MUTUAL_CONNECTION/` |
| …filtered to shared school | `…/received/PEOPLE_WITH_MUTUAL_SCHOOL/` |
| Sent/pending invitations | `…/invitation-manager/sent/` |
| Archive request | `https://www.linkedin.com/mypreferences/d/download-my-data` |
| Messaging | `https://www.linkedin.com/messaging/` (Focused / Other tabs; filters: Unread, InMail, Starred, Archived, Spam) |

The filtered URLs render a chip counter with the remaining count. **The chip
count is the authoritative loop terminator** — not the number of cards on screen,
and not a scroll position.

## Controls

Accept and Ignore are found by `aria-label`, not by class (classes are hashed and
change without notice):

```js
// NOTE the CURLY apostrophe in "<Name>’s" — a straight ' will not match.
const accepts = Array.from(document.querySelectorAll('button, a'))
  .filter(b => (b.getAttribute('aria-label') || '').startsWith('Accept '));
const ignores = Array.from(document.querySelectorAll('button'))
  .filter(b => (b.getAttribute('aria-label') || '').toLowerCase().startsWith('ignore'));
```

- Accept: `aria-label="Accept <Name>’s invitation"`
- Ignore: `aria-label="Ignore an invitation to connect from <Name>"`

## Trap: the "Follows you" card cannot be accepted programmatically

On invitations auto-generated for Premium members who already follow you, the
Accept control renders as an **`<a>` element, not a `<button>`**, with an `href`
pointing at the current page. `.click()`, a dispatched `MouseEvent`, and
coordinate-based `Input.dispatchMouseEvent` all fail to fire the handler. **There
is no known CDP workaround.**

Detect it by carrying the tag name out with the row (`ingest.py` already does):

```js
accepts.map(a => ({ aria: a.getAttribute('aria-label'), tag: a.tagName }))
```

`tag === 'A'` → route the row to Ignore (always a real `<button>`) or skip it and
report it as needing a manual click. Do **not** report it as accepted.

## Trap: scrolling does not paginate

The manager mounts roughly 10 cards per load. Scrolling to the bottom does **not**
mount the next batch, and after acting on the visible rows LinkedIn swaps in
acknowledgement copy and suggestions rather than the next page. Re-navigate:

```js
cdp("Page.navigate", { url: INVITATION_MANAGER })   // then wait ~2.5–3s
```

Loop until the chip counter reads `(0)` or no Accept controls remain. `ingest.py`
uses a stall counter (two consecutive rounds with zero new rows) so a broken
selector cannot spin forever.

## Trap: the "Take care when connecting" interstitial

Accepting an invitation from someone outside your network intermittently opens a
modal titled **"Take care when connecting"** with *View profile* and *Accept
invite* buttons. It is not predictable per row. Handle it by clicking *Accept
invite* before continuing; if a native dialog is open instead, page JavaScript is
blocked entirely and must be dismissed via `Page.handleJavaScriptDialog`.

## Trap: reaction/engagement counts read as zero

Logged-in LinkedIn renders engagement as "*Name* and 28 others". A numeric regex
over that string silently yields 0. This zeroed 21 of 24 posts on a first pass in
a sibling study. If a count cannot be parsed, emit **blank, not zero** — the
grader distinguishes "we did not look" from "we looked and found none", and the
whole spam score depends on that distinction.

## Messaging surface

Conversation rows are `li.msg-conversation-listitem` (class names are hashed and
change, so `li[class*="conversation"]` is kept as a fallback). The counterparty
name is the only stable handle on a row — there is no per-thread aria-label
equivalent to the invitation controls.

Archive and Delete live behind the row's overflow menu, not on the row itself:

```js
const menu = li.querySelector('button[aria-label*="ptions" i], button[class*="overflow"]');
menu.click();                       // then click the menu item by its text
```

Match the menu item on exact text ("Archive" / "Delete"), not position — the menu
contents differ between connected and non-connected threads.

Folders are query params on `/messaging/`: unread, InMail, starred, archived, and
spam. LinkedIn's own **Focused / Other** split is separate from all of them and
is not a reliable signal of whether something matters.

**Archive is reversible** (LinkedIn keeps the thread and it returns on a new
message). **Delete is not**, and neither is reporting — both stay behind an
explicit named list.

## Rate and safety

- Accepting: keep batches small and paced. A published accepter tool caps itself
  at 50 per launch and recommends less, spread across runs.
- LinkedIn names invitations "ignored, left pending, or marked as spam" among its
  documented account-restriction triggers, so **sudden mass action is the risk,
  not volume over time**. Slow, consistent cleanup looks human.
- Reporting someone as spam / "I don't know this person" is **not reversible** and
  affects the other account. It stays at L2 approval permanently.

## Archive request page

Requesting specific categories (Invitations, Connections, Messages) is documented
to deliver "within minutes"; the full archive can take up to 24h, and the link
stays live for 72h. The page is not available on mobile.

Controls are found by label text rather than id, because the ids are generated:
pick the "want something in particular" radio, tick the checkboxes whose label
matches `/invitation|connection|message/`, then click the button reading
"Request archive". If a "Download archive" link is already present, an earlier
request is ready — short-circuit and take it.

The download must be fetched **from inside the page** (`fetch(..., {credentials:
'include'})`) so the session cookie applies; a plain out-of-band GET returns a
login wall.

## What the archive does and does not contain

Contains: invitee/inviter first and last name, profile URL, date sent, and the
invitation **message**. That is enough to score the rubric.

Does **not** contain: headline, mutual-connection count, or network size. Those
stay blank, and blank is not zero. Only the live rung can fill them.
