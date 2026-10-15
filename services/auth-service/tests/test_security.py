from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_roundtrip():
    h = hash_password("secret123")
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    import uuid

    uid = str(uuid.uuid4())
    tok = create_access_token(uid, "a@ex.ru")
    payload = decode_token(tok)
    assert payload["sub"] == uid
    assert payload["email"] == "a@ex.ru"
