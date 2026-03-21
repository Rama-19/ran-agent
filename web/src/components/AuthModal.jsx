import { useState, useEffect } from 'react'
import api from '../api'

// 阶段：login | register | verify | forgot | reset
export default function AuthModal({ onSuccess }) {
  const [phase, setPhase] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [code, setCode] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmNewPwd, setConfirmNewPwd] = useState('')
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState({ text: '', error: false })
  const [countdown, setCountdown] = useState(0)

  useEffect(() => {
    if (countdown <= 0) return
    const t = setTimeout(() => setCountdown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [countdown])

  const info = (text) => setMsg({ text, error: false })
  const err = (text) => setMsg({ text, error: true })
  const clear = () => setMsg({ text: '', error: false })
  const go = (p) => { setPhase(p); clear() }

  const onKey = (e, action) => { if (e.key === 'Enter') action() }
  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  // ── Login ──
  const handleLogin = async () => {
    if (!email || !password) return err('请填写邮箱和密码')
    setLoading(true); clear()
    try {
      const res = await api.login(email, password)
      localStorage.setItem('auth_token', res.access_token)
      onSuccess(res.access_token, res.user)
    } catch (e) { err(e.message) }
    finally { setLoading(false) }
  }

  // ── Register ──
  const handleRegister = async () => {
    if (!email || !password) return err('请填写邮箱和密码')
    if (password !== confirm) return err('两次密码不一致')
    if (password.length < 6) return err('密码至少 6 位')
    setLoading(true); clear()
    try {
      const res = await api.register(email, password)
      info(res.message)
      setCountdown(300)
      setPhase('verify')
    } catch (e) { err(e.message) }
    finally { setLoading(false) }
  }

  // ── Verify (registration) ──
  const handleVerify = async () => {
    if (!code) return err('请输入验证码')
    setLoading(true); clear()
    try {
      const res = await api.verifyCode(email, code)
      localStorage.setItem('auth_token', res.access_token)
      onSuccess(res.access_token, res.user)
    } catch (e) { err(e.message) }
    finally { setLoading(false) }
  }

  // ── Forgot password ──
  const handleForgot = async () => {
    if (!email) return err('请输入邮箱')
    setLoading(true); clear()
    try {
      const res = await api.forgotPassword(email)
      info(res.message)
      setCountdown(300)
      setCode(''); setNewPwd(''); setConfirmNewPwd('')
      setPhase('reset')
    } catch (e) { err(e.message) }
    finally { setLoading(false) }
  }

  // ── Reset password ──
  const handleReset = async () => {
    if (!code) return err('请输入验证码')
    if (!newPwd || newPwd.length < 6) return err('新密码至少 6 位')
    if (newPwd !== confirmNewPwd) return err('两次密码不一致')
    setLoading(true); clear()
    try {
      const res = await api.resetPassword(email, code, newPwd)
      info(res.message + ' 请登录')
      setTimeout(() => go('login'), 1500)
    } catch (e) { err(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <span style={styles.title}>✦ Ran Agent</span>
        </div>

        <div style={styles.body}>
          {/* Phase selector (login / register only) */}
          {(phase === 'login' || phase === 'register') && (
            <div style={styles.phaseTabs}>
              {[{ id: 'login', label: '登录' }, { id: 'register', label: '注册' }].map(p => (
                <button
                  key={p.id}
                  style={{ ...styles.phaseTab, ...(phase === p.id ? styles.phaseTabActive : {}) }}
                  onClick={() => go(p.id)}
                >{p.label}</button>
              ))}
            </div>
          )}

          {/* ── Login ── */}
          {phase === 'login' && <>
            <label style={styles.label}>邮箱</label>
            <input style={styles.input} type="email" placeholder="your@email.com"
              value={email} onChange={e => setEmail(e.target.value)}
              onKeyDown={e => onKey(e, handleLogin)} autoFocus />
            <label style={styles.label}>密码</label>
            <input style={styles.input} type="password" placeholder="输入密码"
              value={password} onChange={e => setPassword(e.target.value)}
              onKeyDown={e => onKey(e, handleLogin)} />
            {msg.text && <MsgLine msg={msg} />}
            <button style={styles.primaryBtn} onClick={handleLogin} disabled={loading}>
              {loading ? '登录中…' : '登录'}
            </button>
            <button style={styles.linkBtn} onClick={() => { setCode(''); clear(); go('forgot') }}>
              忘记密码？
            </button>
          </>}

          {/* ── Register ── */}
          {phase === 'register' && <>
            <label style={styles.label}>邮箱</label>
            <input style={styles.input} type="email" placeholder="your@email.com"
              value={email} onChange={e => setEmail(e.target.value)} autoFocus />
            <label style={styles.label}>密码</label>
            <input style={styles.input} type="password" placeholder="至少 6 位"
              value={password} onChange={e => setPassword(e.target.value)} />
            <label style={styles.label}>确认密码</label>
            <input style={styles.input} type="password" placeholder="再次输入密码"
              value={confirm} onChange={e => setConfirm(e.target.value)}
              onKeyDown={e => onKey(e, handleRegister)} />
            {msg.text && <MsgLine msg={msg} />}
            <button style={styles.primaryBtn} onClick={handleRegister} disabled={loading}>
              {loading ? '发送中…' : '发送验证码'}
            </button>
          </>}

          {/* ── Verify (registration) ── */}
          {phase === 'verify' && <>
            <div style={styles.hint}>
              验证码已发送至 <strong>{email}</strong>
              {countdown > 0 && <span style={styles.cd}> （{fmt(countdown)} 后过期）</span>}
            </div>
            <label style={styles.label}>6 位验证码</label>
            <input style={{ ...styles.input, ...styles.codeInput }}
              type="text" placeholder="000000" maxLength={6}
              value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
              onKeyDown={e => onKey(e, handleVerify)} autoFocus />
            {msg.text && <MsgLine msg={msg} />}
            <button style={styles.primaryBtn} onClick={handleVerify} disabled={loading}>
              {loading ? '验证中…' : '验证并登录'}
            </button>
            <button style={styles.ghostBtn} onClick={() => go('register')}>← 重新注册</button>
          </>}

          {/* ── Forgot password ── */}
          {phase === 'forgot' && <>
            <div style={styles.hint}>输入注册邮箱，我们将发送密码重置验证码。</div>
            <label style={styles.label}>邮箱</label>
            <input style={styles.input} type="email" placeholder="your@email.com"
              value={email} onChange={e => setEmail(e.target.value)}
              onKeyDown={e => onKey(e, handleForgot)} autoFocus />
            {msg.text && <MsgLine msg={msg} />}
            <button style={styles.primaryBtn} onClick={handleForgot} disabled={loading}>
              {loading ? '发送中…' : '发送重置验证码'}
            </button>
            <button style={styles.ghostBtn} onClick={() => go('login')}>← 返回登录</button>
          </>}

          {/* ── Reset password ── */}
          {phase === 'reset' && <>
            <div style={styles.hint}>
              重置码已发送至 <strong>{email}</strong>
              {countdown > 0 && <span style={styles.cd}> （{fmt(countdown)} 后过期）</span>}
            </div>
            <label style={styles.label}>6 位重置码</label>
            <input style={{ ...styles.input, ...styles.codeInput }}
              type="text" placeholder="000000" maxLength={6}
              value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
              autoFocus />
            <label style={styles.label}>新密码</label>
            <input style={styles.input} type="password" placeholder="至少 6 位"
              value={newPwd} onChange={e => setNewPwd(e.target.value)} />
            <label style={styles.label}>确认新密码</label>
            <input style={styles.input} type="password" placeholder="再次输入新密码"
              value={confirmNewPwd} onChange={e => setConfirmNewPwd(e.target.value)}
              onKeyDown={e => onKey(e, handleReset)} />
            {msg.text && <MsgLine msg={msg} />}
            <button style={styles.primaryBtn} onClick={handleReset} disabled={loading}>
              {loading ? '重置中…' : '重置密码'}
            </button>
            <button style={styles.ghostBtn} onClick={() => go('forgot')}>← 重新发送</button>
          </>}
        </div>
      </div>
    </div>
  )
}

function MsgLine({ msg }) {
  return (
    <div style={{ fontSize: 13, padding: '4px 0', color: msg.error ? 'var(--red)' : 'var(--green)' }}>
      {msg.text}
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,.85)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 200,
  },
  modal: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    width: 380, maxWidth: '95vw',
    boxShadow: '0 20px 60px rgba(0,0,0,.6)',
  },
  header: {
    padding: '20px 24px 16px',
    borderBottom: '1px solid var(--border)',
    textAlign: 'center',
  },
  title: { fontWeight: 700, fontSize: 18, color: 'var(--accent)' },
  body: { padding: '20px 24px 24px', display: 'flex', flexDirection: 'column', gap: 10 },
  phaseTabs: {
    display: 'flex', gap: 0, marginBottom: 4,
    borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)',
  },
  phaseTab: {
    flex: 1, background: 'transparent', border: 'none',
    color: 'var(--text-dim)', fontSize: 14, padding: '8px 0', cursor: 'pointer', fontWeight: 500,
  },
  phaseTabActive: { background: 'var(--accent-dim)', color: 'var(--text)', fontWeight: 700 },
  label: { color: 'var(--text-dim)', fontSize: 12, fontWeight: 600 },
  input: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 6, padding: '9px 12px',
    fontSize: 14, outline: 'none', width: '100%',
  },
  codeInput: { fontSize: 22, letterSpacing: 8, textAlign: 'center', fontFamily: 'monospace' },
  primaryBtn: {
    background: 'var(--accent)', color: '#fff', border: 'none',
    borderRadius: 6, padding: '10px 0', fontSize: 14, fontWeight: 600,
    cursor: 'pointer', marginTop: 4,
  },
  ghostBtn: {
    background: 'transparent', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 6, padding: '8px 0',
    fontSize: 13, cursor: 'pointer',
  },
  linkBtn: {
    background: 'transparent', border: 'none',
    color: 'var(--accent)', fontSize: 13, cursor: 'pointer',
    textAlign: 'right', padding: '0 2px',
  },
  hint: { color: 'var(--text-dim)', fontSize: 13, lineHeight: 1.6 },
  cd: { color: 'var(--accent)', fontWeight: 600 },
}
