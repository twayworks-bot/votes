import uvicorn
from app.core.config import HOST, PORT, DEFAULT_PREFIX

if __name__ == "__main__":
    print(f"==================================================")
    print(f" VoteEvent 서버 시작")
    print(f" - 서비스 URL: http://localhost:{PORT}{DEFAULT_PREFIX}")
    print(f" - 포트 번호: {PORT}")
    print(f" - Base Path: {DEFAULT_PREFIX}")
    print(f"==================================================")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
