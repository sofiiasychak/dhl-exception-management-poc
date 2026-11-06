from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Annotated, Callable

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from app.core.rules import Role


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    role: Role
    email: str | None = None


@lru_cache
def jwks_client() -> PyJWKClient:
    region = os.getenv("AWS_REGION", "eu-central-1")
    pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
    return PyJWKClient(
        f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    )


def verify_token(token: str) -> AuthenticatedUser:
    local_dev = os.getenv("LOCAL_DEV", "").lower() == "true"
    if local_dev:
        claims = jwt.decode(
            token,
            os.getenv("LOCAL_JWT_SECRET", ""),
            algorithms=["HS256"],
            issuer=os.getenv("COGNITO_LOCAL_ISSUER", "http://localhost:9100"),
            options={"verify_aud": False},
        )
    else:
        region = os.getenv("AWS_REGION", "eu-central-1")
        pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
        client_id = os.getenv("COGNITO_APP_CLIENT_ID", "")
        if not pool_id or not client_id:
            raise jwt.InvalidTokenError("Cognito is not configured.")
        issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
        signing_key = jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=client_id,
        )
        if claims.get("token_use") != "id":
            raise jwt.InvalidTokenError("An ID token is required.")

    groups = claims.get("cognito:groups", [])
    matching_roles = [role for role in Role if role.value in groups]
    if len(matching_roles) != 1:
        raise jwt.InvalidTokenError("The token must contain exactly one application role.")
    return AuthenticatedUser(
        user_id=str(claims["sub"]),
        role=matching_roles[0],
        email=claims.get("email"),
    )


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_token(authorization.removeprefix("Bearer ").strip())
    except (jwt.PyJWTError, KeyError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired sign-in token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def roles_required(*roles: Role) -> Callable:
    def dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="This role cannot access this endpoint.")
        return user

    return dependency
