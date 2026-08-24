"""API server entry point: `python -m apps.api` to start."""
import os

import uvicorn


def main():
    host = os.environ.get("LML_HOST", "127.0.0.1")
    port = int(os.environ.get("LML_PORT", "8322"))
    print(f"Local Market Lab API starting on {host}:{port}")
    print(f"Health:  http://{host}:{port}/api/v1/health")
    print(f"Web UI:  http://{host}:{port}/")
    uvicorn.run("apps.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
