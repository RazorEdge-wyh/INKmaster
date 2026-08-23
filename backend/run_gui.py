"""
INKmaster — Native Desktop Window Launcher
============================================
Renders the React SPA inside a native OS window via pywebview (Edge WebView2).
The FastAPI backend runs on localhost in a background daemon thread.

Double-click the .exe → opens a window like any desktop app.
No browser. No visible port. No terminal.
"""

import sys
import os
import io
import threading
import time
import socket
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# PyInstaller 打包环境：把 stdout / stderr 重定向到 exe 旁的日志文件，
# 方便排查问题（开发环境不做任何处理）。
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).parent
    _log_dir = _exe_dir / "data" / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _log_path = _log_dir / "inkmaster.log"
    try:
        _fh = open(_log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = _fh
        sys.stderr = _fh
    except Exception:
        pass

# uvicorn 日志：GUI 模式下保持安静，不往终端刷屏

os.environ["UVICORN_LOG_LEVEL"] = "warning"
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)


# --- 工具函数 ---
def _find_free_port() -> int:
    """Bind to port 0 and let the OS assign an ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- 后端服务（后台 daemon 线程）---
# 阻塞运行直到服务退出
def _run_server(port: int) -> None:
    """Start uvicorn in this (daemon) thread.  Blocks until the server exits."""
    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        log_config=None,
        access_log=False,
    )


def _wait_for_server(url: str, timeout_s: float = 20.0) -> bool:
    """Poll *url* until it returns HTTP 200, or *timeout_s* expires."""
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=1.5)
            return True
        except Exception:
            time.sleep(0.25)
    return False


# --- 主入口 ---
# 空闲端口起后端 → 轮询 /health 等就绪 → 打开原生窗口
def main() -> None:
    # 1. 选一个空闲端口，避免占用固定端口引发冲突
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    # daemon 线程跑后端：主线程（窗口）退出后自动结束
    server = threading.Thread(
        target=_run_server,
        args=(port,),
        daemon=True,
        name="inkmaster-server",
    )
    server.start()

    # 轮询 /health，等后端就绪
    if not _wait_for_server(f"{url}/health"):
        # 后端没起来 —— 显示错误页后退出
        import webview
        webview.create_window(
            title="INKmaster — 启动失败",
            html=f"<h2 style='color:red;font-family:sans-serif;padding:2rem;'>⚠ 后端启动失败</h2>"
                f"<p style='font-family:sans-serif;padding:0 2rem;'>无法连接到 {url}</p>"
                f"<p style='font-family:sans-serif;padding:0 2rem;'>请检查杀毒软件是否拦截，或尝试重新启动。</p>",
            width=480,
            height=280,
        )
        webview.start()
        sys.exit(1)

    # 后端就绪 —— 打开主窗口
    import webview

    webview.create_window(
        title="INKmaster — AI 小说创作平台",
        url=url,
        width=1400,
        height=900,
        min_size=(960, 600),
        text_select=True,
        confirm_close=False,
    )

    # Windows：优先使用 Edge WebView2（Chromium 内核），
    # 系统缺少 WebView2 运行时时回退到默认后端
    try:
        webview.start(gui="edgechromium", debug=False)
    except (RuntimeError, Exception):
        # WebView2 不可用 —— 用默认 GUI 后端再试一次
        # （例如未安装 Edge / WebView2 的精简系统）
        webview.start(debug=False)

    # 正常退出
    sys.exit(0)


if __name__ == "__main__":
    main()
