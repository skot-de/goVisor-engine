"""XML → flache (Pfad, Wert)-Paare — die Grundlage der Verlust-Garantie.

Jeder Blattwert einer Notice wird über seinen Pfad aus lokalen Element-Namen
adressiert (z.B. ``TED_EXPORT.FORM_SECTION.F03_2014.OBJECT_CONTRACT.SHORT_DESCR``).
Der Pfad *ist* die Zuordnung: nichts wird weggeworfen, alles ist über seinen
semantischen Ort auffindbar. Attribute erscheinen als ``pfad@name``.

Das speist die ``attributes``-Tabelle in Silber — die vollständige, per SQL
abfragbare Repräsentation jeder Notice, redundant zu den typisierten Tabellen,
aber der Beweis, dass kein Feld verloren geht.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Iterator

_RE_TEXT_FIELD = re.compile(r"^([A-Z]{2}):\s?(.*)$")

ATTR_PREFIX = "@"
TEXT_KEY = "#text"


def decode_text(raw: bytes) -> str:
    """Vor-XML-Textformat verlustfrei dekodieren.

    Die meisten Alt-Pakete liefern jede Notice doppelt — eine UTF-8- und eine
    ISO-Edition; die UTF-8-Edition gewinnt beim Dedup. 2004 fehlt für ~11.400
    DE-Notices der UTF-8-Zwilling: nur die ISO-8859-1-/CP1252-Edition existiert.
    Als UTF-8 gelesen zerfallen dort alle Umlaute zu U+FFFD (``�``) — irreparabel.
    Darum erst UTF-8 (Normalfall), dann CP1252 als Fallback: Obermenge von
    Latin-1, bildet jedes Byte auf sein Original-Zeichen ab, ``replace`` nur für
    die 5 in CP1252 undefinierten Bytes.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def leaves(raw: bytes) -> Iterator[tuple[str, str]]:
    """Yield ``(path, value)`` für jedes Blatt und jedes Attribut.

    Vollständig: die Summe der Paare über alle Notices deckt jeden Wert im
    Original-XML ab. Genau das prüft die Vollständigkeits-Verifikation.

    Textformat (vor-XML): kein XML-Baum — die 2-Buchstaben-Feldcodes werden als
    ``TEXT.<code>`` → Wert geflattet, damit die Verlustgarantie auch dort gilt.
    """
    if raw.lstrip()[:1] != b"<":
        fields: dict[str, list[str]] = {}
        cur: str | None = None
        for line in decode_text(raw).splitlines():
            m = _RE_TEXT_FIELD.match(line)
            if m:
                cur = m.group(1)
                fields.setdefault(cur, []).append(m.group(2))
            elif cur is not None:
                fields[cur].append(line.strip())
        for code, vals in fields.items():
            value = "\n".join(vals).strip()
            if value:
                yield f"TEXT.{code}", value
        return

    root = ET.fromstring(raw)

    def walk(elem: ET.Element, path: str) -> Iterator[tuple[str, str]]:
        for key, value in elem.attrib.items():
            value = (value or "").strip()
            if value:
                yield f"{path}@{_local(key)}", value
        children = list(elem)
        if not children:
            text = (elem.text or "").strip()
            if text:
                yield path, text
        else:
            for child in children:
                yield from walk(child, f"{path}.{_local(child.tag)}")

    yield from walk(root, _local(root.tag))


def element_to_obj(elem: ET.Element) -> Any:
    children = list(elem)
    text = "".join(elem.itertext() if not children else [elem.text or ""]).strip()

    if not children and not elem.attrib:
        return text or None

    node: dict[str, Any] = {}
    for key, value in elem.attrib.items():
        node[ATTR_PREFIX + _local(key)] = value

    if children:
        # <P> and friends carry inline markup; their nested text belongs to the
        # paragraph, not to a child node, so flatten them to a plain string.
        for child in children:
            name = _local(child.tag)
            value = element_to_obj(child)
            if value is None:
                continue
            if name in node:
                if not isinstance(node[name], list):
                    node[name] = [node[name]]
                node[name].append(value)
            else:
                node[name] = value
        tail_text = "".join(t for t in (elem.text or "",)).strip()
        if tail_text:
            node[TEXT_KEY] = tail_text
    elif text:
        node[TEXT_KEY] = text

    return node or None


def notice_to_obj(raw: bytes) -> dict[str, Any]:
    """Parse a notice's XML into a nested dict keyed by its root tag."""
    root = ET.fromstring(raw)
    return {_local(root.tag): element_to_obj(root)}


def iter_paths(obj: Any, prefix: str = "") -> Any:
    """Yield ``(path, value)`` for every scalar in a flattened notice.

    Used to inventory which fields actually occur, not for bulk querying.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from iter_paths(value, f"{prefix}/{key}")
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_paths(item, prefix)
    elif obj is not None:
        yield prefix, obj
