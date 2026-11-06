from typing import Annotated

import httpx
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.features.auth.service import AuthService
from app.security import AuthenticatedUser, get_current_user


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DemoLoginRequest(BaseModel):
    user_id: str


class MfaChallengeRequest(BaseModel):
    email: EmailStr
    session: str = Field(min_length=1)
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/login")
async def login(payload: LoginRequest):
    try:
        return await AuthService().sign_in(str(payload.email), payload.password)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.") from error
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        status_code = 401 if code in {"NotAuthorizedException", "UserNotFoundException"} else 503
        detail = "Email or password is incorrect." if status_code == 401 else "Sign-in is temporarily unavailable."
        raise HTTPException(status_code=status_code, detail=detail) from error
    except (httpx.HTTPError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable.") from error


@router.post("/challenge")
def verify_mfa(payload: MfaChallengeRequest):
    try:
        token = AuthService().respond_to_software_token(
            str(payload.email), payload.session, payload.code
        )
    except PermissionError as error:
        raise HTTPException(status_code=404, detail="Not found.") from error
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        status_code = 401 if code in {"CodeMismatchException", "NotAuthorizedException"} else 503
        detail = "The verification code is invalid or expired." if status_code == 401 else "Sign-in is temporarily unavailable."
        raise HTTPException(status_code=status_code, detail=detail) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable.") from error
    return {"id_token": token}


@router.post("/demo-login")
async def demo_login(payload: DemoLoginRequest):
    service = AuthService()
    try:
        token = await service.demo_sign_in(payload.user_id)
    except PermissionError as error:
        raise HTTPException(status_code=404, detail="Not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail="Demo user not found.") from error
    except (httpx.HTTPError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="Local sign-in is unavailable.") from error
    return token


@router.get("/me")
def me(user: Annotated[AuthenticatedUser, Depends(get_current_user)]):
    return {"user_id": user.user_id, "role": user.role.value, "email": user.email}
