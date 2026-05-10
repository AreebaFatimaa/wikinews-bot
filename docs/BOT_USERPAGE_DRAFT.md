# Bot user-page text

Publish to `User:WikimediaNYC-CurrentEventsBot` on Wikidata once the bot account is registered. This must exist before the BRFA is submitted.

```wikitext
{{Bot
| operator   = [[User:YOUR_OPERATOR_USERNAME|YOUR_OPERATOR_USERNAME]]
| purpose    = Adds source/reference statements to existing Wikidata items based on entries in the English Wikipedia [[w:Portal:Current events|Portal:Current events]]. Stewarded by [[w:Wikipedia:Wikimedia New York City|Wikimedia NYC]] as part of the post-Wikinews effort.
| status     = Pre-BRFA — manual edits only during trust-building period
| source     = [PUBLIC SOURCE CODE URL]
| license    = MIT
| language   = Python
| frameworks = pywikibot, mwparserfromhell, Wikimedia Enterprise Realtime API
| flagged    = no
}}

== Scope ==

* Adds {{P|248}} (stated in), {{P|854}} (reference URL), {{P|813}} (retrieved), and {{P|1343}} (described by source) references to existing items.
* Operates only on items linked from Portal:Current events sections '''Disasters and accidents''' and '''Sports'''.
* Does '''not''' mint new items.
* Does '''not''' modify labels, descriptions, aliases, or any non-citation statements.
* Does '''not''' edit Wikipedia or any other project.

== How to stop the bot ==

Edit [[User:WikimediaNYC-CurrentEventsBot/Run]] and replace the contents with anything other than {{c|true}}. The bot polls that page every 60 seconds and halts on anything but the literal string {{c|true}}. Any administrator (and the operator) can stop the bot this way.

== Rate limits ==

* ≤ 1 edit per minute
* ≤ 200 edits per day
* Auto-pauses if the 24-hour revert ratio exceeds 5%.

== Bot flag ==

Pending. See [[Wikidata:Requests for permissions/Bot/WikimediaNYC-CurrentEventsBot]].

== Reporting issues ==

* Open an issue at [PUBLIC SOURCE CODE URL]/issues
* Or ping the operator at [[User talk:YOUR_OPERATOR_USERNAME]]
* Email: af3618@columbia.edu

[[Category:Bots]]
```

## Run-control page

Also create `User:WikimediaNYC-CurrentEventsBot/Run` with content exactly:

```
true
```

This is the kill switch. Document it on the user page (above) so any admin knows how to use it.
