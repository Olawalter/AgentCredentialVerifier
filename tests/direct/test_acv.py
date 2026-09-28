"""The lifecycle, the credentials and the views a consumer reads.

Each test drives the contract the way a caller would - publish a standard, file a
claim, assess it, contest it, finalise it - and checks what the contract stored,
not what the harness said.
"""

from tests.direct import support as s

LATER = "2026-09-28T14:00:00Z"
MUCH_LATER = "2026-09-29T14:00:00Z"
EXPIRED = "2026-11-15T12:00:00Z"


def setup(acv, vm, issuer, **overrides):
    standard_id = s.published(acv, vm, issuer, **overrides)
    s.serve_all(vm)
    return standard_id, acv.get_standard(standard_id)["definition_hash"]


def final(acv, vm, claim_id):
    vm.warp(LATER)
    return acv.finalize(claim_id)


# -- the standard --------------------------------------------------------------

def test_a_standard_is_published_with_its_hash(acv, direct_vm, direct_alice, mod):
    standard_id = s.published(acv, direct_vm, direct_alice)
    info = acv.get_standard(standard_id)
    assert info["found"] and standard_id == "CS-000001"
    assert info["issuer"] == direct_alice.as_hex.lower()
    assert info["status"] == "ACTIVE" and info["claim_count"] == 0
    assert info["definition_hash"] == mod._sha256_hex(mod._canonical(info["standard"]))
    assert acv.get_standard_hash(standard_id)["definition_hash"] == info["definition_hash"]
    assert acv.get_standard_hash(standard_id)["accepting_claims"] is True


def test_standard_ids_run_in_order(acv, direct_vm, direct_alice):
    first = s.published(acv, direct_vm, direct_alice)
    second = s.published(acv, direct_vm, direct_alice)
    assert (first, second) == ("CS-000001", "CS-000002")
    assert acv.list_standards(0, 10)["ids"] == [first, second]


