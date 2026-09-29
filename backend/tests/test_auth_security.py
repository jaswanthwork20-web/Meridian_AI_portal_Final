from app.auth.security import create_access_token, decode_access_token


def test_access_token_round_trip():
    token = create_access_token(42, "maya.sharma@meridian.com")

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["email"] == "maya.sharma@meridian.com"


def test_invalid_access_token_is_rejected():
    assert decode_access_token("not-a-valid-token") is None
