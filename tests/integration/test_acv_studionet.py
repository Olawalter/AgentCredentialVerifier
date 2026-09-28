"""Reads against the canonical StudioNet deployment.

These tests do not re-run consensus: they check that the contract on chain is the
contract in this repository, that it answers, and that every credential the live
run recorded is what the chain still holds - including through the view a
marketplace would use. One write is opt-in (`ACV_LIVE_WRITES=1`), because it
sends a real transaction.

Each test is independently runnable:

    python -m pytest tests/integration -q
    python -m pytest tests/integration -q -k source_is_this_repository
"""

import base64
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

RECORD = ROOT / "deploy" / "deployment.json"
TRANSCRIPT = ROOT / "deploy" / "live_run_transcript.json"
CONTRACT = ROOT / "contracts" / "agent_credential_verifier.py"
WALLETS = ROOT / "fixtures" / "wallets.json"
RPC = "https://studio.genlayer.com/api"

pytestmark = pytest.mark.skipif(not RECORD.exists(),
                                reason="no canonical deployment recorded yet")


def rpc(method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    request = urllib.request.Request(RPC, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "acv-integration"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                answer = json.loads(response.read().decode())
            if "error" in answer and "-32029" in json.dumps(answer["error"]):
                raise RuntimeError("rate limited")
            return answer
        except Exception:
            if attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client():
    """A read-only client. Reads need no key, so a fresh throwaway account is used
    and nothing under .data/ is required to run this suite."""
    import studionet_transport  # noqa: F401 - retries RPC transport failures
    from genlayer_py import create_account, create_client
    from genlayer_py.chains import studionet
    return create_client(chain=studionet, account=create_account(), endpoint=RPC)


def read(client, record, method, args=None):
    return client.read_contract(address=record["contract_address"],
                                function_name=method, args=args or [])


def steps() -> dict:
    return json.loads(TRANSCRIPT.read_text(encoding="utf-8"))["steps"]


def test_the_deployed_source_is_this_repository(record):
    answer = rpc("gen_getContractCode", [record["contract_address"]])
    raw = answer.get("result")
    deployed = str(raw).encode()
    if hashlib.sha256(deployed).hexdigest() != record["source_sha256"]:
        deployed = base64.b64decode(raw)
    assert hashlib.sha256(deployed).hexdigest() == record["source_sha256"]
    assert record["source_sha256"] == hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    assert record["byte_identical"] is True


def test_the_schema_is_the_whole_surface(record):
    schema = rpc("gen_getContractSchema", [record["contract_address"]]).get("result") or {}
    methods = schema.get("methods") or {}
    assert len(methods) == 22
    for name in ("publish_standard", "retire_standard", "file_claim", "withdraw_claim",
                 "assess", "contest", "finalize", "lapse_claim", "check_credential",
                 "get_verdict", "get_evidence_status", "get_standard_hash"):
        assert name in methods, name


def test_the_config_on_chain_matches_the_contract(client, record):
    config = read(client, record, "get_config")
    assert config["contract_version"] == "0.1.0" and config["payable"] is False
    assert config["verdicts"] == ["PENDING", "VERIFIED", "PARTIALLY_VERIFIED",
                                  "NOT_VERIFIED", "INSUFFICIENT_EVIDENCE", "CANCELLED"]
    assert config["evidence_roles"] == ["DEMONSTRATION", "ASSERTION"]
    assert config["caps"]["evidence_items"] == 4


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_every_credential_the_run_recorded_is_still_on_chain(client, record):
    checked = 0
    for name, entry in sorted(steps().items()):
        if not name.startswith(("assess:", "contest:")) or "resolution_id" not in entry:
            continue
        answer = read(client, record, "get_resolution", [entry["resolution_id"]])
        assert answer["found"], name
        resolution = answer["resolution"]
        assert resolution["verdict"] == entry["observed_verdict"], name
        assert resolution["reason_code"] == entry["observed_reason"], name
        assert resolution["scope"] == entry["observed_scope"], name
        checked += 1
    assert checked > 0


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_the_consumer_view_agrees_with_the_records(client, record):
    """What a marketplace reads must agree with the full record behind it."""
    wallets = json.loads(WALLETS.read_text(encoding="utf-8"))
    cases = json.loads((ROOT / "fixtures" / "cases.json").read_text(encoding="utf-8"))
    wallet_of = {c["case"]: wallets[c["wallet"]] for c in cases["cases"]}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    checked = 0
    for name, entry in sorted(steps().items()):
        if not name.startswith("finalize:") or "consumer_view" not in entry:
            continue
        seen = entry["consumer_view"]
        # the agent's address as the fixtures record it, not as the view echoed it
        agent = wallet_of[name.split(":", 1)[1]]
        assert seen["agent"] == agent.lower(), name
        answer = read(client, record, "check_credential", [agent, seen["standard_id"], now])
        assert answer["found"] and answer["final"], name
        assert answer["claim_id"] == seen["claim_id"], name
        assert answer["verdict"] == seen["verdict"], name
        assert answer["scope"] == seen["scope"], name
        verdict = read(client, record, "get_verdict", [seen["claim_id"]])
        assert answer["verified"] == (verdict["verdict"] == "VERIFIED"
                                      and verdict["final"]), name
        checked += 1
    assert checked > 0


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_a_positive_credential_rests_on_bound_bytes_and_independent_origins(client,
                                                                           record):
    positives = [e for e in steps().values()
                 if e.get("observed_verdict") in ("VERIFIED", "PARTIALLY_VERIFIED")]
    assert positives, "the run recorded no positive credential"
    for entry in positives:
        resolution = read(client, record, "get_resolution",
                          [entry["resolution_id"]])["resolution"]
        assert resolution["bytes_bound"] is True
        assert len(resolution["independent_origins"]) \
            >= resolution["min_independent_origins"]
        assert resolution["scope"], entry["step"]
        cited = {q["evidence_id"] for f in resolution["findings"]
                 if f["state"] == "DEMONSTRATED" for q in f["quotes"]}
        roles = {s["evidence_id"]: s for s in resolution["sources"]}
        for evidence_id in cited:
            assert roles[evidence_id]["role"] == "DEMONSTRATION"
            assert roles[evidence_id]["names_agent"] is True


@pytest.mark.skipif(not TRANSCRIPT.exists(), reason="no live run recorded yet")
def test_a_description_never_became_a_credential(client, record):
    """The rule the primitive exists for, read back from the chain: every case
    built from descriptions ended negative, and the code-decided ones never
    convened a panel."""
    for name, entry in steps().items():
        if not name.startswith("assess:"):
            continue
        if entry.get("observed_reason") in ("ASSERTIONS_ONLY", "AGENT_NOT_NAMED"):
            assert entry["observed_verdict"] == "INSUFFICIENT_EVIDENCE", name
            assert entry["panel_state"] == "SKIPPED", name
        if entry.get("observed_reason") in ("ONLY_ASSERTED", "NOT_DEMONSTRATED"):
            assert entry["observed_verdict"] == "NOT_VERIFIED", name


@pytest.mark.skipif(os.environ.get("ACV_LIVE_WRITES") != "1",
                    reason="set ACV_LIVE_WRITES=1 to send one transaction")
def test_a_standard_can_still_be_published(record):
    import studionet_transport  # noqa: F401
    from genlayer_py import create_account, create_client
    from genlayer_py.chains import studionet
    from genlayer_py.types import TransactionStatus
    keys = json.loads((ROOT / ".data" / "demo_wallets.json").read_text(encoding="utf-8"))
    writer = create_client(chain=studionet, account=create_account(
        account_private_key=keys["keeper"]), endpoint=RPC)
    standard = json.loads((ROOT / "fixtures" / "standards.json")
                          .read_text(encoding="utf-8"))["shipdocs"]
    before = read(writer, record, "get_stats")["standards"]
    tx = writer.write_contract(address=record["contract_address"],
                               function_name="publish_standard",
                               args=[json.dumps(standard, sort_keys=True)])
    writer.wait_for_transaction_receipt(transaction_hash=tx,
                                        status=TransactionStatus.FINALIZED,
                                        interval=5000, retries=240)
    assert read(writer, record, "get_stats")["standards"] == before + 1
