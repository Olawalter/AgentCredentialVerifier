<p align="center">
  <img src="docs/assets/acv-mark.svg" width="84" height="84" alt="AgentCredentialVerifier">
</p>

<h1 align="center">AgentCredentialVerifier</h1>

## Thesis

**AgentCredentialVerifier is a reusable GenLayer Intelligent Contract that
decides whether an agent's evidence actually demonstrates a capability - judged
against a standard published before the claim existed, with the agent's own
description treated as a claim and never as evidence - and issues a typed,
expiring, machine-readable credential a marketplace can read in one call.**

<!-- DEPLOYMENT:START -->
## Canonical deployment

[`0xCD691bD37c11a3c9585340c3eC65E929073a184d`](https://explorer-studio.genlayer.com/address/0xCD691bD37c11a3c9585340c3eC65E929073a184d)
on GenLayer StudioNet (chain id 61999), from commit `589c561`, deployed source
read back with `gen_getContractCode` and **byte-identical** to this repository.
Deployment transaction
[`0x38977f7695b9a4fbf08ba4a54d489cc5438415b4486c636e83b59e4dd49033cf`](https://explorer-studio.genlayer.com/tx/0x38977f7695b9a4fbf08ba4a54d489cc5438415b4486c636e83b59e4dd49033cf),
FINALIZED, leader execution SUCCESS, votes AGREE x3.
<!-- DEPLOYMENT:END -->

## The problem

An agent says:

> "I can retrieve and verify shipping documents."

Today the only thing behind that sentence is the agent's own description, or a
platform that took the operator's word for it. A marketplace that routes real
work on it is trusting the party with the most to gain from a yes.

The evidence that would settle it usually exists - a conformance run, a
verification report, a previous output - but reading it means answering
questions no signature and no scanner can: does this run record *this* agent
doing the thing, or another agent? Does this page show the work done, or only
describe it? Did the test pass, or was it skipped? Does it cover every part of
the capability, or only some?

AgentCredentialVerifier turns that reading into a record: a standard published
before any claim, a claim with evidence bound to its bytes, and a typed
credential several independent validators had to agree on.

## Why GenLayer

The decision is a reading of prose requirements against execution evidence,
made where the claimant supplies the evidence. It needs:

- interpretation of test logs, reports and outputs against written
  requirements;
- independent retrieval, because the party supplying the evidence is the party
  judged;
- a leader whose proposed reading other validators can reject on substance, not
  on formatting;
- a record a marketplace can act on without trusting whoever produced it.

## Delete GenLayer: what breaks?

Either the agent writes its own credential - the self-description this contract
exists to refuse - or one platform reviewer decides in private, with nothing a
consumer can check. A signature scheme does not fill the gap: it proves who
wrote a test report, not that the report shows the capability.

## A description is a claim, never evidence

Three rules, two of them in code:

| Rule | Where | What it refuses |
|---|---|---|
| a claim with no readable `DEMONSTRATION` never reaches the panel | code: `ASSERTIONS_ONLY` | a feature list, a profile, documentation - on its own |
| a demonstration must contain the agent's name | code: `AGENT_NOT_NAMED`, and the gate for every quote | another agent's passing run, filed as this one's |
| text that states a capability without recording it done is read as such | the panel: `ASSERTED_ONLY` | a brochure labelled `DEMONSTRATION` |

And the mirror, which is what makes a negative credential fair: a **failure**
must be quoted from a record of this agent's own work too, so another agent's
failed run can never mark this one `NOT_VERIFIED`.

## Why this is not a rejected pattern

| Rejected pattern | AgentCredentialVerifier |
|---|---|
| "ask an LLM whether this agent is good" | asks whether specific evidence demonstrates requirements written before the claim |
| a model that produces the answer | the model returns readings only; code derives the verdict, the reason, the scope and the expiry |
| a reputation score | a scoped, expiring credential per standard - no number to compare across contexts |
| a directory of agents and their claims | the claims are exactly what is not trusted |

## Lifecycle

```
publish_standard ───────────────────────── immutable, hashed, versioned
        │
        ├─ retire_standard (issuer: no new claims; issued credentials stand)
        │
   file_claim ── assess ──┬── contest (once, in window, claimant or issuer)
        │                 │
        │                 └── finalize (anyone, after the window) ── FINAL
        │                                                             │
        ├─ withdraw_claim (claimant, before assessment)      check_credential
        └─ lapse_claim (anyone, if nobody assessed it in time)   (until expiry)
```

## Example standard

```json
{
  "name": "Shipping document retrieval and verification",
  "capability": "Retrieves a shipping document from a carrier portal, verifies it
    against the issuing registry, and flags a copy that has been altered.",
  "requirements": [
    {"requirement_id": "retrieve", "description": "...", "required": true},
    {"requirement_id": "verify", "description": "...", "required": true},
    {"requirement_id": "flag_altered", "description": "...", "required": true}
  ],
  "evidence_domains": ["raw.githubusercontent.com", "cdn.jsdelivr.net"],
  "min_independent_origins": 2,
  "validity_seconds": 2592000,
  "assess_window": 1800,
  "contest_window": 900,
  "spec_version": 1
}
```

A claim against it names the agent as its outputs name it, carries the agent's
own description (labelled a claim), and declares up to four evidence items from
those hosts - each `PINNED` with the sha256 of its exact bytes or `LIVE` with
none, and each a `DEMONSTRATION` or an `ASSERTION`.

## The credential

| Verdict | Means |
|---|---|
| `VERIFIED` | every required requirement demonstrated, on bound bytes, across the standard's independent origins |
| `PARTIALLY_VERIFIED` | some required requirements demonstrated; `scope` names which |
| `NOT_VERIFIED` | the evidence was read and records a failure, only describes the capability, or does not demonstrate it |
| `INSUFFICIENT_EVIDENCE` | the evidence could not be read or judged - never a finding against the agent |

## Contract surface

| Writes | |
|---|---|
| `publish_standard`, `retire_standard` | the standard, and closing it to new claims |
| `file_claim`, `withdraw_claim` | one open claim per agent per standard |
| `assess`, `contest` | one consensus round each; contest at most once, by the claimant or the issuer |
| `finalize`, `lapse_claim` | permissionless exits, after the relevant window |

| Views | |
|---|---|
| `check_credential` | the consumer's one call: verified, partially verified, scope, final, expiry |
| `get_verdict` | one claim's answer, with the standard hash it was judged under |
| `get_evidence_status` | per item: kind, role, status, whether it names the agent, whether it was compared |
| `get_claim`, `get_resolution`, `get_latest_resolution`, `get_history` | the claim and every round behind it |
| `get_standard`, `get_standard_hash` | the standard as published |
| `get_actions`, `list_standards`, `list_claims`, `get_stats`, `get_config` | what may happen next, paging, counts, the vocabulary |

22 methods: 14 views, 8 writes, none payable.

## Nondeterministic operations

Exactly two, both inside one `run_nondet_unsafe` per assessment:
`gl.nondet.web.get` once per declared evidence item, and
`gl.nondet.exec_prompt(..., response_format="json")` once per round. The panel
is asked, for each requirement, whether the evidence demonstrates it, only
asserts it, records the agent failing it, does not show it, or cannot be read -
and whether the items agree with each other. Nothing else.

## Deterministic responsibilities

Identity (the credential is keyed by the claimant's wallet); the standard, its
hash and the version a claim commits to; every field limit; URL admission; the
permitted evidence sources; evidence integrity, by verifying a declared sha256
against the bytes fetched; which items are readable, unavailable, mismatched or
addressed to the verifier; each item's role; whether a demonstration names the
agent; how many independent origins a positive credential rests on; the verdict,
its reason, its scope and its expiry; windows; one open claim per agent per
standard; and every state transition.

## Equivalence / validator design

Validators reproduce the round from their own retrieval and their own model
call, then compare the **consequence**: the verdict, the reason, the scope, each
item's status, and each `PINNED` item's digest - plus what was retrieved,
including which items name the agent. Not compared: notes, which passage was
quoted, and readings no rule reached. A leader payload that is well-formed but
substantively false is refused, and the refusal is printed. Details:
[`docs/CONSENSUS.md`](docs/CONSENSUS.md).

## Safety and failure semantics

Every ambiguity fails closed on the positive path: unreadable evidence, a digest
that does not match, an item addressing the verifier, only assertions, no
demonstration naming the agent, an unusable model answer, contradictory
documents, an unclear reading, too few independent origins or unbound bytes -
each produces `INSUFFICIENT_EVIDENCE`, never a credential. And the negative path
is guarded too: `NOT_VERIFIED` needs a failure quoted from the agent's own
record, or a reading of evidence that does not demonstrate the capability. A
failed fetch is never a failed agent. Where validators disagree, the round
stores nothing. [`docs/SECURITY.md`](docs/SECURITY.md).

## Reuse surface

```python
answer = IAgentCredentialVerifier(ACV).view().check_credential(agent, standard_id, now)
if not answer["verified"]:
    raise gl.vm.UserError("[EXPECTED] that agent holds no current credential for this work")
```

No web access, no prompts, no equivalence principle, no parsing of the evidence.
Three consumers read the same contract: marketplaces gating listings, routers
splitting work by `scope`, and auditors reading the record behind a credential.
[`docs/INTEGRATION.md`](docs/INTEGRATION.md).

## Limitations

- **A credential is not a guarantee.** It means the filed evidence demonstrated
  the standard's requirements when it was read - nothing broader. That is what
  the expiry is for.
- The claimant chooses the evidence. A standard narrows where it may come from
  and how many publishers it must span; a standard that names weak sources gets
  weak credentials.
- Whether a document names the agent is a string test; whose work a run records
  is a model reading. Where honest models split, the round stores nothing.
- The contract judges demonstrations, not the agent's code.
- One contest per claim, for whichever party uses it first; the second reading
  is of the same bound bytes.
- Identity is a wallet. The caps bound abuse; they do not stop one operator from
  using several wallets.
- ShipDocs Agent 7, CargoScan Bot, the carrier portal and the registry in the
  demonstration are fixtures that exist only in this repository.

## Verification

<!-- VERIFIED:START -->
| Check | Result |
|---|---|
| `python -m pytest tests/direct -q` | 130 passed |
| pickling of the nondeterministic closures | checked (`direct_vm.check_pickling = True`) |
| `genvm-lint check contracts/agent_credential_verifier.py --json` (`GENVM_VERSION=v0.3.0-rc7`) | lint ok (3 checks), validation ok, 22 methods (14 view, 8 write), exit 0 |
| `ruff check .` | clean |
| `python scripts/generate_fixtures.py --check` | 11 fixture files regenerate byte for byte |
| `python scripts/mutation_check.py` | 86 mutations, **86 killed, 0 survived** |
| `python scripts/deploy_studionet.py --verify` | deployed and repository sha256 equal, 22 schema methods |
| `python -m pytest tests/integration -q` | 7 passed, 1 skipped (the opt-in live write) |
| live run of record | 42 transactions, **17 of 17 outcomes held**, 11 of 11 refusals refused |

Every verdict was reached by real transactions against the canonical
deployment: a full credential resting on two origins, a partial one scoped to
what was shown, a failure quoted from the agent's own run, a brochure read as
`ONLY_ASSERTED`, and each code-decided refusal of evidence - assertions only,
another agent's run, a digest that did not match, unpublished evidence, an
injection, one origin, unbound bytes, a contradiction. Then the issuer's contest,
three credentials finalised and read back through `check_credential`, a lapse,
and eleven refusals. A diagnostic pass before it recorded the same 17 of 17:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md#live-run-of-record).
<!-- VERIFIED:END -->

## Reviewer fast path

1. [`DECISION.md`](DECISION.md) - the specification, written before the
   contract, the collision audit against the owner's own portfolio, and what was
   deliberately left out.
2. [`docs/CONSENSUS.md`](docs/CONSENSUS.md) - the two nondeterministic calls,
   the gate, and what validators compare.
3. `contracts/agent_credential_verifier.py` - `_verdict_for` is the whole
   derivation; `_code_reason` and `_quotable` are the three rules above.
4. [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) - the canonical deployment, and a
   transaction table for every verdict, the contest, finality and the refusals.
5. `tests/direct/test_acv_adversarial.py` - the attacker list, one test at a
   time.

## Licence

MIT. See [`LICENSE`](LICENSE).
