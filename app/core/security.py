import hashlib
import hmac
import secrets


def hash_pin(pin: str) -> str:
    """
    사용자가 등록한 핀번호(PIN)를 랜덤 솔트와 함께 PBKDF2-HMAC-SHA256으로 단방향 암호화합니다.
    저장 형식: {salt}${hex_digest}
    """
    pin_str = str(pin).strip()
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", pin_str.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${hashed.hex()}"


def verify_pin(pin: str, stored_hash: str) -> bool:
    """
    입력한 핀번호가 저장된 해시와 일치하는지 비교 검증합니다.
    """
    if not stored_hash or "$" not in stored_hash:
        return False
    try:
        salt, expected_hex = stored_hash.split("$", 1)
        pin_str = str(pin).strip()
        computed = hashlib.pbkdf2_hmac("sha256", pin_str.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return hmac.compare_digest(computed.hex(), expected_hex)
    except Exception:
        return False
