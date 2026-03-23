"use client"
import { useEffect, useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { 
  TrendingUp, TrendingDown, Activity, Zap, 
  Bell, User, LogOut, RefreshCcw, Shield 
} from "lucide-react"

export default function Dashboard() {
  const [signal, setSignal] = useState<any>(null)
  const [status, setStatus] = useState("connecting") // connecting | online | offline
  const [history, setHistory] = useState([])
  const socketRef = useRef<WebSocket | null>(null)
  const router = useRouter()

  useEffect(() => {
    const token = localStorage.getItem("token")
    if (!token) {
      router.push("/auth/login")
      return
    }

    // 1. Connect WebSocket
    const connectWS = () => {
      // หมายเหตุ: ใน production เปลี่ยน localhost เป็น domain ของคุณ
      const ws = new WebSocket(`ws://localhost:8000/ws/signal?token=${token}`)
      socketRef.current = ws

      ws.onopen = () => setStatus("online")
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === "signal" || data.signal) {
          setSignal(data)
          // เพิ่มเข้าประวัติ (Mock history update)
          setHistory(prev => [data, ...prev].slice(0, 10) as any)
        }
      }

      ws.onclose = () => {
        setStatus("offline")
        // Reconnect auto ทุก 5 วินาที
        setTimeout(connectWS, 5000)
      }
    }

    connectWS()
    return () => socketRef.current?.close()
  }, [router])

  const handleLogout = () => {
    localStorage.removeItem("token")
    router.push("/auth/login")
  }

  return (
    <div className="dash-container">
      {/* --- Sidebar / Nav --- */}
      <aside className="sidebar">
        <div className="logo">AU<span>Signal</span></div>
        <nav>
          <div className="nav-item active"><Activity size={20}/> Dashboard</div>
          <div className="nav-item"><TrendingUp size={20}/> History</div>
          <div className="nav-item"><Shield size={20}/> AI Strategy</div>
        </nav>
        <button onClick={handleLogout} className="logout-btn">
          <LogOut size={18}/> ออกจากระบบ
        </button>
      </aside>

      {/* --- Main Content --- */}
      <main className="main-content">
        <header>
          <div className="status-bar">
            <span className={`dot ${status}`}></span>
            AI Server: {status.toUpperCase()}
          </div>
          <div className="user-profile">
            <Bell size={20} className="icon"/>
            <div className="avatar">VIP</div>
          </div>
        </header>

        <section className="hero-signal">
          {!signal ? (
            <div className="loading-state">
              <RefreshCcw className="spinner" />
              <p>กำลังรอสัญญาณล่าสุดจาก AI...</p>
            </div>
          ) : (
            <div className={`signal-card ${signal.signal}`}>
              <div className="card-header">
                <div className="pair">XAU/USD <span className="time">{signal.interval}</span></div>
                <div className="conf">Confidence: {signal.confidence}%</div>
              </div>
              
              <div className="main-signal">
                <div className="side">{signal.signal}</div>
                <div className="price">${signal.price?.toLocaleString()}</div>
              </div>

              <div className="targets">
                <div className="target-item">
                  <span className="label">ENTRY</span>
                  <span className="val">{signal.price}</span>
                </div>
                <div className="target-item sl">
                  <span className="label">STOP LOSS</span>
                  <span className="val">{signal.sl || "N/A"}</span>
                </div>
                <div className="target-item tp">
                  <span className="label">TAKE PROFIT</span>
                  <span className="val">{signal.tp || "N/A"}</span>
                </div>
              </div>

              <div className="ai-insight">
                <Zap size={16} /> AI Proba: 
                BUY {signal.proba_buy}% | SELL {signal.proba_sell}%
              </div>
            </div>
          )}
        </section>

        <section className="stats-grid">
           <div className="stat-box">
             <label>RSI (14)</label>
             <div className="val">{signal?.rsi_14?.toFixed(2) || "--"}</div>
           </div>
           <div className="stat-box">
             <label>ADX</label>
             <div className="val">{signal?.adx_14?.toFixed(2) || "--"}</div>
           </div>
           <div className="stat-box">
             <label>Trend</label>
             <div className="val">{signal?.trend_regime === 1 ? "Bullish" : "Bearish"}</div>
           </div>
        </section>
      </main>

      <style jsx>{`
        .dash-container { display: flex; min-height: 100vh; background: #050505; color: #e8e0cc; font-family: 'DM Sans', sans-serif; }
        
        /* Sidebar */
        .sidebar { width: 260px; border-right: 1px solid #1a1810; padding: 32px; display: flex; flex-direction: column; }
        .logo { font-family: 'DM Serif Display', serif; fontSize: 24px; color: #c9a84c; margin-bottom: 48px; }
        .logo span { color: #e8e0cc; }
        nav { flex: 1; }
        .nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 8px; cursor: pointer; color: #6a6050; margin-bottom: 8px; transition: 0.2s; }
        .nav-item.active { background: rgba(201, 168, 76, 0.1); color: #c9a84c; }
        .logout-btn { display: flex; align-items: center; gap: 8px; background: none; border: none; color: #5a5240; cursor: pointer; padding: 16px; }

        /* Main Content */
        .main-content { flex: 1; padding: 32px 48px; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; }
        .status-bar { font-size: 12px; display: flex; align-items: center; gap: 8px; color: #8a8070; }
        .dot { width: 8px; height: 8px; border-radius: 50%; }
        .dot.online { background: #4ade80; box-shadow: 0 0 10px #4ade80; }
        .dot.connecting { background: #facc15; }
        .dot.offline { background: #f87171; }
        .user-profile { display: flex; align-items: center; gap: 20px; }
        .avatar { width: 40px; height: 40px; background: #1a1810; border: 1px solid #c9a84c; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; color: #c9a84c; }

        /* Signal Card */
        .signal-card { background: #0f0e0a; border: 1px solid #2a2410; border-radius: 24px; padding: 40px; position: relative; overflow: hidden; }
        .signal-card.BUY { border-left: 8px solid #4ade80; }
        .signal-card.SELL { border-left: 8px solid #f87171; }
        
        .card-header { display: flex; justify-content: space-between; margin-bottom: 24px; color: #8a8070; font-size: 14px; }
        .main-signal { display: flex; align-items: baseline; gap: 24px; margin-bottom: 32px; }
        .side { font-family: 'DM Serif Display', serif; font-size: 72px; line-height: 1; }
        .BUY .side { color: #4ade80; }
        .SELL .side { color: #f87171; }
        .price { font-size: 48px; color: #e8e0cc; }

        .targets { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 32px; }
        .target-item { background: #0a0a0a; padding: 16px; border-radius: 12px; border: 1px solid #1a1810; display: flex; flex-direction: column; }
        .label { font-size: 11px; color: #5a5240; margin-bottom: 4px; }
        .val { font-size: 20px; font-weight: 700; color: #c9a84c; }
        .sl .val { color: #f87171; }
        .tp .val { color: #4ade80; }

        .ai-insight { font-size: 13px; color: #8a7040; background: rgba(201, 168, 76, 0.05); padding: 12px; border-radius: 8px; display: inline-flex; gap: 8px; }

        /* Stats Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 24px; }
        .stat-box { background: #0f0e0a; border: 1px solid #1a1810; padding: 20px; border-radius: 16px; }
        .stat-box label { font-size: 12px; color: #5a5240; }
        .stat-box .val { font-size: 24px; color: #e8e0cc; margin-top: 8px; }

        .spinner { animation: spin 2s linear infinite; color: #c9a84c; margin-bottom: 16px; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}