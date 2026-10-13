from models import User

CREDS = {"email": "a@test.com", "password": "password123"}


def login(client, email="a@test.com", password="password123"):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_signup_creates_user(client):
    response = client.post("/auth/signup", json=CREDS)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "a@test.com"
    assert "hashed_password" not in body


def test_password_is_stored_hashed(client, db_session):
    client.post("/auth/signup", json=CREDS)

    user = db_session.query(User).filter(User.email == "a@test.com").first()
    assert user.hashed_password != "password123"


def test_signup_duplicate_email_returns_400(client):
    client.post("/auth/signup", json=CREDS)
    response = client.post("/auth/signup", json=CREDS)

    assert response.status_code == 400


def test_signup_short_password_returns_422(client):
    response = client.post("/auth/signup", json={"email": "a@test.com", "password": "short"})

    assert response.status_code == 422


def test_signup_invalid_email_returns_422(client):
    response = client.post("/auth/signup", json={"email": "not-an-email", "password": "password123"})

    assert response.status_code == 422


def test_login_returns_both_tokens(client):
    client.post("/auth/signup", json=CREDS)
    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_wrong_password_returns_401(client):
    client.post("/auth/signup", json=CREDS)

    assert login(client, password="wrong-password").status_code == 401


def test_login_unknown_user_returns_401(client):
    assert login(client, email="nobody@test.com").status_code == 401


def test_me_without_token_returns_401(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_garbage_token_returns_401(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})

    assert response.status_code == 401


def test_me_returns_current_user(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "user@test.com"


def test_refresh_returns_working_tokens(client):
    client.post("/auth/signup", json=CREDS)
    tokens = login(client).json()

    response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_refresh_with_garbage_token_returns_401(client):
    response = client.post("/auth/refresh", json={"refresh_token": "garbage"})

    assert response.status_code == 401