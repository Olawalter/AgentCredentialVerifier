# Security

The threat model, what each boundary holds, and what this contract does not
defend against.

## Assets

| Asset | Why it is worth attacking |
|---|---|
| a **positive credential** (`VERIFIED`, `PARTIALLY_VERIFIED`) | marketplaces and routers hand work to the agents that hold one; a false credential sends tasks to an agent that cannot do them |
| a **negative credential** | a false `NOT_VERIFIED` shuts a capable agent out; that is why a failure, like a demonstration, must rest on a record of the agent's own work |
| the **scope** of a partial credential | a router sends only the demonstrated parts of a task; a wider scope sends the rest too |
| the **standard** | if it could change after a claim was filed, the requirements could be rewritten around the evidence |
| the **evidence record** | a dispute later reads the stored record; bytes nobody agreed on must never enter it |

No funds. No method is payable, there is no treasury and no ledger, so there is
nothing to drain and no settlement to race.

## Actors

| Actor | Can | Cannot |
|---|---|---|
| standard **issuer** (a marketplace, registry or buyer) | publish a standard; retire it, which stops new claims; contest a credential once inside its window | change a published standard; revoke a credential already issued; assess, or influence a reading |
| **agent** (the claimant, a wallet) | file one open claim per standard with up to four evidence items; withdraw it before assessment; contest once inside the window; renew by filing again after a claim is final | file a second open claim, cite a source the standard did not name, change the evidence after filing, or improve it for a second reading |
| **keeper** (anyone) | assess, lapse, finalise | change any outcome - none of those calls carries a judgement |
| **validators** | reproduce the round and refuse the leader | write a credential; they compare, code derives |
| **consumer** | read credentials, scope, finality and expiry | write anything |

## Trust assumptions

- The hosts a standard names are trusted only to *serve bytes*; nothing they say
  is trusted, and a `PINNED` item is trusted only to the extent it hashes to what
  was declared.
- **The agent's description of itself is never trusted.** It is shown to the
  panel labelled as a claim to test, and it is screened at filing for text
  addressed to the verifier.
- **The agent's role labels are trusted only to narrow, never to widen.** An
  item declared `ASSERTION` can never carry a demonstration; an item declared
  `DEMONSTRATION` still has to name the agent in code, and still has to be read
  by the panel as a record of work done - a feature list labelled
  `DEMONSTRATION` is read `ASSERTED_ONLY`.
- Validators are assumed to retrieve independently. The corroboration floor and
  the digest binding are what remain when one validator is wrong.
- The model is assumed to be fallible and possibly adversarially prompted. It is
  never asked for a verdict, a scope or an expiry, and every reading that bears
  on the credential must quote the evidence it rests on.
- The issuer is assumed to be self-interested. It cannot edit a standard,
  cannot revoke a credential, and retiring a standard leaves every credential
  already issued standing until its expiry.

## Input attacks

**Self-description as evidence.** The whole primitive exists to refuse it, in
three places: a claim with no readable `DEMONSTRATION` never reaches the panel
(`ASSERTIONS_ONLY`); a demonstration that does not contain the agent's name
never reaches it either (`AGENT_NOT_NAMED`); and the panel has a reading for
text that states a capability without recording it done (`ASSERTED_ONLY`).

**Someone else's work.** A passing run of another agent does not name this one,
so it cannot carry a `DEMONSTRATED` reading - the gate refuses such a quote. The
same holds for a `FAILED` reading, so another agent's failure cannot mark this
one `NOT_VERIFIED`. The agent name must hold at least six letters or digits, so
it cannot be a word every document contains.

**Prompt injection.** Every evidence document is data. `_markers` scans each
readable item in code for text addressed to the verifier - in the visible text,
in markup and attributes a reader never sees, and in the title - and undoes the
tricks that hide such text from a naive match: soft hyphens, zero-width joiners,
bidirectional controls, byte order marks, numeric character references, and tags
or comments splitting a word. A document carrying such text decides the round in
code as `SOURCE_ADDRESSES_VERIFIER`; the panel is never convened. The standard's
own fields, the agent's name and description, and every label are checked for
the same markers at write time.

