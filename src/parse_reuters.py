import re
import html
from datetime import datetime
from typing import Any, Dict, List, Optional

_REUTERS_RE = re.compile(r"(?is)<REUTERS([^>]*)>(.*?)</REUTERS>")


def _strip_tags(s: str) -> str:
    # Remove all XML/HTML tags
    return re.sub(r"(?is)<[^>]+>", " ", s)


def parse_reuters_file(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="latin-1") as f:
        text = f.read()

    docs: List[Dict[str, Any]] = []

    for m in _REUTERS_RE.finditer(text):
        attrs = m.group(1)
        inner = m.group(2)

        # Extract document ID
        newid = re.search(r'NEWID="(\d+)"', attrs, re.I)
        doc_id = newid.group(1) if newid else None

        # extract one tag value
        def tag(name: str) -> str:
            m2 = re.search(rf"(?is)<{name}[^>]*>(.*?)</{name}>", inner)
            return html.unescape(m2.group(1)).strip() if m2 else ""

        # extract list tags like TOPICS or PLACES
        def tag_list(name: str) -> List[str]:
            m2 = re.search(rf"(?is)<{name}[^>]*>(.*?)</{name}>", inner)
            if not m2:
                return []
            return [
                html.unescape(x).strip()
                for x in re.findall(r"(?is)<D>(.*?)</D>", m2.group(1))
                if html.unescape(x).strip()
            ]

        #  ublication date known Reuters formats
        raw_date = tag("DATE")
        date_published: Optional[datetime] = None
        if raw_date:
            for fmt in ("%d-%b-%Y %H:%M:%S.%f", "%d-%b-%Y %H:%M:%S"):
                try:
                    date_published = datetime.strptime(raw_date, fmt)
                    break
                except Exception:
                    pass

        title = tag("TITLE")

        body = tag("BODY")
        if not body:
            text_block = tag("TEXT")
            if text_block:
                m_body = re.search(r"(?is)<BODY[^>]*>(.*?)</BODY>", text_block)
                if m_body:
                    body = html.unescape(m_body.group(1)).strip()
                else:
                    body = _strip_tags(html.unescape(text_block)).strip()

        docs.append({
            "id": doc_id,
            "title": title,
            "content": body or "",
            "dateline": tag("DATELINE"),
            "date_published": date_published,
            "topics": tag_list("TOPICS"),
            "places": tag_list("PLACES"),
            "author_raw": tag("AUTHOR"),
        })

    return docs
