"use client"
import React, { useState } from "react"
import Link from "next/link"
import { ArrowLeft, Mail, Lock, User, Phone, ShieldCheck, Loader2, CheckCircle2 } from "lucide-react"

export default function RegisterPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    // สมมติว่าส่ง API ไปสมัครสมาชิก
    setTimeout(() => {
      setIsLoading(false)
      setIsSuccess(true)
    }, 2000)
  }

  if (isSuccess) {
    return (
      <div className="register-container">
        <div className="auth-card success-card">
          <CheckCircle2 size={64} color="#4ade80" style={{ marginBottom: 20 }} />
          <h1>สร้างบัญชีสำเร็จ!</h1>
          <p>ระบบเตรียม AI วิเคราะห์ทองให้คุณแล้ว</p>
          <Link href="/dashboard" className="submit-btn" style={{ textDecoration: 'none', marginTop: 24 }}>
            ไปที่ Dashboard ของฉัน
          </Link>
        </div>
        <style jsx>{`
            .register-container { min-height: 100vh; background: #0a0a0a; display: flex; align-items: center; justify-content: center; font-family: 'DM Sans', sans-serif; }
            .auth-card { width: 100%; max-width: 420px; background: rgba(15, 14, 10, 0.8); border: 1px solid #2a2410; border-radius: 24px; padding: 40px; text-align: center; backdrop-filter: blur(20px); }
            h1 { font-family: 'DM Serif Display', serif; color: #e8e0cc; margin-bottom: 12px; }
            p { color: #8a8070; }
            .submit-btn { padding: 14px; background: linear-gradient(135deg,#c9a84c,#e8c84a); border: none; border-radius: 10px; color: #0a0a0a; font-weight: 700; display: block; }
        `}</style>
      </div>
    )
  }

  return (
    <div className="register-container">
      <div className="bg-glow" />
      
      <div className="auth-card">
        <Link href="/" className="back-link">
          <ArrowLeft size={16} /> กลับหน้าหลัก
        </Link>

        <div className="auth-header">
          <div className="badge">FREE 7-DAY TRIAL</div>
          <h1>เริ่มเทรดด้วย AI</h1>
          <p>สมัครสมาชิกเพื่อรับสัญญาณ XAU/USD แม่นยำสูง</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="input-row">
            <div className="input-group">
              <label>ชื่อผู้ใช้งาน</label>
              <div className="input-wrapper">
                <User className="input-icon" size={16} />
                <input type="text" placeholder="Trader Name" required />
              </div>
            </div>
          </div>

          <div className="input-group">
            <label>อีเมลสำหรับเข้าใช้งาน</label>
            <div className="input-wrapper">
              <Mail className="input-icon" size={16} />
              <input type="email" placeholder="name@company.com" required />
            </div>
          </div>

          <div className="input-group">
            <label>เบอร์โทรศัพท์ (สำหรับรับ Alert)</label>
            <div className="input-wrapper">
              <Phone className="input-icon" size={16} />
              <input type="tel" placeholder="08x-xxx-xxxx" required />
            </div>
          </div>

          <div className="input-group">
            <label>กำหนดรหัสผ่าน</label>
            <div className="input-wrapper">
              <Lock className="input-icon" size={16} />
              <input type="password" placeholder="••••••••" required />
            </div>
          </div>

          <div className="terms-check">
            <input type="checkbox" id="terms" required />
            <label htmlFor="terms">ฉันยอมรับ <Link href="/terms">เงื่อนไขการใช้งาน</Link> และเข้าใจความเสี่ยงในการลงทุน</label>
          </div>

          <button type="submit" className="submit-btn" disabled={isLoading}>
            {isLoading ? <Loader2 className="spinner" size={20} /> : "สร้างบัญชีผู้ใช้"}
          </button>
        </form>

        <div className="auth-footer">
          มีบัญชีอยู่แล้ว? <Link href="/auth/login">เข้าสู่ระบบที่นี่</Link>
        </div>
      </div>

      <style jsx>{`
        .register-container {
          min-height: 100vh;
          background: #0a0a0a;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px 20px;
          font-family: 'DM Sans', sans-serif;
          position: relative;
          overflow-y: auto;
        }

        .bg-glow {
          position: absolute;
          width: 500px;
          height: 500px;
          background: radial-gradient(circle, rgba(201, 168, 76, 0.12) 0%, transparent 70%);
          top: -100px;
          right: -100px;
          pointer-events: none;
        }

        .auth-card {
          width: 100%;
          max-width: 480px;
          background: rgba(15, 14, 10, 0.85);
          border: 1px solid #2a2410;
          border-radius: 28px;
          padding: 48px;
          backdrop-filter: blur(20px);
          z-index: 1;
        }

        .badge {
          display: inline-block;
          padding: 4px 12px;
          background: rgba(201, 168, 76, 0.1);
          border: 1px solid #c9a84c;
          color: #c9a84c;
          border-radius: 100px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1px;
          margin-bottom: 16px;
        }

        .back-link {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #5a5240;
          text-decoration: none;
          font-size: 13px;
          margin-bottom: 24px;
        }

        .auth-header { margin-bottom: 32px; }
        h1 { font-family: 'DM Serif Display', serif; font-size: 32px; color: #e8e0cc; margin-bottom: 8px; }
        p { color: #6a6050; font-size: 15px; }

        .auth-form { display: flex; flex-direction: column; gap: 18px; }
        .input-group { display: flex; flex-direction: column; gap: 6px; }
        .input-group label { font-size: 13px; color: #8a8070; font-weight: 500; }

        .input-wrapper { position: relative; display: flex; align-items: center; }
        .input-icon { position: absolute; left: 14px; color: #3a3520; }

        input[type="text"], input[type="email"], input[type="tel"], input[type="password"] {
          width: 100%;
          background: #0d0c08;
          border: 1px solid #1e1c17;
          border-radius: 12px;
          padding: 12px 14px 12px 42px;
          color: #e8e0cc;
          font-size: 14px;
          transition: all 0.2s;
        }

        input:focus { outline: none; border-color: #c9a84c; box-shadow: 0 0 0 4px rgba(201, 168, 76, 0.05); }

        .terms-check { display: flex; gap: 10px; align-items: flex-start; margin: 8px 0; }
        .terms-check input { margin-top: 3px; accent-color: #c9a84c; }
        .terms-check label { font-size: 12px; color: #5a5240; line-height: 1.5; }
        .terms-check a { color: #c9a84c; text-decoration: none; }

        .submit-btn {
          padding: 16px;
          background: linear-gradient(135deg,#c9a84c,#e8c84a);
          border: none;
          border-radius: 12px;
          color: #0a0a0a;
          font-weight: 700;
          font-size: 16px;
          cursor: pointer;
          display: flex;
          justify-content: center;
          transition: transform 0.2s;
        }

        .submit-btn:hover { transform: translateY(-2px); opacity: 0.95; }
        .submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .auth-footer { margin-top: 24px; text-align: center; font-size: 14px; color: #5a5240; }
        .auth-footer a { color: #c9a84c; text-decoration: none; font-weight: 600; }

        .spinner { animation: rotate 1s linear infinite; }
        @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        @media (max-width: 480px) {
          .auth-card { padding: 30px 20px; border: none; }
        }
      `}</style>
    </div>
  )
}