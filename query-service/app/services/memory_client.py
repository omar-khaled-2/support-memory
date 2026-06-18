from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings


async def fetch_active_facts() -> List[Dict[str, Any]]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.memory_service_url}/facts", params={"status": "active"}
        )
        response.raise_for_status()
        return response.json()


async def fetch_briefing(entity_id: str) -> Dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.memory_service_url}/entities/{entity_id}/briefing"
        )
        response.raise_for_status()
        return response.json()


async def fetch_beliefs(entity_id: str) -> Dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.memory_service_url}/entities/{entity_id}/beliefs"
        )
        response.raise_for_status()
        return response.json()


async def fetch_digest(
    entity_id: str, since_snapshot_id: Optional[str] = None
) -> Dict[str, Any]:
    settings = get_settings()
    params = {}
    if since_snapshot_id:
        params["since_snapshot_id"] = since_snapshot_id
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.memory_service_url}/entities/{entity_id}/digest",
            params=params,
        )
        response.raise_for_status()
        return response.json()