def test_a_retired_standard_takes_no_new_claims(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    assert acv.retire_standard(standard_id) == "RETIRED"
    assert acv.get_standard_hash(standard_id)["accepting_claims"] is False
    with direct_vm.expect_revert("retired"):
        s.filed(acv, direct_vm, direct_bob, standard_id, digest)


def test_only_the_issuer_retires_a_standard(acv, direct_vm, direct_alice, direct_bob):
    standard_id = s.published(acv, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only the standard's issuer"):
        acv.retire_standard(standard_id)


def test_retiring_keeps_credentials_already_issued(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    final(acv, direct_vm, claim_id)
    direct_vm.sender = direct_alice
    acv.retire_standard(standard_id)
    answer = acv.check_credential(direct_bob.as_hex, standard_id, LATER)
    assert answer["verified"] is True


def test_get_config_publishes_the_vocabulary(acv):
    config = acv.get_config()
    assert config["contract_version"] == "0.1.0" and config["payable"] is False
    assert config["verdicts"] == ["PENDING", "VERIFIED", "PARTIALLY_VERIFIED",
                                  "NOT_VERIFIED", "INSUFFICIENT_EVIDENCE", "CANCELLED"]
    assert config["evidence_roles"] == ["DEMONSTRATION", "ASSERTION"]
    assert config["evidence_kinds"] == ["PINNED", "LIVE"]
    assert "ASSERTED_ONLY" in config["requirement_states"]
    assert set(config["code_reasons"]) <= set(config["reason_codes"])
    assert config["caps"]["evidence_items"] == 4


# -- the claim -----------------------------------------------------------------

def test_a_claim_commits_to_the_standard_it_read(acv, direct_vm, direct_alice, direct_bob,
                                                 mod):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id = s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    claim = acv.get_claim(claim_id)
    assert claim["found"] and claim_id == "CL-000001"
    assert claim["agent"] == direct_bob.as_hex.lower()
    assert claim["agent_name"] == s.AGENT
    assert claim["standard_hash"] == digest
    assert claim["status"] == "PENDING" and claim["verdict"] == "PENDING"
    assert [i["evidence_id"] for i in claim["evidence"]] == ["E1", "E2", "E3"]
    assert [i["role"] for i in claim["evidence"]] == ["DEMONSTRATION", "DEMONSTRATION",
                                                      "ASSERTION"]
    assert claim["description_is_a_claim"] is True
    assert claim["evidence_commitment"] == mod._sha256_hex(mod._canonical(claim["evidence"]))


def test_a_claim_needs_the_matching_standard_hash(acv, direct_vm, direct_alice, direct_bob):
    standard_id, _digest = setup(acv, direct_vm, direct_alice)
    with direct_vm.expect_revert("standard_hash does not match"):
        s.filed(acv, direct_vm, direct_bob, standard_id, "00" * 32)


def test_one_open_claim_per_agent_per_standard(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    first = s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    with direct_vm.expect_revert("already has an open claim"):
        s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    direct_vm.sender = direct_bob
    acv.withdraw_claim(first)
    assert s.filed(acv, direct_vm, direct_bob, standard_id, digest) == "CL-000002"


def test_a_final_claim_frees_the_slot_for_a_renewal(acv, direct_vm, direct_alice,
                                                    direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    with direct_vm.expect_revert("already has an open claim"):
        s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    final(acv, direct_vm, claim_id)
    assert s.filed(acv, direct_vm, direct_bob, standard_id, digest) == "CL-000002"


def test_only_the_claimant_withdraws(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id = s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("only the claimant withdraws"):
        acv.withdraw_claim(claim_id)
    direct_vm.sender = direct_bob
    assert acv.withdraw_claim(claim_id) == "CANCELLED"
    claim = acv.get_claim(claim_id)
    assert claim["verdict"] == "CANCELLED" and claim["reason_code"] == "WITHDRAWN"


# -- the credential: each verdict ----------------------------------------------

def test_every_requirement_demonstrated_on_two_origins_is_verified(acv, direct_vm,
                                                                   direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    verdict = acv.get_verdict(claim_id)
    assert verdict["verdict"] == "VERIFIED"
    assert verdict["reason_code"] == "CAPABILITY_DEMONSTRATED"
    assert verdict["scope"] == ["retrieve", "verify", "flag_altered"]
    assert verdict["final"] is False
    record = acv.get_resolution(resolution_id)["resolution"]
    assert record["independent_origins"] == ["outputs.example.net", "runs.example.org"]
    assert record["bytes_bound"] is True
    assert record["named"] == ["E1", "E2"]
    assert acv.get_stats()["verified"] == 1


def test_a_verified_credential_expires(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    assert acv.get_claim(claim_id)["expires_at"] == "2026-10-28T12:00:00Z"
    final(acv, direct_vm, claim_id)
    live = acv.check_credential(direct_bob.as_hex, standard_id, LATER)
    assert live["verified"] is True and live["expired"] is False
    gone = acv.check_credential(direct_bob.as_hex, standard_id, EXPIRED)
    assert gone["verified"] is False and gone["expired"] is True
    assert gone["verdict"] == "VERIFIED"


def test_some_required_demonstrated_is_partially_verified(acv, direct_vm, direct_alice,
                                                          direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    subjects = s.verified_said(flag_altered="NOT_DEMONSTRATED")
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                              subjects=subjects)
    verdict = acv.get_verdict(claim_id)
    assert verdict["verdict"] == "PARTIALLY_VERIFIED"
    assert verdict["reason_code"] == "PARTIAL_DEMONSTRATION"
    assert verdict["scope"] == ["retrieve", "verify"]
    final(acv, direct_vm, claim_id)
    answer = acv.check_credential(direct_bob.as_hex, standard_id, LATER)
    assert answer["verified"] is False and answer["partially_verified"] is True
    assert answer["scope"] == ["retrieve", "verify"]


def test_a_failed_required_demonstration_is_not_verified(acv, direct_vm, direct_alice,
                                                         direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    items = [s.item(s.FAILED_URL, s.FAILED_RUN, "Conformance run 0413"),
             s.item(s.OUTPUT_URL, s.OUTPUT, "Verification report for BL-7731")]
    subjects = s.verified_said(flag_altered="FAILED",
                               quotes={"flag_altered": [("E1", s.FLAG_FAIL_LINE)]})
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                              subjects=subjects, items=items)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("NOT_VERIFIED",
                                                            "DEMONSTRATION_FAILED")
    assert verdict["scope"] == [] and acv.get_claim(claim_id)["expires_at"] == ""


def test_evidence_that_only_describes_the_agent_is_not_verified(acv, direct_vm,
                                                                direct_alice, direct_bob):
    """A claimant who labels a feature list DEMONSTRATION still gets ASSERTED_ONLY."""
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    items = [s.item(s.DOCS_URL, s.DOCS, "Feature list")]
    subjects = s.verified_said(retrieve="ASSERTED_ONLY", verify="ASSERTED_ONLY",
                               flag_altered="ASSERTED_ONLY")
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                              subjects=subjects, items=items)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("NOT_VERIFIED", "ONLY_ASSERTED")


def test_nothing_addressing_the_requirements_is_not_demonstrated(acv, direct_vm,
                                                                 direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    subjects = s.verified_said(retrieve="NOT_DEMONSTRATED", verify="NOT_DEMONSTRATED",
                               flag_altered="NOT_DEMONSTRATED")
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                         subjects=subjects)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("NOT_VERIFIED",
                                                            "NOT_DEMONSTRATED")
    record = acv.get_resolution(resolution_id)["resolution"]
    compared = {f["id"]: f["compared"] for f in record["findings"]}
    assert compared == {"EVIDENCE_CONSISTENCY": False, "REQ_RETRIEVE": True,
                        "REQ_VERIFY": True, "REQ_FLAG_ALTERED": True}


def test_only_assertions_declared_never_reach_the_panel(acv, direct_vm, direct_alice,
                                                        direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    items = [s.item(s.DOCS_URL, s.DOCS, "Feature list", role="ASSERTION")]
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                         items=items)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "ASSERTIONS_ONLY")
    record = acv.get_resolution(resolution_id)["resolution"]
    assert record["panel_state"] == "SKIPPED"
    assert all(f["by"] == "CODE" for f in record["findings"])


def test_a_demonstration_of_another_agent_never_reaches_the_panel(acv, direct_vm,
                                                                  direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    items = [s.item(s.OTHER_URL, s.OTHER, "Conformance run 0099")]
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                         items=items)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "AGENT_NOT_NAMED")
    assert acv.get_resolution(resolution_id)["resolution"]["named"] == []


def test_a_digest_that_does_not_match_is_insufficient(acv, direct_vm, direct_alice,
                                                      direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    items = s.usual_items(run_body=s.RUN + " ")
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                         items=items)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "EVIDENCE_DIGEST_MISMATCH")
    sources = acv.get_resolution(resolution_id)["resolution"]["sources"]
    assert sources[0]["status"] == "DIGEST_MISMATCH"


def test_nothing_readable_is_insufficient_not_a_failure(acv, direct_vm, direct_alice,
                                                        direct_bob):
    # the web mock answers with the first pattern registered, so the 404s go first
    s.serve_all(direct_vm, {s.RUN_URL: None, s.OUTPUT_URL: None, s.DOCS_URL: None})
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "NO_EVIDENCE_READABLE")
    sources = acv.get_resolution(resolution_id)["resolution"]["sources"]
    assert [x["status"] for x in sources] == ["NOT_FOUND"] * 3
    assert [x["http_status"] for x in sources] == [404] * 3


def test_a_contradiction_is_insufficient(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                         subjects=s.verified_said(
                                             consistency="CONTRADICTORY"))
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "EVIDENCE_CONTRADICTORY")
    findings = acv.get_resolution(resolution_id)["resolution"]["findings"]
    assert s.finding_in({"findings": findings}, "EVIDENCE_CONSISTENCY")["compared"] is True


def test_an_unclear_required_reading_is_insufficient(acv, direct_vm, direct_alice,
                                                     direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                              subjects=s.verified_said(verify="UNCLEAR"))
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "REQUIREMENT_UNCLEAR")


def test_one_origin_is_not_enough_when_the_standard_asks_for_two(acv, direct_vm,
                                                                 direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    subjects = s.verified_said(quotes={"verify": [("E1", s.VERIFY_LINE)]})
    items = [s.item(s.RUN_URL, s.RUN, "Conformance run 0412")]
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                              subjects=subjects, items=items)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "CORROBORATION_SHORT")


