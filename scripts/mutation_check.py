#!/usr/bin/env python3
"""Mutation kill check: prove the Direct Mode suite pins each load-bearing
guard, not merely that the code passes today.

For each mutation the repository is copied to a scratch directory with ONE
guard in the contract mechanically broken, and the whole Direct Mode suite
runs against the copy. A mutation is KILLED when the suite fails and SURVIVED
when it passes (an unpinned guard). The run starts with an accept-control:
the unmodified copy must pass, or every kill would be vacuous.

Anchors are code TEXT, never line numbers. An anchor that is not found
exactly once is reported as ANCHOR MISSING - the guard moved or was deleted,
which is its own finding.

Run:  python scripts/mutation_check.py              (full sweep)
      python scripts/mutation_check.py --anchors    (anchor check only)
      python scripts/mutation_check.py --only gate  (names containing "gate";
                                                     separate several with |)
      python scripts/mutation_check.py --jobs 3     (three scratch copies)
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = "contracts/agent_credential_verifier.py"


def off(condition: str) -> tuple:
    """(anchor, replacement) turning one `if` line into `if False:`."""
    head = condition[:len(condition) - len(condition.lstrip())]
    keyword = condition.lstrip().split(" ", 1)[0]
    return (condition + "\n", head + keyword + " False:\n")


def m(name: str, anchor: str, replacement: str = None) -> tuple:
    if replacement is None:
        anchor, replacement = off(anchor)
    return (name, anchor, replacement)


MUTATIONS = [
    # -- retrieval ------------------------------------------------------------------------
    m("a redirect is read as a retrieved item", "    if 300 <= code < 400:"),
    m("a 404 is a generic failure", "    if code in (404, 410):"),
    m("a forbidden document is a generic failure", "    if code in (401, 403):"),
    m("a binary content type is read",
      '    if content_type != "" and not any(t in content_type for t in TEXT_TYPES):'),
    m("an undecodable body is read",
      '    if text is None:\n        return (_empty_source(INVALID_CONTENT',
      '    if False:\n        return (_empty_source(INVALID_CONTENT'),
    m("an oversized document is not marked partial",
      "    truncated = len(body) > BODY_BYTES_CAP or len(normalized) > TEXT_CAP\n",
      "    truncated = False\n"),
    # -- evidence integrity ---------------------------------------------------------------
    m("a pinned item's bytes are not checked against the declared digest",
      '                and source["raw_sha256"] != item["sha256"]:',
      '                and False:'),
    m("a digest mismatch is judged by the panel anyway",
      '    if any(s["status"] == DIGEST_MISMATCH for s in sources):'),
    m("a round with no readable evidence is judged anyway",
      '    if not any(s["status"] in READABLE for s in sources):'),
    m("evidence addressing the verifier is judged anyway",
      "    if len(markers) > 0:\n        return \"SOURCE_ADDRESSES_VERIFIER\"\n",
      "    if False:\n        return \"SOURCE_ADDRESSES_VERIFIER\"\n"),
    m("text in the visible body is not scanned", "    if body_hit:"),
    m("markup and attributes are not scanned",
      "    if not body_hit and _evaluator_hits(_scan_form(raw_text)):"),
    m("the title is not scanned", '    if _evaluator_hits(_scan_form(source["title"])):'),
    m("nothing is bound to a declared item, so bytes are neither compared nor stored",
      "def _item_of(ctx: dict, evidence_id: str):\n"
      '    for item in ctx["evidence"]:\n',
      "def _item_of(ctx: dict, evidence_id: str):\n"
      "    return None\n"
      '    for item in ctx["evidence"]:\n'),
    # -- a description is a claim, never evidence -----------------------------------------
    m("a claim of nothing but assertions reaches the panel",
      "    if len(_demonstrations(ctx, sources)) == 0:"),
    m("a claim whose demonstrations never name the agent reaches the panel",
      "    if len(named) == 0:"),
    m("an assertion that names the agent counts as a named demonstration",
      '            if item["role"] == ROLE_DEMONSTRATION and _names_agent(text, '
      'ctx["agent_name"]):',
      '            if _names_agent(text, ctx["agent_name"]):'),
    m("a demonstration need not name the agent",
      '            if item["role"] == ROLE_DEMONSTRATION and _names_agent(text, '
      'ctx["agent_name"]):',
      '            if item["role"] == ROLE_DEMONSTRATION:'),
    m("any text names any agent",
      "    return len(words) > 0 and _find_run(_word_tokens(text), words, 0) >= 0\n",
      "    return True\n"),
    m("an assertion counts as a demonstration",
      '        if s["status"] in READABLE and item is not None and item["role"] == '
      'ROLE_DEMONSTRATION:',
      '        if s["status"] in READABLE and item is not None:'),
    m("a reading about the agent's own work may quote any readable item",
      "    if state in (DEMONSTRATED, FAILED):\n"
      "        return [e for e in eligible if e in named]\n",
      "    if False:\n        return [e for e in eligible if e in named]\n"),
    m("a failure may be quoted from a record of another agent",
      "    if state in (DEMONSTRATED, FAILED):\n", "    if state == DEMONSTRATED:\n"),
    m("an agent name may be a word any document contains",
      '    if len("".join(_word_tokens(value))) < AGENT_NAME_MIN:'),
    m("the agent's description is not screened",
      '        error = _text_error(agent_description, AGENT_DESCRIPTION_CAP, '
      '"agent_description",\n                            True)\n'
      '        if error != "":\n            self._fail(error)\n',
      ""),
    # -- what a reading must show ----------------------------------------------------------
    m("a reading that bears on the credential needs no quote",
      "    if state in QUOTED_STATES:\n        return len(quotes) > 0\n",
      "    if state in QUOTED_STATES:\n        return True\n"),
    m("a spliced quote is accepted when the panel answers",
      '        if _spliced(rq["text"]):\n            continue\n', ""),
    m("a spliced quote passes the gate",
      '        if q in seen or _spliced(q["text"]) or not _quote_grounded(q, quotable, texts):',
      "        if q in seen or not _quote_grounded(q, quotable, texts):"),
    m("a quote need not ground in the text this node retrieved",
      "    return _grounds_in_order(_word_tokens(source), quote[\"text\"])\n",
      "    return True\n"),
    m("the gate lets a demonstration quote any readable item",
      '    quotable = _quotable(f["state"], eligible, named)\n',
      "    quotable = eligible\n"),
    # -- the credential --------------------------------------------------------------------
    m("a code reason is overridden by the panel's reading",
      '    if reason != "":\n        return (INSUFFICIENT_EVIDENCE, reason)\n',
      '    if False:\n        return (INSUFFICIENT_EVIDENCE, reason)\n'),
    m("an unusable panel answer reaches a credential",
      '    if payload["panel_state"] != PANEL_ASSESSED:\n'
      '        return (INSUFFICIENT_EVIDENCE, "PANEL_UNUSABLE")',
      '    if False:\n        return (INSUFFICIENT_EVIDENCE, "PANEL_UNUSABLE")'),
    m("contradictory evidence is credited anyway",
      "    if _state_of(payload, SUBJECT_CONSISTENCY) == CONTRADICTORY:"),
    m("a failed required demonstration is credited",
      "    if any(state == FAILED for _r, state in required):"),
    m("an unclear required reading is credited",
      "    if any(state == UNCLEAR for _r, state in required):"),
    m("an optional requirement decides the credential",
      '    required = [(r, state) for r, state in _requirement_states(ctx, payload) '
      'if r["required"]]\n',
      "    required = _requirement_states(ctx, payload)\n"),
    m("no demonstration at all falls through to the corroboration floor",
      "    if len(shown) == 0:"),
    m("a description read as such is reported as undemonstrated",
      "        if any(state == ASSERTED_ONLY for _r, state in required):"),
    m("the corroboration floor does not hold",
      '    if not pinned_only or len(origins) < ctx["standard"]["min_independent_origins"]:',
      "    if not pinned_only:"),
    m("unbound bytes may carry a credential",
      '    if not pinned_only or len(origins) < ctx["standard"]["min_independent_origins"]:',
      '    if len(origins) < ctx["standard"]["min_independent_origins"]:'),
    m("corroboration counts items, not distinct hosts",
      '            hosts.append(_host_of(item["url"]))\n',
      '            hosts.append(item["evidence_id"])\n'),
    m("a partial demonstration is a full credential",
      "    if len(shown) == len(required):", "    if len(shown) > 0:"),
    m("an optional demonstration counts toward the credential",
      '            if r["required"] and state == DEMONSTRATED]\n',
      "            if state == DEMONSTRATED]\n"),
    m("a negative credential carries a scope",
      "    if verdict not in POSITIVE_VERDICTS:\n        return []\n", ""),
    m("the scope includes requirements read on unbound bytes",
      "            if state == DEMONSTRATED\n"
      '            and _bound(ctx, payload, _requirement_subject(r["requirement_id"]))]\n',
      "            if state == DEMONSTRATED]\n"),
    # -- what validators compare -----------------------------------------------------------
    m("the consequence is not compared",
      "    for key in sorted(mine.keys()):\n        if mine[key] != theirs[key]:\n",
      "    for key in sorted(mine.keys()):\n        if False:\n"),
    m("the scope is not compared",
      '        "verdict": verdict, "reason_code": reason, "scope": scope,\n',
      '        "verdict": verdict, "reason_code": reason,\n'),
    m("which items name the agent is not compared",
      '    if own["named"] != theirs["named"]:'),
    m("the named list is not gated",
      "    return all(isinstance(e, str) and e in demonstrations for e in named)\n",
      "    return True\n"),
    m("the leader's payload is gated against its own text, not this node's",
      "        parsed = _parse_payload(leader_res.calldata, ctx, own_texts)\n",
      "        parsed = _parse_payload(leader_res.calldata, ctx, None)\n"),
    m("a transient failure ratifies a different failure",
      "        if leader_text.startswith(ERROR_TRANSIENT):\n"
      "            return own_text.startswith(ERROR_TRANSIENT)\n"
      "        return own_text == leader_text\n",
      "        return True\n"),
    m("a payload about another claim is accepted",
      '            or p["claim_id"] != ctx["claim_id"] or not _is_int(p["round"]) \\\n',
      '            or not _is_int(p["round"]) \\\n'),
    # -- the standard ----------------------------------------------------------------------
    m("a standard need not name its evidence sources",
      '    if not isinstance(domains, list) or len(domains) < 1 or len(domains) > MAX_DOMAINS \\\n',
      "    if False \\\n"),
    m("a requirement id may shadow a built-in subject",
      "    if text.upper() in BUILT_IN_SUBJECTS:"),
    m("no requirement need be required",
      '    if not any(entry["required"] for entry in values):'),
    m("min_independent_origins may exceed the sources the standard names",
      '    if spec["min_independent_origins"] > len(domains):'),
    m("standard text may address the verifier",
      "    if _evaluator_hits(value) or _hidden_hits(value):"),
    m("the windows are unbounded", '        if not _int_in(spec[field], MIN_WINDOW, MAX_WINDOW):'),
    m("the validity is unbounded",
      '    if not _int_in(spec["validity_seconds"], MIN_VALIDITY, MAX_VALIDITY):'),
    m("an IP literal is a host", "    if all_numeric or labels[-1].isdigit():"),
    # -- the evidence a claim declares ----------------------------------------------------
    m("a pinned item needs no digest", '            if not _is_hex(entry["sha256"], 64):'),
    m("a live item may declare a digest it is not held to", '        elif entry["sha256"] != "":'),
    m("an item need not declare a role", '        if entry["role"] not in EVIDENCE_ROLES:'),
    m("an item may come from any host at all",
      "        if not _domain_allowed(_host_of(canonical_url), domains):"),
    m("the same document may be declared twice", "        if canonical_url in urls:"),
    m("the evidence list is unbounded",
      "    if not isinstance(values, list) or len(values) < 1 or len(values) > MAX_EVIDENCE:"),
    # -- the state machine ------------------------------------------------------------------
    m("a claim may be assessed twice",
      '        if str(claim.status) != CLAIM_PENDING:\n'
      '            self._fail("only a PENDING claim is assessed")',
      '        if False:\n            self._fail("only a PENDING claim is assessed")'),
    m("a claim may be assessed after its window",
      '        if _iso_epoch(now) > _iso_epoch(str(claim.window_ends)):\n'
      '            self._fail("the assess window closed at " + str(claim.window_ends))',
      '        if False:\n'
      '            self._fail("the assess window closed at " + str(claim.window_ends))'),
    m("a credential may be contested twice", "        if bool(claim.contested):"),
    m("a stranger may contest a credential",
      "        if self._sender_hex() not in (str(claim.claimant), str(standard.issuer)):"),
    m("a credential may be contested after its window",
      '        if _iso_epoch(now) > _iso_epoch(str(claim.window_ends)):\n'
      '            self._fail("the contest window closed at " + str(claim.window_ends))',
      '        if False:\n'
      '            self._fail("the contest window closed at " + str(claim.window_ends))'),
    m("a credential may be made final inside its contest window",
      '        if _iso_epoch(now) <= _iso_epoch(str(claim.window_ends)):\n'
      '            self._fail("the contest window closes at " + str(claim.window_ends))',
      '        if False:\n'
      '            self._fail("the contest window closes at " + str(claim.window_ends))'),
    m("a claim may lapse while its window is open",
      '        if _iso_epoch(now) <= _iso_epoch(str(claim.window_ends)):\n'
      '            self._fail("the assess window closes at " + str(claim.window_ends))',
      '        if False:\n'
      '            self._fail("the assess window closes at " + str(claim.window_ends))'),
    m("anyone may withdraw somebody else's claim",
      "        if self._sender_hex() != str(claim.claimant):"),
    m("a retired standard still takes claims",
      "        if str(standard.status) != STD_ACTIVE:\n"
      '            self._fail("the standard was retired and accepts no new claims")',
      "        if False:\n"
      '            self._fail("the standard was retired and accepts no new claims")'),
    m("anyone may retire a standard", "        if self._sender_hex() != str(standard.issuer):"),
    m("the standard hash a claim commits to is not checked",
      "        if standard_hash != str(standard.definition_hash):"),
    m("one agent may hold two open claims against one standard",
      '        if held is not None and held != "":'),
    m("the open-claim cap does not hold",
      "        if self._counter_value(wallet) >= MAX_OPEN_PER_WALLET:"),
    m("a closed claim keeps the agent's slot",
      "        if self.open_claims.get(key) == str(claim.claim_id):\n"
      '            self.open_claims[key] = ""\n', ""),
    m("finality does not issue the credential",
      "        self.credentials[self._key(str(claim.standard_id), str(claim.claimant))] = \\\n"
      "            str(claim.claim_id)\n", ""),
    m("a credential never expires",
      '        expired = expires != "" and at > _iso_epoch(expires)\n',
      "        expired = False\n"),
    m("a negative credential carries an expiry",
      "            if outcome[\"verdict\"] in POSITIVE_VERDICTS else \"\"\n",
      "            if True else \"\"\n"),
    m("the consumer view is case-sensitive about the address",
      '        wallet = agent.lower() if isinstance(agent, str) else ""\n',
      '        wallet = agent if isinstance(agent, str) else ""\n'),
    m("a record stores a live item's bytes",
      '            pinned = item is not None and item["kind"] == KIND_PINNED\n',
      "            pinned = True\n"),
    m("every reading is marked compared",
      '            entry["compared"] = self._compared(ctx, outcome, finding)\n',
      '            entry["compared"] = True\n'),
    m("the verified count is not corrected when a contest overturns",
      "        if was_verified and not now_verified:\n"
      "            self.verified_counter = u32(int(self.verified_counter) - 1)\n", ""),
]


def run_suite(workdir: pathlib.Path) -> bool:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/direct", "-q", "-x", "-p", "no:cacheprovider",
         "--no-header"], cwd=workdir, capture_output=True, text=True)
    return completed.returncode == 0


def check_anchors(source: str) -> int:
    missing = 0
    for name, old, _new in MUTATIONS:
        hits = source.count(old)
        if hits != 1:
            print(f"ANCHOR MISSING ({hits} hits): {name}")
            missing += 1
    return missing


def copy_repo(scratch: pathlib.Path, index: int) -> pathlib.Path:
    work = scratch / ("repo%d" % index)
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "deploy", "artifacts", ".data", "docs"))
    return work


def main() -> None:
    source = (ROOT / CONTRACT).read_text(encoding="utf-8")
    missing = check_anchors(source)
    print(f"{len(MUTATIONS)} mutations, {missing} anchor problems")
    if "--anchors" in sys.argv:
        sys.exit(0 if missing == 0 else 1)
    only = ""
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].casefold()
    jobs = 1
    if "--jobs" in sys.argv:
        jobs = max(1, int(sys.argv[sys.argv.index("--jobs") + 1]))
    todo = [x for x in MUTATIONS if source.count(x[1]) == 1
            and (not only or any(part in x[0].casefold() for part in only.split("|")))]
    jobs = min(jobs, max(1, len(todo)))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="acv-mut-"))
    copies = [copy_repo(scratch, i) for i in range(jobs)]
    print("accept-control: unmodified copy must pass ...", flush=True)
    if not run_suite(copies[0]):
        print("CONTROL FAILED: the unmodified suite does not pass; aborting")
        shutil.rmtree(scratch, ignore_errors=True)
        sys.exit(1)
    print(f"control green; {len(todo)} mutations over {jobs} job(s)\n", flush=True)
    results = [None] * len(todo)
    cursor = [0]
    done = [0]
    lock = threading.Lock()

    def worker(work: pathlib.Path) -> None:
        target = work / CONTRACT
        while True:
            with lock:
                i = cursor[0]
                if i >= len(todo):
                    return
                cursor[0] = i + 1
            name, old, new = todo[i]
            target.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
            passed = run_suite(work)
            target.write_text(source, encoding="utf-8", newline="\n")
            with lock:
                results[i] = passed
                done[0] += 1
                print(f"  [{done[0]}/{len(todo)}] {'SURVIVED' if passed else 'killed  '}: "
                      f"{name}", flush=True)

    threads = [threading.Thread(target=worker, args=(w,)) for w in copies]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    shutil.rmtree(scratch, ignore_errors=True)
    print()
    killed = survived = 0
    for (name, _old, _new), passed in zip(todo, results):
        print(("SURVIVED: " if passed else "killed:   ") + name)
        survived += 1 if passed else 0
        killed += 0 if passed else 1
    print(f"\nmutations: {killed} killed, {survived} survived, {missing} anchor missing")
    sys.exit(0 if survived == 0 and missing == 0 else 1)


if __name__ == "__main__":
    main()
