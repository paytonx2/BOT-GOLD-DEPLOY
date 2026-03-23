# main.py  — FastAPI Backend
# pip install fastapi uvicorn[standard] python-jose[cryptography]
#             passlib[bcrypt] supabase apscheduler python-dotenv joblib
#             lightgbm xgboost scikit-learn pandas numpy requests

import os, json, asyncio, logging
from datetime import datetime, timedelta
from typing import Optional

import joblib, numpy as np, pandas as pd, requests
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from jose import JWTError, jwt
from passlib.context import CryptContext
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL  = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY  = os.getenv("SUPABASE_ANON_KEY", "")
TWELVE_KEY    = os.getenv("TWELVE_DATA_API_KEY", "")
JWT_SECRET    = os.getenv("JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE    = 60 * 24   # 24 hours (minutes)
MODEL_PATH    = "models/ensemble_models.pkl"
SYMBOL        = "XAU/USD"
INTERVAL      = "1h"
SIGNAL_KILL   = False      # Kill Switch — set True เพื่อหยุดส่ง signal

app = FastAPI(title="AuSignal API", version="1.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=["*"],   # Production: ใส่ domain จริง
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

# ── Supabase ──────────────────────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# ── Auth utils ────────────────────────────────────────────────────────────────
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2  = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_token(data: dict, expire_minutes: int = JWT_EXPIRE) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(token: str = Depends(oauth2)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        uid: str = payload.get("sub")
        role: str = payload.get("role", "user")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"id": uid, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user

# ── Pydantic Models ───────────────────────────────────────────────────────────
class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = ""

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str

class SignalOut(BaseModel):
    id: str
    symbol: str
    interval: str
    signal: str
    confidence: float
    proba_buy: float
    proba_wait: float
    proba_sell: float
    price: float
    sl: Optional[float]
    tp: Optional[float]
    rsi_14: float
    adx_14: float
    trend_regime: int
    ema_alignment: int
    high_vol: int
    created_at: str

# ── WebSocket Manager ─────────────────────────────────────────────────────────
class WSManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        log.info(f"WS connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active = [w for w in self.active if w != ws]

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = WSManager()

# ── AI Engine ─────────────────────────────────────────────────────────────────
_models = None

def load_models():
    global _models
    if not os.path.exists(MODEL_PATH):
        log.warning(f"Model not found: {MODEL_PATH}")
        return None
    _models = joblib.load(MODEL_PATH)
    log.info("โมเดลโหลดสำเร็จ")
    return _models

def fetch_bars(n: int = 350) -> pd.DataFrame:
    params = dict(symbol=SYMBOL, interval=INTERVAL, outputsize=n,
                  order="ASC", apikey=TWELVE_KEY, format="JSON")
    r = requests.get("https://api.twelvedata.com/time_series",
                     params=params, timeout=15)
    data = r.json()
    if data.get("status") == "error":
        raise RuntimeError(data["message"])
    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["open","high","low","close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = 0.0
    return df.sort_values("datetime").reset_index(drop=True)

def run_predict(df: pd.DataFrame, models: dict) -> dict:
    """import จาก run_pipeline_v2 — ต้องอยู่ใน path เดียวกัน"""
    from run_pipeline_v2 import predict, FEATURE_COLS
    signal, conf, proba, ctx = predict(models, df)
    return {
        "type": "signal",
        "id":   datetime.utcnow().isoformat(),
        "symbol": SYMBOL, "interval": INTERVAL,
        "signal": signal,
        "confidence": round(conf * 100, 1),
        "proba_buy":  round(proba["BUY"]  * 100, 1),
        "proba_wait": round(proba["WAIT"] * 100, 1),
        "proba_sell": round(proba["SELL"] * 100, 1),
        **ctx,
        "created_at": datetime.utcnow().isoformat(),
    }

async def ai_loop():
    """รันทุกชั่วโมง หลังแท่งปิด"""
    global SIGNAL_KILL
    if SIGNAL_KILL:
        log.warning("Kill Switch ON — ข้ามรอบนี้")
        return
    if _models is None:
        log.warning("ยังไม่มีโมเดล")
        return
    try:
        log.info("AI loop เริ่มทำงาน...")
        df     = fetch_bars(350)
        result = run_predict(df, _models)
        close  = float(df["close"].iloc[-1])
        result["price"] = close

        log.info(f"Signal: {result['signal']}  Conf: {result['confidence']}%  Price: ${close:,.2f}")

        # บันทึกลง Supabase
        if supabase and result["signal"] != "WAIT":
            supabase.table("signals").insert({
                "symbol":     result["symbol"],
                "interval":   result["interval"],
                "signal":     result["signal"],
                "confidence": result["confidence"],
                "price":      result["price"],
                "sl":         result.get("sl"),
                "tp":         result.get("tp"),
                "rsi_14":     result.get("rsi_14"),
                "adx_14":     result.get("adx_14"),
                "created_at": result["created_at"],
            }).execute()

        # Push ผ่าน WebSocket
        await ws_manager.broadcast(result)

    except Exception as e:
        log.error(f"AI loop error: {e}")
        await ws_manager.broadcast({"type":"error","message":str(e)})

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    load_models()
    scheduler = AsyncIOScheduler()
    # รันทุกชั่วโมงที่นาทีที่ 2 (หลังแท่งปิด 2 นาที)
    scheduler.add_job(ai_loop, "cron", minute=2)
    scheduler.start()
    log.info("Scheduler started — AI loop จะรันทุกชั่วโมง ที่ hh:02")

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/register", tags=["auth"])
async def register(body: RegisterBody):
    if not supabase:
        # Dev mode: คืน mock token
        token = create_token({"sub": "dev-user-001", "role": "user"})
        return TokenOut(access_token=token, role="user")

    try:
        res = supabase.auth.sign_up({"email": body.email, "password": body.password})
        uid = res.user.id
        supabase.table("profiles").insert({
            "id": uid, "email": body.email,
            "name": body.name, "role": "user",
        }).execute()
        token = create_token({"sub": uid, "role": "user"})
        return TokenOut(access_token=token, role="user")
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@app.post("/auth/login", tags=["auth"])
async def login(form: OAuth2PasswordRequestForm = Depends()):
    if not supabase:
        # Dev mode
        token = create_token({"sub": "dev-user-001", "role": "user"})
        return TokenOut(access_token=token, role="user")

    try:
        res  = supabase.auth.sign_in_with_password({"email": form.username, "password": form.password})
        uid  = res.user.id
        prof = supabase.table("profiles").select("role").eq("id", uid).single().execute()
        role = prof.data.get("role", "user")
        token = create_token({"sub": uid, "role": role})
        return TokenOut(access_token=token, role=role)
    except Exception:
        raise HTTPException(status_code=401, detail="อีเมล/รหัสผ่านไม่ถูกต้อง")


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/signal/latest", tags=["signals"])
async def get_latest_signal(user=Depends(get_current_user)):
    """ดึงสัญญาณล่าสุดทันที (REST fallback)"""
    if _models is None:
        raise HTTPException(503, "Model not loaded")
    try:
        df     = fetch_bars(350)
        result = run_predict(df, _models)
        result["price"] = float(df["close"].iloc[-1])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/signals/history", tags=["signals"])
async def get_signal_history(limit: int = 50, user=Depends(get_current_user)):
    """ประวัติสัญญาณจาก Supabase"""
    if not supabase:
        return {"data": [], "message": "Supabase not configured"}
    res = (supabase.table("signals")
           .select("*")
           .order("created_at", desc=True)
           .limit(limit)
           .execute())
    return {"data": res.data}


@app.get("/api/signals/stats", tags=["signals"])
async def get_signal_stats(user=Depends(get_current_user)):
    """สถิติ Win/Loss"""
    if not supabase:
        return {"win_rate": 73.4, "total": 0, "wins": 0, "losses": 0}
    res = supabase.table("signals").select("result").execute()
    data = res.data
    wins   = sum(1 for d in data if d.get("result") == "win")
    losses = sum(1 for d in data if d.get("result") == "loss")
    total  = wins + losses
    return {
        "win_rate": round(wins/total*100, 1) if total else 0,
        "total": total, "wins": wins, "losses": losses,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET
# ══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/signal")
async def ws_signal(ws: WebSocket, token: Optional[str] = None):
    """WebSocket endpoint — Frontend เชื่อมที่นี่"""
    await ws_manager.connect(ws)
    try:
        # ส่ง snapshot ทันทีที่เชื่อมต่อ
        if _models:
            try:
                df     = fetch_bars(350)
                result = run_predict(df, _models)
                result["price"] = float(df["close"].iloc[-1])
                await ws.send_json(result)
            except Exception as e:
                await ws.send_json({"type":"error","message":str(e)})

        # รอรับ ping จาก client
        while True:
            msg = await asyncio.wait_for(ws.receive_text(), timeout=60)
            if msg == "ping":
                await ws.send_json({"type":"pong","time":datetime.utcnow().isoformat()})

    except (WebSocketDisconnect, asyncio.TimeoutError):
        ws_manager.disconnect(ws)


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/admin/stats", tags=["admin"])
async def admin_stats(admin=Depends(require_admin)):
    users = 0
    if supabase:
        res   = supabase.table("profiles").select("id", count="exact").execute()
        users = res.count or 0
    return {
        "users_total":   users,
        "ws_connected":  len(ws_manager.active),
        "model_loaded":  _models is not None,
        "kill_switch":   SIGNAL_KILL,
        "server_time":   datetime.utcnow().isoformat(),
    }


@app.post("/admin/kill-switch", tags=["admin"])
async def toggle_kill_switch(enable: bool, admin=Depends(require_admin)):
    global SIGNAL_KILL
    SIGNAL_KILL = enable
    msg = "🛑 Kill Switch ON — หยุดส่ง Signal" if enable else "✅ Kill Switch OFF — กลับมาส่ง Signal"
    log.warning(msg)
    await ws_manager.broadcast({"type":"admin","message":msg,"kill_switch":enable})
    return {"kill_switch": SIGNAL_KILL, "message": msg}


@app.post("/admin/retrain", tags=["admin"])
async def trigger_retrain(admin=Depends(require_admin)):
    """Trigger retrain ใน background (ใช้เวลานาน)"""
    async def _retrain():
        import subprocess
        log.info("เริ่ม Retrain...")
        subprocess.run(["python", "run_pipeline_v2.py"], capture_output=True)
        load_models()
        await ws_manager.broadcast({"type":"admin","message":"✅ Retrain เสร็จแล้ว โมเดลใหม่โหลดแล้ว"})

    asyncio.create_task(_retrain())
    return {"message":"Retrain เริ่มทำงานใน background (~30-60 นาที)"}


@app.post("/admin/trigger-signal", tags=["admin"])
async def manual_trigger(admin=Depends(require_admin)):
    """Force run AI loop ทันที"""
    await ai_loop()
    return {"message": "AI loop triggered"}


@app.get("/admin/users", tags=["admin"])
async def list_users(limit: int = 100, admin=Depends(require_admin)):
    if not supabase:
        return {"data": []}
    res = supabase.table("profiles").select("*").limit(limit).execute()
    return {"data": res.data}


@app.patch("/admin/users/{uid}/role", tags=["admin"])
async def update_user_role(uid: str, role: str, admin=Depends(require_admin)):
    if role not in ["user","premium","admin"]:
        raise HTTPException(400, "role ต้องเป็น user | premium | admin")
    if supabase:
        supabase.table("profiles").update({"role": role}).eq("id", uid).execute()
    return {"uid": uid, "role": role}


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status":"ok","model":_models is not None,"ws_clients":len(ws_manager.active)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
