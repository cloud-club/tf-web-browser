# Lab1: 웹페이지 다운로드

import socket
import ssl
import wbetools

# ---------------------------------------------------------
# URL 클래스: URL 문자열을 파싱하고, 해당 서버에 HTTP 요청을 보내는 기능을 담당
# ---------------------------------------------------------
class URL:
    def __init__(self, url):
        try:
            # URL을 scheme(프로토콜)과 나머지 부분으로 분리
            # 예: "https://example.com/path" → scheme="https", url="example.com/path"
            self.scheme, url = url.split("://", 1)
            assert self.scheme in ["http", "https"]  # 지원하는 프로토콜만 허용

            # 경로가 없는 경우 자동으로 '/' 추가
            if "/" not in url:
                url = url + "/"

            # 호스트명과 경로 분리
            self.host, url = url.split("/", 1)
            self.path = "/" + url  # 다시 '/' 붙여서 경로 구성

            # 기본 포트 설정 (HTTP=80, HTTPS=443)
            if self.scheme == "http":
                self.port = 80
            elif self.scheme == "https":
                self.port = 443

            # 만약 호스트에 포트번호가 명시되어 있다면 분리해서 숫자로 저장
            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)

        # URL 형식이 잘못된 경우 예외 처리
        except:
            print("Malformed URL found, falling back to the WBE home page.")
            print("  URL was: " + url)
            # 오류가 나면 기본 페이지로 다시 초기화
            self.__init__("https://browser.engineering")

    # -----------------------------------------------------
    # request(): URL에 접속해 HTTP 요청을 보내고, 응답 본문을 문자열로 반환
    # -----------------------------------------------------
    def request(self):
        # TCP 소켓 생성
        s = socket.socket(
            family=socket.AF_INET,          # IPv4
            type=socket.SOCK_STREAM,        # TCP 스트림
            proto=socket.IPPROTO_TCP,
        )
        # 지정된 호스트와 포트에 연결
        s.connect((self.host, self.port))
    
        # HTTPS의 경우 SSL/TLS 암호화 래핑
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)

        # HTTP 요청 헤더 작성 (단순 GET 요청)
        request = "GET {} HTTP/1.0\r\n".format(self.path)
        request += "Host: {}\r\n".format(self.host)
        request += "\r\n"  # 빈 줄로 헤더 종료 표시

        # 서버로 요청 전송
        s.send(request.encode("utf8"))

        # 응답을 텍스트 모드로 읽기 위한 파일 객체로 변환
        response = s.makefile("r", encoding="utf8", newline="\r\n")
    
        # 첫 줄(상태 줄) 읽기: 예) "HTTP/1.0 200 OK"
        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)
    
        # 헤더 읽기
        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n":  # 빈 줄이 나오면 헤더 끝
                break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()
    
        # 단순화를 위해 압축 전송 등의 복잡한 응답은 처리하지 않음
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers
    
        # 나머지 본문(HTML 텍스트 등)을 모두 읽음
        content = response.read()
        s.close()  # 소켓 닫기
    
        return content  # 서버 응답 본문 반환

    # __repr__ 메서드는 객체를 문자열로 표현할 때 사용됨
    # @wbetools.js_hide 데코레이터는 자바스크립트 인터페이스에서 숨기기 위한 장식자
    @wbetools.js_hide
    def __repr__(self):
        return "URL(scheme={}, host={}, port={}, path={!r})".format(
            self.scheme, self.host, self.port, self.path)

# ---------------------------------------------------------
# show(): HTML 태그를 제거하고, 실제 텍스트 내용만 출력하는 단순 렌더러
# ---------------------------------------------------------
def show(body):
    in_tag = False
    for c in body:
        if c == "<":          # 태그 시작
            in_tag = True
        elif c == ">":        # 태그 끝
            in_tag = False
        elif not in_tag:      # 태그 외부의 문자만 출력
            print(c, end="")

# ---------------------------------------------------------
# load(): URL 객체에서 요청을 보내고(show) HTML 본문을 표시
# ---------------------------------------------------------
def load(url):
    body = url.request()
    show(body)

# ---------------------------------------------------------
# 메인 실행부: 명령줄 인자에서 URL을 받아 페이지 로드
# ---------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]  # 인자로 받은 URL 사용
    else:
        url = "https://browser.engineering"  # 인자가 없으면 기본 URL 사용
    load(URL(url))