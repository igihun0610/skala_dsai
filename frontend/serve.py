#!/usr/bin/env python3
"""
간단한 HTTP 서버로 프론트엔드 파일을 서빙합니다.
"""

import os
import sys
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, HTTPServer
import webbrowser
import threading
import time

class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    """CORS를 지원하는 HTTP 요청 핸들러"""

    def end_headers(self):
        # CORS 헤더 추가
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        # OPTIONS 요청 처리 (CORS preflight)
        self.send_response(200)
        self.end_headers()

def start_server(port=3000):
    """HTTP 서버 시작"""
    # 현재 디렉토리를 프론트엔드 디렉토리로 변경
    frontend_dir = Path(__file__).parent
    os.chdir(frontend_dir)

    # 서버 설정
    server_address = ('', port)
    httpd = HTTPServer(server_address, CORSHTTPRequestHandler)

    print(f"\n🌐 프론트엔드 서버가 시작되었습니다!")
    print(f"   URL: http://localhost:{port}")
    print(f"   디렉토리: {frontend_dir}")
    print(f"\n⭐ 백엔드 서버도 실행되어야 합니다:")
    print(f"   백엔드 URL: http://localhost:8000")
    print(f"\n종료하려면 Ctrl+C를 누르세요.\n")

    # 3초 후 브라우저 자동 열기
    def open_browser():
        time.sleep(3)
        webbrowser.open(f'http://localhost:{port}')

    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 프론트엔드 서버를 종료합니다.")
        httpd.shutdown()

if __name__ == '__main__':
    # 포트 번호 처리
    port = 3000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("잘못된 포트 번호입니다. 기본값 3000을 사용합니다.")

    start_server(port)