"""Property-based tests of the controller's invariants (Hypothesis).

Example-based tests check chosen cases. These check statements that must hold for EVERY sequence of tool results, so they find
cases nobody thought of. They test only: they change no controller behaviour and read no published result.
"""
import pytest

pytest.importorskip("hypothesis")

from hypothesis import given, settings, strategies as st  # noqa: E402

from netwing.backend import ToolResult  # noqa: E402
from netwing.controller import Controller, Verdict  # noqa: E402

TOOLS = ["ping", "traceroute", "dns_lookup", "port_check", "show_routes"]
CATEGORIES = ["connectivity", "dns", "port", "invalid"]
FAULTS = ["dns_failure", "route_failure", "port_blocked"]

result_st = st.builds(
    ToolResult,
    tool=st.sampled_from(TOOLS),
    args=st.fixed_dictionaries({"dst": st.sampled_from(["web.lab", "10.0.2.10"])}),
    output=st.just("x"),
    ok=st.booleans(),
    category=st.sampled_from(CATEGORIES),
    evidence=st.booleans(),
)
ledger_st = st.lists(result_st, max_size=20)
cap_st = st.integers(min_value=1, max_value=15)

PROFILE = settings(max_examples=300, deadline=None)


def feed(results, max_tests=12):
    c = Controller(max_tests=max_tests)
    ids = [c.observe(r) for r in results]
    return c, ids


def has_failing_evidence(results):
    return any((not r.ok) and r.evidence and r.category != "invalid" for r in results)


@PROFILE
@given(ledger_st)
def test_ledger_ids_are_sequential_and_count_every_test(results):
    c, ids = feed(results)
    assert ids == [f"E{i}" for i in range(1, len(results) + 1)]
    assert c.tests_run == len(results)


@PROFILE
@given(ledger_st, cap_st)
def test_decide_is_deterministic_and_has_no_hidden_state(results, cap):
    c, _ = feed(results, cap)
    first = c.decide()
    assert c.decide() == first
    fresh, _ = feed(results, cap)
    assert fresh.decide() == first


@PROFILE
@given(ledger_st, cap_st)
def test_decision_after_k_results_equals_a_fresh_controller_on_that_prefix(results, cap):
    """Append-only ledger: the verdict at step k depends only on the first k results, never on later ones."""
    c = Controller(max_tests=cap)
    for k, r in enumerate(results, start=1):
        c.observe(r)
        fresh, _ = feed(results[:k], cap)
        assert c.decide() == fresh.decide()


@PROFILE
@given(ledger_st, cap_st)
def test_never_stops_with_a_fault_without_a_failing_result(results, cap):
    c, _ = feed(results, cap)
    if c.decide() == Verdict.STOP_FAULT:
        assert has_failing_evidence(results)


@PROFILE
@given(ledger_st, cap_st)
def test_budget_is_respected_in_the_verdict(results, cap):
    c, _ = feed(results, cap)
    verdict = c.decide()
    if verdict == Verdict.STOP_CAP:
        assert c.tests_run >= cap
    if c.tests_run >= cap:
        assert verdict != Verdict.CONTINUE


@PROFILE
@given(ledger_st, st.sampled_from(["fault", "healthy"]), st.sampled_from(FAULTS))
def test_a_claim_citing_a_nonexistent_id_is_always_rejected(results, verdict, fault):
    c, _ = feed(results)
    ok, message = c.allow_claim(verdict, fault, [f"E{len(results) + 5}"])
    assert not ok
    assert "does not exist" in message


@PROFILE
@given(ledger_st, st.sampled_from(FAULTS), st.data())
def test_an_accepted_fault_claim_always_rests_on_a_failing_result(results, fault, data):
    c, ids = feed(results)
    cited = data.draw(st.lists(st.sampled_from(ids), max_size=4)) if ids else []
    ok, _ = c.allow_claim("fault", fault, cited)
    if ok:
        assert has_failing_evidence(results)


@PROFILE
@given(ledger_st)
def test_the_default_controller_never_calls_a_failing_network_healthy(results):
    c, _ = feed(results)
    standing = c._failures()
    ok, _ = c.allow_claim("healthy", "none", [])
    if ok:
        assert not standing
        assert any(r.ok and r.evidence and r.category != "invalid" for r in results)


@PROFILE
@given(ledger_st)
def test_invalid_results_never_count_as_evidence(results):
    """Turning every result into an invalid one must make the controller see no failures and no coverage."""
    invalid = [ToolResult(tool=r.tool, args=r.args, output=r.output, ok=r.ok, category="invalid", evidence=r.evidence) for r in results]
    c, _ = feed(invalid)
    assert c._failures() == []
    assert c.decide() in (Verdict.CONTINUE, Verdict.STOP_CAP)


def test_a_blip_cleared_by_two_identical_passes_is_not_a_standing_failure():
    fail = ToolResult(tool="ping", args={"dst": "web.lab"}, ok=False, category="connectivity")
    ok = ToolResult(tool="ping", args={"dst": "web.lab"}, ok=True, category="connectivity")
    c, _ = feed([fail, ok, ok])
    assert c._failures() == []
