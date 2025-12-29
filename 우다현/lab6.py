# Lab6: 개발자 스타일 적용하기
# - 외부 CSS 파일 로드
# - CSS 선택자(Tag, Descendant)
# - 스타일 상속 및 캐스케이딩
# - 색상/배경/폰트 스타일 렌더링

import wbetools
import socket
import ssl
import tkinter
import tkinter.font

from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import FONTS, get_font
from lab4 import Text, Element, print_tree, HTMLParser
from lab5 import BLOCK_ELEMENTS, DrawRect, DrawText, paint_tree
from lab5 import BlockLayout, DocumentLayout, Browser


# =====================================================
# URL 확장: 상대경로 → 절대경로 해석
# =====================================================
@wbetools.patch(URL)
class URL:
    def resolve(self, url):
        """
        상대 URL을 현재 문서 기준으로 절대 URL로 변환
        """
        if "://" in url:
            return URL(url)

        if not url.startswith("/"):
            dir, _ = self.path.rsplit("/", 1)
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url

        if url.startswith("//"):
            return URL(self.scheme + ":" + url)
        else:
            return URL(self.scheme + "://" + self.host +
                       ":" + str(self.port) + url)


# =====================================================
# DOM 트리를 리스트로 펼치기 (CSS 적용용)
# =====================================================
@wbetools.patchable
def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


# =====================================================
# CSS 파서
# =====================================================
class CSSParser:
    """
    CSS 문자열을 파싱해
    (selector, {property: value}) 형태의 rule 리스트 생성
    """
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if self.i <= start:
            raise Exception("Parsing error")
        return self.s[start:self.i]

    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            self.i += 1
        return None

    def body(self):
        """
        { color: red; font-size: 16px; } 파싱
        """
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def selector(self):
        """
        tag / tag tag (후손 선택자) 파싱
        """
        out = TagSelector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendant = TagSelector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                if self.ignore_until(["}"]) == "}":
                    self.literal("}")
                else:
                    break
        return rules


# =====================================================
# CSS 선택자
# =====================================================
class TagSelector:
    """단일 태그 선택자 (예: p, div)"""
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag


class DescendantSelector:
    """후손 선택자 (예: div p)"""
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def matches(self, node):
        if not self.descendant.matches(node):
            return False
        while node.parent:
            if self.ancestor.matches(node.parent):
                return True
            node = node.parent
        return False


# =====================================================
# 스타일 상속 기본값
# =====================================================
INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}


# =====================================================
# 스타일 계산 (CSS 캐스케이드)
# =====================================================
def style(node, rules):
    """
    1. 상속 스타일 적용
    2. CSS 규칙 적용
    3. inline style 적용
    4. 자식 노드 재귀 처리
    """
    node.style = {}

    # 상속
    for prop, default in INHERITED_PROPERTIES.items():
        node.style[prop] = node.parent.style[prop] if node.parent else default

    # CSS 규칙
    for selector, body in rules:
        if selector.matches(node):
            node.style.update(body)

    # inline style
    if isinstance(node, Element) and "style" in node.attributes:
        node.style.update(CSSParser(node.attributes["style"]).body())

    # 퍼센트 font-size 처리
    if node.style["font-size"].endswith("%"):
        parent_size = node.parent.style["font-size"] if node.parent else "16px"
        node_pct = float(node.style["font-size"][:-1]) / 100
        node.style["font-size"] = str(node_pct * float(parent_size[:-2])) + "px"

    for child in node.children:
        style(child, rules)


def cascade_priority(rule):
    return rule[0].priority


# =====================================================
# BlockLayout 확장: 스타일 반영
# =====================================================
@wbetools.patch(BlockLayout)
class BlockLayout:
    def word(self, node, word):
        weight = node.style["font-weight"]
        style = "roman" if node.style["font-style"] == "normal" else "italic"
        size = int(float(node.style["font-size"][:-2]) * 0.75)
        font = get_font(size, weight, style)

        w = font.measure(word)
        if self.cursor_x + w > self.width:
            self.flush()

        color = node.style["color"]
        self.line.append((self.cursor_x, word, font, color))
        self.cursor_x += w + font.measure(" ")

    def paint(self):
        cmds = []

        # 배경색
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            cmds.append(DrawRect(
                self.x, self.y,
                self.x + self.width, self.y + self.height,
                bgcolor))

        # 텍스트
        for x, y, word, font, color in self.display_list:
            cmds.append(DrawText(x, y, word, font, color))

        return cmds


# =====================================================
# DrawText 확장: 색상 지원
# =====================================================
@wbetools.patch(DrawText)
class DrawText:
    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            fill=self.color,
            anchor="nw"
        )


# =====================================================
# 기본 CSS 로드
# =====================================================
DEFAULT_STYLE_SHEET = CSSParser(
    open("browser6.css").read()
).parse()


# =====================================================
# Browser 확장: CSS + 렌더링 통합
# =====================================================
@wbetools.patch(Browser)
class Browser:
    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()

        # 기본 CSS + <link rel="stylesheet"> 처리
        rules = DEFAULT_STYLE_SHEET.copy()
        links = [
            node.attributes["href"]
            for node in tree_to_list(self.nodes, [])
            if isinstance(node, Element)
            and node.tag == "link"
            and node.attributes.get("rel") == "stylesheet"
        ]

        for link in links:
            try:
                rules.extend(CSSParser(url.resolve(link).request()).parse())
            except:
                pass

        style(self.nodes, sorted(rules, key=cascade_priority))

        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        self.draw()


# =====================================================
# 실행부
# =====================================================
if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()