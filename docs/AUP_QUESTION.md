# Toolforge AUP question

Post this in `#wikimedia-cloud` on Libera Chat, or send to `cloud@lists.wikimedia.org`. Wait for a yes/no on both before proceeding with Phase 0.

---

> Hi all — I'm setting up a Toolforge tool (`current-events-pipeline`) for a project stewarded by Wikimedia NYC. It scrapes [[Portal:Current_events]] into structured data and publishes source/reference statements to Wikidata under a flagged bot account (BRFA pending). Two AUP questions before I start:
>
> 1. **Outbound Discord gateway connection.** I'd like to run a `discord.py` bot from a Toolforge continuous job. The bot would maintain an outbound WebSocket to `gateway.discord.gg` and post status updates / accept slash commands from a small set of Wikimedia NYC operators. The bot is purely operator-facing — it doesn't relay public Wikimedia content into Discord, and reading/writing user-generated Discord content stays inside the operator team. Is this acceptable on Toolforge, or should the Discord half move to a chapter-controlled VPS?
>
> 2. **Outbound Anthropic API calls (LLM scoring).** I'm probing Liftwing for a newsworthiness scoring model first; if no fit, I'd fall back to calling the Anthropic API for structured-output scoring. Volume would be low (≤200 events/day, prompt-cached). Is outbound to `api.anthropic.com` acceptable from a tool's continuous job, or should the scorer move off Toolforge?
>
> Source code will be public, MIT-licensed, and the tool meets the standard "benefits the Wikimedia movement" criterion (it's the post-Wikinews data layer for current events). Happy to share the BRFA draft if it helps the AUP read.
>
> Thanks!

---

## Why this question matters

If either answer is **no**, the Phase 0 plan changes:

- **Discord disallowed** → Discord bot moves to a Wikimedia NYC chapter VPS; Toolforge keeps scraper/parser/writer; halves talk via authenticated HTTPS callback.
- **Anthropic disallowed** → Either commit to Liftwing-only scoring (if probe finds a fit), or move the scorer off Toolforge alongside the Discord bot.

The architecture is designed to handle either fallback cleanly, but the answer determines deployment shape.
