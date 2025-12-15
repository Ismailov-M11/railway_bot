import httpx
from typing import Dict, Any, List
from config import BASE_HEADERS, STATIONS_API, TRAINS_API

async def api_post(url: str, lang: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = dict(BASE_HEADERS)
    headers["Accept-Language"] = lang
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()

async def search_stations(query: str, lang: str) -> List[Dict[str, str]]:
    q = (query or "").strip()
    if len(q) < 2:
        return []
    data = await api_post(STATIONS_API, lang, {"name": q})
    return data.get("data", {}).get("stations", []) or []

async def fetch_trains(dep_code: str, arv_code: str, date_yyyy_mm_dd: str, lang: str) -> Dict[str, Any]:
    payload = {
        "directions": {
            "forward": {
                "date": date_yyyy_mm_dd,
                "depStationCode": dep_code,
                "arvStationCode": arv_code,
            }
        }
    }
    return await api_post(TRAINS_API, lang, payload)
