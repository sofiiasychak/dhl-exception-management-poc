import asyncio

import pytest

from app.features.auth.repository import AuthRepository
from app.features.auth.service import AuthService


class FakeCognito:
    def initiate_auth(self, **kwargs):
        assert kwargs["AuthFlow"] == "USER_PASSWORD_AUTH"
        assert kwargs["AuthParameters"]["USERNAME"] == "user@example.test"
        assert kwargs["ClientId"] == "client-id"
        return {"AuthenticationResult": {"IdToken": "signed-in"}}

def test_production_sign_in_uses_cognito_client(monkeypatch):
    monkeypatch.setenv("LOCAL_DEV", "false")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "client-id")
    service = AuthService(AuthRepository(FakeCognito()))
    assert asyncio.run(service.sign_in("user@example.test", "password")) == {
        "id_token": "signed-in"
    }


def test_cognito_mfa_challenge_is_returned_for_second_sign_in_step(monkeypatch):
    class ChallengeClient:
        def initiate_auth(self, **kwargs):
            return {"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "challenge-session"}

    monkeypatch.setenv("LOCAL_DEV", "false")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "client-id")
    service = AuthService(AuthRepository(ChallengeClient()))
    assert asyncio.run(service.sign_in("user@example.test", "password")) == {
        "challenge_name": "SOFTWARE_TOKEN_MFA",
        "session": "challenge-session",
    }


def test_cognito_mfa_verification_uses_the_cognito_challenge(monkeypatch):
    class ChallengeClient:
        def respond_to_auth_challenge(self, **kwargs):
            assert kwargs["ChallengeName"] == "SOFTWARE_TOKEN_MFA"
            assert kwargs["Session"] == "challenge-session"
            assert kwargs["ChallengeResponses"]["SOFTWARE_TOKEN_MFA_CODE"] == "123456"
            return {"AuthenticationResult": {"IdToken": "verified"}}

    monkeypatch.setenv("LOCAL_DEV", "false")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "client-id")
    service = AuthService(AuthRepository(ChallengeClient()))
    assert service.respond_to_software_token(
        "user@example.test", "challenge-session", "123456"
    ) == "verified"


def test_demo_sign_in_is_disabled_outside_local(monkeypatch):
    monkeypatch.setenv("LOCAL_DEV", "false")
    with pytest.raises(PermissionError):
        asyncio.run(AuthService().demo_sign_in("marta-l"))
