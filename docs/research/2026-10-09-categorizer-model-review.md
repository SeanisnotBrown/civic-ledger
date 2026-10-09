# Categorizer model review — GPT-6.1 Sol, 2026-10-09

Reference input only, filed the same way as `docs/design/2026-10-08-sol-aesthetics-audit.md`. An outside model's review of the Phase 3 statement categorizer: model choice, field difficulty, the evaluation process, token costs, and operating settings. **Nothing here is ratified.** Phase 3 task 4 (categorizer prompt + held-out precision test) reads this document; each recommendation applies only if the owner approves it at task 4.

Two things the owner acted on immediately, 2026-10-09, because they change the ai.yaml schema stub written at task 1 rather than the prompt written at task 4:

- **Stance gained a fourth value, `none`** — no position on an identifiable policy. `mixed` means genuinely competing positions and never "unclear".
- **A `proposition` field was added** — what the stance is about, nullable when stance is `none`.

The schema stub is marked provisional; every field definition is ratified at task 4.

Model IDs and prices below were checked against `platform.claude.com/docs/en/about-claude/models/overview.md` on 2026-10-09 and are correct: `claude-opus-5-5` ($4 / $20 per MTok, default effort `medium`), `claude-sonnet-5-5` ($2 / $10, default effort `high`), `claude-haiku-5-5` ($0.10 / $0.50, default effort `medium`). Claude Opus 5 is now a legacy model.

---

**Fix the stance contract before launch:** `for / against / mixed` cannot truthfully describe a statement that expresses no position. "Mixed" means the speaker expresses competing positions; it must not mean "unclear."

**My provisional choice: Claude Opus 5.5, with Claude Sonnet 5.5 as the fallback.** Neither has been tested on Civic Ledger statements yet. Prices and API identifiers below were verified against official documentation on **October 9, 2026**.

## 1. Model recommendation

