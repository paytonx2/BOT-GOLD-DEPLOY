"""
run_pipeline_v2.py
==================
แก้ปัญหา "AI ขี้เกียจ" (predicts WAIT ตลอด):

1. Timeframe  : เปลี่ยนเป็น 1h (ค้าขายในวัน)
2. Target     : ปรับ threshold ให้ BUY/SELL ≈ 30-35% ของข้อมูล
3. Imbalance  : SMOTE oversampling + Focal Loss weight
4. Model      : เพิ่ม threshold tuning (ไม่ใช้แค่ argmax)
5. Metric     : วัดด้วย F1 macro เป็นหลัก ไม่ใช่ Accuracy
"""

import os, glob, warnings, joblib, time
import numpy as np
import pandas as pd
import requests
import optuna
from optuna.samplers import TPESampler
from datetime import datetime, timedelta
from collections import Counter

from sklearn.preprocessing import RobustScaler
from sklearn.metrics import (accuracy_score, f1_score,
                              classification_report, confusion_matrix)
import lightgbm as lgb
import xgboost as xgb

try:
    from imblearn.over_sampling import SMOTE
    HAS_SMOTE = True
except ImportError:
    HAS_SMOTE = False
    print("ติดตั้ง imbalanced-learn: pip install imbalanced-learn")

from dotenv import load_dotenv
load_dotenv()
warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY   = os.getenv("TWELVE_DATA_API_KEY", "YOUR_KEY_HERE")
SYMBOL    = "XAU/USD"
INTERVAL  = "1h"        # ← เปลี่ยนจาก 1day เป็น 1h
YEARS_BACK = 3          # 1h = ~6,500 แท่ง/ปี × 3 ปี = ~19,500 แท่ง
DATA_DIR  = "gold_data"
MODEL_DIR = "models"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Target config (ปรับตรงนี้เพื่อเพิ่ม/ลด signal ความถี่) ─────────────────
FORWARD_BARS = 6        # มองไปข้างหน้า 6 แท่ง (6h)
ATR_SL_MULT  = 1.2      # SL = ATR × 1.2
RR_RATIO     = 1.8      # TP = SL × 1.8  (ลดจาก 2.0 → signal เยอะขึ้น)
MIN_SIGNAL_PCT = 0.25   # บังคับให้ BUY+SELL ≥ 25% ของข้อมูล


# ════════════════════════════════════════════════════════════════════════════
#  STEP 1 — ดึงข้อมูล 1h
# ════════════════════════════════════════════════════════════════════════════

