# Deployment

The canonical StudioNet deployment, how to reproduce it, and the live run of
record against it. Every value below is read from `deploy/deployment.json` and
`deploy/live_run_transcript.json`; nothing is typed by hand.

## Environment

| | |
|---|---|
| Network | GenLayer StudioNet, chain id 61999, `https://studio.genlayer.com/api` |
| Explorer | `https://explorer-studio.genlayer.com` |
| Wallets | the deployer key is created on first use in `.data/deployer.json`; the demo wallets' keys are in `.data/demo_wallets.json` (`scripts/make_wallets.py`), their public addresses in `fixtures/wallets.json`; `.data/` is gitignored and no key is ever printed |
| Toolchain | Python 3.12, genlayer-test 0.29.2, genlayer-py 0.16.3, genvm-linter 0.11.0 with GenVM bundle v0.3.0-rc7 |
| Runner | `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`, pinned in the contract header |

The linter picks the newest GenVM bundle in its cache; a newer bundle does not
carry this runner, so pin the one the suite was verified against:

```bash
GENVM_VERSION=v0.3.0-rc7 genvm-lint check contracts/agent_credential_verifier.py --json
```

## Reproduce

```bash
pip install -r requirements-test.txt
python scripts/fetch_genvm_bundle.py
python -m pytest tests/direct -q
python scripts/deploy_studionet.py
python scripts/deploy_studionet.py --verify
python scripts/make_wallets.py
python scripts/live_run.py <address> --raw-base https://raw.githubusercontent.com/<owner>/<repo>/<commit>/fixtures/ --phase full
python -m pytest tests/integration -q
```

`deploy_studionet.py` refuses to deploy a contract with uncommitted changes, CR
bytes or non-ASCII bytes, waits for FINALIZED, asserts the leader's execution
result is SUCCESS - lifecycle status alone is not execution success - and reads
the deployed source back to compare its sha256 with the committed file.

## Canonical deployment

