import pytest
from netwing.backend import ToolResult
from netwing.controller import Controller


def _fail_dns():
    c = Controller()
    e = c.observe(ToolResult(tool="dns_lookup", args={}, output="x", ok=False, category="dns"))
    c.observe(ToolResult(tool="dns_lookup", args={}, output="x", ok=False, category="dns"))  # reproduced
    c.observe(ToolResult(tool="ping", args={}, output="x", ok=True, category="connectivity"))
    c.observe(ToolResult(tool="port_check", args={}, output="x", ok=True, category="port"))
    return c, e


@pytest.mark.parametrize("fmt", ["[{e}]", "{e}: dns lookup failed", "[{e}] SERVFAIL", " {e} "])
def test_model_style_evidence_citations_are_accepted(fmt):
    c, e = _fail_dns()
    ok, why = c.allow_claim("fault", "dns_failure", [fmt.format(e=e)])
    assert ok, why


def test_citation_of_nonexistent_id_still_rejected():
    c, _ = _fail_dns()
    ok, _ = c.allow_claim("fault", "dns_failure", ["[E9] made up"])
    assert not ok


def test_text_with_no_id_is_rejected():
    c, _ = _fail_dns()
    ok, _ = c.allow_claim("fault", "dns_failure", ["it was DNS"])
    assert not ok
