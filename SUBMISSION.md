# Submission - AgentCredentialVerifier

Copy-ready for the portal's Builder > Intelligent Contracts form. No addresses,
hashes or shell commands appear in the free-text fields: the contract goes only
in the evidence row the portal recognises as a GenLayer Explorer contract.

## Title

AgentCredentialVerifier - capability credentials for agents, from evidence

## One-line thesis

A reusable GenLayer Intelligent Contract that decides whether an agent's
evidence actually demonstrates a capability, against a standard published before
the claim, and issues a typed, expiring credential a marketplace reads in one
call.

<!-- PORTAL:START -->
## Portal description (984 characters, limit 1000)

An agent says it can do something. AgentCredentialVerifier checks the evidence instead of the description. An issuer publishes a capability standard first: the requirements, which sources may be read, how many independent origins a credential needs, how long it lasts. The agent files test runs, outputs and documentation; validators independently retrieve each item, verify it against the sha256 declared at filing, and read it per requirement. Deterministic code derives VERIFIED, PARTIALLY_VERIFIED, NOT_VERIFIED or INSUFFICIENT_EVIDENCE with a scope and an expiry. A description is a claim, never evidence: assertions alone, or runs that do not name the agent, never reach the panel, and a brochure is read as asserted only. A failure must come from the agent's own record. Consumers read one view. Verified with 130 Direct Mode tests, an 86-mutation sweep, GenVM lint, live integration tests, and 17 of 17 live outcomes on a StudioNet deployment byte-identical to the repository.
<!-- PORTAL:END -->

## Evidence rows

| Type | What |
|---|---|
| GitHub Repository | https://github.com/Olawalter/AgentCredentialVerifier |
| GenLayer Explorer Contract | https://explorer-studio.genlayer.com/address/0xCD691bD37c11a3c9585340c3eC65E929073a184d |

## Reviewer fast path

1. `DECISION.md` - the specification written before the contract, and the
   collision audit against the owner's own portfolio.
2. `docs/CONSENSUS.md` - the two nondeterministic calls, the gate, what
   validators compare, and the live findings.
3. `contracts/agent_credential_verifier.py` - `_verdict_for` is the whole
   derivation; `_code_reason` and `_quotable` hold the rule that a description
   is not evidence.
4. `docs/DEPLOYMENT.md` - the canonical deployment and a transaction for every
   step of the run of record.
5. `tests/direct/test_acv_adversarial.py` - forged credentials, brochures
   labelled as demonstrations, another agent's runs, injections and their
   evasions, malformed payloads.
