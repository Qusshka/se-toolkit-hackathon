import os
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


async def post(path: str, data: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BACKEND_URL}{path}", json=data, timeout=10)
        r.raise_for_status()
        return r.json()


async def get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BACKEND_URL}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()


async def put(path: str, data: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.put(f"{BACKEND_URL}{path}", json=data, timeout=10)
        r.raise_for_status()
        return r.json()


async def patch(path: str, data: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{BACKEND_URL}{path}", json=data, timeout=10)
        r.raise_for_status()
        return r.json()
