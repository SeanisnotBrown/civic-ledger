# MISSION.md — Civic Ledger

This is the core of the project. Every session reads it first, before the
spec (`IMPLEMENTATIONv3.md`) and before the live state (`STATUS.md`). It is
written for the people and agents who build the site, not for display on the
site. When the spec and this document seem to pull in different directions,
this document wins, and the spec gets fixed.

Adopted 2026-10-07. Written from the owner's own words, captured in his scope
notes and in the conversation that reset the project on that date.

---

## 1. What the site is

Civic Ledger is an as-objective-as-possible source for vetting politicians.
It answers two questions a citizen should never have to become an expert to
answer:

1. **How has this person actually voted, and where have they stood on the
   things they say matter to them?**
2. **What laws are actually being worked on, passed, or killed right now in
   the House and Senate?**

The first question is about people. The second is about the work those
people are doing this week and next. Both are answered from the official
record: roll-call votes, bill text and bill actions, sponsorships, absences,
and the politicians' own public statements.

The site starts with the federal government, the House and the Senate. States
are added over time, after federal works the way the owner wants it to. The
Mississippi data already in the repository stays where it is, untouched, until
that day.

---

## 2. Who it is for

The site is for two audiences at once, and it must not pick one over the
other:

- **People who are new to politics or have never followed it.** They may not
  know what a roll call is, what a cosponsor does, or how a bill becomes law.
  They are not stupid; they are busy, and nobody ever explained it to them in
  a way worth their time.
- **People who are engaged and well informed.** They want depth: the full
  voting record, the formula behind a grade, the source for every number.

The thing both groups share is that **nobody should have to become an expert,
or spend their life tracking the people they vote for, to know what those
people actually do.** That sentence is the reason the site exists. If a
feature asks the reader to do the tracking themselves, the feature has failed.

Attention spans are short, and the site is built for that rather than against
it. A reader should be able to look at a politician and get the verdict in
seconds. Then, if they want, they should be able to read exactly how that
verdict was reached, step by step, down to the individual vote and the
individual statement. Verdict first; detail one click away; never the other
way around.

---

## 3. The core: transparency and accountability

Two ideas carry the whole project.

### Transparency

What a politician says should mirror what they do. The site puts the two side
by side so the reader can see for themselves whether they match. "What they
say" means public statements: what they said on the record, what they
published, and what they ran on when they campaigned for the office. "What
they do" means the record of their actions in office: votes, bills they wrote
or backed, attendance, and the rest of the public trail.

Without the "say" half, the site is just a voting record. The voting record is
necessary, but it is not the point. The point is the comparison.

### Accountability

Politicians are graded on clear metrics, and the formula is shown. The
baseline for the grade is **what the politician says matters to them**, stated
publicly and stated when they ran for office. That baseline is measured
against **what they actually do** once in office.

Several categories are graded, and the categories roll up into one overall
grade. The default weights are visible to everyone. Readers can adjust the
weights to match what matters to them, because the reader's priorities are
theirs, not the site's. Every grade can be opened to show exactly how it was
calculated. Historical data is kept so that when the formula changes, every
past grade can be recalculated cleanly and long-term trends are never skewed
by a formula change.

---

## 4. The problem it exists to fight

American politics has become a two-sided war, and the owner sees that war as a
cancer killing the country from the inside. The site exists to push back on
it, with facts.

**Nobody can honestly stand with one side on every topic.** A person who
agrees with their party on every single issue has stopped thinking. The site
makes that visible for politicians: where their votes have actually landed
over time, and whether they have ever crossed the aisle.

**Working across the aisle to get things done is rewarded.** Refusing to work
with the other side counts against a politician. Getting things done is the
job; being loud about a topic is not.

**Context beats outrage.** A blind follower repeats "they said X but voted Y"
with anger, without knowing that the bill also contained something the
politician found deeply concerning. The loss was bigger than the gain, but
nobody sees that, because nobody read the bill. The site reads the bill. When
a vote looks like a contradiction, the site shows what else was in the bill
and what the politician has said about that other thing before. The reader
gets the context the outrage left out.

**Echo chambers.** The site pulls people out of them, with objective facts as
the guardrails. No side is "right." No side is "the best." A reader who comes
in certain should leave having seen at least one thing they did not expect
about the people they support, and one thing they did not expect about the
people they oppose.

---

## 5. How it judges

The site calls good where it is good and bad where it is bad, regardless of
party. It exposes corruption and poor performance, backed by evidence that
the reader can check.

The owner's own moral compass shapes what counts as good and bad. That bias is
acknowledged openly rather than hidden, and it is not extreme in either
direction. What the site never does is push a narrative secretly. The
judgments are stated, the formula behind them is published, and the same
formula is applied to every politician of every party. A reader who disagrees
with a weight can change it and see what happens to the grade.

The site gives the benefit of the doubt where the record supports it. A vote
that contradicts a stated position is not automatically dishonesty. Bills
bundle many things, and a politician may have voted against something they
support because it was tied to something they oppose. When the bill's actual
contents and the politician's own prior public statements support that
explanation, the site shows it. When they do not, the site does not invent
one. And when the site cannot tell, it asks the politician's office and shows
the reader that it asked, when it asked, and whether anyone answered.

The owner's original scope put it plainly: do not punish a concession made to
win something else. Identify their values, identify the gains and the losses,
and weigh them. That is harder than counting contradictions, and it is the
only honest way to do it.

---

## 6. How it presents

Simple and digestible. Verdict first, detail one click away. Built for a
phone screen and a short attention span, without talking down to anyone.

The site does not carry "our values" bullet lists, "hard values" banners, or
"every fact links to its source" badges. Those read as written by a machine,
and they ask the reader to take credibility on faith. Credibility comes from
sources that work when you click them and reasoning you can follow when you
open it. The site earns trust by being checkable, not by saying it is
trustworthy.

The homepage welcomes a newcomer and tells them what the site is and why it
exists. It does not open with dataset statistics or jargon. The statistics
are there, further down, for the reader who wants them.

---

## 7. What this means for the people building it

The project drifted once. The build turned into bill-tracking plumbing and
alert infrastructure while the "what they say" half of the site held zero
statements and only one category was graded. The process documents grew until
sessions spent their time reading their own state files instead of building.
This document exists so that cannot happen again.

Some consequences, stated plainly:

- **Statements are not optional.** Until politicians' public statements are
  collected and categorized, the core comparison cannot be made and the
  project is not doing what it exists to do. Work that moves statements
  forward outranks work that does not.
- **Grading is several categories rolled into one grade, with the formula
  shown and the weights adjustable.** One graded category is not grading.
- **Plumbing serves features.** A backfill, a feed, a dedupe pass, or a
  privacy-page rewrite is worth doing when a feature on the page needs it.
  It is not worth doing because it is tidy.
- **The reader is a person, not a dataset.** Every page is judged by whether
  a newcomer understands it in seconds and an expert can go as deep as they
  like.
- **Everything is checkable.** Every number traces to an official record.
  Every grade opens to its math. Every explanation of a vote traces to the
  bill's text and the politician's own words.
- **The owner's judgment shapes what counts as good and bad**, and that is
  stated rather than hidden. Builders do not author those judgments on their
  own; they ask the owner, in plain language, and build what he decides.

---

## 8. The test

Before any action, ask: does this serve the mission? If it does not, it does
not happen.
