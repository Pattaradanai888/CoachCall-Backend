# tests/test_main.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_read_root_endpoint(async_client: AsyncClient):
    """Test the root endpoint."""
    response = await async_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"msg": "Welcome to FastAPIApp!"}

@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health-check")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
