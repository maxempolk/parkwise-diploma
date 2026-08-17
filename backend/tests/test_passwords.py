from app.passwords import hash_password, verify_password


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_password_hashes_use_unique_salts() -> None:
    assert hash_password("same password") != hash_password("same password")


def test_malformed_password_hash_is_rejected() -> None:
    assert not verify_password("password", "not-a-valid-hash")
