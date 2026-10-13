"""Business-free diagnostic for the Windows TestClient portal issue; not a pytest test."""

import faulthandler

from fastapi import FastAPI
from fastapi.testclient import TestClient


app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    faulthandler.dump_traceback_later(5, repeat=False)
    with TestClient(app) as client:
        print(client.get("/health").json())
    faulthandler.cancel_dump_traceback_later()
