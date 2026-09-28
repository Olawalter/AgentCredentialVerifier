"""The live-run fixtures, checked against the deployed code.

The panel's readings cannot be checked here - that is what the live run is for -
but everything around them can: the standard parses, each declared digest is the
digest of the document that will be served, every referenced document exists
unless the case is about its absence, the injected document trips the marker scan
and no honest one does, and the code-decided cases decide in code.
"""

import hashlib
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"

STANDARDS = json.loads((FIXTURES / "standards.json").read_text(encoding="utf-8"))
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
MISSING = ("evidence/run-0499.json", "evidence/bl-9999-verification.html")
INJECTED = ("evidence/bl-7731-verification-annotated.html",)
AGENT = CASES["agent_name"]


def _text(path: str) -> str:
    return (FIXTURES / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(STANDARDS))
def test_every_standard_parses(mod, name):
    error, spec = mod._parse_standard(json.dumps(STANDARDS[name]))
    assert error == "", name
    assert sorted(spec["evidence_domains"]) == sorted(CASES["origins"])


def test_the_catalogue_is_coherent(mod):
    for case in CASES["cases"]:
        code = case["case"]
        assert case["standard"] in STANDARDS, code
        assert case["expect_verdict"] in mod.VERDICTS, code
        assert case["expect_reason"] in mod.REASON_CODES, code
        assert mod._agent_name_error(case["agent_name"]) == "", code
        assert mod._text_error(case["description"], mod.AGENT_DESCRIPTION_CAP, "d",
                               True) == "", code
        assert 1 <= len(case["evidence"]) <= mod.MAX_EVIDENCE, code
        ids = [r["requirement_id"] for r in STANDARDS[case["standard"]]["requirements"]]
        assert set(case["expect_scope"]) <= set(ids), code
        assert bool(case["expect_scope"]) == (case["expect_verdict"]
                                              in mod.POSITIVE_VERDICTS), code
    assert CASES["contest_case"] in [c["case"] for c in CASES["cases"]]
    assert len({c["wallet"] for c in CASES["cases"]}) == len(CASES["cases"])


def test_every_verdict_and_every_reason_the_live_run_can_reach_is_exercised():
    verdicts = {c["expect_verdict"] for c in CASES["cases"]}
    assert verdicts == {"VERIFIED", "PARTIALLY_VERIFIED", "NOT_VERIFIED",
                        "INSUFFICIENT_EVIDENCE", "CANCELLED"}
    reasons = {c["expect_reason"] for c in CASES["cases"]}
    for reason in ("CAPABILITY_DEMONSTRATED", "PARTIAL_DEMONSTRATION",
                   "DEMONSTRATION_FAILED", "ONLY_ASSERTED", "ASSERTIONS_ONLY",
                   "AGENT_NOT_NAMED", "EVIDENCE_DIGEST_MISMATCH", "NO_EVIDENCE_READABLE",
                   "SOURCE_ADDRESSES_VERIFIER", "CORROBORATION_SHORT",
                   "EVIDENCE_CONTRADICTORY", "LAPSED"):
        assert reason in reasons, reason


def test_only_the_description_case_tolerates_a_second_reason():
    """A feature list may be read ASSERTED_ONLY or NOT_DEMONSTRATED; both are
    NOT_VERIFIED. That case asserts the verdict and accepts either reason; every
    other case asserts one exact reason."""
    tolerant = [c for c in CASES["cases"] if c.get("expect_reason_any")]
    assert [c["case"] for c in tolerant] == ["AC04"]
    assert tolerant[0]["expect_verdict"] == "NOT_VERIFIED"
    assert set(tolerant[0]["expect_reason_any"]) == {"ONLY_ASSERTED", "NOT_DEMONSTRATED"}


def test_every_declared_digest_is_the_digest_of_the_document_that_is_served():
    for case in CASES["cases"]:
        for entry in case["evidence"]:
            if entry["kind"] != "PINNED" or entry["path"] in MISSING:
                continue
            if case["expect_reason"] == "EVIDENCE_DIGEST_MISMATCH":
                continue        # that case declares a wrong digest on purpose
            served = hashlib.sha256((FIXTURES / entry["path"]).read_bytes()).hexdigest()
            assert entry["sha256"] == served, (case["case"], entry["path"])


