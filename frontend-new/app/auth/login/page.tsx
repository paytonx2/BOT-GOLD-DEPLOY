"use client"
import React, { useState } from "react"
import Link from "next/link"
import { ArrowLeft, Mail, Lock, Eye, EyeOff, Loader2 } from "lucide-react"

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);

    // ดึงข้อมูลจาก Form
    const formData = new FormData(e.currentTarget);
    const name = formData.get("name");
    const email = formData.get("email");
    const password = formData.get("password");

    try {
        const response = await fetch("http://localhost:8000/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            email: email,
            password: password,
            name: name,
        }),
        });

        const data = await response.json();

        if (response.ok) {
        // สมัครเสร็จ เก็บ Token และแสดงหน้า Success
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("role", data.role);
        setIsSuccess(true);
        } else {
        // จัดการ Error เช่น "Email already exists"
        alert(data.detail || "เกิดข้อผิดพลาดในการสมัครสมาชิก");
        }
    } catch (error) {
        alert("ไม่สามารถติดต่อ Server ได้ โปรดตรวจสอบว่า Backend รันอยู่");
    } finally {
        setIsLoading(false);
    }
    };

  return (
    <div className="login-container">
      {/* Background Decor */}
      <div className="bg-glow" />
      
      <div className="auth-card">
        {/* Back to Home */}
        <Link href="/" className="back-link">
          <ArrowLeft size={16} />
          กลับหน้าหลัก
        </Link>

        <div className="auth-header">
          <div className="logo-box">AU</div>
          <h1>ยินดีต้อนรับกลับมา</h1>
          <p>เข้าสู่ระบบเพื่อดูสัญญาณ AI ล่าสุด</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="input-group">
            <label>อีเมล</label>
            <div className="input-wrapper">
              <Mail className="input-icon" size={18} />
              <input 
                type="email" 
                placeholder="email@example.com" 
                required 
              />
            </div>
          </div>

          <div className="input-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label>รหัสผ่าน</label>
              <Link href="/auth/forgot" className="forgot-link">ลืมรหัสผ่าน?</Link>
            </div>
            <div className="input-wrapper">
              <Lock className="input-icon" size={18} />
              <input 
                type={showPassword ? "text" : "password"} 
                placeholder="••••••••" 
                required 
              />
              <button 
                type="button" 
                className="toggle-password"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button type="submit" className="submit-btn" disabled={isLoading}>
            {isLoading ? <Loader2 className="spinner" size={20} /> : "เข้าสู่ระบบ"}
          </button>
        </form>

        <div className="auth-footer">
          ยังไม่มีบัญชี? <Link href="/auth/register">สมัครสมาชิกฟรี</Link>
        </div>
      </div>

      <style jsx>{`
        .login-container {
          min-height: 100vh;
          background: #0a0a0a;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
          font-family: 'DM Sans', sans-serif;
          position: relative;
          overflow: hidden;
        }

        .bg-glow {
          position: absolute;
          width: 400px;
          height: 400px;
          background: radial-gradient(circle, rgba(201, 168, 76, 0.15) 0%, transparent 70%);
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          pointer-events: none;
        }

        .auth-card {
          width: 100%;
          max-width: 420px;
          background: rgba(15, 14, 10, 0.8);
          border: 1px solid #2a2410;
          border-radius: 24px;
          padding: 40px;
          backdrop-filter: blur(20px);
          position: relative;
          z-index: 1;
          box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }

        .back-link {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #5a5240;
          text-decoration: none;
          font-size: 14px;
          margin-bottom: 32px;
          transition: color 0.2s;
        }
        .back-link:hover { color: #c9a84c; }

        .auth-header { text-align: center; margin-bottom: 32px; }
        
        .logo-box {
          width: 48px;
          height: 48px;
          background: linear-gradient(135deg,#c9a84c,#e8c84a);
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 16px;
          font-weight: 800;
          color: #0a0a0a;
          font-size: 18px;
        }

        h1 {
          font-family: 'DM Serif Display', serif;
          font-size: 28px;
          color: #e8e0cc;
          margin-bottom: 8px;
        }

        p { color: #6a6050; font-size: 15px; }

        .auth-form { display: flex; flex-direction: column; gap: 20px; }

        .input-group { display: flex; flex-direction: column; gap: 8px; }
        .input-group label { font-size: 14px; color: #8a8070; }

        .input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }

        .input-icon {
          position: absolute;
          left: 14px;
          color: #3a3520;
        }

        input {
          width: 100%;
          background: #0f0e0a;
          border: 1px solid #2a2410;
          border-radius: 10px;
          padding: 12px 14px 12px 42px;
          color: #e8e0cc;
          font-size: 15px;
          transition: all 0.2s;
        }

        input:focus {
          outline: none;
          border-color: #c9a84c;
          background: #15140f;
          box-shadow: 0 0 0 4px rgba(201, 168, 76, 0.1);
        }

        .toggle-password {
          position: absolute;
          right: 12px;
          background: none;
          border: none;
          color: #3a3520;
          cursor: pointer;
        }
        .toggle-password:hover { color: #8a7040; }

        .forgot-link { font-size: 12px; color: #8a7040; text-decoration: none; }
        .forgot-link:hover { color: #c9a84c; }

        .submit-btn {
          margin-top: 10px;
          padding: 14px;
          background: linear-gradient(135deg,#c9a84c,#e8c84a);
          border: none;
          border-radius: 10px;
          color: #0a0a0a;
          font-weight: 700;
          font-size: 16px;
          cursor: pointer;
          transition: transform 0.1s, opacity 0.2s;
          display: flex;
          justify-content: center;
          align-items: center;
        }

        .submit-btn:hover { opacity: 0.9; transform: translateY(-1px); }
        .submit-btn:active { transform: translateY(0); }
        .submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }

        .auth-footer {
          margin-top: 24px;
          text-align: center;
          font-size: 14px;
          color: #5a5240;
        }

        .auth-footer a {
          color: #c9a84c;
          text-decoration: none;
          font-weight: 600;
        }

        .spinner { animation: rotate 1s linear infinite; }
        @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        @media (max-width: 480px) {
          .auth-card { padding: 32px 24px; border: none; background: transparent; box-shadow: none; }
          .bg-glow { width: 300px; height: 300px; }
        }
      `}</style>
    </div>
  )
}