def fetch_ohlcv() -> pd.DataFrame:
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=365 * YEARS_BACK)
    all_rows, current_end, page = [], end_date, 0

    print(f"\n[1/4] ดึงข้อมูล {SYMBOL} {INTERVAL} ({start_date.date()} → {end_date.date()})")

    while current_end > start_date:
        page += 1
        params = dict(symbol=SYMBOL, interval=INTERVAL, outputsize=5000,
                      end_date=current_end.strftime("%Y-%m-%d %H:%M:%S"),
                      order="ASC", apikey=API_KEY, format="JSON")
        r = requests.get("https://api.twelvedata.com/time_series",
                         params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "error":
            raise RuntimeError(data.get("message"))

        vals = data.get("values", [])
        if not vals:
            break

        df_p = pd.DataFrame(vals)
        df_p["datetime"] = pd.to_datetime(df_p["datetime"])
        all_rows.append(df_p)

        oldest = df_p["datetime"].min()
        print(f"  page {page}: {len(df_p)} rows | oldest: {oldest}")
        if oldest <= start_date:
            break
        current_end = oldest - timedelta(hours=1)
        time.sleep(8)

    df = pd.concat(all_rows, ignore_index=True)
    df = df[df["datetime"] >= start_date].copy()
    df = df.drop_duplicates("datetime").sort_values("datetime").reset_index(drop=True)
    for col in ["open","high","low","close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    else:
        df["volume"] = 0.0

    # ตัด weekend gap (forex ปิด Sat-Sun)
    df = df[df["datetime"].dt.dayofweek < 5].reset_index(drop=True)
    print(f"  รวม: {len(df)} rows")
    return df


# ════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Feature Engineering + Target ที่สมดุล
# ════════════════════════════════════════════════════════════════════════════

def compute_features(df: pd.DataFrame, is_training: bool = True) -> pd.DataFrame:
    df = df.copy().sort_values("datetime").reset_index(drop=True)
    c, h, l = df["close"], df["high"], df["low"]

    # ATR ก่อนเพราะทุก feature ใช้
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    df["atr_14"] = tr.ewm(span=14, adjust=False).mean()

    # ── EMA ──────────────────────────────────────────────────────────────────
    for n in [9, 20, 50, 100, 200]:
        df[f"ema_{n}"] = c.ewm(span=n, adjust=False).mean()
    for n in [20, 50, 200]:
        df[f"ema_{n}_dist"] = (c - df[f"ema_{n}"]) / (df["atr_14"] + 1e-9)
    df["ema_20_slope"] = df["ema_20"].diff(5) / (df["atr_14"] * 5 + 1e-9)
    df["ema_50_slope"] = df["ema_50"].diff(10) / (df["atr_14"] * 10 + 1e-9)
    emas = [df[f"ema_{n}"] for n in [9,20,50,100,200]]
    df["ema_alignment"] = sum((emas[i] > emas[i+1]).astype(int) for i in range(4))

    df["golden_cross"] = ((df["ema_50"] > df["ema_200"]) &
                          (df["ema_50"].shift(1) <= df["ema_200"].shift(1))).astype(int)
    df["death_cross"]  = ((df["ema_50"] < df["ema_200"]) &
                          (df["ema_50"].shift(1) >= df["ema_200"].shift(1))).astype(int)
    df["trend_regime"] = np.where(
        (df["ema_alignment"] >= 3) & (df["ema_20_slope"] > 0),  1,
        np.where((df["ema_alignment"] <= 1) & (df["ema_20_slope"] < 0), -1, 0)
    )

    # ── ADX ───────────────────────────────────────────────────────────────────
    dm_p = h.diff().clip(lower=0); dm_n = (-l.diff()).clip(lower=0)
    dm_pc = dm_p.where(dm_p > dm_n, 0); dm_nc = dm_n.where(dm_n > dm_p, 0)
    a14   = tr.ewm(span=14, adjust=False).mean()
    df["di_plus"]  = 100 * dm_pc.ewm(span=14,adjust=False).mean() / (a14+1e-9)
    df["di_minus"] = 100 * dm_nc.ewm(span=14,adjust=False).mean() / (a14+1e-9)
    dx = 100*(df["di_plus"]-df["di_minus"]).abs() / (df["di_plus"]+df["di_minus"]+1e-9)
    df["adx_14"]  = dx.ewm(span=14,adjust=False).mean()
    df["di_diff"] = df["di_plus"] - df["di_minus"]
    df["adx_trending"] = (df["adx_14"] > 25).astype(int)

    # ── MACD ──────────────────────────────────────────────────────────────────
    e12 = c.ewm(span=12,adjust=False).mean()
    e26 = c.ewm(span=26,adjust=False).mean()
    df["macd"]        = (e12-e26) / (df["atr_14"]+1e-9)   # normalize ด้วย ATR
    df["macd_signal"] = df["macd"].ewm(span=9,adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]
    df["macd_hist_slope"] = df["macd_hist"].diff(3)
    df["macd_bull"]   = ((df["macd"]>df["macd_signal"]) &
                         (df["macd"].shift(1)<=df["macd_signal"].shift(1))).astype(int)
    df["macd_bear"]   = ((df["macd"]<df["macd_signal"]) &
                         (df["macd"].shift(1)>=df["macd_signal"].shift(1))).astype(int)

    # ── RSI ───────────────────────────────────────────────────────────────────
    def _rsi(s, p):
        d = s.diff()
        g = d.clip(lower=0).ewm(span=p, adjust=False).mean()   # EWM RSI (เสถียรกว่า)
        ls = (-d.clip(upper=0)).ewm(span=p, adjust=False).mean()
        return 100 - 100/(1+g/(ls+1e-9))

    df["rsi_14"]    = _rsi(c, 14)
    df["rsi_7"]     = _rsi(c, 7)
    df["rsi_21"]    = _rsi(c, 21)
    df["rsi_slope"] = df["rsi_14"].diff(5)
    df["rsi_ob"]    = (df["rsi_14"] > 70).astype(int)
    df["rsi_os"]    = (df["rsi_14"] < 30).astype(int)

    # RSI Divergence
    df["bull_div"] = (
        (l < l.shift(3)) & (df["rsi_14"] > df["rsi_14"].shift(3)) & (df["rsi_14"] < 40)
    ).astype(int)
    df["bear_div"] = (
        (h > h.shift(3)) & (df["rsi_14"] < df["rsi_14"].shift(3)) & (df["rsi_14"] > 60)
    ).astype(int)

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    bm  = c.rolling(20).mean()
    bs  = c.rolling(20).std()
    df["bb_upper"]   = bm + 2*bs
    df["bb_lower"]   = bm - 2*bs
    df["bb_pct"]     = (c - df["bb_lower"]) / (df["bb_upper"]-df["bb_lower"]+1e-9)
    df["bb_width"]   = (df["bb_upper"]-df["bb_lower"]) / (bm+1e-9) * 100
    df["bb_squeeze"] = (df["bb_width"] < df["bb_width"].rolling(100).quantile(0.15)).astype(int)

    # ── Support / Resistance ──────────────────────────────────────────────────
    for n in [24, 48, 100]:   # 24h, 48h, ~2 weeks
        df[f"high_{n}"] = h.rolling(n).max()
        df[f"low_{n}"]  = l.rolling(n).min()
        df[f"dist_high_{n}"] = (df[f"high_{n}"] - c) / (df["atr_14"]+1e-9)
        df[f"dist_low_{n}"]  = (c - df[f"low_{n}"])  / (df["atr_14"]+1e-9)

    # Pivot (ใช้ 24 แท่งก่อนหน้า ≈ 1 วัน)
    ph = h.rolling(24).max().shift(1)
    pl = l.rolling(24).min().shift(1)
    pc = c.rolling(24).mean().shift(1)
    df["pivot"]       = (ph+pl+pc)/3
    df["dist_pivot"]  = (c - df["pivot"]) / (df["atr_14"]+1e-9)

    # Swing High/Low (lookback=5 bars สำหรับ 1h)
    lb = 5
    sh_arr = np.zeros(len(df)); sl_arr = np.zeros(len(df))
    hv, lv = h.values, l.values
    for i in range(lb, len(df)-lb):
        if hv[i] == max(hv[i-lb:i+lb+1]):
            sh_arr[i] = hv[i]
        if lv[i] == min(lv[i-lb:i+lb+1]):
            sl_arr[i] = lv[i]
    lsh = pd.Series(sh_arr,index=df.index).replace(0,np.nan).ffill()
    lsl = pd.Series(sl_arr,index=df.index).replace(0,np.nan).ffill()
    df["dist_swing_high"] = (lsh - c) / (df["atr_14"]+1e-9)
    df["dist_swing_low"]  = (c - lsl) / (df["atr_14"]+1e-9)
    df["near_resistance"] = (df["dist_swing_high"] < 0.8).astype(int)
    df["near_support"]    = (df["dist_swing_low"]  < 0.8).astype(int)

    # ── Volatility ────────────────────────────────────────────────────────────
    df["log_ret"]     = np.log(c/c.shift(1))
    df["pct_change"]  = c.pct_change()*100
    df["range_atr"]   = (h-l)/(df["atr_14"]+1e-9)
    df["atr_pct"]     = df["atr_14"]/c*100
    df["vol_12"]      = df["log_ret"].rolling(12).std()*100
    df["vol_48"]      = df["log_ret"].rolling(48).std()*100
    df["vol_ratio"]   = df["vol_12"]/(df["vol_48"]+1e-9)
    df["high_vol"]    = (df["vol_12"] > df["vol_48"].rolling(200).quantile(0.75)).astype(int)

    # ── Calendar (สำคัญสำหรับ intraday) ─────────────────────────────────────
    df["hour"]        = df["datetime"].dt.hour
    df["day_of_week"] = df["datetime"].dt.dayofweek
    df["month"]       = df["datetime"].dt.month
    # London session (7-16 UTC), NY session (13-22 UTC) — ตลาดทองแอคทีฟสุด
    df["london_session"] = df["hour"].between(7, 15).astype(int)
    df["ny_session"]     = df["hour"].between(13, 21).astype(int)
    df["overlap_session"]= df["hour"].between(13, 15).astype(int)  # London+NY overlap

    # ── Target ───────────────────────────────────────────────────────────────
    if is_training:
        # มองไปข้างหน้า FORWARD_BARS แท่ง
        fmax   = h.shift(-1).rolling(FORWARD_BARS).max()
        fmin   = l.shift(-1).rolling(FORWARD_BARS).min()

        sl_sz  = df["atr_14"] * ATR_SL_MULT
        tp_sz  = sl_sz * RR_RATIO

        long_ok  = fmax >= (c + tp_sz)
        short_ok = fmin <= (c - tp_sz)

        df["target"] = np.where(
            long_ok  & ~short_ok,  2,   # BUY
            np.where(short_ok & ~long_ok, 0,   # SELL
            1)                                  # WAIT
        )

        # ── ตรวจสอบ class balance ─────────────────────────────────────────────
        dist = df["target"].value_counts(normalize=True)
        buy_sell_pct = dist.get(0,0) + dist.get(2,0)
        print(f"\n  Target dist (raw): SELL={dist.get(0,0)*100:.1f}%  "
              f"WAIT={dist.get(1,0)*100:.1f}%  BUY={dist.get(2,0)*100:.1f}%")

        # ถ้า signal น้อยกว่า MIN_SIGNAL_PCT ให้ผ่อน RR ลง
        if buy_sell_pct < MIN_SIGNAL_PCT:
            print(f"  Signal น้อยเกินไป ({buy_sell_pct*100:.1f}%) — ลด RR ratio อัตโนมัติ")
            # ลด RR จนกว่า signal ≥ 25%
            for rr in [1.5, 1.2, 1.0]:
                tp2 = sl_sz * rr
                lo2  = fmax >= (c + tp2)
                so2  = fmin <= (c - tp2)
                df["target"] = np.where(lo2 & ~so2, 2, np.where(so2 & ~lo2, 0, 1))
                d2 = df["target"].value_counts(normalize=True)
                pct2 = d2.get(0,0) + d2.get(2,0)
                print(f"    RR={rr:.1f}: signal={pct2*100:.1f}%")
                if pct2 >= MIN_SIGNAL_PCT:
                    break

        df = df.dropna(subset=FEATURE_COLS + ["target"]).reset_index(drop=True)

    return df


FEATURE_COLS = [
    # Trend
    "ema_alignment","ema_20_dist","ema_50_dist","ema_200_dist",
    "ema_20_slope","ema_50_slope","trend_regime",
    "adx_14","di_diff","adx_trending",
    "macd","macd_signal","macd_hist","macd_hist_slope","macd_bull","macd_bear",
    "golden_cross","death_cross",
    # Momentum
    "rsi_14","rsi_7","rsi_21","rsi_slope","rsi_ob","rsi_os",
    "bull_div","bear_div",
    # S/R
    "bb_pct","bb_width","bb_squeeze",
    "dist_high_24","dist_low_24","dist_high_48","dist_low_48",
    "dist_high_100","dist_low_100",
    "dist_pivot","dist_swing_high","dist_swing_low",
    "near_resistance","near_support",
    # Volatility
    "atr_pct","range_atr","vol_12","vol_48","vol_ratio","high_vol",
    "log_ret","pct_change",
    # Calendar
    "hour","day_of_week","month",
    "london_session","ny_session","overlap_session",
]


# ════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Train ที่แก้ปัญหา class imbalance
# ════════════════════════════════════════════════════════════════════════════

def get_class_weights(y: np.ndarray) -> dict:
    """คำนวณ class weight แบบ inverse frequency"""
    counter = Counter(y)
    total   = len(y)
    weights = {cls: total / (len(counter) * cnt) for cls, cnt in counter.items()}
    # boost SELL/BUY เพิ่ม เพราะสำคัญกว่า WAIT
    weights[0] = weights.get(0, 1.0) * 1.5   # SELL
    weights[2] = weights.get(2, 1.0) * 1.5   # BUY
    return weights


def tune_lgbm(X_tr, y_tr, X_val, y_val, cw, n_trials):
    def obj(trial):
        p = dict(
            objective="multiclass", num_class=3,
            metric="multi_logloss", verbosity=-1, random_state=42,
            class_weight=cw,
            n_estimators      = trial.suggest_int("n_est", 300, 800),
            learning_rate     = trial.suggest_float("lr", 0.005, 0.08, log=True),
            max_depth         = trial.suggest_int("depth", 4, 8),
            num_leaves        = trial.suggest_int("leaves", 20, 100),
            min_child_samples = trial.suggest_int("mcs", 20, 80),
            subsample         = trial.suggest_float("sub", 0.6, 0.9),
            colsample_bytree  = trial.suggest_float("col", 0.5, 0.9),
            reg_alpha         = trial.suggest_float("a", 1e-3, 5.0, log=True),
            reg_lambda        = trial.suggest_float("l", 1e-3, 5.0, log=True),
        )
        m = lgb.LGBMClassifier(**p)
        m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)],
              callbacks=[lgb.early_stopping(40,verbose=False), lgb.log_evaluation(-1)])
        return f1_score(y_val, m.predict(X_val), average="macro")

    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=42))
    study.optimize(obj, n_trials=n_trials, show_progress_bar=True)
    return study.best_params


