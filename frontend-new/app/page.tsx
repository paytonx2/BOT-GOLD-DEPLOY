/* app/page.tsx  — Landing Page  (Dark Gold Theme)
   ต้องการ: npm install framer-motion lucide-react
   Font: เพิ่มใน app/layout.tsx
     import { DM_Serif_Display, DM_Sans } from "next/font/google"
*/

"use client"
import { useEffect, useRef, useState } from "react"
import Link from "next/link"

/* ─── Ticker data (replace with real WebSocket later) ─── */
const TICKER_ITEMS = [
  { label: "XAU/USD", value: "4,372.24", change: "+0.84%", up: true },
  { label: "XAG/USD", value: "32.41",    change: "+0.31%", up: true },
  { label: "DXY",     value: "103.82",   change: "-0.12%", up: false },
  { label: "US10Y",   value: "4.21%",    change: "-0.03%", up: false },
  { label: "VIX",     value: "18.44",    change: "+2.10%", up: false },
]

/* ─── Stats ─── */
const STATS = [
  { label: "Win Rate",     value: "73.4%",  sub: "จาก 2,840 signal" },
  { label: "Avg R:R",      value: "1 : 2.1",sub: "ต่อ signal" },
  { label: "Max Drawdown", value: "−4.2%",  sub: "ย้อนหลัง 12 เดือน" },
  { label: "Sharpe Ratio", value: "2.34",   sub: "annualized" },
]

/* ─── How it works ─── */
const HOW = [
  { n:"01", title:"ดึงราคาทุกชั่วโมง",  body:"ระบบดึง OHLCV ทุกแท่งเทียน 1h จาก Twelve Data แบบ Real-time" },
  { n:"02", title:"AI วิเคราะห์ 48 Feature", body:"LightGBM + XGBoost ประมวล Trend, S/R, Momentum ใน <100ms" },
  { n:"03", title:"ส่ง Signal พร้อม SL/TP", body:"เมื่อ Confidence ≥ 65% ระบบ push แจ้งเตือนที่ Dashboard ทันที" },
]

