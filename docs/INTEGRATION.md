# Integration

How a marketplace, a router or another Intelligent Contract reads an agent's
credential without reinterpreting storage.

## The consumer's interface

A consumer needs one view:

```python
@gl.contract_interface
class IAgentCredentialVerifier:
    class View:
        def check_credential(self, agent: str, standard_id: str, as_of: str) -> dict: ...
        def get_verdict(self, claim_id: str) -> dict: ...
        def get_standard_hash(self, standard_id: str) -> dict: ...

    class Write:
        pass
```

Gating a task on a capability, inside another contract:

```python
ACV = Address("0x...")                  # the canonical deployment
SHIPPING_DOCS = "CS-000001"             # the standard this marketplace trusts

now = str(gl.message_raw["datetime"])[:19] + "Z"
answer = IAgentCredentialVerifier(ACV).view().check_credential(agent, SHIPPING_DOCS, now)

if not answer["verified"]:
    raise gl.vm.UserError("[EXPECTED] that agent holds no current credential for this work")
# from here the marketplace's own rules apply
```

`verified` is already the conjunction a consumer wants: the latest final claim
of that agent against that standard is `VERIFIED` and has not expired. The
consumer needs **no** web access, **no** prompt, **no** equivalence principle
and **no** parsing of the evidence. That is the whole reuse surface.

A router that can split work reads the scope instead:

```python
if answer["partially_verified"] and "retrieve" in answer["scope"]:
    ...   # hand this agent the retrieval step only
```

## What each view answers

| Method | Returns |
|---|---|
| `check_credential(agent, standard_id, as_of)` | `found`, `verified`, `partially_verified`, `verdict`, `reason_code`, `scope`, `final`, `expires_at`, `expired`, `claim_id`, and the `standard_hash` it was judged under. The agent is the claimant's wallet, in any letter case |
| `get_verdict(claim_id)` | one claim's answer: `verdict`, `reason_code`, `scope`, `final`, `assessed_at`, `expires_at`, `resolution_id`, `rounds` |
| `get_evidence_status(claim_id)` | per item: its kind, role, status, whether it names the agent and whether it was compared; plus the independent origins a positive credential rested on, whether the bytes were bound, and any markers |
| `get_claim(claim_id)` | the claim as filed, including the agent's own description - flagged `description_is_a_claim` - and the evidence list with its commitment |
| `get_resolution(resolution_id)` / `get_latest_resolution` | one full record: every reading with its `compared` flag, every source record, the named list, the markers, the panel state, the excerpt |
| `get_history(claim_id)` | one line per round: mode, verdict, reason, scope |
| `get_standard(standard_id)` / `get_standard_hash` | the standard as published, its hash and version, and whether it still accepts claims |
| `get_actions(claim_id, as_of)` | what can happen next, and who may do it |
| `list_standards` / `list_claims` / `get_stats` / `get_config` | paging, counts, and the vocabulary every field above uses |

A view has no clock, which is why `check_credential` and `get_actions` take
`as_of`. Every write checks its own transaction time.

## Reading a credential correctly

1. **Only a final claim is a credential.** A claim inside its contest window can
   still be read again once. `check_credential` answers only with final claims.
2. **The latest final claim is the answer.** A renewal that fails replaces a
   credential that passed: the view reports what the agent most recently
   demonstrated, not the best it ever did.
3. **`INSUFFICIENT_EVIDENCE` is not `NOT_VERIFIED`.** The first means the
   evidence could not be read or judged - unpublished, altered, only
   descriptions, someone else's run, an injection, too few origins. The second
   is a finding: the evidence was read and a failure was recorded, or nothing
   demonstrated the capability. A consumer that treats both as "cannot do it"
   loses a distinction the contract took care to keep.
4. **The scope is the standard's own vocabulary.** It names `requirement_id`s
   of the standard the credential was judged under; read them against
   `get_standard`, not against a global list of skills.

## The three consumers, concretely

| Consumer | Call | Reaction |
|---|---|---|
| agent marketplace | `check_credential` | list the agent for this kind of task only while `verified` is true |
| task router | `check_credential`, reading `scope` | route only the demonstrated steps to a partially verified agent |
| auditor | `get_latest_resolution` | read which documents each reading quoted, which items named the agent, and what was compared |

## Writing, for the parties who do

| Method | Who |
|---|---|
| `publish_standard(standard_json)` | anyone; the sender becomes the issuer. Fields: [`../DECISION.md`](../DECISION.md#the-standard-immutable-hashed) |
| `retire_standard(standard_id)` | the issuer; stops new claims, leaves issued credentials standing |
| `file_claim(standard_id, standard_hash, agent_name, agent_description, evidence_json)` | the agent's wallet; one open claim per standard |
| `withdraw_claim(claim_id)` | the claimant, while pending |
| `assess(claim_id)` | anyone, inside the assess window |
| `contest(claim_id)` | the claimant or the issuer, once, inside the contest window |
| `finalize(claim_id)` | anyone, after the contest window |
| `lapse_claim(claim_id)` | anyone, after the assess window, if nobody assessed it |

`evidence_json` is a list of 1 to 4 items, each
`{"url", "kind", "role", "sha256", "label"}` - `kind` is `PINNED` with the
sha256 of the exact bytes, or `LIVE` with an empty sha256 and no claim on a
positive credential; `role` is `DEMONSTRATION` or `ASSERTION`.

## Failures a client should expect

| Symptom | Meaning |
|---|---|
| leader execution `ERROR` with `[EXPECTED] ...` | the contract refused: a bad field, a closed window, a source outside the standard's domains, a second open claim, a state that does not allow the call. The message says which |
| leader execution `ERROR` with `[TRANSIENT] ...` | the model call or the clock failed on that node; send it again |
| the transaction finalises but nothing changed | the round reached no majority. Nothing is stored; the claim is still pending |
| `INSUFFICIENT_EVIDENCE` with `EVIDENCE_DIGEST_MISMATCH` | the bytes served are not the bytes that were filed - a statement about the evidence, not about the agent |