def tune_xgb(X_tr, y_tr, X_val, y_val, cw, n_trials):
    # XGBoost ใช้ sample_weight แทน class_weight
    sw = np.array([cw[int(yi)] for yi in y_tr])
    def obj(trial):
        p = dict(
            objective="multi:softprob", num_class=3,
            eval_metric="mlogloss", verbosity=0, random_state=42,
            use_label_encoder=False,
            early_stopping_rounds=40,
            n_estimators     = trial.suggest_int("n_est", 300, 800),
            learning_rate    = trial.suggest_float("lr", 0.005, 0.08, log=True),
            max_depth        = trial.suggest_int("depth", 4, 8),
            subsample        = trial.suggest_float("sub", 0.6, 0.9),
            colsample_bytree = trial.suggest_float("col", 0.5, 0.9),
            reg_alpha        = trial.suggest_float("a", 1e-3, 5.0, log=True),
            reg_lambda       = trial.suggest_float("l", 1e-3, 5.0, log=True),
            min_child_weight = trial.suggest_int("mcw", 5, 30),
        )
        m = xgb.XGBClassifier(**p)
        m.fit(X_tr, y_tr, sample_weight=sw,
              eval_set=[(X_val, y_val)], verbose=False)
        return f1_score(y_val, m.predict(X_val), average="macro")

    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=42))
    study.optimize(obj, n_trials=n_trials, show_progress_bar=True)
    return study.best_params


