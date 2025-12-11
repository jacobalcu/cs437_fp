from __future__ import annotations

import uvicorn

from .api import build_app


def main() -> None:
    app = build_app()
    uvicorn.run(app, host="0.0.0.0", port=9001, reload=False)


if __name__ == "__main__":
    main()
