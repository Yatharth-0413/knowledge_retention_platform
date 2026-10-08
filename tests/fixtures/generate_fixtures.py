"""Generate sample_email.eml and sample_email.msg for exercising email ingestion.

Run: python tests/fixtures/generate_fixtures.py   (needs reportlab for the PDF attachment)

The .msg is built with a small OLE2/CFB writer below, since no Python library writes .msg files.
"""
import io
import struct
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

OUT = Path(__file__).parent

HTML_BODY = """<html><body>
<p>Hi team,</p>
<p>Following up on the <b>Q3 customer-retention review</b>. The decision was to move the
churn-alert threshold from 12% to 9% and to hand the weekly renewal digest to the Support Ops team.
Rationale and owner notes are in the attached PDF.</p>
<p>Thanks,<br>Priya Sharma<br>Customer Success Lead</p>
<div style="border-top:1px solid #ccc">
<p><b>From:</b> Marcus Lee &lt;marcus.lee@example.com&gt;<br>
<b>Sent:</b> Monday, September 29, 2026 9:14 AM<br>
<b>To:</b> Priya Sharma<br><b>Subject:</b> RE: Q3 retention review</p>
<p>Can you confirm the new threshold before Friday? Older reply history that should be stripped.</p>
</div>
<p>On Mon, Sep 29, 2026 at 9:14 AM Marcus Lee wrote:<br>&gt; Previous quoted message.</p>
</body></html>"""

PLAIN_BODY = (
    "Hi,\n\nSharing the Q3 renewal numbers. The attached CSV lists accounts at risk; "
    "Dana owns the follow-ups and the escalation path is Support Ops -> CS Lead.\n\n"
    "Regards,\nPriya Sharma\n\n"
    "-----Original Message-----\nFrom: Marcus Lee\nSent: Monday\nSubject: Q3 numbers\n\nOld quoted text."
)

CSV_DATA = b"account,risk_score,owner\nAcme Corp,0.82,Dana\nGlobex,0.64,Dana\nInitech,0.41,Priya\n"


def make_pdf() -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in [
        "Q3 Retention Review - Decision Notes",
        "Churn-alert threshold lowered from 12% to 9% to catch at-risk accounts earlier.",
        "Weekly renewal digest ownership moves to Support Ops (owner: Dana Whitfield).",
        "Escalations go to the CS Lead if an account stays above threshold for two weeks.",
    ]:
        c.drawString(50, y, line)
        y -= 24
    c.save()
    return buf.getvalue()


def make_eml() -> None:
    msg = EmailMessage()
    msg["From"] = "Priya Sharma <priya.sharma@example.com>"
    msg["To"] = "team@example.com"
    msg["Subject"] = "Q3 retention review - decisions"
    msg["Date"] = format_datetime(datetime(2026, 9, 30, 10, 30, tzinfo=timezone.utc))
    msg.set_content("Plain-text fallback. See the HTML version.")
    msg.add_alternative(HTML_BODY, subtype="html")
    msg.add_attachment(make_pdf(), maintype="application", subtype="pdf", filename="q3_retention_notes.pdf")
    (OUT / "sample_email.eml").write_bytes(bytes(msg))


# ---------------------------------------------------------------- minimal CFB (OLE2) writer
_FREE, _EOC, _FATSECT = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD
_SEC, _MINI, _CUTOFF = 512, 64, 4096


class _Node:
    def __init__(self, name, data=None):
        self.name, self.data, self.children = name, data, []  # data None => storage

    def storage(self, name):
        node = _Node(name)
        self.children.append(node)
        return node

    def stream(self, name, data):
        self.children.append(_Node(name, data))


