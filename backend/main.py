"""Production entry point: `python main.py`.

Used by hosts that start a Python app from the folder (Embarko builds with Railpack). Reads the port from PORT and
binds 0.0.0.0. Locally it behaves like `uvicorn app.main:app --port 8000`.
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
                proxy_headers=True, forwarded_allow_ips="*")  # https scheme from the platform's proxy
