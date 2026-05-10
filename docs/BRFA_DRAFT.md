# BRFA Draft — `WikimediaNYC-CurrentEventsBot`

**For submission at:** <https://www.wikidata.org/wiki/Wikidata:Requests_for_permissions/Bot>

> **Do not submit until Phase 3 is complete** (50–100 manual trust-building edits made from the bot account, bot user page published, repo public on a forge with stable URL).

---

## Operator

[YOUR WIKIDATA USERNAME] — affiliated with Wikimedia NYC.
Operator email: af3618@columbia.edu.

## Bot account

[`User:WikimediaNYC-CurrentEventsBot`] (or final approved name).

## Source code

[Public repository URL — TBD; recommend mirroring this repo to `https://gitlab.wikimedia.org/repos/wmnyc/current-events-pipeline` once Phase 0 is complete].

License: MIT.

## Function summary

Daily ingestion of [Portal:Current events](https://en.wikipedia.org/wiki/Portal:Current_events) from English Wikipedia, parsing each top-level bullet under structured section headings into a canonical event record, and publishing source/reference statements to **existing** Wikidata items that the bullet's wikilinks resolve to.

This is the v1 BRFA scope. Future BRFAs will request expansion (e.g. minting new event items, additional categories).

## Function details

For each top-level bullet on a dated portal subpage in the categories listed in **Scope**, the bot:

1. Resolves each `[[wikilink]]` in the bullet to its corresponding Wikidata QID via the `wikibase_item` page-prop.
2. Parses external `<ref>` URLs into citation records (URL, domain, retrieved timestamp).
3. For the resolved QIDs, **adds** the following statements where they are not already present:
   - `P1343` (described by source) → reference URL of the citation
   - References on existing matching statements: `P248` (stated in), `P854` (reference URL), `P813` (retrieved)

The bot does not:
- Mint new Wikidata items.
- Modify or delete existing labels, descriptions, or aliases.
- Add `P31` (instance-of), `P585` (point-in-time), `P276` (location), or any other claim type beyond the citation/reference statements above.
- Edit Wikipedia or any other Wikimedia project.

Items where the bot considers minting a new event item, or adding to politically-sensitive items, are routed to a Discord-based human-review queue and never written autonomously. Those edits, when made, will be made under the operator's account, not under the bot account, until a future BRFA expands scope.

## Scope (v1 BRFA)

- **Categories:** `Disasters and accidents`, `Sports`. Items in other portal sections are **not** in scope for v1 — they are routed to the review queue.
- **Project:** Wikidata only. No edits to any Wikipedia.
- **Languages:** English Wikipedia portal only as input. Statements may be added to items in any language.

## Edit period(s)

Continuous, triggered by the [Wikimedia Enterprise Realtime API](https://enterprise.wikimedia.com/docs/realtime/) when the portal is edited. Backfills only at operator-initiated `/scrape` from Discord.

## Estimated number of edits

- Trial period: 50 total edits.
- Steady-state v1 (post-BRFA): ≤200 edits/day, ≤1 edit/minute. Hard-coded rate limit; not a config.

## Namespace(s)

Item namespace (NS 0) only.

## Bot flag

Requested. The bot will operate at human-account rate limits during the trial.

## Exclusion compliant

Yes. The bot polls `User:WikimediaNYC-CurrentEventsBot/Run` every 60 seconds and halts if the page contains anything other than `true`. Any administrator can stop the bot by editing that page. The bot also respects `{{bots}}` and `{{nobots}}` templates on item pages.

## Edit summary template

```
[[Wikidata:Bots/WikimediaNYC-CurrentEventsBot|CE-Bot]]: adding source reference from Portal:Current events ({{date}} – {{section}})
```

Each edit summary includes:
- The bot's project page link
- The portal date and section the citation came from
- The idempotency key (`event_id` + statement fingerprint), so repeat edits are detectable

## Trial commitments

- Provide a public dashboard of all proposed edits (Phabricator paste or Toolforge static site) during the trial.
- Auto-pause the bot if revert ratio exceeds 5% in any 24-hour window.
- Weekly summary of edits posted to [[Wikidata:Project chat]] during the trial.

## What this bot does NOT replace

The Portal:Current_events portal itself. This bot enriches Wikidata with sources discovered on the portal; it does not mirror or replace the portal.

---

## Notes for the operator before submission

- Replace `[YOUR WIKIDATA USERNAME]` with your actual username.
- Replace the bot name with the final account name once registered.
- Add the public source code URL once the repo is mirrored to a public forge.
- Read [Wikidata:Bots](https://www.wikidata.org/wiki/Wikidata:Bots) end-to-end before submitting; reviewer comments are easier to handle when you've already addressed standard issues.
- Be ready to adjust scope downward in response to reviewer feedback. Most first BRFAs do not pass without at least one round of scope reduction; budget for 2–4 weeks between submission and approval.
