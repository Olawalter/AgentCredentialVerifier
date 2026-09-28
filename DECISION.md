# Decision record - AgentCredentialVerifier

Written before the contract. It fixes what the contract decides, what it
refuses to decide, and why each boundary sits where it does.

## The trust question

An agent marketplace, a router, or another agent is about to hand a task to an
agent that says:

> "I can retrieve and verify shipping documents."

Today the only thing behind that sentence is the agent's own description, or a
platform that took the operator's word for it. The question this contract
answers is narrower and harder:

> Given a capability standard published before this claim existed, does the
> evidence this agent filed actually **demonstrate** each thing the standard
> says the capability requires - as opposed to describing it, promising it, or
> showing some other agent doing it?

The output is a typed credential: `VERIFIED`, `PARTIALLY_VERIFIED`,
`NOT_VERIFIED` or `INSUFFICIENT_EVIDENCE`, with the requirements it covers,
the reason, the bytes it rests on, and an expiry.

## The delete-GenLayer test

Delete GenLayer and one of two things decides the credential:

- **the agent**, through its own description - the party with the most to gain
  from a positive answer writes it;
- **the platform**, through a reviewer or a backend model - one private
  judgement, with no way for a consumer to check what it read or why.

Neither a signature scheme nor a scanner fills the gap. A signature proves who
wrote a test report, not that the report shows the capability. The question is
a reading of prose requirements against execution evidence - test results,
previous outputs, logs - which several independent validators can each perform
on bytes they retrieve themselves, and compare.

## One primitive

A **capability standard** is published by an issuer (a marketplace, a
registry, a buyer) before any claim. An agent files a **claim** against it with
up to four evidence items. One consensus round produces the credential. A
consumer reads one view keyed by the agent's wallet and the standard.

What it is not: a reputation score (RepMerit, AgentPassport), a task escrow
(AgentPassport, AgentSLA), an authorization gate (MANDATE), a dispute court
(Court of Agents). Those answer "how has this agent behaved" or "was this
agreement met". This answers "is this specific capability demonstrated", before
any task is handed over.

## Collision audit (the owner's own portfolio, 52 repositories)

| Nearest | What it decides | Why this is different |
|---|---|---|
| RepMerit | a general reputation number from evidence URLs about an agent | no predeclared rubric, no per-requirement demonstration, a score not a scoped credential; self-published links are read as evidence |
| AgentPassport | whether a worker satisfied one task, with escrow and reputation deltas | judges a completed task after the fact; this certifies a capability before a task exists |
| MANDATE | whether an agent is still authorized to take one action, given world conditions | permission, not competence |
| AgentSLA Core | whether a provider met an agreement's requirements | an agreement between two parties with funds; this is one-sided, non-payable, reusable by any consumer |
| Court of Agents | which of two parties wins a dispute | adversarial two-party ruling; no evidence integrity, no standard |

## The rule that makes it a credential and not a review

**A description is a claim, never evidence.** Three mechanisms enforce it, the
first two in code:

1. Every evidence item is declared with a **role**: `DEMONSTRATION` (a test
   result, a previous output, a run log) or `ASSERTION` (documentation, a
   profile, the agent's own description). A claim with no readable
   demonstration never convenes the panel: `INSUFFICIENT_EVIDENCE /
   ASSERTIONS_ONLY`, decided in code.
2. A reading of `DEMONSTRATED` may only quote a `DEMONSTRATION` item that
   **names the agent** - the `agent_name` filed with the claim must occur in
   that item's text. Evidence of some other agent doing the work cannot carry a
   demonstration; if no readable demonstration names the agent, the round
   ends in code: `INSUFFICIENT_EVIDENCE / AGENT_NOT_NAMED`.
3. The panel has a state for the thing a review usually misses:
   `ASSERTED_ONLY` - the item states the agent can do it, without showing it
   done. A claimant who labels a brochure `DEMONSTRATION` still gets
   `ASSERTED_ONLY`, and the credential is `NOT_VERIFIED`.

## Responsibility split

**Deterministic code owns:** identity (the claimant is the signer, and the
credential is keyed by that wallet); the immutable standard and its hash; the
spec version a claim commits to; every field limit; URL admission; the
standard's evidence domains; evidence integrity (a `PINNED` item's declared
sha256 checked against the bytes fetched, every round); which items are
readable, unavailable, mismatched, or addressed to the verifier; the role of
each item; whether a demonstration names the agent; how many independent
origins a positive credential rests on; the verdict, its reason and its scope;
windows and expiry; one open claim per agent per standard; every transition.

**GenLayer consensus owns meaning:** for each requirement, whether the
evidence demonstrates it, only asserts it, shows the agent failing it, does not
show it, or cannot be read; and whether the items agree with each other.

**The model never returns a verdict, a reason code, a scope or an expiry.**

## The standard (immutable, hashed)

```json
{
  "name": "Shipping document retrieval and verification",
  "capability": "Retrieves a shipping document from a URL, verifies it against the issuing registry, and flags one that has been altered.",
  "requirements": [
    {"requirement_id": "retrieve", "description": "...", "required": true},
    {"requirement_id": "verify",   "description": "...", "required": true},
    {"requirement_id": "flag_altered", "description": "...", "required": true}
  ],
  "evidence_domains": ["raw.githubusercontent.com", "cdn.jsdelivr.net"],
  "min_independent_origins": 2,
  "validity_seconds": 2592000,
  "assess_window": 3600,
  "contest_window": 900,
  "spec_version": 1
}
```