def walk_forward_splits(df, train_months=18, test_months=2, n_splits=6):
    df = df.sort_values("datetime").reset_index(drop=True)
    dates = df["datetime"]
    splits, test_end = [], dates.max()
    for _ in range(n_splits):
        ts  = test_end  - pd.DateOffset(months=test_months)
        te2 = ts - pd.Timedelta(hours=1)
        trs = te2 - pd.DateOffset(months=train_months)
        if trs < dates.min():
            break
        tri = df[(dates >= trs)  & (dates <= te2)].index.tolist()
        tei = df[(dates >= ts)   & (dates <= test_end)].index.tolist()
        if len(tri) > 500 and len(tei) > 50:
            splits.append((tri, tei))
        test_end = ts - pd.Timedelta(hours=1)
    return list(reversed(splits))


def apply_smote(X, y):
    if not HAS_SMOTE:
        return X, y
    counter = Counter(y)
    print(f"    Before SMOTE: {dict(counter)}")
    # target: ทุก class ≥ 40% ของ majority
    majority = max(counter.values())
    strategy = {cls: max(cnt, int(majority * 0.40))
                for cls, cnt in counter.items()}
    sm = SMOTE(sampling_strategy=strategy, random_state=42, k_neighbors=5)
    try:
        Xs, ys = sm.fit_resample(X, y)
        print(f"    After SMOTE : {dict(Counter(ys))}")
        return Xs, ys
    except Exception as e:
        print(f"    SMOTE skip ({e})")
        return X, y