def test_a_live_demonstration_can_never_carry_a_credential(acv, direct_vm, direct_alice,
                                                           direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice, min_independent_origins=1)
    items = [s.item(s.LIVE_URL, s.LIVE, "Latest output", kind="LIVE")]
    subjects = s.verified_said(quotes={"retrieve": [("E1", s.RETRIEVE_LINE)],
                                       "verify": [("E1", s.OUTPUT_LINE)],
                                       "flag_altered": [("E1", s.OUTPUT_LINE)]})
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                         subjects=subjects, items=items)
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "CORROBORATION_SHORT")
    assert acv.get_resolution(resolution_id)["resolution"]["bytes_bound"] is False


def test_an_injection_stops_the_round(acv, direct_vm, direct_alice, direct_bob):
    poisoned = s.page("BL-7731 verification report", [s.OUTPUT_LINE, s.INJECTION])
    s.serve(direct_vm, s.OUTPUT_URL, poisoned)
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                         items=s.usual_items(output_body=poisoned))
    verdict = acv.get_verdict(claim_id)
    assert (verdict["verdict"], verdict["reason_code"]) == ("INSUFFICIENT_EVIDENCE",
                                                            "SOURCE_ADDRESSES_VERIFIER")
    assert acv.get_resolution(resolution_id)["resolution"]["markers"] == ["E2:BODY"]


