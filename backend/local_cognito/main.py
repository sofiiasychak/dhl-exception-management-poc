from datetime import datetime, timedelta, timezone
import os

import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr


app = FastAPI(title="Local Cognito Emulator", docs_url=None, redoc_url=None)
ISSUER = os.getenv("COGNITO_LOCAL_ISSUER", "http://localhost:9100")
SECRET = os.getenv("LOCAL_JWT_SECRET", "local-only-demo-signing-key-change-me")

USERS = {
    "marta.ops@example.com": ("marta-l", "ops", "Marta L.", "Kyiv-East"),
    "oleh.ops@example.com": ("oleh-s", "ops", "Oleh S.", "Kyiv-West"),
    "kateryna.support@example.com": ("kateryna-b", "support", "Kateryna B.", ""),
    "thomas.courier@example.com": ("thomas-a", "courier", "Thomas A.", "K-14"),
    "ivan.courier@example.com": ("ivan-s", "courier", "Ivan S.", "K-09"),
    "anna.depot@example.com": ("anna-k", "depot", "Anna K.", "Kyiv Hub"),
}
LOCAL_PASSWORD = "demo-local-only"


class Credentials(BaseModel):
    email: EmailStr
    password: str


@app.post("/login")
def login(credentials: Credentials):
    email = str(credentials.email).lower()
    user = USERS.get(email)
    if user is None or credentials.password != LOCAL_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    user_id, role, _name, _scope = user
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "iss": ISSUER,
            "sub": user_id,
            "aud": "local-demo-app-client",
            "iat": now,
            "exp": now + timedelta(hours=8),
            "email": email,
            "cognito:groups": [role],
            "token_use": "id",
        },
        SECRET,
        algorithm="HS256",
    )
    return {"id_token": token}