**A poisoned item is not dropped.** Judging the rest would let whoever poisoned
it choose which evidence counts, and with a corroboration floor, removing an
item changes what a credential can rest on.

**Evidence manipulation after filing.** A `PINNED` item's sha256 is declared at
filing and verified against the bytes on every retrieval, in every round. Serve
different bytes later and the item is `DIGEST_MISMATCH` and the credential is
`INSUFFICIENT_EVIDENCE` - never a positive credential, and never a fresh reading
of improved evidence.

**Unbound evidence.** A `LIVE` item has no digest, so a positive credential may
not rest on one, and a requirement read on `LIVE` bytes is left out of the scope.

**One publisher wearing several hats.** Corroboration is counted over distinct
hosts, not items, and a standard cannot demand more origins than the sources it
named could provide.

**Fabricated support.** A quote is a quote only if it grounds in the text this
node retrieved, as a contiguous run of words; splices joined by an ellipsis are
dropped even though grounding would walk their parts. A reading that bears on
the credential without a quote is downgraded to `UNCLEAR`, and the downgrade is
printed.

**Malformed or hostile model output.** Types are checked, not coerced; unknown
states, missing subjects, extra fields, booleans where integers belong and
floats where integers belong all fail closed.

**Stale standards.** A claim commits to the standard hash it read; any other
hash is refused at filing, and every stored resolution records the hash its
round judged under.

**Griefing by volume.** At most ten open claims per wallet and one per standard,
at most four evidence items each, at most 200 KB read per item and 9,000
normalised characters shown to the panel. Every per-record list is bounded.

## Fail-open / fail-closed policy

Fail-closed on the positive path, without exception: unreachable evidence, a
digest mismatch, an injection, only assertions, no demonstration naming the
agent, an unusable panel answer, contradictory documents, an unclear reading,
too few origins or unbound bytes all produce `INSUFFICIENT_EVIDENCE`.

And fail-closed on the **negative** path too, which is where this primitive
differs from a court: `NOT_VERIFIED` is a finding against an agent, so it is
reached only when the evidence was read and a failure was quoted from the
agent's own record, or nothing demonstrated the capability. A failure asserted
without a quote, or quoted from someone else, is `INSUFFICIENT_EVIDENCE`.

Both sides of each asymmetry:

| Floor | Mirror |
|---|---|
| a positive credential needs the standard's independent origins | a negative one needs none: refusing a credential moves nothing |
| a positive credential may not rest on `LIVE` bytes | a negative one may |
| a demonstration must quote a record of this agent's work | so must a failure |
| an issuer cannot revoke a credential or edit a standard | an agent cannot edit its evidence or improve it for a contest |
| a contest is limited to one, inside a window | the window is wall-clock and anyone may finalise after it |

## Limitations

- **A credential is not a guarantee.** It means the filed evidence demonstrated
  the standard's requirements when it was read - nothing broader. Agents change;
  that is what the expiry is for, and renewal is a new claim.
- The contract judges demonstrations, not the agent's code. An agent that
  performs well on the runs it chose to file can still fail on others.
- The evidence is chosen by the claimant. The standard can narrow where it may
  come from (its evidence domains) and how many independent publishers it must
  span; a standard that names weak sources gets weak credentials, and the
  permitted hosts are on the record for a reader to judge.
- Whether a document names the agent is a string test. A document can mention
  the agent without recording its work; the panel is asked whose work each run
  records, and that reading is a model judgement.
- **One contest per claim, for whichever party uses it first.** An issuer who
  contests a credential spends the only contest; the second reading is of the
  same bound bytes, so the lever it offers is panel variance and nothing else.
  Where honest models split, the round reaches no majority and stores nothing.
- Identity is a wallet. The credential is keyed by the wallet that filed; the
  per-wallet caps bound abuse, they do not prevent one operator from using
  several wallets.
