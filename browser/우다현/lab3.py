# Lab3: 텍스트 포맷팅하기

import wbetools
import socket
import ssl
import tkinter
import tkinter.font
from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP, Browser

# -------------------------------
# HTML 텍스트와 태그 구분용 클래스
# -------------------------------

class Text:
    """단순 텍스트 노드를 나타내는 클래스"""
    def __init__(self, text):
        self.text = text

    @wbetools.js_hide
    def __repr__(self):
        return f"Text('{self.text}')"


class Tag:
    """<b>, <i> 같은 HTML 태그를 나타내는 클래스"""
    def __init__(self, tag):
        self.tag = tag

    @wbetools.js_hide
    def __repr__(self):
        return f"Tag('{self.tag}')"


# -------------------------------
# HTML 파싱 (간단한 렉서 구현)
# -------------------------------

def lex(body):
    """
    HTML 텍스트를 <태그>와 일반 텍스트로 구분.
    예: "<b>Hello</b>" -> [Tag('b'), Text('Hello'), Tag('/b')]
    """
    out = []
    buffer = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
            if buffer:
                out.append(Text(buffer))
            buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))
    return out


# -------------------------------
# 폰트 캐싱 (중복 생성 방지)
# -------------------------------

FONTS = {}

def get_font(size, weight, style):
    """폰트 속성 조합(size, weight, style)에 따라 캐싱"""
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]


# -------------------------------
# 텍스트 레이아웃 엔진
# -------------------------------

class Layout:
    """
    토큰 리스트(Text/Tag)를 받아 위치 계산 및 스타일 적용.
    각 줄별로 (x, y, word, font)를 display_list에 저장.
    """
    def __init__(self, tokens):
        self.tokens = tokens
        self.display_list = []

        # 현재 커서 및 기본 스타일
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"  # bold or normal
        self.style = "roman"    # italic or roman
        self.size = 12          # 기본 폰트 크기

        self.line = []  # 현재 줄 단어들 저장
        for tok in tokens:
            self.token(tok)
        self.flush()  # 마지막 줄 반영

    def token(self, tok):
        """토큰 유형에 따라 처리 (텍스트 or 태그)"""
        if isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP  # 문단 간격

    def word(self, word):
        """단어별 폭 계산 및 줄바꿈 처리"""
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > WIDTH - HSTEP:
            self.flush()
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    def flush(self):
        """현재 줄을 display_list에 반영하고 줄바꿈"""
        if not self.line:
            return
        wbetools.record("initial_y", self.cursor_y, self.line)

        metrics = [font.metrics() for x, word, font in self.line]
        wbetools.record("metrics", metrics)

        # 줄의 최대 높이 계산
        max_ascent = max(metric["ascent"] for metric in metrics)
        baseline = self.cursor_y + 1.25 * max_ascent
        wbetools.record("max_ascent", max_ascent)

        # display_list에 실제 그릴 좌표 추가
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
            wbetools.record("aligned", self.display_list)

        # 다음 줄로 이동
        max_descent = max(metric["descent"] for metric in metrics)
        wbetools.record("max_descent", max_descent)
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = HSTEP
        self.line = []
        wbetools.record("final_y", self.cursor_y)


# -------------------------------
# Browser 클래스 확장 (텍스트 스타일 적용)
# -------------------------------

@wbetools.patch(Browser)
class Browser:
    """기존 Browser를 확장하여 폰트/스타일 지원"""
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()

        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.display_list = []

    def load(self, url):
        """URL에서 HTML을 받아 렉싱 후 레이아웃 구성"""
        body = url.request()
        tokens = lex(body)
        self.display_list = Layout(tokens).display_list
        self.draw()

    def draw(self):
        """display_list를 기반으로 화면에 텍스트 출력"""
        self.canvas.delete("all")
        for x, y, word, font in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + font.metrics("linespace") < self.scroll: continue
            self.canvas.create_text(
                x, y - self.scroll,
                text=word,
                font=font,
                anchor="nw"
            )


# -------------------------------
# 실행부 (기본 URL 예제 포함)
# -------------------------------

if __name__ == "__main__":
    import sys

    # 명령줄 인자 확인
    if len(sys.argv) > 1:
        url = sys.argv[1]  # 사용자가 입력한 URL
    else:
        url = "https://browser.engineering"  # 기본 URL

    # 브라우저 인스턴스 생성 및 페이지 로드
    Browser().load(URL(url))

    # Tkinter 메인 루프 실행 (윈도우 유지)
    tkinter.mainloop()