| | |
|---|---|
| Contract | [`0xCD691bD37c11a3c9585340c3eC65E929073a184d`](https://explorer-studio.genlayer.com/address/0xCD691bD37c11a3c9585340c3eC65E929073a184d) |
| Deployment transaction | [`0x38977f7695b9a4fbf08ba4a54d489cc5438415b4486c636e83b59e4dd49033cf`](https://explorer-studio.genlayer.com/tx/0x38977f7695b9a4fbf08ba4a54d489cc5438415b4486c636e83b59e4dd49033cf) |
| Status | FINALIZED, leader execution SUCCESS, votes AGREE, AGREE, AGREE, IDLE, IDLE |
| Deployer | `0xC47f2C130f67901c140336a6dB3140e36dB012A5` |
| Source commit | `589c5610bd576942a51d57c06c13485533452fa2` |
| Contract blob | `532c03ccfa5b83c9792fc2a127e28ef3a3692e47` |
| sha256, repository and deployed | `236ff2725bb98dbd14446fe6398c77b8993a04435554e091f11fb949c495d3a5` - byte-identical |
| Schema | 22 methods (14 view, 8 write), read from the chain |

The contract was deployed once. Nothing a live pass found required a change to
it, so every record below is against this one deployment.

## Live run of record

`python scripts/live_run.py` against the canonical deployment, 2026-09-28
13:22:16Z to 14:02:13Z, with the evidence served from commit `bc9f10a` on two
origins - `raw.githubusercontent.com` and the jsDelivr mirror of the same
commit, which return byte-identical files.

**42 transactions, 17 of 17 outcomes held, 11 of 11 refusals refused.** Every
verdict and every code-decided reason the catalogue names was reached on chain,
the issuer's contest produced a second reading of the same bytes, three
credentials were finalised and read back through `check_credential`, one claim
nobody assessed was lapsed, and every refusal failed for the reason it was sent
to test.

| Step | Transaction | Recorded | |
|---|---|---|---|
| `standard:shipdocs` | [`0x63ad6d5e...`](https://explorer-studio.genlayer.com/tx/0x63ad6d5e607db7ff1001b9b9a3c73f00bbc13eb37a2bb65c2407e4f53f3560e3) | publish_standard FINALIZED/SUCCESS |  |
| `file:AC13` | [`0xf5f85bab...`](https://explorer-studio.genlayer.com/tx/0xf5f85bab9428b4b8509d7531e21a6438b4f678d684e38f020507a13ddf36d446) | file_claim FINALIZED/SUCCESS |  |
| `file:AC01` | [`0xc6ee44c3...`](https://explorer-studio.genlayer.com/tx/0xc6ee44c3f3fcc1e0557ffa7f0088bcebb37670b401027bdc8cca394642300522) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC01` | [`0xe79a2e52...`](https://explorer-studio.genlayer.com/tx/0xe79a2e52660b14c99468294a17cc633e01d9c00e3a3eeac8eba87933bbf88c7e) | VERIFIED / CAPABILITY_DEMONSTRATED / scope retrieve, verify, flag_altered | held |
| `contest:AC01` | [`0x5dd404a3...`](https://explorer-studio.genlayer.com/tx/0x5dd404a327b6f6cd0160ef82b667068aa7de04cdb62cfb11122f59569677f2b3) | VERIFIED / CAPABILITY_DEMONSTRATED / scope retrieve, verify, flag_altered | held |
| `file:AC02` | [`0x2a3d5cc4...`](https://explorer-studio.genlayer.com/tx/0x2a3d5cc46d68777253c907ac71a97ae2bb44acd751f094e779e33976c95d04d6) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC02` | [`0x2363cf47...`](https://explorer-studio.genlayer.com/tx/0x2363cf4722515eafc20033f79b66cbd35c65c0ce5911f5d2b04c47d40b84c8ba) | PARTIALLY_VERIFIED / PARTIAL_DEMONSTRATION / scope retrieve, verify | held |
| `file:AC03` | [`0xf33f5e2b...`](https://explorer-studio.genlayer.com/tx/0xf33f5e2bee9d1af48a0d857901d2ef4363355e37065325b5e6673baebc0bbf8a) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC03` | [`0xdb20cdf7...`](https://explorer-studio.genlayer.com/tx/0xdb20cdf72273ddb2886dbd8b6767c4f1066a38c4bd2e6fc81a7e8d56626cf173) | NOT_VERIFIED / DEMONSTRATION_FAILED | held |
| `file:AC04` | [`0x0dc790fb...`](https://explorer-studio.genlayer.com/tx/0x0dc790fbc318575bc5762bf67063b314e73611a254832a0aa192413e70b802ce) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC04` | [`0xe6d45e99...`](https://explorer-studio.genlayer.com/tx/0xe6d45e99ac113cd8b524c7c1850b445c19baa2de8a27d5cc40bb7f36b945b11f) | NOT_VERIFIED / ONLY_ASSERTED | held |
| `file:AC05` | [`0x9e0bd5ee...`](https://explorer-studio.genlayer.com/tx/0x9e0bd5eee58faecddd4271218531b7556dc53528296d6873550272d5cc1e6b3b) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC05` | [`0x1f52e8c0...`](https://explorer-studio.genlayer.com/tx/0x1f52e8c05128708539dece5d4174ad19154a80be956d858c2e13e7974aec7564) | INSUFFICIENT_EVIDENCE / ASSERTIONS_ONLY | held |
| `file:AC06` | [`0xdfa9bc48...`](https://explorer-studio.genlayer.com/tx/0xdfa9bc4830b2e5905ce0b66412f127319a57256a839101dcd4095e646474bafb) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC06` | [`0xc9076676...`](https://explorer-studio.genlayer.com/tx/0xc90766764824d668dd9f3cce598d360ea1c3c7fc2aebeccf641ee089552aeb8a) | INSUFFICIENT_EVIDENCE / AGENT_NOT_NAMED | held |
| `file:AC07` | [`0xacf3d6e8...`](https://explorer-studio.genlayer.com/tx/0xacf3d6e8918c359ad46a3f609fdebeb8baf40f6de33103c9c42caa5953ee54ec) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC07` | [`0x65a6b3cb...`](https://explorer-studio.genlayer.com/tx/0x65a6b3cba120a5f040d5688070de08914824a45f31e77e2503e8ce672d3cf5dc) | INSUFFICIENT_EVIDENCE / EVIDENCE_DIGEST_MISMATCH | held |
| `file:AC08` | [`0x1a5c7811...`](https://explorer-studio.genlayer.com/tx/0x1a5c7811f43e8350ac35070a0ebff679f508aa07b9b89f8e7c313c686345d48a) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC08` | [`0x04be7ba2...`](https://explorer-studio.genlayer.com/tx/0x04be7ba2adbce57feae51ce2c34a9c08678cd507d4aae06ee2369ec19cb16216) | INSUFFICIENT_EVIDENCE / NO_EVIDENCE_READABLE | held |
| `file:AC09` | [`0xb8e226f7...`](https://explorer-studio.genlayer.com/tx/0xb8e226f70ac7110c67efd966fbeddcc507d07222a3760966b1a985b95e26c8bd) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC09` | [`0x1f71e26f...`](https://explorer-studio.genlayer.com/tx/0x1f71e26f117d384a4e871d11753e863f03e66ac7b367b2a8fbf8929abf8604a4) | INSUFFICIENT_EVIDENCE / SOURCE_ADDRESSES_VERIFIER | held |
| `file:AC10` | [`0x79de05c3...`](https://explorer-studio.genlayer.com/tx/0x79de05c3947e6f5a300092c55ada9d60b677b0c1de4d8a698b9d490099a0f20e) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC10` | [`0xc2887d35...`](https://explorer-studio.genlayer.com/tx/0xc2887d35a969b9d57a4f18f0c2ada057e8288c97189a6439928939c3edd6ae06) | INSUFFICIENT_EVIDENCE / CORROBORATION_SHORT | held |
| `file:AC11` | [`0xa3e7ab6e...`](https://explorer-studio.genlayer.com/tx/0xa3e7ab6e6c54498119af0e3b2f79587b21b46bd240a6d44ed8d63b48fc10cfdd) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC11` | [`0x92015a58...`](https://explorer-studio.genlayer.com/tx/0x92015a58aea63870e5104d2328980143963148f04a00f667336fe066b0cf3f14) | INSUFFICIENT_EVIDENCE / CORROBORATION_SHORT | held |
| `file:AC12` | [`0x171a02c4...`](https://explorer-studio.genlayer.com/tx/0x171a02c4e7e04e23126ec98553b60cd97b055c727524835adc90f94e8eef89ba) | file_claim FINALIZED/SUCCESS |  |
| `assess:AC12` | [`0x74e22a61...`](https://explorer-studio.genlayer.com/tx/0x74e22a61bf36be03e04661e62f731b3f45e870cfed39d457489d77edf364d79b) | INSUFFICIENT_EVIDENCE / EVIDENCE_CONTRADICTORY | held |
| `finalize:AC01` | [`0x82586103...`](https://explorer-studio.genlayer.com/tx/0x825861037ffde841a102b6d80022e0f0b470a6957d16b418b884b51e548c8a22) | FINAL; check_credential verified=true, partially_verified=false | held |
| `finalize:AC02` | [`0x8af1da07...`](https://explorer-studio.genlayer.com/tx/0x8af1da072ac5e269f2cdc7ddc41ffa0e0c37baef70b9cc503aec85c25ba950f8) | FINAL; check_credential verified=false, partially_verified=true | held |
| `finalize:AC03` | [`0xb6aef3f0...`](https://explorer-studio.genlayer.com/tx/0xb6aef3f070ef68945e794921cdc40607c722ee91fb44c0ff529091502f2fedd1) | FINAL; check_credential verified=false, partially_verified=false | held |
| `lapse:AC13` | [`0xf9a24f3d...`](https://explorer-studio.genlayer.com/tx/0xf9a24f3d2f7d4cfa7aa43af9d83e41f2fee61ced48ac4e29675eac95767c2ee7) | CANCELLED / LAPSED | held |
| `refuse:wrong_hash` | [`0xbb99b645...`](https://explorer-studio.genlayer.com/tx/0xbb99b6450bb5102cb1dde60d035e8e5c81eb2fed27db504fdb34f8e50b305dc4) | refused: standard_hash does not match the standard | held |
| `refuse:unknown_standard` | [`0x7d67c61d...`](https://explorer-studio.genlayer.com/tx/0x7d67c61d87d2b4140c46a0a70fff76e9ebfff6fc2483e66c33815d0c40a8155c) | refused: unknown standard_id | held |
| `refuse:outside_domains` | [`0x12784864...`](https://explorer-studio.genlayer.com/tx/0x1278486478634579e7f5e02465b558d00d8cdc3622ff9c0da1719da67132129e) | refused: evidence[0] host is outside the standard's evidence domains | held |
| `refuse:undeclared_role` | [`0x482c4038...`](https://explorer-studio.genlayer.com/tx/0x482c4038dd71da7bf96a65e9680fc207cd2c3506ac1d6d522bbec1bd77ecc6a6) | refused: evidence[0] role must be one of: DEMONSTRATION, ASSERTION | held |
| `refuse:vague_agent_name` | [`0x2f263dc9...`](https://explorer-studio.genlayer.com/tx/0x2f263dc94ded684b3f70b6c18d72b30f9a813ba519972d98585e85b551512548) | refused: agent_name needs at least 6 letters or digits, so it cannot match by accident | held |
| `refuse:description_addresses_verifier` | [`0xb3c66bb1...`](https://explorer-studio.genlayer.com/tx/0xb3c66bb1027eaad67c024a65b0b5814366f4e256dad111287325c80c93dee313) | refused: agent_description must not contain instructions to the evaluator or hidden text | held |
| `refuse:second_open_claim` | [`0x9c1d9850...`](https://explorer-studio.genlayer.com/tx/0x9c1d9850742b5e10ced11393fdddf4f9b7c52a994a74d9ef8f1cbfa388b600bb) | refused: this agent already has an open claim against this standard: CL-000018 | held |
| `refuse:double_assessment` | [`0x911627ca...`](https://explorer-studio.genlayer.com/tx/0x911627ca433d516453fa40794ff7a69e694cffb1820fa9215669d5489cba0683) | refused: only a PENDING claim is assessed | held |
| `refuse:stranger_contest` | [`0xd3680002...`](https://explorer-studio.genlayer.com/tx/0xd36800025812002bdb744871f8a1969d16f2d44b08e501d9b6963648ce19d55f) | refused: only the claimant or the standard's issuer contests a credential | held |
| `refuse:stranger_withdraw` | [`0x920edf54...`](https://explorer-studio.genlayer.com/tx/0x920edf543cd6a5a674b0ba6939c7acf039ce92300bcdfa8942b6780795111698) | refused: only the claimant withdraws its own claim | held |
| `refuse:stranger_retire` | [`0x3f6e4cd2...`](https://explorer-studio.genlayer.com/tx/0x3f6e4cd2564fe2fd246817998f04b6f497ef66677e7e2f18366835c9447deb12) | refused: only the standard's issuer retires it | held |

## The diagnostic pass

One pass ran first against the same deployment
(`deploy/diagnostics/pass1_0xcd691bd3.*`, 12:41:37Z to 13:20:48Z): the same 42
transactions, 17 of 17 held, 11 of 11 refused. It is kept as evidence that the
outcomes repeat across independent panels, and it is not the run of record.
The reason the catalogue tolerates on one case - a feature list read as
`ONLY_ASSERTED` or as `NOT_DEMONSTRATED`, both `NOT_VERIFIED` - did not vary:
both passes read `ONLY_ASSERTED`.

## Mutation sweeps

| Sweep | Result |
|---|---|
| `deploy/mutation_sweep_first.txt` - the first sweep, on the suite as first written | 85 mutations, 75 killed, 10 survived |
| `deploy/mutation_sweep.txt` - the sweep of record, on the final contract and suite | 86 mutations, **86 killed, 0 survived** |

Every survivor of the first sweep was a gap in the tests, not in the contract,
and each now has the test that kills it: a 404 and an undecodable body recorded
as what they are; a spliced quote forged into a leader payload; a scope that
differs while the verdict agrees; a named list that is false but unused; the
named-list gate on its own; a quote grounded only in the leader's text; an empty
or oversized domain list; a lapse inside its window; a `LIVE` item's bytes kept
out of the record. The one contract change between the two sweeps came from the
pre-deployment audit, not from the sweep: a failure, like a demonstration, may
now be quoted only from a record of this agent's own work.
