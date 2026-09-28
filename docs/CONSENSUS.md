# Consensus

How one reading of an agent's evidence becomes one typed credential, and what
validators may and may not differ on.

## The exact nondeterministic calls

Two, and no others:

| Call | Where | What it does |
|---|---|---|
| `gl.nondet.web.get(url)` | `_fetch_source`, once per declared evidence item | retrieves the bytes, derives the source status from the HTTP answer and the content type, normalises the text a reader sees, takes the sha256 of the raw bytes and of the normalised text, extracts the title |
| `gl.nondet.exec_prompt(..., response_format="json")` | `_node_round`, once per round | asks the panel for readings, and only readings |

Both sit inside one `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` per
assessment. There is no other source of nondeterminism: no clock read, no
random, no float arithmetic on a decision path.

## What every node does

`_node_round(ctx)`, on the leader and on every validator:

1. retrieves every item the claim declared (`_retrieve`);
2. verifies integrity: a `PINNED` item whose bytes do not hash to the sha256
   the claimant declared at filing is recorded `DIGEST_MISMATCH` and becomes
   unreadable - neither the evidence that was filed nor something quotable;
3. scans in code for text addressed to the verifier (`_markers`): the visible
   text, the markup and attributes a reader never sees, the title;
4. records which readable `DEMONSTRATION` items contain the agent's name
   (`_names_agent`) - the `named` list;
5. derives the code reason (`_code_reason`): a mismatch, nothing readable, an
   item addressing the verifier, no readable demonstration, or no
   demonstration naming the agent decides the round **without the panel**;
6. otherwise convenes the panel once and reduces each subject's answer to a
   finding (`_normalize_finding`), re-grounding every quote in this node's own
   text.

The payload the leader returns holds one source record per declared item, the
markers, the named list, the code reason, the panel state and one finding per
subject. **It contains no verdict, no reason code, no scope and no expiry** -
those are code's, derived from the findings.

## What the validator does

`_validator_decision` does not check the leader's JSON and stop. It:

1. **reproduces the round** from its own retrieval and its own model call;
2. runs the strict gate on the leader's payload **with its own texts**, so every
   quote must ground in the bytes this validator fetched;
3. compares what was retrieved (`_evidence_difference`);
4. derives its own credential and compares the consequence
   (`_consequence_difference`);
5. prints the reason for every refusal, so a rotation is diagnosable.

A well-formed but substantively false leader result is refused at step 2, 3 or 4.

## The structural gate

`_parse_payload` runs twice: on the leader's payload during validation, and
again on the ratified payload before anything is stored. It requires exact keys
and types; the same mode, claim, round, standard hash, commitment and
transaction time; one source record per declared item in order, each internally
consistent; a marker list that is sorted, unique and names only readable items
and real places; a named list that is sorted, unique and names only readable
`DEMONSTRATION` items; the code reason recomputed from those records; and one
finding per subject, in order, with clean notes and every quote contiguous,
within length, unique and grounded in this node's retrieval of an item it may
cite.

Which items a quote may cite depends on the reading. A reading about the
agent's own work - `DEMONSTRATED` or `FAILED` - may quote only a readable
`DEMONSTRATION` item that names the agent (`_quotable`). A feature list cannot
carry a demonstration, and another agent's run log can carry neither a
demonstration nor a failure.

Types are checked, not coerced: a boolean where an integer belongs, a float
where an integer belongs, an extra field, a missing field, or a state outside
the subject's vocabulary each refuse the payload.

## Decision-critical fields

**What was retrieved** (`_evidence_difference`): the panel state and code
reason, the marker list, the named list, and for every item its status, HTTP
status and truncation - plus, for a `PINNED` item, its byte count, normalised
content digest, raw sha256, title and content type.

**What it leads to** (`_consequence_difference`), derived by code:

| Field | Compared |
|---|---|
| `verdict` | every round |
| `reason_code` | every round |
| `scope` - the requirements a positive credential covers | every round (empty when negative) |
| `statuses` (each item's) | every round |
| `digests` (each `PINNED` item's raw sha256) | every round |

## Equivalence: what may differ

Notes, which passage the panel chose to quote, the readings no rule reached,
and everything about a `LIVE` item beyond its status. A `LIVE` item still has to
carry every quote the leader cites, in each validator's own retrieval.

The comparison carries values, not implications. A reason already fixes the
reading it names, and the scope already names every requirement a positive
credential rests on; comparing those readings a second time would pin nothing,
and comparing readings no rule reached would split a round over findings that
cannot change the credential. Each stored finding says whether it was fixed by
what was compared (`compared: true`): a requirement in the scope, every
required requirement under `NOT_DEMONSTRATED`, the consistency reading under a
contradiction.

## Forged-leader defence

| Forgery | What stops it |
|---|---|
| a credential the readings do not support | the consequence comparison: each validator derives its own |
| a wider scope than the evidence shows | `scope` is compared |
| a demonstration quoted from a feature list | `_quotable`: an `ASSERTION` cannot carry one, in the gate |
| a demonstration or a failure quoted from another agent's run | `_quotable`: only items that name the agent |
| a named list that promotes an assertion, or hides a real demonstration | the gate (subset of readable demonstrations) and the evidence comparison |
| a claimed code decision - "no demonstration names the agent" - to skip the panel | the reason is recomputed from the records, and `named` is compared |
| a quote that is not in the evidence | grounding, in each validator's own bytes |
| a spliced quote assembled from distant passages | `_spliced` refuses an ellipsis, even though grounding would walk its parts |
| a digest or status that was not what was fetched | the evidence comparison |
| a marker list hiding an injection | the markers are compared, and the reason recomputed |
| a payload about another claim, round or moment | the identity fields are compared against the round's own context |
| malformed JSON, extra fields, wrong types | the gate |

## Failure semantics

| Situation | Result |
|---|---|
| a `PINNED` item's bytes are not the ones filed | `INSUFFICIENT_EVIDENCE` / `EVIDENCE_DIGEST_MISMATCH`, in code |
| no item readable | `INSUFFICIENT_EVIDENCE` / `NO_EVIDENCE_READABLE`, in code |
| an item addresses the verifier | `INSUFFICIENT_EVIDENCE` / `SOURCE_ADDRESSES_VERIFIER`, the whole round, in code |
| nothing but assertions declared | `INSUFFICIENT_EVIDENCE` / `ASSERTIONS_ONLY`, in code |
| no demonstration names the agent | `INSUFFICIENT_EVIDENCE` / `AGENT_NOT_NAMED`, in code |
| the model's answer is unusable | `INSUFFICIENT_EVIDENCE` / `PANEL_UNUSABLE` |
| the items contradict each other | `INSUFFICIENT_EVIDENCE` / `EVIDENCE_CONTRADICTORY` |
| a required reading is unclear, or asserted without a quote | `INSUFFICIENT_EVIDENCE` / `REQUIREMENT_UNCLEAR` |
| a positive credential would rest on one origin, or on unbound bytes | `INSUFFICIENT_EVIDENCE` / `CORROBORATION_SHORT` |
| the model call fails on a node | `[TRANSIENT]`, ratified only by another transient failure |
| validators disagree | no majority, nothing stored, the claim stays `PENDING` until its window passes |

**A failed observation is never a failed agent.** `NOT_VERIFIED` is reserved
for evidence that was read and does not demonstrate the capability;
everything that could not be read or judged is `INSUFFICIENT_EVIDENCE`. And
nothing in the derivation turns an unreachable document, an unusable answer or
an unclear reading into a credential.

A leader that raised is ratified only by the same deterministic failure, or by
a transient failure meeting a transient one; a model failure (`[LLM_ERROR]`) is
never ratified, and a leader that failed where the validator succeeded is
refused.

## Why consensus is load-bearing here

Delete it and either the agent - the party with the most to gain - writes its
own credential, or one platform reviewer decides in private. A signature
cannot take that place: it proves who wrote a test report, not that the report
shows the capability. The question is a reading of prose requirements against
execution evidence, which is exactly what several independent validators can
each perform on bytes they fetch themselves, and compare.

What consensus is **not** asked for: whether a document names the agent, which
items are demonstrations, how many independent origins a credential rests on,
the integrity of the bytes, the scope, the expiry, or the identity of anyone.
Code owns all of that.

<!-- LIVE:START -->
## Live findings

Filled from the run of record.
<!-- LIVE:END -->
