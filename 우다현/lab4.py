# Lab4: 문서 트리 구축하기

import wbetools
import socket
import ssl
import tkinter
import tkinter.font
from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import FONTS, get_font, Layout, Browser


# -------------------------------
# 텍스트 노드 클래스 (Text)
# -------------------------------
class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)


# -------------------------------
# HTML 태그 노드 클래스 (Element)
# -------------------------------
class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        attrs = [" " + k + "=\"" + v + "\"" for k, v in self.attributes.items()]
        attr_str = "".join(attrs)
        return "<" + self.tag + attr_str + ">"


# -------------------------------
# 트리 구조 출력(디버그용)
# -------------------------------
@wbetools.patchable
def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)


# -------------------------------
# HTML 파서: 문자열 → 트리 변환
# -------------------------------
class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []


    # ---------------------------
    # 파싱 시작
    # ---------------------------
    def parse(self):
        text = ""
        in_tag = False

        for c in self.body:
            if c == "<":                     # 태그 시작
                in_tag = True
                if text: self.add_text(text)
                text = ""
            elif c == ">":                   # 태그 끝
                in_tag = False
                self.add_tag(text)
                text = ""
            else:
                text += c

        if not in_tag and text:
            self.add_text(text)

        return self.finish()


    # ---------------------------
    # 태그명 + 속성 파싱
    # ---------------------------
    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}

        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""
        return tag, attributes


    # ---------------------------
    # 텍스트 노드 추가
    # ---------------------------
    def add_text(self, text):
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)


    # ---------------------------
    # Self-closing 태그 목록
    # ---------------------------
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]


    # ---------------------------
    # 태그 처리
    # ---------------------------
    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"):
            return

        self.implicit_tags(tag)

        # 닫는 태그
        if tag.startswith("/"):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)

        # self-closing 태그
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)

        # 여는 태그
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)


    # ---------------------------
    # HTML implicit tag 처리
    # ---------------------------
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]

            if open_tags == [] and tag != "html":
                self.add_tag("html")

            elif open_tags == ["html"] and \
                tag not in ["head", "body", "/html"]:

                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")

            elif open_tags == ["html", "head"] and \
                tag not in ["/head"] + self.HEAD_TAGS:

                self.add_tag("/head")

            else:
                break


    # ---------------------------
    # 파싱 종료: 남은 태그 정리
    # ---------------------------
    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)

        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)

        return self.unfinished.pop()


# -------------------------------
# Layout 패치: 트리 → display_list
# -------------------------------
@wbetools.patch(Layout)
class Layout:
    def __init__(self, tree):
        self.display_list = []

        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12

        self.line = []

        self.recurse(tree)
        self.flush()

    @wbetools.delete
    def token(self, tok): pass


    # ---------------------------
    # 트리 재귀 순회
    # ---------------------------
    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)


    # ---------------------------
    # 태그 open 처리
    # ---------------------------
    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "br":
            self.flush()


    # ---------------------------
    # 태그 close 처리
    # ---------------------------
    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP


# -------------------------------
# Browser 패치: 파싱 → 렌더링
# -------------------------------
@wbetools.patch(Browser)
class Browser:
    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()
        self.display_list = Layout(self.nodes).display_list
        self.draw()


# -------------------------------
# 프로그램 실행
# -------------------------------
if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()