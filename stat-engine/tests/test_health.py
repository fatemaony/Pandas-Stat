import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app


@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app()
    async with ASGITransport(app=app) as transport:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "version" in data
            assert "database" in data