# -- windows, contest, finality ------------------------------------------------

def test_the_assess_window_closes_and_the_claim_lapses(acv, direct_vm, direct_alice,
                                                       direct_bob, direct_charlie):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id = s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    direct_vm.warp(LATER)
    s.panel(direct_vm, s.verified_said())
    with direct_vm.expect_revert("assess window closed"):
        acv.assess(claim_id)
    direct_vm.sender = direct_charlie
    assert acv.lapse_claim(claim_id) == "CANCELLED"
    assert acv.get_claim(claim_id)["reason_code"] == "LAPSED"
    assert s.filed(acv, direct_vm, direct_bob, standard_id, digest) == "CL-000002"


def test_a_claim_cannot_lapse_while_its_window_is_open(acv, direct_vm, direct_alice,
                                                      direct_bob, direct_charlie):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id = s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("the assess window closes at"):
        acv.lapse_claim(claim_id)
    assert acv.get_claim(claim_id)["status"] == "PENDING"


def test_a_live_item_stores_nothing_that_was_not_compared(acv, direct_vm, direct_alice,
                                                          direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    items = s.usual_items()[:2] + [s.item(s.LIVE_URL, s.LIVE, "Latest output", kind="LIVE")]
    _c, resolution_id = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                   items=items)
    sources = acv.get_resolution(resolution_id)["resolution"]["sources"]
    live = [x for x in sources if x["evidence_id"] == "E3"][0]
    assert live["status"] == "RETRIEVED" and live["compared"] is False
    for key in ("raw_sha256", "content_digest", "byte_count", "title", "declared_sha256"):
        assert key not in live, key
    pinned = [x for x in sources if x["evidence_id"] == "E1"][0]
    assert pinned["compared"] is True and pinned["raw_sha256"] == s.digest(s.RUN)


def test_a_contest_is_a_second_reading_of_the_same_bytes(acv, direct_vm, direct_alice,
                                                         direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, first = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                                 subjects=s.verified_said(verify="UNCLEAR"))
    assert acv.get_verdict(claim_id)["verdict"] == "INSUFFICIENT_EVIDENCE"
    s.panel(direct_vm, s.verified_said())
    direct_vm.sender = direct_bob
    second = acv.contest(claim_id)
    record = acv.get_resolution(second)["resolution"]
    assert record["mode"] == "CONTEST" and record["round"] == 2
    assert record["supersedes"] == first
    assert acv.get_verdict(claim_id)["verdict"] == "VERIFIED"
    with direct_vm.expect_revert("contested once already"):
        acv.contest(claim_id)
    assert [r["mode"] for r in acv.get_history(claim_id)["rounds"]] == ["ASSESS", "CONTEST"]