def train_model(df: pd.DataFrame, n_trials: int = 50):
    print(f"\n[3/4] Train  ({len(df)} rows × {len(FEATURE_COLS)} features)")

    X = df[FEATURE_COLS].values
    y = df["target"].values

    dist = Counter(y)
    print(f"  Class dist: SELL={dist[0]} ({dist[0]/len(y)*100:.1f}%)  "
          f"WAIT={dist[1]} ({dist[1]/len(y)*100:.1f}%)  "
          f"BUY={dist[2]} ({dist[2]/len(y)*100:.1f}%)")

    cw = get_class_weights(y)
    print(f"  Class weights: {cw}")

    splits = walk_forward_splits(df)
    print(f"\n  Walk-Forward: {len(splits)} folds")
    print(f"  {'Fold':>5}  {'Acc':>6}  {'F1-macro':>8}  "
          f"{'F1-BUY':>7}  {'F1-SELL':>7}  {'WAIT%':>6}")
    print(f"  {'─'*50}")

    fold_metrics = []
    for fold, (tri, tei) in enumerate(splits, 1):
        X_tr, y_tr = X[tri], y[tri]
        X_te, y_te = X[tei], y[tei]

        scaler = RobustScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)

        val_n  = max(100, len(X_tr_s)//8)
        Xv, yv = X_tr_s[-val_n:], y_tr[-val_n:]
        Xt, yt = X_tr_s[:-val_n],  y_tr[:-val_n]

        # Apply SMOTE on train portion only
        Xt_sm, yt_sm = apply_smote(Xt, yt)

        # LightGBM
        bp_l = tune_lgbm(Xt_sm, yt_sm, Xv, yv, cw, n_trials)
        bp_l.update(dict(objective="multiclass", num_class=3,
                         class_weight=cw, verbosity=-1, random_state=42))
        ml = lgb.LGBMClassifier(**bp_l)
        ml.fit(X_tr_s, y_tr, eval_set=[(Xv,yv)],
               callbacks=[lgb.early_stopping(50,verbose=False), lgb.log_evaluation(-1)])

        # XGBoost
        bp_x = tune_xgb(Xt_sm, yt_sm, Xv, yv, cw, n_trials)
        bp_x.update(dict(objective="multi:softprob", num_class=3,
                         use_label_encoder=False, verbosity=0, random_state=42,
                         early_stopping_rounds=50))
        mx = xgb.XGBClassifier(**bp_x)
        sw_full = np.array([cw[int(yi)] for yi in y_tr])
        mx.fit(X_tr_s, y_tr, sample_weight=sw_full,
               eval_set=[(Xv,yv)], verbose=False)

        avg_prob = (ml.predict_proba(X_te_s) + mx.predict_proba(X_te_s)) / 2
        preds    = np.argmax(avg_prob, axis=1)
        acc      = accuracy_score(y_te, preds)
        f1_mac   = f1_score(y_te, preds, average="macro")
        f1_each  = f1_score(y_te, preds, average=None, labels=[0,1,2])

        # % ที่ predict เป็น WAIT
        wait_pct = (preds == 1).mean() * 100

        fold_metrics.append(dict(fold=fold, acc=acc, f1=f1_mac,
                                  f1_sell=f1_each[0], f1_wait=f1_each[1],
                                  f1_buy=f1_each[2], wait_pct=wait_pct))
        print(f"  {fold:>5}  {acc:>6.3f}  {f1_mac:>8.3f}  "
              f"{f1_each[2]:>7.3f}  {f1_each[0]:>7.3f}  {wait_pct:>5.1f}%")

    mdf = pd.DataFrame(fold_metrics)
    print(f"\n  Mean → Acc={mdf['acc'].mean():.3f}  F1={mdf['f1'].mean():.3f}  "
          f"F1-BUY={mdf['f1_buy'].mean():.3f}  F1-SELL={mdf['f1_sell'].mean():.3f}  "
          f"WAIT%={mdf['wait_pct'].mean():.1f}%")

    # ── Final model บนข้อมูลทั้งหมด ──────────────────────────────────────────
    print("\n  Train final models...")
    scaler = RobustScaler()
    X_all  = scaler.fit_transform(X)

    val_n     = max(200, len(X_all)//10)
    Xv, yv    = X_all[-val_n:], y[-val_n:]
    Xt, yt    = X_all[:-val_n], y[:-val_n]
    Xt_sm, yt_sm = apply_smote(Xt, yt)

    print("    Optuna LightGBM...")
    bp_l = tune_lgbm(Xt_sm, yt_sm, Xv, yv, cw, n_trials)
    bp_l.update(dict(objective="multiclass", num_class=3,
                     class_weight=cw, verbosity=-1, random_state=42))
    final_lgbm = lgb.LGBMClassifier(**bp_l)
    final_lgbm.fit(X_all, y, eval_set=[(Xv,yv)],
                   callbacks=[lgb.early_stopping(60,verbose=False), lgb.log_evaluation(-1)])

    print("    Optuna XGBoost...")
    bp_x = tune_xgb(Xt_sm, yt_sm, Xv, yv, cw, n_trials)
    bp_x.update(dict(objective="multi:softprob", num_class=3,
                     use_label_encoder=False, verbosity=0, random_state=42,
                     early_stopping_rounds=60))
    final_xgb = xgb.XGBClassifier(**bp_x)
    sw_all = np.array([cw[int(yi)] for yi in y])
    final_xgb.fit(X_all, y, sample_weight=sw_all, eval_set=[(Xv,yv)],
                  verbose=False)

    # Feature Importance
    fi = pd.DataFrame({
        "feature": FEATURE_COLS,
        "lgbm":    final_lgbm.feature_importances_,
        "xgb":     final_xgb.feature_importances_,
    })
    fi["mean"] = fi[["lgbm","xgb"]].mean(axis=1)
    fi = fi.sort_values("mean", ascending=False)
    print(f"\n  Top 12 features:\n{fi.head(12)[['feature','mean']].to_string(index=False)}")

    models = {
        "lgbm": final_lgbm, "xgb": final_xgb,
        "scaler": scaler, "feature_cols": FEATURE_COLS,
        "interval": INTERVAL, "trained_at": datetime.now().isoformat(),
    }
    path = f"{MODEL_DIR}/ensemble_models.pkl"
    joblib.dump(models, path)
    fi.to_csv(f"{MODEL_DIR}/feature_importance.csv", index=False)
    mdf.to_csv(f"{MODEL_DIR}/walkforward_metrics.csv", index=False)
    print(f"\n  บันทึกโมเดล → {path}")
    return models


# ════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Predict
# ════════════════════════════════════════════════════════════════════════════

def predict(models: dict, df_raw: pd.DataFrame,
            conf_threshold: float = 0.55):
    """
    conf_threshold: ต่ำกว่านี้ → WAIT เสมอ (ป้องกัน overconfident WAIT)
    """
    feat_cols = models.get("feature_cols", FEATURE_COLS)
    df_feat   = compute_features(df_raw, is_training=False)

    if df_feat.empty or len(df_feat) < 10:
        raise ValueError("ข้อมูลไม่พอสำหรับ feature computation")

    last = df_feat[feat_cols].iloc[[-1]]
    X    = models["scaler"].transform(last.values)

    p_lgbm = models["lgbm"].predict_proba(X)[0]
    p_xgb  = models["xgb"].predict_proba(X)[0]
    avg    = (p_lgbm + p_xgb) / 2   # [SELL, WAIT, BUY]

    pred_idx   = int(np.argmax(avg))
    confidence = float(avg[pred_idx])

    # margin = BUY/SELL ที่แรงสุด เทียบกับ WAIT
    buy_sell_margin = max(avg[0], avg[2]) - avg[1]

    if pred_idx == 1:
        # โมเดลเลือก WAIT — ถ้า BUY/SELL โอกาสสูงพอก็ให้ผ่าน
        best_action_prob = max(avg[0], avg[2])
        if best_action_prob >= conf_threshold:
            signal = "SELL" if avg[0] > avg[2] else "BUY"
        else:
            signal = "WAIT"
    else:
        # โมเดลเลือก BUY/SELL โดยตรง
        signal = "WAIT" if confidence < conf_threshold else {0: "SELL", 2: "BUY"}[pred_idx]

    row   = df_feat.iloc[-1]
    close = float(df_raw["close"].iloc[-1])
    atr   = float(row.get("atr_14", 0))

    context = {
        "close":      close,
        "atr_14":     atr,
        "sl": round(close - atr*ATR_SL_MULT, 2) if signal=="BUY"  else
              round(close + atr*ATR_SL_MULT, 2) if signal=="SELL" else None,
        "tp": round(close + atr*ATR_SL_MULT*RR_RATIO, 2) if signal=="BUY"  else
              round(close - atr*ATR_SL_MULT*RR_RATIO, 2) if signal=="SELL" else None,
        "rsi_14":     float(row.get("rsi_14", 50)),
        "adx_14":     float(row.get("adx_14", 0)),
        "trend_regime": int(row.get("trend_regime", 0)),
        "ema_alignment": int(row.get("ema_alignment", 0)),
        "bull_div":   int(row.get("bull_div", 0)),
        "bear_div":   int(row.get("bear_div", 0)),
        "near_support":    int(row.get("near_support", 0)),
        "near_resistance": int(row.get("near_resistance", 0)),
        "vol_ratio":  float(row.get("vol_ratio", 1.0)),
        "high_vol":   int(row.get("high_vol", 0)),
        "london_session":  int(row.get("london_session", 0)),
        "ny_session":      int(row.get("ny_session", 0)),
        "overlap_session": int(row.get("overlap_session", 0)),
        "margin":     round(float(buy_sell_margin), 4),
    }
    return signal, confidence, {"SELL":float(avg[0]),"WAIT":float(avg[1]),"BUY":float(avg[2])}, context


def quick_test(models: dict):
    print("\n[4/4] Quick test (ดึงราคาจริงล่าสุด)...")
    params = dict(symbol=SYMBOL, interval=INTERVAL, outputsize=350,
                  order="ASC", apikey=API_KEY, format="JSON")
    r  = requests.get("https://api.twelvedata.com/time_series", params=params, timeout=15)
    df = pd.DataFrame(r.json()["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["open","high","low","close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = 0

    signal, conf, proba, ctx = predict(models, df)
    regime = {1:"Uptrend", -1:"Downtrend", 0:"Sideways"}.get(ctx["trend_regime"], "?")

    print(f"\n{'='*48}")
    print(f"  XAU/USD {INTERVAL} — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'─'*48}")
    print(f"  สัญญาณ      : {signal}")
    print(f"  Confidence  : {conf*100:.1f}%  (margin={ctx['margin']:.3f})")
    print(f"  BUY {proba['BUY']*100:.1f}% / WAIT {proba['WAIT']*100:.1f}% / SELL {proba['SELL']*100:.1f}%")
    print(f"{'─'*48}")
    print(f"  ราคา        : ${ctx['close']:,.2f}")
    if ctx['sl']:
        print(f"  Stop Loss   : ${ctx['sl']:,.2f}")
        print(f"  Take Profit : ${ctx['tp']:,.2f}")
    print(f"{'─'*48}")
    print(f"  Trend       : {regime}  (EMA align {ctx['ema_alignment']}/4)")
    print(f"  ADX         : {ctx['adx_14']:.1f}  {'Trending' if ctx['adx_14']>25 else 'Ranging'}")
    print(f"  RSI 14      : {ctx['rsi_14']:.1f}")
    print(f"  Volatility  : {'HIGH ⚠️' if ctx['high_vol'] else 'Normal'}")
    print(f"  Session     : {'London' if ctx['london_session'] else ''}{'Overlap' if ctx['overlap_session'] else ''}{'NY' if ctx['ny_session'] else ''}")
    print(f"{'='*48}")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if API_KEY == "YOUR_KEY_HERE":
        raise SystemExit("ใส่ TWELVE_DATA_API_KEY ใน .env ก่อน")

    # ── ดึงข้อมูล ─────────────────────────────────────────────────────────────
    csv_files = sorted(glob.glob(f"{DATA_DIR}/gold_xauusd_{INTERVAL}_*.csv"))
    if csv_files:
        print(f"[1/4] ใช้ข้อมูลที่มีอยู่: {csv_files[-1]}")
        raw = pd.read_csv(csv_files[-1], parse_dates=["datetime"])
    else:
        raw = fetch_ohlcv()
        out = f"{DATA_DIR}/gold_xauusd_{INTERVAL}_{datetime.today().strftime('%Y%m%d')}.csv"
        raw.to_csv(out, index=False)
        print(f"  บันทึก → {out}")

    # ── Feature Engineering ───────────────────────────────────────────────────
    print("\n[2/4] Feature Engineering...")
    df = compute_features(raw, is_training=True)
    print(f"  {len(df)} rows × {len(df.columns)} columns")

    # ── Train ─────────────────────────────────────────────────────────────────
    models = train_model(df, n_trials=50)

    # ── Test ──────────────────────────────────────────────────────────────────
    quick_test(models)

    print("\n✅  เสร็จ — โมเดลอยู่ที่ models/ensemble_models.pkl")
    print("   โหลดใช้งาน: joblib.load('models/ensemble_models.pkl')")