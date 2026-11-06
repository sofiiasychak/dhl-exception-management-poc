import os

import boto3
import httpx

from app.features.auth.repository import AuthRepository


class AuthService:
    def __init__(self, repository: AuthRepository | None = None):
        self.repository = repository

    @property
    def local_dev(self) -> bool:
        return os.getenv("LOCAL_DEV", "").lower() == "true"

    async def sign_in(self, email: str, password: str) -> dict[str, str]:
        if self.local_dev:
            return {"id_token": await self._local_sign_in(email, password)}
        client_id = os.getenv("COGNITO_APP_CLIENT_ID", "")
        if not client_id:
            raise RuntimeError("Cognito app client is not configured.")
        return self._repository().sign_in(
            client_id=client_id, email=email, password=password
        )

    def respond_to_software_token(self, email: str, session: str, code: str) -> str:
        if self.local_dev:
            raise PermissionError("TOTP verification is not used for local demo sign-in.")
        client_id = os.getenv("COGNITO_APP_CLIENT_ID", "")
        if not client_id:
            raise RuntimeError("Cognito app client is not configured.")
        return self._repository().respond_to_software_token(
            client_id=client_id, email=email, session=session, code=code
        )

    async def demo_sign_in(self, user_id: str) -> dict[str, str]:
        if not self.local_dev:
            raise PermissionError("Demo sign-in is available only in the local environment.")
        user = DEMO_USERS.get(user_id)
        if user is None:
            raise ValueError("Unknown demo user.")
        return {"id_token": await self._local_sign_in(user["email"], user["password"])}

    def _repository(self) -> AuthRepository:
        if self.repository is None:
            cognito = boto3.client(
                "cognito-idp", region_name=os.getenv("AWS_REGION", "eu-central-1")
            )
            self.repository = AuthRepository(cognito)
        return self.repository

    async def _local_sign_in(self, email: str, password: str) -> str:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                f"{os.getenv('COGNITO_LOCAL_URL', 'http://localhost:9100')}/login",
                json={"email": email, "password": password},
            )
        if response.status_code == 401:
            raise ValueError("Email or password is incorrect.")
        response.raise_for_status()
        return response.json()["id_token"]


DEMO_USERS = {
    "marta-l": {"email": "marta.ops@example.com", "password": "demo-local-only"},
    "oleh-s": {"email": "oleh.ops@example.com", "password": "demo-local-only"},
    "kateryna-b": {"email": "kateryna.support@example.com", "password": "demo-local-only"},
    "thomas-a": {"email": "thomas.courier@example.com", "password": "demo-local-only"},
    "ivan-s": {"email": "ivan.courier@example.com", "password": "demo-local-only"},
    "anna-k": {"email": "anna.depot@example.com", "password": "demo-local-only"},
}
