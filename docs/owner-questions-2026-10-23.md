# Owner questions — overnight 2026-10-23

Written by the builder overnight; nobody could answer them then. Each has the builder's
pick, which is what the code does now, so nothing waited on these. Change any pick and
the builder changes the code. Already pending in `STATUS.md` and NOT repeated here:
multi-topic labels, the banned-words check, ratifying Q-K, Q-C, Q-D.

## 1. The AI's "confidence" word — what should each level mean?

The categorizer says `high`, `medium` or `low` about its own labels. The builder wrote:
high = "the text says it plainly; another careful reader would agree"; medium = "supported,
but it took a judgment call"; low = "unsure; look closely".

- **A. Keep these.** The review screen shows them as the AI's own guess about itself.
- **B. Drop the word.** The screen is simpler, and you lose a hint about which items to
  read carefully.
- **C. Reword them.** Tell the builder the wording.

**Builder's pick: A.** It costs nothing, and the review log will show whether `high` is
actually right more often than `low`.

## 2. Topic hints in the AI's instructions

To help the AI choose among the 33 areas, the builder added short hints that follow how
Congress itself files bills. Examples: veterans → Armed Forces and National Security,
Social Security → Social Welfare, guns → Crime and Law Enforcement.

- **A. Keep the hints.** Topic choices match Congress's own filing. Some readers might
  expect "veterans" to sit somewhere else.
- **B. Remove them.** The AI guesses from the list alone, so the same kind of statement
  may land in different areas.

**Builder's pick: A.** Statements are compared against votes on bills, so using the same
filing system as the bills is what lines the two up.

## 3. Does "Today I introduced a bill to…" count as a priority signal?

Your rule (Q-J): a priority signal is (a) explicitly ranking the issue, or (b) "a concrete
commitment — a pledge to introduce, pass or block a specific thing". A press release
announcing a bill the member ALREADY introduced is an act, not a pledge.

- **A. Yes, it counts.** Many more statements get the priority flag, because introducing
  a bill is about the strongest commitment a member can make.
- **B. No: only a pledge about the future counts.** Fewer flags. A member who introduces
  ten bills and never says "I will" gets none.
- **C. Leave it to the AI and your review.** The flag varies from case to case. The
  instructions quote your rule word for word and do not decide this.

**Builder's pick: C for now**, which is how the instructions are written tonight. Your
answer goes into the next version of the instructions.

## 4. Should the first-pass screen have its own accuracy bar?

The provisional Q-K bar covers topic, stance, priority and specificity. The cheap first
pass, which decides whether a statement takes a position at all, has no bar. It is still
reported.

- **A. No bar.** Its mistakes are caught later: you review every statement, and anything
  it wrongly passes is shown to you as such.
- **B. Give it a bar (for example 0.90).** Its errors are held to the same standard, and
  a weak first pass can block launch.

**Builder's pick: A.** A wrong pass only costs you one review. The two dangerous mistakes,
wrong stance and wrong topic, already have bars.

## 5. Where should your review log live?

Your approvals, edits, rejections and blind labels are logged so the site can work out
running accuracy. The log holds your labels and whether the AI agreed. It holds none of
the AI's text.

- **A. On this computer only** (git ignores it, like the AI's raw answers). If the disk
  dies, your review history and the running accuracy number are lost.
- **B. Committed to the public repository.** Nothing is lost, and anyone can check the
  accuracy number. Your labels on unpublished statements become public.

**Builder's pick: A for now**, with the accuracy number committed in reports. Choose B
before reviewing at volume if you want the history kept safe.

## 6. A "Reject" on the review screen: should it count against the AI?

At the moment, Reject records no label, so it does not change the accuracy number. Only
your blind labels feed that number, and they are unaffected.

- **A. Keep it that way.** One click to reject. Rejects say nothing about accuracy.
- **B. Ask why on every reject** ("takes no position", "wrong member", "text broken").
  One more click, and the rejects then explain the AI's misses.

**Builder's pick: B, eventually.** It is not built tonight. It changes no published
number, because accuracy comes from the blind labels.

## 7. Matching the AI's labels to the statement records the site already publishes

The published statement record (from the hand-curation tool) uses `support` / `oppose` and
specificity 0–3. The AI uses `for` / `against` / `mixed` / `none` and specificity 1–3. To
export an approved statement, the two must be mapped.

- **A. for → support, against → oppose, mixed and none → blank** (blank means "no stated
  position", which the say-vs-do check skips). Specificity 1–3 carried over unchanged.
- **B. Change the published record to the AI's four values.** It is more expressive, but
  it changes the published data format and the say-vs-do check.

**Builder's pick: A.** It changes nothing already published. Nothing exports until Q-K is
ratified and archiving exists, so this can wait.

## 8. Which statements count toward the "5 across 3 topics" bar (Q-B)?

Your rule for priorities (Q-J) uses only statements from the member's current term. Q-B, the
bar for showing a list at all, does not say. The code counts every approved statement since
January 2023 toward Q-B, and only current-term statements toward priorities.

- **A. Every approved statement counts toward Q-B** (what the code does). More members get a
  list. A member who spoke mostly last term may show a list that says no priority meets the
  rule yet.
- **B. Only current-term statements count.** Fewer members get a list, but every list that
  shows draws on the same statements as its priorities.

**Builder's pick: A.** Q-B exists so that no member is summarized from too little, and older
approved statements are still on the record.

## 9. Wording of a member's priorities list (AES-14)

No member has a list today: no statements are approved yet. When one does, each line
currently reads like *"Health — In support, called a priority in an approved statement
(1 approved statement)"*. The audit item AES-14 covers this panel and its wording, and it
waits for your approval. Nobody will see the wording until statements are approved.

- **A. Approve this wording for now.** Lists can appear as soon as statements are approved.
- **B. Review AES-14 first.** No list can appear until you do.

**Builder's pick: B.** It is your evaluative wording, and nothing is waiting on it yet.
Unlike the other picks, this is NOT what the code does tonight. The code would show the
list as soon as a member qualifies. No member can qualify yet: nothing is approved, and
the export is gated. If you pick B, the builder adds a switch that keeps the list hidden
until AES-14 is reviewed.
