"""Khởi động web app Causal Targeting Lab.

App chỉ đọc artifact trong ``output/``. Nếu thiếu artifact nào, endpoint tương ứng
trả trạng thái ``unavailable`` thay vì giá trị bịa; ``/api/health`` liệt kê đầy đủ.

    .venv\\Scripts\\python.exe scripts\\serve_webapp.py --port 8000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Tự nạp lại khi sửa code; chỉ dùng khi phát triển.",
    )
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    import uvicorn

    from webapp.service import get_repository

    repository = get_repository()
    missing = [
        status.name for status in repository.artifact_status() if not status.available
    ]
    if missing:
        print(f"[warn] artifacts not built yet: {', '.join(missing)}", flush=True)
    print(f"[serve] http://{args.host}:{args.port}", flush=True)
    uvicorn.run(
        "webapp.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