**Primary — Claude Opus 5.5 (`claude-opus-5-5`).** Start with Opus because interpreting hedged stance, distinguishing explicit priority from routine messaging, and avoiding unsupported specificity matter more here than throughput. It preserves your Anthropic integration, and its additional token cost is modest at the volumes estimated below; whether it actually produces fewer confident errors must be established on your labeled set. Its documented default effort is `medium`. [Opus documentation](https://platform.claude.com/docs/en/models/opus-5-5/overview)

**Fallback — Claude Sonnet 5.5 (`claude-sonnet-5-5`).** Evaluate Sonnet at `high` effort against exactly the same topic, stance, specificity, priority, and confidence requirements. It preserves the existing integration at half Opus's token rates; use it only if it passes the same acceptance criteria, and make it primary if Opus shows no meaningful advantage. This fallback does not protect against an Anthropic-wide outage—queue statements during an outage. [Sonnet documentation](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)

**Third candidate — GPT-6.1 Sol.** It is a useful outside-provider challenger, but switching requires the second integration and decision amendment you described. Make that change only for a demonstrated reduction in consequential errors or reviewer workload; vendor benchmarks do not establish superiority on political speech. [Official OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)

### Verified candidate prices

USD per **1 million tokens**, standard processing, ordinary short prompts, uncached:

| Candidate | API model ID | Input | Output |
|---|---|---:|---:|
| Claude Haiku 5.5 | `claude-haiku-5-5` | $0.10 | $0.50 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2 | $10 |
| Claude Opus 5.5 | `claude-opus-5-5` | $4 | $20 |
| Claude Fable 5.1 | `claude-fable-5-1` | $10 | $50 |
| GPT-6 Luna | `gpt-6-luna` | $0.10 | $0.50 |
| GPT-6.1 Sol | `gpt-6.1-sol` | $2 | $10 |
| GPT-6 Astra | `gpt-6-astra` | $10 | $50 |

Your supplied prices are correct for these conditions. Haiku's rates rise above 100,000 input tokens, which should not affect this task. Sources: [Anthropic pricing](https://claude.com/pricing), [Fable model ID](https://platform.claude.com/docs/en/models/fable-5-1/overview), [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [OpenAI model catalog](https://developers.openai.com/api/docs/models/compare).

Haiku and Luna deserve a cheap screening run, but low price is not evidence that they handle priority and ambiguity safely. Fable and Astra need to demonstrate enough additional quality to justify their higher costs; I would not start with them.

## 2. Field difficulty and whether to split models

| Field | Difficulty | What makes it difficult |
|---|---|---|
| **Topic** | Usually easiest; medium on boundary cases | A farm-worker statement could concern agriculture, labor, or immigration. A statement may span several areas. |
| **Stance** | Hard | Negation, quoted opponents, conditional support, competing provisions, and an unclear policy target. |
| **Specificity** | Medium | Naming a bill is different from committing to support it. Concrete facts are different from concrete promises. |
| **Priority signal** | Hardest substantive field | "This is my top priority" provides evidence; merely discussing an issue does not establish importance. |
| **Confidence** | Easy to emit; hard to validate | A confidence word is another model prediction. Its reliability has to be measured. |

**Stance needs an identifiable proposition.** "Against" on the topic *Immigration* is too broad: opposing a particular restriction is different from opposing immigration. Preserve the proposition and supporting excerpt in the review record, even if they sit outside the five-field output.

Allow an unresolved stance through a nullable value or a workflow-level abstention. Until that exists, send statements without a defensible stance directly to manual labeling. Forcing a label defeats the credibility rule.

For priority, ask **"Does this text present the issue as a priority?"** A single statement cannot establish the member's actual priorities or motives. Likewise, the five-statements/three-topics threshold establishes enough material to display a list; it does not make every mentioned topic a priority.

**Do not split topic onto a cheap model initially.** The stronger model still needs the original statement and policy definitions to interpret stance and priority. Splitting adds another call, version, failure path, and potentially an incorrect topic that biases the remaining fields, while saving little of the difficult reasoning.

Reconsider splitting only after measuring substantial volume and showing that the combined pipeline preserves quality.

## 3. Evaluation process

### Step 1 — Write the labeling rules before labeling the test set

Build a short rulebook using separate development examples. Freeze it before the final test.

| Field | Required rule |
|---|---|
| Topic | Define all 33 allowed areas, boundaries, and how to choose one primary area. Route irreducibly multi-topic statements for splitting or manual handling. |
| Stance | Define the policy proposition, conditional support, genuine mixed positions, quotations, and unresolved cases. |
| Specificity | Use anchored levels—for example: **0** broad value, **1** policy direction, **2** concrete proposal/action, **3** named bill or precisely identifiable commitment. |
| Priority | Require evidence of importance or commitment under a written standard. A press release or campaign-page heading alone should not automatically qualify. |
| Confidence | Define it as confidence that **all four substantive labels** are supported by the supplied text. |

Keep specificity and priority separate. A vague statement can explicitly identify a priority; a detailed bill announcement can be routine messaging.

When humans disagree repeatedly, repair the rulebook. More expensive models cannot resolve an undefined standard.

### Step 2 — Build the initial 50-statement set

Use **48 statements distributed evenly across party and source**, plus two independent-member statements where available:

| Source | Democratic | Republican |
|---|---:|---:|
| Official press releases | 6 | 6 |
| Congressional Record speeches | 6 | 6 |
| Most recent campaign issue pages | 6 | 6 |
| Official social accounts | 6 | 6 |
| **Subtotal** | **24** | **24** |

Within each six-statement cell, select three routine examples randomly and three hard examples deliberately. Include both chambers, different members, and varied policy areas. Hard examples should cover these five groups:

1. **Unsupported conclusions:** slogans, ceremonial language, praise without a policy position.
2. **Conditional positions:** support with reservations, package compromises, genuinely mixed provisions.
3. **Speaker confusion:** quoting opponents, reporting another person's position, ambiguous pronouns.
4. **Category boundaries:** overlapping topics, several proposals, bill names without commitments.
5. **Context dependence:** short social posts, sarcasm, missing thread context, boilerplate and repeated announcements.

This is a **balanced diagnostic set**, not a representative estimate of production accuracy. Deliberately including many hard cases changes the distribution.

Fifty statements cannot adequately cover 33 topics, three stance labels, four sources, and party comparisons simultaneously. Record which categories are absent or thin rather than claiming full coverage.

### Step 3 — Establish trustworthy human answers

Have two people label each statement independently **before seeing model suggestions**. Give them the exact archived excerpt and surrounding context that the model will receive.

For each record, retain the source, capture date, member/chamber/party metadata, labels, supporting text, and any ambiguity. Remove explicit party metadata from model input unless needed to interpret the statement; keep it separately for fairness analysis.

Resolve disagreements by applying the rulebook and document the resolution. Do not use another model as the deciding authority. Report initial human agreement as evidence of how consistently the task can be labeled.

If only you can label, do a second pass after at least a week with the previous labels hidden. That helps detect inconsistency, but **it is not independent validation**.

Keep duplicates and related versions together. The same announcement copied to a press release and social account is not two independent examples. Separate development and test material by member where practical, and at minimum by announcement/document family.

### Step 4 — Compare frozen model configurations

Run the same held-out statements through Opus, Sonnet, and Sol, with identical available evidence and equivalent labeling instructions.

Choose prompts and reasoning settings on development material. Then freeze the model ID, prompt, schema, effort, and token cap before testing. If you tune after seeing test errors, those examples become development material; obtain a fresh confirmation set.

Score five things:

| Measure | What to report |
|---|---|
| **Topic** | Exact accuracy, precision/recall by topic, and a confusion table showing commonly confused areas. Mark unsupported categories explicitly. |
| **Stance** | Precision/recall for each stance and a separate count of direct reversals: gold "for," model "against," or vice versa. |
| **Specificity** | Exact agreement, average distance between levels, and serious errors spanning two or more levels. |
| **Priority** | Positive precision, recall, and false-positive rate. A model that always says "routine" must not receive a misleadingly excellent score. |
| **Operational result** | All-four-fields correctness, missing/invalid outputs, abstentions, serious errors, and reviewer time/edit/rejection rates. |

For priority:

- **Precision:** Of the statements labeled "priority," how many actually meet the rule?
- **Recall:** Of the actual priority statements, how many did the model identify?
- **False-positive rate:** Of routine statements, how many were incorrectly elevated to priorities?

For a single-label field such as topic, overall accuracy equals micro-averaged precision when every record receives one prediction. Publish per-category results too; otherwise common topics can hide failures on rare ones.

Count failed calls and abstentions separately and report **coverage**—the share receiving usable suggestions. Do not silently discard failures. A model that defers on almost everything can look precise while being operationally poor.

#### Confidence calibration

Start with a table like this; the numbers are illustrative:

| Confidence word | Number of outputs | All four labels correct | Serious errors |
|---|---:|---:|---:|
| High | 30 | 27/30 = 90% | 1 |
| Medium | 15 | 12/15 = 80% | 1 |
| Low | 5 | 2/5 = 40% | 1 |

"High" in this example means 90% observed whole-record correctness. It does not mean safe to skim.

Measure both **accuracy within the High bucket** and **the fraction of all serious errors labeled High**. Break these down by party and source when counts permit. An overall confidence word can conceal a model that gets topic right but invents priority.

Words provide confidence buckets, not numerical probabilities. Do not arbitrarily translate "High" into 95%. Numerical calibration scores require declared or separately calibrated probabilities, evaluated on fresh data. Research supports evaluating verbalized confidence, but its findings do not establish calibration for these models or this task. [Confidence-calibration research](https://aclanthology.org/2023.emnlp-main.330/)

In the dashboard, present the word as **model self-assessment**. Show the source prominently and require verification of stance and priority regardless of confidence.

### How many statements are enough?

**Fifty is enough to discover obvious failures. It is not enough to certify high precision, close model differences, or party fairness.**

For perspective:

- **49 correct out of 50** is 98% observed accuracy, but its two-sided 95% Wilson interval is approximately **89.5%–99.6%**.
- Even **50/50 correct** gives a one-sided exact 95% lower bound of only **94.2%**.
- With zero errors, establishing a one-sided 95% lower bound above **95%, 98%, or 99%** requires respectively **59, 149, or 299 independent relevant predictions**.

For priority precision, "relevant predictions" means predicted priorities—not every statement tested. These bounds also assume a suitable sampling process; a handpicked challenge set does not certify production performance. [NIST confidence-interval guidance](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm)

A practical progression is:

1. **50 diagnostic statements:** repair definitions and eliminate obvious model/configuration failures.
2. **400–600 fresh held-out statements:** obtain a useful initial performance estimate and source/party breakdowns.
3. **Expand targeted samples:** resolve close comparisons, rare labels, high-confidence errors, or uncertain party gaps.

For close models, compare their answers on the **same statements**. The informative cases are those where one is correct and the other is wrong. Use a paired test such as McNemar's and report a confidence interval for the difference.

Illustrative planning estimates, assuming the models differ in correctness on 10% of statements, 80% statistical power, and a two-sided 5% significance level:

| True accuracy difference | Approximate paired sample needed |
|---|---:|
| 5 percentage points | 314 |
| 3 percentage points | 872 |
| 2 percentage points | 1,960 |

These are approximations for correctness, not universal requirements for every precision measure. Repeated statements from the same members reduce effective independence; account for that by grouping uncertainty calculations by member.

For the larger evaluation, maintain a randomly selected operational sample and a separate challenge set. If sources are deliberately sampled equally, publish source-specific results and weight the operational estimate using the observed collection mix. Do not present the equal-source average as production accuracy.

### Check whether errors lean by party

Use both ordinary party-specific results and comparisons among statements with similar source, topic, gold label, and difficulty.

Focus on five outcomes:

1. **Stance reversals:** Does one party get more incorrectly reversed positions?
2. **Invented priorities:** Does routine messaging become "priority" more often for one party?
3. **Missed priorities:** Does the model overlook explicit commitments more often for one party?
4. **False confidence:** Are errors more often labeled High for one party?
5. **Deferral and reviewer burden:** Does one party receive more unusable suggestions or require more corrections?

Publish numerators and denominators. "Two errors versus one" is not persuasive evidence without the number and types of statements assessed.

A nonsignificant difference does **not** establish fairness; it may reflect insufficient data. Predeclare a tolerable gap—for example, five percentage points—and require the uncertainty interval to fit within that limit before making a parity claim. Finer parity claims require much larger samples.

As an additional diagnostic, swap member names or explicit party identifiers only where the statement's meaning remains unchanged. Changed labels reveal sensitivity to identity cues; this exercise does not replace testing real statements.

Balanced model evaluation also cannot establish balanced **collection**. Track whose statements were collected, from which sources, over what dates. Unequal collection can distort stated-priority lists even with accurate classification.

### Options for the launch bar

These are proposed owner-set thresholds for **raw suggestions before review**, not guarantees about published facts:

| Option | Suggested minimums | Consequence |
|---|---|---|
| **Reviewer-assist pilot** | 90% substantive-field accuracy; serious errors tracked individually | Useful for finding workflow problems, but potentially substantial correction and anchoring risk. |
| **Credibility-first launch — recommended** | Topic and specificity ≥95%; stance-label and positive-priority precision ≥98%; High-confidence whole-record correctness ≥98% | Prioritizes errors that can affect the grade. Requires enough relevant predictions to support the claims. |
| **Strict launch** | ≥99% on consequential precision measures and High-confidence correctness | Greater labeling cost and likely more deferrals/manual work. Still cannot guarantee zero published errors. |

Apply uncertainty bounds to the selected gates, not only point estimates. Set a priority-recall floor and minimum usable coverage too; otherwise precision can be improved merely by avoiding difficult predictions.

Any discovered stance reversal or fabricated priority should trigger investigation, regardless of aggregate score. Fix systematic causes and validate the fix on fresh examples.

Because human approval is the publishing gate, also test the **completed review workflow**: have the owner review model-assisted records, then independently check the final labels against the gold answers. Raw model accuracy does not measure errors that survive review.

For the methods page, publish test dates, sampling method, model/configuration versions, per-field counts and uncertainty intervals, party/source breakdowns, deferrals, and limitations. Distinguish model suggestions from reviewed final results.

## 4. Estimated token costs

**Illustrative estimate per statement:**

- **1,500 input tokens:** instructions, policy definitions, schema, statement and context.
- **150 visible output tokens:** the five-field JSON.
- **850 reasoning tokens:** an assumed planning allowance.
- **1,000 total billed output tokens.**

The reasoning allowance is an estimate, not a measured average. Claude bills internal thinking as output even when it is hidden. [Thinking billing](https://platform.claude.com/docs/en/build-with-claude/thinking-steering-and-cost)

Formula:

`statements × (input_tokens × input_rate + billed_output_tokens × output_rate) / 1,000,000`

| Candidate | 1,000 standard | 10,000 standard | 1,000 batch | 10,000 batch |
|---|---:|---:|---:|---:|
| **Opus 5.5** | **$26** | **$260** | **$13** | **$130** |
| **Sonnet 5.5** | **$13** | **$130** | **$6.50** | **$65** |
| **GPT-6.1 Sol** | **$13** | **$130** | **$6.50** | **$65** |

Both providers document a 50% batch discount. [Anthropic batch processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [OpenAI Batch API](https://developers.openai.com/api/docs/guides/batch)

Actual usage can differ substantially. Each additional 1,000 average output/reasoning tokens adds **$20 per 1,000 statements for Opus**, or **$10 for Sonnet/Sol**, before batch discounts.

These estimates exclude retries, caching, collection, archiving, human review, and integration work. Use actual billed usage from the evaluation to replace them.

Under these assumptions, Opus costs **$65 more than Sonnet per 10,000 batch-processed statements**. Saving just five seconds of review per statement would save nearly 14 hours over that volume—so reviewer performance should drive the decision.

## 5. Settings and operating rules

1. **Reasoning effort:** Start Opus at `medium`, Sonnet at `high`, and Sol at `medium`. Compare alternative efforts on development examples and freeze the selected configuration before testing. Opus thinking cannot be disabled; Sol supports `low` through `max`, but not `none` or `minimal`. [Claude effort](https://platform.claude.com/docs/en/build-with-claude/effort), [OpenAI reasoning settings](https://developers.openai.com/api/docs/guides/latest-model)

2. **Structured output:** Use native JSON Schema, require all five keys, restrict allowed values, and disallow extra properties. Anthropic uses `output_config.format`; OpenAI Responses uses `text.format` with strict JSON Schema. Validate locally and route refusals, incomplete responses, and invalid values to manual handling—valid JSON does not establish valid interpretation. [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

3. **Sampling and token limits:** Omit temperature and other sampling controls for the initial configurations. Sonnet 5.5 rejects non-default sampling settings; reasoning-enabled OpenAI requests also restrict them. Start with a **4,096-token output cap**, which must accommodate reasoning and JSON; raise it if evaluation shows meaningful truncation. Repeat a small set of difficult inputs to measure instability. [Sonnet parameter restrictions](https://platform.claude.com/docs/en/models/sonnet-5-5/overview), [OpenAI parameter guidance](https://developers.openai.com/api/docs/guides/latest-model)

4. **Batch and caching:** Use batch processing for collected statements, with unique record IDs so results cannot attach to the wrong source. Plan for a 24-hour processing window and incomplete/expired requests. Keep the shared instructions stable for possible caching, but estimate savings from observed cache hits. [Anthropic batch behavior](https://platform.claude.com/docs/en/build-with-claude/batch-processing), [OpenAI batch behavior](https://developers.openai.com/api/docs/guides/batch)

5. **Evidence and audit trail:** Give each call one statement with sufficient archived context, no browsing tools, and instructions to treat quoted source content as data. Prohibit inference from party reputation, motives, or outside knowledge. Record model ID, prompt/schema versions, effort, input hash, usage, raw suggestion, final human decision and edits; revalidate meaningful configuration changes.

**Verified:** current model IDs, listed prices, documented settings, and cost/interval arithmetic. **Untested:** classification performance, confidence calibration, party gaps, and reviewer outcomes.

**Next: label one slogan such as "I stand with our farmers" and decide how the workflow records "no supported stance."**
