# If the automation cannot do it — the exact clicks

Read this only when the tool has told you it is stuck. It does all of this by
itself when it can. Everything here takes about a minute and needs no technical
knowledge.

Every step below is a link you click and a button you press. Nothing to install,
nothing to configure, nothing to paste.

---

## A. Get your data out of LinkedIn (the one that matters)

This is the safe path for a large backlog: one download, no automation running
against your account, no risk of a restriction.

**1. Open the export page directly:**

> https://www.linkedin.com/mypreferences/d/download-my-data

(If that redirects you, sign in first at https://www.linkedin.com/login and click
the link again.)

**2. Choose the targeted export, not the whole archive.**

Click the option **"Want something in particular?"** — the second of the two
choices on the page. The first one ("Download larger data archive…") takes 24
hours and returns far more than is needed.

**3. Tick exactly these three boxes:**

- **Invitations** — who has asked to connect and is still pending
- **Messages** — your DM threads
- **Connections** — used to tell a stranger from someone you already know

**4. Click "Request archive".**

**5. Type your LinkedIn password when it asks, then click "Done".**

This step is the reason the automation sometimes stops here. LinkedIn requires
the password to confirm an export and there is no way around it — nor should
there be.

**6. Wait for the email.**

- **Invitations** arrive in **about 10 minutes**.
- **Messages and Connections** are in LinkedIn's **48-hour** bucket. They can
  take that long. This is normal.

The email goes to your primary LinkedIn address, subject line roughly *"Your
LinkedIn data archive is ready"*. **The download link expires after 72 hours** —
download it when it arrives rather than later.

**7. Hand the file over.** Say to Claude:

> "the LinkedIn export landed, it's in my Downloads"

It finds it and takes over from there. Or, in a terminal:

```bash
python3 linkedin_triage.py --from-archive ~/Downloads/<the-file>.zip
```

You do not need to unzip it.

---

## B. Sign in, when it says it cannot reach LinkedIn

The tool opens a browser window on the sign-in page and waits. If you would
rather do it yourself first:

> https://www.linkedin.com/login

Sign in **in the window the tool opened**, not in your normal browser — that
window has its own profile, which is what keeps the tool out of your everyday
browsing. Once you are in, it continues on its own and never asks again.

If a verification code or a security check appears, complete it in the same
window. It is LinkedIn checking, not the tool.

---

## C. Useful pages, in case you want to look yourself

| What | Link |
|---|---|
| Invitations waiting on you | https://www.linkedin.com/mynetwork/invitation-manager/received/ |
| Invitations you sent | https://www.linkedin.com/mynetwork/invitation-manager/sent/ |
| Messages | https://www.linkedin.com/messaging/ |
| Archived messages | https://www.linkedin.com/messaging/?filter=archived |
| Spam messages | https://www.linkedin.com/messaging/?filter=spam |
| Export your data | https://www.linkedin.com/mypreferences/d/download-my-data |
| Data privacy settings | https://www.linkedin.com/mypreferences/d/categories/privacy |

---

## D. No Chrome, Brave, Edge or Arc on this machine

The tool downloads Google's own Chrome for Testing build into its own folder and
uses that. It does not touch your normal browser, does not install anything
system-wide, and deleting the tool's folder removes it.

If that download is blocked on your network, install any one of Chrome, Edge,
Brave or Arc normally and run the tool again — it finds whichever is there.
Safari and Firefox cannot be driven this way; use path **A** instead, which needs
no browser automation at all.

---

## E. Nothing is working and you want the report anyway

```bash
python3 linkedin_triage.py --demo
```

That produces a complete report from fictional people so you can see the shape
of it. It is clearly labelled as sample data on every page, it touches none of
your own data, and it proves the tool itself is fine — which means the problem is
getting the data in, and section **A** is the answer.
