from datetime import timedelta, datetime
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from passlib.context import CryptContext
from jose import jwt
from database import db
from database import db_schema
from dependencies import SECRET_KEY
from dependencies import ALGORITHM
from dependencies import ACCESS_TOKEN_EXPIRE_MINUTES
from dependencies import get_user

router = APIRouter()

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user['password']):
        return None
    return user


class RegisterUserBody(BaseModel):
    name: str
    username: str
    password: str


@router.post('/register')
async def register(new_user: RegisterUserBody):
    users = get_user(new_user.username)
    if users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Username already exists',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    plain_password = new_user.password
    new_user.password = get_password_hash(plain_password)
    db.insert(db_schema, 'user', [dict(new_user)])
    return new_user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


class TokenBody(BaseModel):
    access_token: str
    token_type: str


@router.post('/login', response_model=TokenBody)
async def login(data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(data.username, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={'sub': user['username']}, expires_delta=access_token_expires
    )
    return {'access_token': access_token, 'token_type': 'bearer'}
