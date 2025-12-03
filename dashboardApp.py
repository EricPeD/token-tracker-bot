from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, func
from src.models import AsyncSessionLocal, User, Transaction, UserToken
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import hmac
import hashlib
import time
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from src.config.settings import settings
import logging

# Configure logging for the dashboard app
logger = logging.getLogger("dashboard_app")
logger.setLevel(logging.DEBUG) # Set to DEBUG for more verbose output
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

app = FastAPI()

# Pydantic models for API responses and requests
class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

class UserTokenResponse(BaseModel):
    token_address: str
    token_symbol: Optional[str] = "UNKNOWN"


# --- Authentication ---
SECRET_KEY = settings.telegram_token
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/telegram")

def check_telegram_authorization(data: dict, bot_token: str) -> bool:
    data_check_string = []
    for key, value in sorted(data.items()):
        if key != 'hash':
            data_check_string.append(f"{key}={value}")
    data_check_string = "\n".join(data_check_string)
    secret_key = hashlib.sha256(bot_token.encode('utf-8')).digest()
    hmac_hash = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac_hash == data['hash']

def verify_access_token(token: str, credentials_exception) -> int:
    try:
        # Intenta decodificar el token con la clave secreta
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("id")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError as e: # Si la firma no coincide o el token ha expirado, entra aquí
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception


async def get_current_user(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return verify_access_token(token, credentials_exception)

# --- API Endpoints ---

@app.post("/auth/telegram")
async def authenticate_telegram_user(telegram_user: TelegramUser):
    logger.debug("Request received for /auth/telegram")
    auth_data = telegram_user.dict(exclude_unset=True)
    if not check_telegram_authorization(auth_data, settings.telegram_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram authorization data")
    
    if time.time() - telegram_user.auth_date > 1200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram authorization data is too old")

    async with AsyncSessionLocal() as session:
        user_in_db = await session.get(User, telegram_user.id)
        if not user_in_db:
            new_user = User(user_id=telegram_user.id, wallet_address="")
            session.add(new_user)
            await session.commit()
            logger.info(f"New Telegram user registered in DB: {telegram_user.id}")
        else:
            logger.info(f"Existing Telegram user logged in: {telegram_user.id}")

    to_encode = {"sub": str(telegram_user.id), "id": telegram_user.id}
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"JWT issued for user ID: {telegram_user.id}")
    return {"access_token": encoded_jwt, "token_type": "bearer", "user_id": telegram_user.id}


@app.get("/api/stats")
async def get_general_stats():
    logger.debug("Request received for /api/stats (public access)")
    async with AsyncSessionLocal() as session:
        users_count_result = await session.execute(select(func.count(User.user_id)))
        total_users = users_count_result.scalar_one()
        transactions_count_result = await session.execute(select(func.count(Transaction.id)))
        total_transactions = transactions_count_result.scalar_one()
    return {"total_users": total_users, "total_transactions": total_transactions}


@app.get("/api/me/tokens", response_model=List[UserTokenResponse])
async def get_user_tokens(current_user_id: int = Depends(get_current_user)):
    """
    Returns a list of tokens monitored by the currently authenticated user.
    """
    logger.debug(f"Request received for /api/me/tokens from user {current_user_id}")
    try:
        async with AsyncSessionLocal() as session:
            tracked_tokens_results = await session.execute(
                select(UserToken.token_address, UserToken.token_symbol).where(
                    UserToken.user_id == current_user_id
                )
            )
            tracked_tokens = tracked_tokens_results.all()
            response_data = [
                {"token_address": address, "token_symbol": symbol or "UNKNOWN"}
                for address, symbol in tracked_tokens
            ]
            return response_data
    except Exception as e:
        logger.error(f"Error fetching tokens for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch user tokens")

# Mount static files - Must be the last thing before running the app
app.mount("/", StaticFiles(directory="static/dashboard", html=True), name="dashboard")
