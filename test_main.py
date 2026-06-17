import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import uuid

## mark all tests in this file as async for pytest-asyncio
pytestmark = pytest.mark.asyncio


## Generate unique username to prevent duplicate databse constraints on the repeat run
random_suffix = uuid.uuid4().hex[:8]
TEST_USER = f"testuser_{random_suffix}"
TEST_PASSWORD = "testpassword123"

async def test_signup():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/signup", json={
            "username": TEST_USER, 
            "password": TEST_PASSWORD
            }) 
    assert response.status_code == 200 ## assert runs the condition, here if we get 200 (which means success!) then it does nothing, or else raises an Assertion error
    assert "account created successfuly!" in response.json()["message"]


async def test_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # FastAPI's login endpoint uses OAuth2PasswordRequestForm (form data), not JSON
        response = await ac.post("/login", data={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_portfolio_unathorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/portfolio")
    assert response.status_code == 401


async def test_portfolio_authorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_response  = await ac.post("/login", data={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        })
        token = login_response.json()["access_token"]


        headers = {"Authorization": f"Bearer {token}"}
        response = await ac.get("/portfolio", headers=headers)

    assert response.status_code == 200
    assert TEST_USER in response.json()["message"]