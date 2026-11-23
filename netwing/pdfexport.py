"""Native PDF export of an investigation report (no third-party library).

Writes a plain, text-only PDF 1.4 with the built-in Helvetica fonts: wrapped lines, page breaks, a header and
page numbers. Characters outside Latin-1 are replaced with '?'. The content mirrors the HTML report.
"""
from __future__ import annotations

import textwrap

from .health import compute_health
from .report import _RECOMMEND, _limitations

PAGE_W, PAGE_H, MARGIN = 595, 842, 50  # A4 in points
_LEAD = 13


def _esc(s: str) -> bytes:
    b = s.encode("latin-1", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _lines(rec: dict) -> list[tuple[str, str, int]]:
    """(font, text, size) for every line of the report, already wrapped."""
    out: list[tuple[str, str, int]] = []

    def h(t):
        out.extend([("F2", "", 11), ("F2", t, 13)])

    def p(t, width=92, indent=""):
        for chunk in str(t).splitlines() or [""]:
            for ln in textwrap.wrap(chunk, width) or [""]:
                out.append(("F1", indent + ln, 10))

    health = compute_health(rec["tests"])
    out.append(("F2", "Network investigation report", 18))
    if rec.get("simulated"):
        out.append(("F2", "SIMULATED network - observations are not real measurements", 10))
    p(f"Record {rec['id']} | scenario {rec['scenario']} | mode {rec['mode']} | model {rec['model']}")
    h("Problem")
    p(rec["ticket"])
    h("Root cause (diagnosis)")
    cause = rec["fault_type"] or ("none found" if rec["verdict"] == "healthy" else "no conclusion")
    if rec["other_faults"]:
        cause += " (also: " + ", ".join(rec["other_faults"]) + ")"
    p(f"{rec['verdict']}: {cause}")
    asr = rec.get("assurance")
    p("Evidence assurance: " + (f"{asr['label']} - {asr['reason']}" if asr else "not assessed (older log)"))
    h("Supporting evidence cited")
    for x in rec["claimed_evidence"] or ["none"]:
        p(x, 88, "- ")
    h(f"Tests performed and observations ({len(rec['tests'])})")
    for t in rec["tests"]:
        p(f"{t['id']}  {t['tool']} {t['args']}  -> {'pass' if t['ok'] else 'FAIL'}", 92)
        p(t["output"], 86, "      ")
    h("Network health (measured values only)")
    sc = "not enough measurements" if health["score"] is None else f"{health['score']}/100 ({health['measured']} of {health['total']} indicators measured)"
    p(f"Score: {sc}. Unmeasured indicators are not assumed healthy.")
    for i in health["indicators"]:
        p(f"{i['label']}: {i['state'].replace('_', ' ')} ({i['measurements']} measurements)", 88, "- ")
    h("Limitations")
    for x in _limitations(rec):
        p(x, 88, "- ")
    h("Recommendations (general guidance)")
    for x in _RECOMMEND.get(rec["fault_type"] or "healthy", _RECOMMEND["healthy"]):
        p(x, 88, "- ")
    return out


def render_pdf(rec: dict) -> bytes:
    """Render an investigation record as a PDF using a minimal built-in writer (no third-party library)."""
    lines = _lines(rec)
    per_page = (PAGE_H - 2 * MARGIN - 20) // _LEAD
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objs: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
                         b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    kids = []
    for n, pg in enumerate(pages, 1):
        parts = [b"BT"]
        y = PAGE_H - MARGIN
        for font, text, size in pg:
            parts.append(b"/%s %d Tf 1 0 0 1 %d %d Tm (%s) Tj" % (font.encode(), size, MARGIN, y, _esc(text)))
            y -= _LEAD
        parts.append(b"/F1 8 Tf 1 0 0 1 %d 30 Tm (NetWing report %s - page %d of %d) Tj ET" % (
            MARGIN, _esc(str(rec["id"])), n, len(pages)))
        stream = b"\n".join(parts)
        objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        cid = len(objs)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>"
                    % (PAGE_W, PAGE_H, cid))
        kids.append(len(objs))
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)
