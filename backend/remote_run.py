"""Private Tailnet gateway launcher. Never listen on a public interface."""
from __future__ import annotations

import os
import uvicorn

from viepn.remote_gateway import create_remote_app


if __name__ == "__main__":
    port = int(os.getenv("VIEPN_REMOTE_PORT", "8766"))
    if not (1024 <= port <= 65535):
        raise SystemExit("Remote gateway port must be 1024..65535")
    if port == int(os.getenv("VIEPN_PORT", "8765")):
        raise SystemExit("Remote gateway must use a different port than the backend")
    print(f"ViePN private remote gateway: http://127.0.0.1:{port}")
    print("Only Tailscale Serve should expose this gateway to iPhone.")
    uvicorn.run(create_remote_app(), host="127.0.0.1", port=port,
                log_level="info", proxy_headers=False)
