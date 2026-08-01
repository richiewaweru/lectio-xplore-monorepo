from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWTError


class JWTHandler:
    def __init__(self, secret_key: str, algorithm: str, expire_minutes: int) -> None:
        self._secret = secret_key
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def create_access_token(self, user_id: str, email: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self._expire_minutes)
        payload = {
            "sub": user_id,
            "email": email,
            "exp": expire,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict:
        """Decode and verify a JWT. Raises PyJWTError on failure."""
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except PyJWTError:
            raise
