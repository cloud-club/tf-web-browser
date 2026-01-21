# Lab6: 개발자 스타일 적용하기

import wbetools
import tkinter
import tkinter.font

from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import get_font
from lab4 import Text, Element, HTMLParser
from lab5 import (
    DrawRect, DrawText,
    paint_tree, BlockLayout, DocumentLayout, Browser
)

# =====================================================
# URL 확장: 상대경로 → 절대경로 해석
# =====================================================
@wbetools.patch(URL)
class URL:
    def resolve(self, url):
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
def tree_to_list(node, list):
    list.append(node)
    for child in node.children:
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

    def literal(self, c):
        if self.i >= len(self.s) or self.s[self.i] != c:
            raise Exception("CSS error")
        self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s) and (
            self.s[self.i].isalnum() or self.s[self.i] in "#-.%"
        ):
            self.i += 1
        if start == self.i:
            raise Exception("CSS error")
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
            except:
                break
        return pairs

    def selector(self):
        """
        tag / tag tag (후손 선택자) 파싱
        """
        out = TagSelector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            out = DescendantSelector(out, TagSelector(self.word().casefold()))
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
            except:
                break
        return rules

# =====================================================
# CSS 선택자
# =====================================================
class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and node.tag == self.tag

class DescendantSelector:
    def __init__(self, a, d):
        self.ancestor = a
        self.descendant = d
        self.priority = a.priority + d.priority

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
    for prop, default in INHERITED_PROPERTIES.items():
        node.style[prop] = node.parent.style[prop] if node.parent else default

    for selector, body in rules:
        if selector.matches(node):
            node.style.update(body)

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
# BlockLayout 확장 : 스타일 반영
# =====================================================
@wbetools.patch(BlockLayout)
class BlockLayout:
    def word(self, node, word):
        weight = node.style["font-weight"]
        style_ = "roman" if node.style["font-style"] == "normal" else "italic"
        size = int(float(node.style["font-size"][:-2]) * 0.75)
        font = get_font(size, weight, style_)

        w = font.measure(word)
        if self.cursor_x + w > self.width:
            self.flush()

        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    def paint(self):
        cmds = []
        color = self.node.style.get("color", "black")

        for x, y, word, font in self.display_list:
            cmds.append(DrawText(x, y, word, font, color))

        return cmds

# =====================================================
# DrawText 확장 : 색상 지원
# =====================================================
@wbetools.patch(DrawText)
class DrawText:
    def __init__(self, x, y, text, font, color):
        self.left = x
        self.top = y
        self.text = text
        self.font = font
        self.color = color
        self.bottom = y + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left,
            self.top - scroll,
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
# Browser 확장 : CSS + 렌더링 통합
# =====================================================
@wbetools.patch(Browser)
class Browser:
    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()

         # 기본 CSS + <link rel="stylesheet"> 처리
        rules = DEFAULT_STYLE_SHEET.copy()
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
