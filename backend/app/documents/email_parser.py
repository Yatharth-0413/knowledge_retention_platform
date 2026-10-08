"""Parsing for Outlook-style email files (.msg and .eml).

Produces a plain dict (subject, sender, date, cleaned body, attachments) that
the upload route turns into Document rows. Like extraction.py, fidelity is
"good enough for chunking and topic extraction", not a faithful mail client.
"""

import base64
import io
import re
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime

from bs4 import BeautifulSoup


class EmailParseError(Exception):
    pass


# A match on any of these marks the start of quoted history / forwarded headers;
# everything from that point on is dropped. Matched per line (re.MULTILINE).
_REPLY_CHAIN_PATTERNS = [
    re.compile(r"^\s*-{2,}\s*(?:Original Message|Forwarded message)\s*-{2,}", re.I | re.M),
    re.compile(r"^\s*_{5,}\s*$", re.M),  # Outlook's underscore divider
    # "On Mon, 3 Jun 2024 at 10:15, Priya <p@x.com> wrote:" (may wrap onto 2 lines)
    re.compile(r"^\s*On\s[^\n]{0,200}(?:\n[^\n]{0,200})?\swrote:\s*$", re.I | re.M),
    # Outlook header block: "From: ..." followed within 3 lines by "Sent:" or "Date:"
    re.compile(r"^\s*From:[^\n]*\n(?:[^\n]*\n){0,2}\s*(?:Sent|Date):", re.I | re.M),
]
_QUOTED_LINE = re.compile(r"^\s*>.*$", re.M)
_BLANK_RUNS = re.compile(r"\n{3,}")
_LOOKS_LIKE_HTML = re.compile(r"<(?:html|body|div|p|br|table|span)[\s>/]", re.I)


def clean_email_body(html_or_text: str) -> str:
    """Strip HTML and cut off quoted reply chains / forwarded headers.

    If trimming would leave nothing (e.g. a pure forward), the un-trimmed text
    is returned so the content isn't lost.
    """
    if not html_or_text:
        return ""

    text = html_or_text
    if _LOOKS_LIKE_HTML.search(text):
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        # Newline only at block boundaries so inline tags (<b>, <a>) don't split sentences.
        for tag in soup.find_all(["br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
            tag.append("\n")
        text = soup.get_text("")

    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = _BLANK_RUNS.sub("\n\n", text).strip()

    cut = len(text)
    for pattern in _REPLY_CHAIN_PATTERNS:
        match = pattern.search(text)
        if match:
            cut = min(cut, match.start())
    trimmed = _QUOTED_LINE.sub("", text[:cut])
    trimmed = _BLANK_RUNS.sub("\n\n", trimmed).strip()
    return trimmed or text


def parse_outlook_file(file_bytes: bytes, file_name: str) -> dict:
    """Parse a .msg or .eml file.

    Returns {"subject", "sender_email", "sender_name", "date" (datetime | None),
    "body" (cleaned), "attachments": [(filename, content_bytes), ...]}.
    Raises EmailParseError for unsupported extensions or corrupt files.
    """
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    try:
        if extension == "msg":
            return _parse_msg(file_bytes)
        if extension == "eml":
            parsed = _parse_eml(file_bytes)
            # mail-parser is lenient and returns empties for non-email input.
            if not (parsed["subject"] or parsed["body"] or parsed["sender_email"] or parsed["attachments"]):
                raise EmailParseError("File contains no recognizable email content")
            return parsed
    except EmailParseError:
        raise
    except Exception as exc:  # noqa: BLE001 - library errors vary widely on corrupt input
        raise EmailParseError(f"Could not parse email file: {exc}") from exc
    raise EmailParseError(f"Unsupported email file type: .{extension}")


def _parse_msg(file_bytes: bytes) -> dict:
    import extract_msg

    msg = extract_msg.Message(io.BytesIO(file_bytes))
    try:
        sender_name, sender_email = parseaddr(str(msg.sender or ""))
        # msg.sender is usually "Name <addr>", but Exchange senders can be a bare name.
        sender_email = sender_email if "@" in sender_email else str(getattr(msg, "senderEmail", "") or "")
        raw_body = msg.htmlBody or msg.body or ""
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode("utf-8", errors="replace")

        attachments = []
        for att in msg.attachments:
            data = getattr(att, "data", None)
            name = getattr(att, "longFilename", None) or getattr(att, "shortFilename", None)
            # Embedded messages expose a Message object (not bytes) as data; skip those.
            if name and isinstance(data, (bytes, bytearray)):
                attachments.append((str(name), bytes(data)))

        return {
            "subject": str(msg.subject or "").strip(),
            "sender_email": sender_email.strip().lower(),
            "sender_name": (sender_name or str(getattr(msg, "senderName", "") or "")).strip(),
            "date": _coerce_date(msg.date),
            "body": clean_email_body(raw_body),
            "attachments": attachments,
        }
    finally:
        msg.close()


def _parse_eml(file_bytes: bytes) -> dict:
    import mailparser

    mail = mailparser.parse_from_bytes(file_bytes)
    from_pairs = mail.from_ or []
    sender_name, sender_email = from_pairs[0] if from_pairs else ("", "")

    raw_body = "\n".join(mail.text_html) if mail.text_html else "\n".join(mail.text_plain)

    attachments = []
    for att in mail.attachments:
        name = att.get("filename")
        payload = att.get("payload")
        if not name or payload is None:
            continue
        # mail-parser base64-encodes binary payloads and leaves text payloads as str.
        content = base64.b64decode(payload) if att.get("binary") else str(payload).encode("utf-8")
        attachments.append((str(name), content))

    return {
        "subject": (mail.subject or "").strip(),
        "sender_email": (sender_email or "").strip().lower(),
        "sender_name": (sender_name or "").strip(),
        "date": _coerce_date(mail.date),
        "body": clean_email_body(raw_body),
        "attachments": attachments,
    }


def _coerce_date(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
        try:  # RFC 2822, as in a raw "Date:" header (.msg often exposes it this way)
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    return None
