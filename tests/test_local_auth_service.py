from services import local_auth_service


def test_verify_password_returns_false_for_malformed_hash() -> None:
    assert local_auth_service.verify_password("demo1234", "not-an-argon2-hash") is False


def test_verify_password_accepts_valid_hash() -> None:
    hashed = local_auth_service.hash_password("demo1234")

    assert local_auth_service.verify_password("demo1234", hashed) is True
    assert local_auth_service.verify_password("wrong-password", hashed) is False
