# Lab2: 화면에 그리기

import wbetools
import socket
import ssl
import tkinter
from lab1 import URL

# -----------------------------------------------------
# HTML 본문에서 태그(<...>)를 제거하고, 순수 텍스트만 추출
# -----------------------------------------------------
def lex(body):
    text = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True         # 태그 시작 → 텍스트 건너뛰기
        elif c == ">":
            in_tag = False        # 태그 끝 → 다시 텍스트 추출 시작
        elif not in_tag:
            text += c             # 태그 외부의 문자만 추가
        wbetools.record("lex", text)  # (학습용) 처리 상태를 기록
    return text

# -----------------------------------------------------
# 화면 크기 및 텍스트 간격 관련 상수 정의
# -----------------------------------------------------
WIDTH, HEIGHT = 800, 600   # 윈도우 캔버스 크기 (픽셀 단위)
HSTEP, VSTEP = 13, 18      # 글자 간 가로/세로 간격 (폰트 크기 대체)
SCROLL_STEP = 100           # 스크롤 시 이동 거리 (픽셀 단위)

# -----------------------------------------------------
# layout(): 텍스트를 화면상의 (x, y) 위치 리스트로 변환
#           - 각 문자가 화면 어디에 표시될지를 계산
# -----------------------------------------------------
def layout(text):
    display_list = []                # (x, y, 문자) 튜플들의 리스트
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        display_list.append((cursor_x, cursor_y, c))  # 현재 좌표에 문자 배치
        cursor_x += HSTEP                             # 가로로 한 칸 이동
        # 화면 오른쪽 끝에 도달하면 다음 줄로 이동
        if cursor_x >= WIDTH - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP
        wbetools.record("layout", display_list)        # 중간 상태 기록
    return display_list

# -----------------------------------------------------
# Browser 클래스: Tkinter를 이용해 단순 웹페이지 텍스트 렌더링
# -----------------------------------------------------
class Browser:
    def __init__(self):
        # Tkinter 윈도우 생성
        self.window = tkinter.Tk()
        # 그릴 영역(Canvas) 생성
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()  # 캔버스를 윈도우에 추가

        self.scroll = 0     # 현재 스크롤 위치
        # ↓ 키를 눌렀을 때 스크롤 이벤트 연결
        self.window.bind("<Down>", self.scrolldown)

    # -------------------------------------------------
    # load(): URL에서 HTML을 가져와 렉싱 → 레이아웃 → 그리기 수행
    # -------------------------------------------------
    def load(self, url):
        body = url.request()           # URL 객체로 HTTP 요청
        text = lex(body)               # HTML 태그 제거 후 텍스트 추출
        self.display_list = layout(text)  # 좌표 리스트 생성
        self.draw()                    # 화면에 출력

    # -------------------------------------------------
    # draw(): display_list의 문자를 Tkinter 캔버스에 그림
    # -------------------------------------------------
    def draw(self):
        self.canvas.delete("all")  # 기존 화면 지우기
        for x, y, c in self.display_list:
            wbetools.record("draw")  # (학습용) 렌더링 단계 기록
            # 현재 스크롤 범위 밖의 문자는 스킵
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            # 화면에 문자 출력 (y좌표는 스크롤량만큼 보정)
            self.canvas.create_text(x, y - self.scroll, text=c)

    # -------------------------------------------------
    # scrolldown(): ↓ 키를 눌렀을 때 화면을 아래로 스크롤
    # -------------------------------------------------
    def scrolldown(self, e):
        self.scroll += SCROLL_STEP  # 스크롤 위치 증가
        self.draw()                 # 다시 그리기

# -----------------------------------------------------
# 프로그램 진입점 (main)
# -----------------------------------------------------
if __name__ == "__main__":
    import sys

    # 명령줄 인자로 URL이 전달되면 그걸 사용하고,
    # 없으면 기본 URL("https://browser.engineering")로 설정
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://browser.engineering"  # 기본 예제용 URL

    # 브라우저 객체 생성 후 페이지 로드
    Browser().load(URL(url))

    # Tkinter 이벤트 루프 실행 (창을 닫을 때까지 유지)
    tkinter.mainloop()