def test_only_the_claimant_or_the_issuer_contests(acv, direct_vm, direct_alice, direct_bob,
                                                  direct_charlie):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("only the claimant or the standard's issuer"):
        acv.contest(claim_id)
    s.panel(direct_vm, s.verified_said(flag_altered="NOT_DEMONSTRATED"))
    direct_vm.sender = direct_alice
    acv.contest(claim_id)
    assert acv.get_verdict(claim_id)["verdict"] == "PARTIALLY_VERIFIED"
    assert acv.get_stats()["verified"] == 0


def test_finality_waits_for_the_contest_window(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    with direct_vm.expect_revert("contest window closes"):
        acv.finalize(claim_id)
    assert acv.check_credential(direct_bob.as_hex, standard_id, s.NOW)["found"] is False
    assert final(acv, direct_vm, claim_id) == "FINAL"
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only an ASSESSED claim is contested"):
        acv.contest(claim_id)


def test_a_contest_after_its_window_is_refused(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    direct_vm.warp(LATER)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("contest window closed"):
        acv.contest(claim_id)


def test_the_latest_final_claim_is_the_credential(acv, direct_vm, direct_alice, direct_bob):
    """A failed renewal replaces a credential that passed: the answer is what
    the agent most recently demonstrated, not the best it ever did."""
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    first, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    final(acv, direct_vm, first)
    direct_vm.warp(MUCH_LATER)
    items = [s.item(s.FAILED_URL, s.FAILED_RUN, "Conformance run 0413"),
             s.item(s.OUTPUT_URL, s.OUTPUT, "Verification report for BL-7731")]
    subjects = s.verified_said(flag_altered="FAILED",
                               quotes={"flag_altered": [("E1", s.FLAG_FAIL_LINE)]})
    second, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest,
                            subjects=subjects, items=items)
    assert acv.check_credential(direct_bob.as_hex, standard_id, MUCH_LATER)["claim_id"] \
        == first
    direct_vm.warp("2026-09-29T16:00:00Z")
    acv.finalize(second)
    answer = acv.check_credential(direct_bob.as_hex, standard_id, "2026-09-29T16:00:00Z")
    assert answer["claim_id"] == second and answer["verified"] is False
    assert answer["verdict"] == "NOT_VERIFIED"


def test_the_consumer_view_reads_any_address_case(acv, direct_vm, direct_alice, direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id, _r = s.assessed(acv, direct_vm, direct_bob, standard_id, digest)
    final(acv, direct_vm, claim_id)
    upper = "0x" + direct_bob.as_hex[2:].upper()
    assert acv.check_credential(upper, standard_id, LATER)["verified"] is True
    assert acv.check_credential(direct_alice.as_hex, standard_id, LATER)["found"] is False
    assert acv.check_credential(direct_bob.as_hex, "CS-000009", LATER)["found"] is False
    assert acv.check_credential(direct_bob.as_hex, standard_id, "yesterday")["found"] is False


def test_the_actions_view_says_what_can_happen_next(acv, direct_vm, direct_alice,
                                                    direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id = s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    pending = acv.get_actions(claim_id, s.NOW)
    assert pending["may_assess"] and pending["may_withdraw"] and not pending["may_lapse"]
    assert acv.get_actions(claim_id, LATER)["effective_status"] == "CANCELLED"
    s.panel(direct_vm, s.verified_said())
    acv.assess(claim_id)
    assessed_now = acv.get_actions(claim_id, s.NOW)
    assert assessed_now["may_contest"] and not assessed_now["may_finalize"]
    assert acv.get_actions(claim_id, LATER)["may_finalize"] is True


def test_the_evidence_status_view_before_and_after(acv, direct_vm, direct_alice,
                                                   direct_bob):
    standard_id, digest = setup(acv, direct_vm, direct_alice)
    claim_id = s.filed(acv, direct_vm, direct_bob, standard_id, digest)
    before = acv.get_evidence_status(claim_id)
    assert [i["status"] for i in before["items"]] == ["", "", ""]
    s.panel(direct_vm, s.verified_said())
    acv.assess(claim_id)
    after = acv.get_evidence_status(claim_id)
    assert [i["status"] for i in after["items"]] == ["RETRIEVED"] * 3
    assert [i["names_agent"] for i in after["items"]] == [True, True, False]
    assert after["independent_origins"] == ["outputs.example.net", "runs.example.org"]
