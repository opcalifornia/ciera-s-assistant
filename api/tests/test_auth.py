async def test_register_login_me_flow(app_client):
    register_payload = {
        "workspace_name": "Demo Workspace",
        "email": "founder@example.com",
        "password": "correct-horse-battery-staple",
        "full_name": "Founder",
    }
    resp = await app_client.post("/auth/register", json=register_payload)
    assert resp.status_code == 201
    tokens = resp.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    # Duplicate registration is rejected.
    dup = await app_client.post("/auth/register", json=register_payload)
    assert dup.status_code == 409

    login_resp = await app_client.post(
        "/auth/login",
        json={"email": "founder@example.com", "password": "correct-horse-battery-staple"},
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    me_resp = await app_client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["email"] == "founder@example.com"
    assert body["role"] == "owner"


async def test_login_wrong_password_rejected(app_client):
    await app_client.post(
        "/auth/register",
        json={
            "workspace_name": "Demo",
            "email": "a@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    resp = await app_client.post(
        "/auth/login", json={"email": "a@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 401


async def test_me_without_token_rejected(app_client):
    resp = await app_client.get("/auth/me")
    assert resp.status_code == 401


async def test_refresh_token_flow(app_client):
    register_resp = await app_client.post(
        "/auth/register",
        json={
            "workspace_name": "Demo",
            "email": "b@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    refresh_token = register_resp.json()["refresh_token"]
    resp = await app_client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