Exactly these keys. 1-4 requirements, at least one required. 1-4 evidence
domains. `min_independent_origins` no larger than the number of domains.

## The claim

`file_claim(standard_id, standard_hash, agent_name, agent_description,
evidence_json)`

- `agent_name` - the name the agent's outputs carry. It must occur in every
  demonstration a positive reading rests on.
- `agent_description` - the agent's own account. Shown to the panel labelled
  as a claim to test; never evidence.
- `evidence_json` - 1-4 items `{url, kind, role, sha256, label}`:
  - `kind` `PINNED` (sha256 declared, verified every round) or `LIVE` (bytes
    unbound, and **never** enough for a positive credential);
  - `role` `DEMONSTRATION` or `ASSERTION`.

One open claim per wallet per standard. A new claim may be filed once the last
is final or cancelled; that is how a credential is renewed.

## State machine

```text
file_claim ──► PENDING ──assess──► ASSESSED ──(contest window)──► finalize ──► FINAL
                 │  │                  │
                 │  └─withdraw──► CANCELLED (WITHDRAWN)
                 └──window passes, lapse_claim──► CANCELLED (LAPSED)
                                       └─contest (claimant or issuer, once)──► ASSESSED, round 2
```

A standard is `ACTIVE` until its issuer retires it. Retiring stops new claims;
credentials already issued keep their expiry.

## The panel's subjects

| Subject | States | Quote required for |
|---|---|---|
| `EVIDENCE_CONSISTENCY` | `CONSISTENT`, `CONTRADICTORY`, `UNCLEAR` | `CONTRADICTORY` |
| `REQ_<id>`, one per requirement | `DEMONSTRATED`, `ASSERTED_ONLY`, `FAILED`, `NOT_DEMONSTRATED`, `UNCLEAR` | `DEMONSTRATED`, `FAILED` |

A `DEMONSTRATED` quote must cite a readable `DEMONSTRATION` item that names
the agent. Every quote is re-grounded by every validator in its own bytes.

## The derivation (code, fail-closed, in this order)

1. a `PINNED` item's bytes differ from the declared sha256 -> `INSUFFICIENT_EVIDENCE / EVIDENCE_DIGEST_MISMATCH`
2. no item readable -> `INSUFFICIENT_EVIDENCE / NO_EVIDENCE_READABLE`
3. an item addresses the verifier -> `INSUFFICIENT_EVIDENCE / SOURCE_ADDRESSES_VERIFIER`
4. no readable `DEMONSTRATION` item -> `INSUFFICIENT_EVIDENCE / ASSERTIONS_ONLY`
5. no readable `DEMONSTRATION` item names the agent -> `INSUFFICIENT_EVIDENCE / AGENT_NOT_NAMED`
6. (1-5 skip the panel.) The panel's answer is unusable -> `INSUFFICIENT_EVIDENCE / PANEL_UNUSABLE`
7. the items contradict each other -> `INSUFFICIENT_EVIDENCE / EVIDENCE_CONTRADICTORY`
8. a required requirement `FAILED` -> `NOT_VERIFIED / DEMONSTRATION_FAILED`
9. a required requirement `UNCLEAR` -> `INSUFFICIENT_EVIDENCE / REQUIREMENT_UNCLEAR`
10. no required requirement demonstrated: any `ASSERTED_ONLY` -> `NOT_VERIFIED / ONLY_ASSERTED`, otherwise `NOT_VERIFIED / NOT_DEMONSTRATED`
11. the demonstrations rest on a `LIVE` item, or on fewer independent origins than the standard requires -> `INSUFFICIENT_EVIDENCE / CORROBORATION_SHORT`
12. every required requirement demonstrated -> `VERIFIED / CAPABILITY_DEMONSTRATED`
13. some -> `PARTIALLY_VERIFIED / PARTIAL_DEMONSTRATION`

Origins are distinct **hosts** behind the quotes of the demonstrated required
requirements; two pages of one publisher are one origin.

The **scope** of a positive credential is the list of requirements - required
or not - read `DEMONSTRATED` on bound bytes.

`NOT_VERIFIED` means the evidence was read and does not demonstrate the
capability. `INSUFFICIENT_EVIDENCE` means it could not be read, or could not be
judged. The two are never collapsed: a failed fetch is not a failed agent.

## What validators compare

Retrieval: panel state and code reason, the marker list, each item's status,
HTTP answer and truncation, and for a `PINNED` item its bytes, digests, title
and content type.

Consequence: `verdict`, `reason_code`, `scope`, each item's status, each
`PINNED` item's raw sha256. Values, not implications: a reason already fixes the
reading it names, so readings are not compared a second time.

## Why non-payable

A credential is a signal. The marketplace that acts on it holds its own funds,
and a verifier that also held stakes would have a reason to prefer an answer.

## Three consumers

| Consumer | Reads |
|---|---|
| an agent marketplace | `check_credential(agent, standard_id, as_of)`: one boolean, final, unexpired |
| a task router | the `scope` of a `PARTIALLY_VERIFIED` credential, to route only the demonstrated parts |
| an auditor | the full resolution: every item's status and digest, the quotes, what was compared |

## Deliberately left out

- **Revocation by the issuer.** An issuer who can revoke is an issuer who can
  bury a competitor. Expiry bounds staleness instead; renewal is a new claim.
- **A numeric score.** A number invites comparison it cannot support.
- **Grading the agent's code.** The contract judges demonstrations, not source.
- **A frontend.** The contract is the product; the consumer view is the API.
