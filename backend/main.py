from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pathlib import Path
import bcrypt
from pydantic import BaseModel

from Features.features import get_dashboard_metrics, get_portfolio_holdings
from Optimization import run_optimization
from Predction.risk_analysis import get_risk_metrics
from rebalance.rebalance import generate_rebalance_plan
from data.mock_data import MarketDataError
import backend.store
import backend.db as db
from rag.qa import answer_question

SECRET_KEY = "CHANGE_ME_BEFORE_PRODUCTION"  # move to env var
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def verify_password(plain: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed)

app = FastAPI(title="Portfolio Manager API")


@app.on_event("startup")
async def on_startup():
    db.init_db()
    print(f"[startup] SQLite DB ready at {db.DB_PATH}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class User(BaseModel):
    email: str
    full_name: str


class OptimizeRequest(BaseModel):
    portfolio: str
    risk_profile: str = "Moderate"
    method: str = "Mean-Variance (Markowitz)"
    min_weight: float = 0
    max_weight: float = 100
    max_sector_exposure: float = 100
    target_volatility: Optional[float] = None
    long_only: bool = True
    cash_buffer: bool = False


class RebalanceRequest(BaseModel):
    use_last_optimization: bool = True

class AskRequest(BaseModel):
    question: str

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = db.get_user_by_email(email)
    if user is None:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = db.get_user_by_email(email)
    if user is None:
        raise credentials_exception

    return User(email=user["email"], full_name=user["full_name"])


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Demo credentials: demo@portfolio.io / Demo@1234 """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user["email"]})
    return Token(access_token=access_token)


@app.get("/auth/me", response_model=User)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/api/dashboard")
def dashboard(current_user: User = Depends(get_current_user)):
    try:
        return get_dashboard_metrics()
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=f"Live market data unavailable: {exc}")


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------
@app.get("/api/portfolio/holdings")
def portfolio_holdings(current_user: User = Depends(get_current_user)):
    try:
        return get_portfolio_holdings()
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=f"Live market data unavailable: {exc}")


@app.post("/api/optimize")
def optimize(payload: OptimizeRequest, current_user: User = Depends(get_current_user)):
    try:
        result = run_optimization(
            method=payload.method,
            risk_profile=payload.risk_profile,
            min_weight=payload.min_weight,
            max_weight=payload.max_weight,
            long_only=payload.long_only,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=f"Live market data unavailable: {exc}")
    # Cache target weights (fraction, not pct) so /api/rebalance can use them.
    backend.store.set_last_optimized_weights(
        {w["ticker"]: w["weightPct"] / 100 for w in result["weights"]}
    )
    return result


@app.post("/api/rebalance")
def rebalance(payload: RebalanceRequest, current_user: User = Depends(get_current_user)):
    target_weights = backend.store.get_last_optimized_weights() if payload.use_last_optimization else None
    try:
        return generate_rebalance_plan(target_weights)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=f"Live market data unavailable: {exc}")


def risk_analysis(current_user: User = Depends(get_current_user)):
    try:
        return get_risk_metrics()
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=f"Live market data unavailable: {exc}")

@app.post("/api/ask")
def ask(payload: AskRequest, current_user: User = Depends(get_current_user)):
    try:
        return answer_question(payload.question)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=f"Live market data unavailable: {exc}")

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)



FRONTEND_FILES = {
    "login.html": "text/html",
    "dashboard.html": "text/html",
    "app.js": "application/javascript",
    "charts.js": "application/javascript",
    "style.css": "text/css",
}


@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "login.html", media_type="text/html")


@app.get("/{filename}")
async def serve_frontend_file(filename: str):
    if filename not in FRONTEND_FILES:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(BASE_DIR / filename, media_type=FRONTEND_FILES[filename])