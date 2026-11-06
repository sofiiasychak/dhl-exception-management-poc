from typing import Any


class AuthRepository:
    def __init__(self, cognito_client: Any | None = None):
        self.cognito_client = cognito_client

    def sign_in(self, *, client_id: str, email: str, password: str) -> dict[str, str]:
        if self.cognito_client is None:
            raise RuntimeError("Cognito is not configured.")
        response = self.cognito_client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
            ClientId=client_id,
        )
        if "AuthenticationResult" in response:
            return {"id_token": response["AuthenticationResult"]["IdToken"]}
        return {
            "challenge_name": response.get("ChallengeName", ""),
            "session": response.get("Session", ""),
        }

    def respond_to_software_token(
        self, *, client_id: str, email: str, session: str, code: str
    ) -> str:
        if self.cognito_client is None:
            raise RuntimeError("Cognito is not configured.")
        response = self.cognito_client.respond_to_auth_challenge(
            ChallengeName="SOFTWARE_TOKEN_MFA",
            ClientId=client_id,
            Session=session,
            ChallengeResponses={
                "USERNAME": email,
                "SOFTWARE_TOKEN_MFA_CODE": code,
            },
        )
        return response["AuthenticationResult"]["IdToken"]
