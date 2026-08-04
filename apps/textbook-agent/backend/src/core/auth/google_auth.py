from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


@dataclass
class GoogleUserInfo:
    email: str
    name: str | None
    picture_url: str | None
    google_id: str


def verify_google_token(token: str, client_id: str) -> GoogleUserInfo:
    """Verify a Google ID token and extract user info.

    Raises ValueError if the token is invalid or the audience doesn't match.
    """
    id_info = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        audience=client_id,
    )

    return GoogleUserInfo(
        email=id_info["email"],
        name=id_info.get("name"),
        picture_url=id_info.get("picture"),
        google_id=id_info["sub"],
    )
