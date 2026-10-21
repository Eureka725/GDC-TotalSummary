"""Small, non-executing HTML reader; the collector needs no third-party packages."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list = field(default_factory=list)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(
            child.text() if isinstance(child, Node) else child for child in self.children
        )).strip()

    def find_all(self, tag: str | None = None, css_class: str | None = None):
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (
                    css_class is None or css_class in child.attrs.get("class", "").split()
                ):
                    yield child
                yield from child.find_all(tag, css_class)

    def first(self, tag: str | None = None, css_class: str | None = None):
        return next(self.find_all(tag, css_class), None)


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack[-1].tag not in {"script", "style"}:
            self.stack[-1].children.append(data)


def definition_list(node: Node | None) -> dict[str, str]:
    if node is None:
        return {}
    pairs = {}
    key = None
    for child in node.children:
        if not isinstance(child, Node):
            continue
        if child.tag == "dt":
            key = child.text().rstrip(":").strip()
        elif child.tag == "dd" and key:
            pairs[key] = child.text()
            key = None
    return pairs