export default function LandingPage() {
  const [price, setPrice]     = useState("4,372.24")
  const [tick,  setTick]      = useState(true)
  const tickerRef             = useRef<HTMLDivElement>(null)

  /* simulate price tick */
  useEffect(() => {
    const id = setInterval(() => {
      const delta = (Math.random() - 0.48) * 1.2
      setPrice(p => (parseFloat(p.replace(",","")) + delta).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}))
      setTick(t => !t)
    }, 2800)
    return () => clearInterval(id)
  }, [])

  return (
    <div style={{background:"#0a0a0a",color:"#e8e0cc",minHeight:"100vh",fontFamily:"'DM Sans',sans-serif",overflowX:"hidden"}}>

      {/* ══ NAV ══ */}
      <nav style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"20px 48px",borderBottom:"1px solid #1e1c17",position:"sticky",top:0,background:"rgba(10,10,10,0.92)",backdropFilter:"blur(12px)",zIndex:100}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div style={{width:32,height:32,background:"linear-gradient(135deg,#c9a84c,#e8c84a)",borderRadius:6,display:"flex",alignItems:"center",justifyContent:"center",fontWeight:700,color:"#0a0a0a",fontSize:14}}>AU</div>
          <span style={{fontFamily:"'DM Serif Display',serif",fontSize:20,color:"#c9a84c",letterSpacing:1}}>AuSignal</span>
        </div>
        <div style={{display:"flex",gap:32,fontSize:14,color:"#8a8070"}}>
          <Link href="#how" style={{color:"inherit",textDecoration:"none"}}>วิธีทำงาน</Link>
          <Link href="#stats" style={{color:"inherit",textDecoration:"none"}}>ผลงาน</Link>
          <Link href="/about" style={{color:"inherit",textDecoration:"none"}}>เกี่ยวกับ</Link>
          <Link href="/disclaimer" style={{color:"inherit",textDecoration:"none"}}>ข้อตกลง</Link>
        </div>
        <div style={{display:"flex",gap:12}}>
          <Link href="/auth/login" style={{padding:"8px 20px",borderRadius:6,border:"1px solid #3a3520",color:"#c9a84c",textDecoration:"none",fontSize:14}}>เข้าสู่ระบบ</Link>
          <Link href="/auth/register" style={{padding:"8px 20px",borderRadius:6,background:"linear-gradient(135deg,#c9a84c,#e8c84a)",color:"#0a0a0a",textDecoration:"none",fontSize:14,fontWeight:600}}>ทดลองใช้ฟรี</Link>
        </div>
      </nav>

      {/* ══ TICKER ══ */}
      <div style={{background:"#111009",borderBottom:"1px solid #1e1c17",padding:"10px 0",overflow:"hidden"}}>
        <div style={{display:"flex",gap:48,animation:"ticker 30s linear infinite",whiteSpace:"nowrap"}}>
          {[...TICKER_ITEMS,...TICKER_ITEMS,...TICKER_ITEMS].map((t,i) => (
            <span key={i} style={{display:"inline-flex",alignItems:"center",gap:8,fontSize:13}}>
              <span style={{color:"#5a5240"}}>{t.label}</span>
              <span style={{color:"#e8e0cc",fontVariantNumeric:"tabular-nums"}}>{t.label==="XAU/USD"?price:t.value}</span>
              <span style={{color: t.up?"#4ade80":"#f87171",fontSize:12}}>{t.change}</span>
            </span>
          ))}
        </div>
      </div>

      {/* ══ HERO ══ */}
      <section style={{minHeight:"88vh",display:"flex",alignItems:"center",justifyContent:"center",padding:"80px 48px",position:"relative",textAlign:"center"}}>
        {/* bg grid */}
        <div style={{position:"absolute",inset:0,backgroundImage:"radial-gradient(circle at 50% 40%, rgba(201,168,76,0.06) 0%, transparent 65%)",pointerEvents:"none"}}/>
        <div style={{position:"absolute",inset:0,backgroundImage:"linear-gradient(rgba(201,168,76,0.04) 1px,transparent 1px),linear-gradient(90deg,rgba(201,168,76,0.04) 1px,transparent 1px)",backgroundSize:"48px 48px",pointerEvents:"none"}}/>

        <div style={{maxWidth:760,position:"relative"}}>
          <div style={{display:"inline-flex",alignItems:"center",gap:8,padding:"6px 16px",border:"1px solid #2a2410",borderRadius:20,fontSize:13,color:"#8a7040",marginBottom:32}}>
            <span style={{width:7,height:7,borderRadius:"50%",background:"#4ade80",display:"inline-block",animation:"pulse 1.8s ease-in-out infinite"}}/>
            AI กำลังวิเคราะห์ตลาดอยู่ตอนนี้
          </div>

          <h1 style={{fontFamily:"'DM Serif Display',serif",fontSize:"clamp(42px,6vw,80px)",lineHeight:1.1,marginBottom:24,letterSpacing:-1}}>
            <span style={{color:"#e8e0cc"}}>สัญญาณเทรดทอง</span><br/>
            <span style={{background:"linear-gradient(135deg,#c9a84c 20%,#f0d878 60%,#c9a84c 100%)",WebkitBackgroundClip:"text",WebkitTextFillColor:"transparent"}}>แม่นยำด้วย AI</span>
          </h1>

          <p style={{fontSize:18,color:"#6a6050",lineHeight:1.8,marginBottom:40,maxWidth:580,margin:"0 auto 40px"}}>
            ระบบวิเคราะห์ XAU/USD ด้วย Machine Learning ทุก 1 ชั่วโมง<br/>
            พร้อม Entry · Stop Loss · Take Profit ส่งตรงถึง Dashboard ของคุณ
          </p>

          {/* live price card */}
          <div style={{display:"inline-flex",alignItems:"center",gap:24,padding:"20px 36px",background:"#0f0e0a",border:"1px solid #2a2410",borderRadius:12,marginBottom:48}}>
            <div style={{textAlign:"left"}}>
              <div style={{fontSize:12,color:"#5a5240",marginBottom:4}}>XAU/USD Live</div>
              <div style={{fontFamily:"'DM Serif Display',serif",fontSize:32,color: tick?"#c9a84c":"#e8c84a",transition:"color 0.3s"}}>${price}</div>
            </div>
            <div style={{width:1,height:48,background:"#1e1c17"}}/>
            <div style={{textAlign:"left"}}>
              <div style={{fontSize:12,color:"#5a5240",marginBottom:4}}>AI สัญญาณล่าสุด</div>
              <div style={{display:"flex",alignItems:"center",gap:8}}>
                <span style={{padding:"4px 14px",background:"rgba(74,222,128,0.1)",border:"1px solid rgba(74,222,128,0.3)",borderRadius:6,color:"#4ade80",fontSize:14,fontWeight:600}}>BUY</span>
                <span style={{fontSize:13,color:"#8a7040"}}>Confidence 87%</span>
              </div>
            </div>
          </div>

          <div style={{display:"flex",gap:16,justifyContent:"center",flexWrap:"wrap"}}>
            <Link href="/auth/register" style={{padding:"14px 36px",background:"linear-gradient(135deg,#c9a84c,#e8c84a)",color:"#0a0a0a",borderRadius:8,textDecoration:"none",fontWeight:700,fontSize:16}}>เริ่มใช้งานฟรี</Link>
            <Link href="#how" style={{padding:"14px 36px",border:"1px solid #2a2410",color:"#8a7040",borderRadius:8,textDecoration:"none",fontSize:16}}>ดูวิธีทำงาน ↓</Link>
          </div>
        </div>
      </section>

      {/* ══ STATS ══ */}
      <section id="stats" style={{padding:"80px 48px",borderTop:"1px solid #1a1810"}}>
        <div style={{maxWidth:1100,margin:"0 auto"}}>
          <div style={{textAlign:"center",marginBottom:56}}>
            <h2 style={{fontFamily:"'DM Serif Display',serif",fontSize:40,color:"#e8e0cc",marginBottom:12}}>ผลการทำงานจริง</h2>
            <p style={{color:"#5a5240",fontSize:15}}>วัดจาก Backtest 3 ปีย้อนหลัง · Walk-Forward Validated</p>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:24}}>
            {STATS.map((s,i) => (
              <div key={i} style={{padding:"32px 28px",background:"#0f0e0a",border:"1px solid #1e1c17",borderRadius:12,textAlign:"center",transition:"border-color 0.2s",cursor:"default"}}
                onMouseEnter={e=>(e.currentTarget.style.borderColor="#3a3020")}
                onMouseLeave={e=>(e.currentTarget.style.borderColor="#1e1c17")}>
                <div style={{fontFamily:"'DM Serif Display',serif",fontSize:38,color:"#c9a84c",marginBottom:8}}>{s.value}</div>
                <div style={{fontSize:15,color:"#e8e0cc",marginBottom:4,fontWeight:500}}>{s.label}</div>
                <div style={{fontSize:12,color:"#5a5240"}}>{s.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ HOW IT WORKS ══ */}
      <section id="how" style={{padding:"80px 48px",background:"#080807"}}>
        <div style={{maxWidth:900,margin:"0 auto"}}>
          <div style={{textAlign:"center",marginBottom:56}}>
            <h2 style={{fontFamily:"'DM Serif Display',serif",fontSize:40,color:"#e8e0cc",marginBottom:12}}>ทำงานอย่างไร</h2>
          </div>
          <div style={{display:"flex",flexDirection:"column",gap:0}}>
            {HOW.map((h,i) => (
              <div key={i} style={{display:"flex",gap:32,padding:"40px 0",borderBottom: i<HOW.length-1?"1px solid #1a1810":"none",alignItems:"flex-start"}}>
                <div style={{fontFamily:"'DM Serif Display',serif",fontSize:48,color:"#2a2410",lineHeight:1,minWidth:64}}>{h.n}</div>
                <div>
                  <div style={{fontSize:20,color:"#c9a84c",fontWeight:600,marginBottom:10}}>{h.title}</div>
                  <div style={{fontSize:15,color:"#6a6050",lineHeight:1.8}}>{h.body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ CTA ══ */}
      <section style={{padding:"100px 48px",textAlign:"center",background:"#0a0a0a",borderTop:"1px solid #1a1810"}}>
        <h2 style={{fontFamily:"'DM Serif Display',serif",fontSize:"clamp(32px,4vw,56px)",color:"#e8e0cc",marginBottom:16}}>
          พร้อมรับสัญญาณทอง<br/>
          <span style={{color:"#c9a84c"}}>จาก AI แล้วหรือยัง?</span>
        </h2>
        <p style={{color:"#5a5240",marginBottom:40,fontSize:16}}>ทดลองใช้ฟรี 7 วัน ไม่ต้องใส่บัตรเครดิต</p>
        <Link href="/auth/register" style={{padding:"16px 48px",background:"linear-gradient(135deg,#c9a84c,#e8c84a)",color:"#0a0a0a",borderRadius:8,textDecoration:"none",fontWeight:700,fontSize:18,display:"inline-block"}}>เริ่มต้นใช้งานฟรี</Link>
      </section>

      {/* ══ FOOTER ══ */}
      <footer style={{padding:"32px 48px",borderTop:"1px solid #1a1810",display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:16}}>
        <span style={{fontFamily:"'DM Serif Display',serif",color:"#c9a84c",fontSize:18}}>AuSignal</span>
        <div style={{display:"flex",gap:24,fontSize:13,color:"#3a3020"}}>
          <Link href="/disclaimer" style={{color:"inherit",textDecoration:"none"}}>Risk Disclaimer</Link>
          <Link href="/about" style={{color:"inherit",textDecoration:"none"}}>About</Link>
          <Link href="/auth/login" style={{color:"inherit",textDecoration:"none"}}>Login</Link>
        </div>
        <span style={{fontSize:12,color:"#2a2010"}}>© 2026 AuSignal · ไม่ใช่คำแนะนำทางการเงิน</span>
      </footer>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&display=swap');
        @keyframes ticker { from{transform:translateX(0)} to{transform:translateX(-33.33%)} }
        @keyframes pulse  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(.85)} }
        *{box-sizing:border-box;margin:0;padding:0}
        html{scroll-behavior:smooth}
        ::-webkit-scrollbar{width:6px;background:#0a0a0a}
        ::-webkit-scrollbar-thumb{background:#2a2410;border-radius:3px}
      `}</style>
    </div>
  )
}