def _chunks(data: bytes, size: int):
    n = max(1, -(-len(data) // size)) if data else 0
    return [data[i * size:(i + 1) * size].ljust(size, b"\0") for i in range(n)]


def _build_cfb(root: _Node) -> bytes:
    entries = []  # (node, id)

    def walk(node):
        entries.append(node)
        node.id = len(entries) - 1
        for child in node.children:
            walk(child)

    walk(root)

    # Mini stream: small streams packed into 64-byte mini sectors.
    mini_data, mini_fat = bytearray(), []
    for node in entries[1:]:
        node.start = _EOC
        if node.data is None or not node.data:
            continue
        if len(node.data) < _CUTOFF:
            parts = _chunks(node.data, _MINI)
            node.start = len(mini_fat)
            for i, p in enumerate(parts):
                mini_fat.append(len(mini_fat) + 1 if i < len(parts) - 1 else _EOC)
                mini_data += p
    mini_fat_chunks = _chunks(b"".join(struct.pack("<I", v) for v in mini_fat), _SEC)
    mini_stream_chunks = _chunks(bytes(mini_data), _SEC)
    dir_count = -(-len(entries) // 4)
    big = [n for n in entries[1:] if n.data and len(n.data) >= _CUTOFF]
    big_chunks = {id(n): _chunks(n.data, _SEC) for n in big}

    n_other = dir_count + len(mini_fat_chunks) + len(mini_stream_chunks) + sum(len(c) for c in big_chunks.values())
    n_fat = 1
    while n_fat * 128 < n_fat + n_other:
        n_fat += 1
    assert n_fat <= 109, "fixture too large for header-only DIFAT"

    fat = [_FATSECT] * n_fat
    sectors = []  # data sectors after FAT

    def alloc(chunks):
        first = n_fat + len(sectors)
        for i, c in enumerate(chunks):
            fat.append(n_fat + len(sectors) + 1 if i < len(chunks) - 1 else _EOC)
            sectors.append(c)
        return first if chunks else _EOC

    placed = {}
    placed["mini_fat"] = alloc(mini_fat_chunks)
    placed["mini_stream"] = alloc(mini_stream_chunks)
    for n in big:
        n.start = alloc(big_chunks[id(n)])
    def sib_tree(nodes):
        """Return (root_id, left, right) maps for a balanced BST over nodes sorted per CFB rules."""
        nodes = sorted(nodes, key=lambda n: (len(n.name), n.name.upper()))
        left, right = {}, {}

        def build(lo, hi):
            if lo >= hi:
                return 0xFFFFFFFF
            mid = (lo + hi) // 2
            left[nodes[mid].id] = build(lo, mid)
            right[nodes[mid].id] = build(mid + 1, hi)
            return nodes[mid].id

        return build(0, len(nodes)), left, right

    dir_raw = b""
    child_of, lefts, rights = {}, {}, {}
    for node in entries:
        if node.children:
            child_of[node.id], l, r = sib_tree(node.children)
            lefts.update(l)
            rights.update(r)

    for node in entries:
        name = node.name.encode("utf-16-le") + b"\0\0"
        is_root = node is root
        obj_type = 5 if is_root else (1 if node.data is None else 2)
        if is_root:
            start = placed["mini_stream"]
            size = len(mini_data)
        else:
            start = node.start
            size = len(node.data) if node.data is not None else 0
        dir_raw += struct.pack(
            "<64sHBBIII16sIQQIQ",
            name.ljust(64, b"\0"), len(name), obj_type, 1,
            lefts.get(node.id, 0xFFFFFFFF), rights.get(node.id, 0xFFFFFFFF), child_of.get(node.id, 0xFFFFFFFF),
            b"\0" * 16, 0, 0, 0, start if (size or is_root) else _EOC, size,
        )
    dir_raw = dir_raw.ljust(dir_count * _SEC, b"\0")
    # Pad unused directory slots as free entries (type 0, siblings = NOSTREAM).
    used = len(entries) * 128
    free = struct.pack("<64sHBBIII16sIQQIQ", b"\0" * 64, 0, 0, 0, _FREE, _FREE, _FREE, b"\0" * 16, 0, 0, 0, 0, 0)
    dir_raw = dir_raw[:used] + free * ((dir_count * _SEC - used) // 128)
    dir_start = alloc(_chunks(dir_raw, _SEC))

    fat += [_FREE] * (n_fat * 128 - len(fat))
    fat_raw = b"".join(struct.pack("<I", v) for v in fat)
    difat = list(range(n_fat)) + [_FREE] * (109 - n_fat)
    header = (
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 16
        + struct.pack("<HHHHHHIIIIIIIII", 0x3E, 3, 0xFFFE, 9, 6, 0, 0, 0, n_fat, dir_start, 0, _CUTOFF,
                      placed["mini_fat"], len(mini_fat_chunks), _EOC)
        + struct.pack("<I", 0)
        + b"".join(struct.pack("<I", v) for v in difat)
    )
    assert len(header) == 512
    return header + fat_raw + b"".join(sectors)


def make_msg() -> None:
    def str_prop(root, tag, text):
        root.stream(f"__substg1.0_{tag:04X}001F", text.encode("utf-16-le"))

    root = _Node("Root Entry")
    root.storage("__nameid_version1.0").children.extend(
        _Node(f"__substg1.0_{t:08X}", b"") for t in (0x00020102, 0x00030102, 0x00040102)
    )
    sent = datetime(2026, 9, 30, 11, 45, tzinfo=timezone.utc)
    filetime = int((sent - datetime(1601, 1, 1, tzinfo=timezone.utc)).total_seconds() * 10_000_000)
    str_prop(root, 0x0037, "Q3 renewal numbers - at-risk accounts")
    str_prop(root, 0x0C1A, "Priya Sharma")
    str_prop(root, 0x0C1E, "SMTP")
    str_prop(root, 0x0C1F, "priya.sharma@example.com")
    str_prop(root, 0x5D01, "priya.sharma@example.com")
    str_prop(root, 0x1000, PLAIN_BODY.replace("\n", "\r\n"))
    str_prop(root, 0x0E04, "team@example.com")

    # Top-level properties: 32-byte header (recip count, attach count) + 16-byte fixed props.
    props = b"\0" * 8 + struct.pack("<IIII", 1, 1, 1, 1) + b"\0" * 8  # 32-byte header
    props += struct.pack("<HHIQ", 0x0040, 0x0039, 0x6, filetime)  # PR_CLIENT_SUBMIT_TIME
    props += struct.pack("<HHIQ", 0x0040, 0x0E06, 0x6, filetime)  # PR_MESSAGE_DELIVERY_TIME
    props += struct.pack("<HHIQ", 0x0003, 0x0E07, 0x6, 1)  # PR_MESSAGE_FLAGS
    root.stream("__properties_version1.0", props)

    att = root.storage("__attach_version1.0_#00000000")
    str_prop(att, 0x3707, "at_risk_accounts.csv")
    str_prop(att, 0x3704, "AT_RISK~1.CSV")
    str_prop(att, 0x3703, ".csv")
    att.stream("__substg1.0_37010102", CSV_DATA)
    att_props = b"\0" * 8 + struct.pack("<HHIQ", 0x0003, 0x3705, 0x6, 1)  # ATTACH_BY_VALUE
    att.stream("__properties_version1.0", att_props)

    recip = root.storage("__recip_version1.0_#00000000")
    str_prop(recip, 0x3001, "Team")
    str_prop(recip, 0x39FE, "team@example.com")
    recip.stream("__properties_version1.0", b"\0" * 8 + struct.pack("<HHIQ", 0x0003, 0x0C15, 0x6, 1))

    (OUT / "sample_email.msg").write_bytes(_build_cfb(root))


if __name__ == "__main__":
    make_eml()
    make_msg()
    print("wrote", [p.name for p in sorted(OUT.glob("sample_email.*"))])
