# Lab5: 페이지 레이아웃

import wbetools
import socket
import ssl
import tkinter
import tkinter.font
from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import FONTS, get_font
from lab4 import Text, Element, print_tree, HTMLParser, Layout, Browser


# -------------------------------
# 블록 요소(HTML Block Elements) 목록
# 블록 레이아웃 모드를 결정하는 데 사용됨
# -------------------------------
BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]


# -------------------------------
# BlockLayout: Block-level / Inline-level 레이아웃 처리
# Layout 클래스를 패치하여 블록 기반 배치를 수행
# -------------------------------
@wbetools.patch(Layout)
class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

        # 레이아웃 영역
        self.x = None
        self.y = None
        self.width = None
        self.height = None

        # inline 모드에서 생성되는 display 리스트
        self.display_list = []

    # ---------------------------
    # 핵심 레이아웃 계산 함수
    # ---------------------------
    def layout(self):
        wbetools.record("layout_pre", self)

        # 블록의 x/width는 부모와 동일
        self.x = self.parent.x
        self.width = self.parent.width

        # previous 블록 아래에 배치
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        # inline 또는 block 모드 결정
        mode = self.layout_mode()

        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next

        else:  # inline mode
            self.cursor_x = 0
            self.cursor_y = 0
            self.weight = "normal"
            self.style = "roman"
            self.size = 12
            self.line = []

            self.recurse(self.node)
            self.flush()

        # 자식 블록 레이아웃 수행
        for child in self.children:
            child.layout()

        # 블록 높이 계산
        if mode == "block":
            self.height = sum([child.height for child in self.children])
        else:
            self.height = self.cursor_y

        wbetools.record("layout_post", self)

    # ---------------------------
    # 블록 또는 inline 모드 판별
    # ---------------------------
    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and child.tag in BLOCK_ELEMENTS
                  for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"

    # ---------------------------
    # inline 단어 배치
    # ---------------------------
    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)

        if self.cursor_x + w > self.width:
            self.flush()

        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    # ---------------------------
    # inline 라인 플러시 → display_list로 변환
    # ---------------------------
    def flush(self):
        if not self.line:
            return

        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        for rel_x, word, font in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        self.cursor_x = 0
        self.line = []

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

    # ---------------------------
    # 페인팅 명령 생성
    # ---------------------------
    def paint(self):
        cmds = []

        # <pre> 태그는 배경 박스 그리기
        if isinstance(self.node, Element) and self.node.tag == "pre":
            x2 = self.x + self.width
            y2 = self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, "gray")
            cmds.append(rect)

        # inline 콘텐츠 그리기
        if self.layout_mode() == "inline":
            for x, y, word, font in self.display_list:
                cmds.append(DrawText(x, y, word, font))

        return cmds

    @wbetools.js_hide
    def __repr__(self):
        return "BlockLayout[{}](x={}, y={}, width={}, height={}, node={})".format(
            self.layout_mode(), self.x, self.y, self.width, self.height, self.node
        )


# -------------------------------
# DocumentLayout: 페이지 전체 블록 루트
# -------------------------------
class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.previous = None
        self.children = []

    def layout(self):
        wbetools.record("layout_pre", self)

        # 문서 루트는 BlockLayout 하나만 가짐
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP

        child.layout()
        self.height = child.height

        wbetools.record("layout_post", self)

    def paint(self):
        return []

    @wbetools.js_hide
    def __repr__(self):
        return "DocumentLayout()"


# -------------------------------
# DrawText: 텍스트 그리기 명령
# -------------------------------
class DrawText:
    def __init__(self, x1, y1, text, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw'
        )

    @wbetools.js_hide
    def __repr__(self):
        return "DrawText(top={} left={} bottom={} text={} font={})".format(
            self.top, self.left, self.bottom, self.text, self.font
        )


# -------------------------------
# DrawRect: 사각형(배경) 그리기 명령
# -------------------------------
class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color
        )

    @wbetools.js_hide
    def __repr__(self):
        return "DrawRect(top={} left={} bottom={} right={} color={})".format(
            self.top, self.left, self.bottom, self.right, self.color
        )


# -------------------------------
# paint_tree: 레이아웃 트리를 순회하며 페인트 명령 수집
# -------------------------------
def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)


# -------------------------------
# Browser 패치: 페이지 파싱 → 레이아웃 → 렌더링
# -------------------------------
@wbetools.patch(Browser)
class Browser:
    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()

        # DocumentLayout를 통해 전체 레이아웃 구성
        self.document = DocumentLayout(self.nodes)
        self.document.layout()

        # display_list 생성
        self.display_list = []
        paint_tree(self.document, self.display_list)

        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT:
                continue
            if cmd.bottom < self.scroll:
                continue
            cmd.execute(self.scroll, self.canvas)

    def scrolldown(self, e):
        max_y = max(self.document.height + 2 * VSTEP - HEIGHT, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()


# -------------------------------
# 프로그램 시작
# -------------------------------
if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()