def test_the_mismatch_case_declares_one_digest_that_cannot_match():
    case = [c for c in CASES["cases"] if c["expect_reason"] == "EVIDENCE_DIGEST_MISMATCH"][0]
    wrong = [e for e in case["evidence"]
             if e["sha256"] != hashlib.sha256((FIXTURES / e["path"]).read_bytes()).hexdigest()]
    assert len(wrong) == 1


def test_every_named_document_exists_unless_the_case_is_about_its_absence():
    for case in CASES["cases"]:
        for entry in case["evidence"]:
            exists = (FIXTURES / entry["path"]).exists()
            assert exists != (entry["path"] in MISSING), (case["case"], entry["path"])


def test_no_document_is_unreferenced():
    served = {"evidence/" + p.name for p in (FIXTURES / "evidence").iterdir()}
    referenced = {e["path"] for c in CASES["cases"] for e in c["evidence"]}
    assert served - referenced == set()


def test_every_document_says_it_is_a_fixture():
    for path in (FIXTURES / "evidence").iterdir():
        text = path.read_text(encoding="utf-8")
        assert "TEST / DEMONSTRATION ONLY" in text and "NOT FOR PRODUCTION" in text, path.name


@pytest.mark.parametrize("path", sorted("evidence/" + p.name
                                        for p in (FIXTURES / "evidence").iterdir()))
def test_the_marker_scan_agrees_with_what_each_document_is(mod, path):
    raw = _text(path)
    html = path.endswith(".html")
    source = {"status": "RETRIEVED", "title": mod._title_of(raw, html)}
    found = mod._markers(source, mod._normalize(raw, html), raw)
    assert bool(found) == (path in INJECTED), (path, found)


def test_only_the_other_agents_run_does_not_name_the_agent(mod):
    for path in (FIXTURES / "evidence").iterdir():
        raw = path.read_text(encoding="utf-8")
        text = mod._normalize(raw, path.name.endswith(".html"))
        assert mod._names_agent(text, AGENT) == (path.name != "cargoscan-run.json"), \
            path.name


def test_verification_is_shown_only_by_the_report():
    """So a credential covering every requirement must quote the second origin."""
    mentions = {p.name for p in (FIXTURES / "evidence").iterdir()
                if "issuing registry" in p.read_text(encoding="utf-8")}
    # the two reports, and the feature list - which only asserts it
    assert mentions == {"bl-7731-verification.html",
                        "bl-7731-verification-annotated.html", "features.html"}
    for name in ("run-0412.json", "run-0413.json", "run-0415.json"):
        assert "Registry verification" not in _text("evidence/" + name), name


def test_the_corroboration_cases_rest_on_what_they_claim():
    short = [c for c in CASES["cases"] if c["expect_reason"] == "CORROBORATION_SHORT"]
    assert len(short) == 2
    for case in short:
        origins = {e["origin"] for e in case["evidence"]}
        kinds = {e["kind"] for e in case["evidence"]}
        assert len(origins) == 1 or kinds == {"LIVE"}, case["case"]
    verified = [c for c in CASES["cases"] if c["expect_verdict"] == "VERIFIED"][0]
    demonstrations = [e for e in verified["evidence"] if e["role"] == "DEMONSTRATION"]
    assert len({e["origin"] for e in demonstrations}) == 2
    assert all(e["kind"] == "PINNED" for e in demonstrations)


def test_the_code_decided_cases_are_built_to_decide_in_code(mod):
    only_assertions = [c for c in CASES["cases"] if c["expect_reason"] == "ASSERTIONS_ONLY"]
    assert all(e["role"] == "ASSERTION" for e in only_assertions[0]["evidence"])
    not_named = [c for c in CASES["cases"] if c["expect_reason"] == "AGENT_NOT_NAMED"][0]
    for entry in not_named["evidence"]:
        text = mod._normalize(_text(entry["path"]), entry["path"].endswith(".html"))
        assert entry["role"] == "DEMONSTRATION" and not mod._names_agent(text, AGENT)
