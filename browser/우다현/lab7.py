# Lab7: 버튼과 링크 처리하기

import wbetools
import socket
import ssl
import tkinter
import tkinter.font

from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import FONTS, get_font
from lab4 import Text, Element, HTMLParser
from lab5 import BLOCK_ELEMENTS, DocumentLayout, paint_tree
from lab6 import (
    CSSParser, TagSelector, DescendantSelector,
    DEFAULT_STYLE_SHEET, INHERITED_PROPERTIES,
    style, cascade_priority,
    DrawText, URL, tree_to_list, BlockLayout
)

# =============================
# URL 문자열 출력 보정
# =============================
@wbetools.patch(URL)
class URL:
    def __str__(self):
        port = ""
        if not ((self.scheme == "https" and self.port == 443) or
                (self.scheme == "http" and self.port == 80)):
            port = ":" + str(self.port)
        return self.scheme + "://" + self.host + port + self.path


# =============================
# LineLayout
# =============================
class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = self.y = self.width = self.height = None

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x
        self.y = self.previous.y + self.previous.height if self.previous else self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        max_ascent = max(w.font.metrics("ascent") for w in self.children)
        baseline = self.y + 1.25 * max_ascent

        for word in self.children:
            word.y = baseline - word.font.metrics("ascent")

        max_descent = max(w.font.metrics("descent") for w in self.children)
        self.height = 1.25 * (max_ascent + max_descent)

    # 추가
    def paint(self):
        cmds = []
        for child in self.children:
            cmds.extend(child.paint())
        return cmds


# =============================
# 단어(Text) 레이아웃
# =============================
class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word # 어떤 단어인지 알기 위해 추가 인수 필요
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = self.y = self.width = self.height = None
        self.font = None

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal": style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * 0.75)

        self.font = get_font(size, weight, style)
        self.width = self.font.measure(self.word)
        self.height = self.font.metrics("linespace")

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

    def paint(self):
        return [DrawText(
            self.x, self.y,
            self.word, self.font,
            self.node.style["color"]
        )]


# =============================
# BlockLayout 확장
# =============================
@wbetools.patch(BlockLayout)
class BlockLayout:
    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x
        self.y = self.previous.y + self.previous.height if self.previous else self.parent.y

        if self.layout_mode() == "block":
            prev = None
            for child in self.node.children:
                layout = BlockLayout(child, self, prev)
                self.children.append(layout)
                prev = layout
        else:
            self.new_line()
            self.recurse(self.node)

        for child in self.children:
            child.layout()

        self.height = sum(child.height for child in self.children)

    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br":
                self.new_line()
            for child in node.children:
                self.recurse(child)

    def new_line(self):
        self.cursor_x = 0
        prev = self.children[-1] if self.children else None
        self.children.append(LineLayout(self.node, self, prev))

    def word(self, node, word):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal": style = "roman"
        size = int(float(node.style["font-size"][:-2]) * 0.75)
        font = get_font(size, weight, style)

        w = font.measure(word)
        if self.cursor_x + w > self.width:
            self.new_line()

        line = self.children[-1] # 현재 줄은 children 배열의 끝에서 찾을 수 있음
        prev = line.children[-1] if line.children else None
        line.children.append(TextLayout(node, word, line, prev))
        self.cursor_x += w + font.measure(" ")


# =============================
# 탭(Tab)
# =============================
class Tab:
    def __init__(self, height):
        self.history = []
        self.url = None
        self.scroll = 0
        self.height = height

    def load(self, url):
        self.url = url
        self.history.append(url)
        body = url.request()

        self.nodes = HTMLParser(body).parse()
        rules = DEFAULT_STYLE_SHEET.copy()

        for node in tree_to_list(self.nodes, []):
            if isinstance(node, Element) and node.tag == "link":
                if node.attributes.get("rel") == "stylesheet":
                    try:
                        rules.extend(
                            CSSParser(url.resolve(node.attributes["href"]).request()).parse()
                        )
                    except:
                        pass

        style(self.nodes, sorted(rules, key=cascade_priority))

        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)

    def draw(self, canvas, offset):
        for cmd in self.display_list:
            if cmd.bottom < self.scroll:
                continue
            if cmd.top > self.scroll + self.height:
                continue
            cmd.execute(self.scroll - offset, canvas)

    def scrolldown(self):
        self.scroll += SCROLL_STEP

    def click(self, x, y):
        y += self.scroll
        for obj in reversed(tree_to_list(self.document, [])):
            if not hasattr(obj, "node"):
                continue
            if obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height:
                node = obj.node
                # 조상 중 <a> 찾기
                while node:
                    if isinstance(node, Element) and node.tag == "a":
                        href = node.attributes.get("href")
                        if href:
                            self.load(self.url.resolve(href))
                        return
                    node = node.parent
                return



# =============================
# 브라우저 크롬(UI)
# =============================
class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = get_font(20, "normal", "roman")
        self.height = self.font.metrics("linespace") + 20

    def paint(self):
        return []


# =============================
# 브라우저 메인
# =============================
class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack()

        self.tabs = []
        self.active_tab = None

        self.window.bind("<Down>", self.scroll)
        self.window.bind("<Button-1>", self.click)

    def new_tab(self, url):
        tab = Tab(HEIGHT)
        tab.load(url)
        self.tabs.append(tab)
        self.active_tab = tab
        self.draw()

    def scroll(self, e):
        self.active_tab.scrolldown()
        self.draw()

    def click(self, e):
        self.active_tab.click(e.x, e.y)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        self.active_tab.draw(self.canvas, 0)


# =============================
# 실행 진입점
# =============================
if __name__ == "__main__":
    import sys
    url = sys.argv[1]
    Browser().new_tab(URL(url))
    tkinter.mainloop()
