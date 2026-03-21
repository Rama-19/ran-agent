import { useState, useEffect } from 'react'
import api from '../api'

const PROVIDERS = [
  {
    id: 'openai', label: 'OpenAI',
    baseUrlPlaceholder: 'https://api.openai.com/v1',
    modelPlaceholder: 'gpt-4o', deepPlaceholder: 'o1',
  },
  {
    id: 'anthropic', label: 'Anthropic',
    baseUrlPlaceholder: 'https://api.anthropic.com',
    modelPlaceholder: 'claude-sonnet-4-6', deepPlaceholder: 'claude-opus-4-6',
  },
]

export default function SettingsModal({ onClose }) {
  const [cfg, setCfg] = useState({ name: 'openai', api_key: '', base_url: '', model: '', deep_model: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  // SMTP section
  const [smtpOpen, setSmtpOpen] = useState(false)
  const [smtp, setSmtp] = useState({ host: 'smtp.qq.com', port: 465, username: '', password: '', from_name: 'Agent' })
  const [smtpSaving, setSmtpSaving] = useState(false)
  const [smtpMsg, setSmtpMsg] = useState('')

  // Change password section
  const [pwdOpen, setPwdOpen] = useState(false)
  const [curPwd, setCurPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [pwdSaving, setPwdSaving] = useState(false)
  const [pwdMsg, setPwdMsg] = useState('')

  useEffect(() => {
    // Load user's own provider config
    api.getUserConfig().then(data => {
      const prov = data.provider || {}
      setCfg({
        name: prov.name || 'openai',
        api_key: '',
        base_url: prov.base_url || '',
        model: prov.model || '',
        deep_model: prov.deep_model || '',
      })
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const loadSmtp = async () => {
    try {
      const data = await api.getSmtpConfig()
      setSmtp({
        host: data.host || 'smtp.qq.com',
        port: data.port || 465,
        username: data.username || '',
        password: '',
        from_name: data.from_name || 'Agent',
      })
    } catch { /* ignore */ }
  }

  const toggleSmtp = () => {
    if (!smtpOpen) loadSmtp()
    setSmtpOpen(v => !v)
    setSmtpMsg('')
  }

  const togglePwd = () => {
    setPwdOpen(v => !v)
    setPwdMsg('')
    setCurPwd(''); setNewPwd(''); setConfirmPwd('')
  }

  const prov = PROVIDERS.find(p => p.id === cfg.name) || PROVIDERS[0]
  const set = (k, v) => setCfg(prev => ({ ...prev, [k]: v }))
  const setS = (k, v) => setSmtp(prev => ({ ...prev, [k]: v }))

  const switchProvider = async (name) => {
    try {
      const data = await api.getUserConfig()
      const p = data.provider || {}
      if (p.name === name) {
        setCfg({ name, api_key: '', base_url: p.base_url || '', model: p.model || '', deep_model: p.deep_model || '' })
      } else {
        setCfg({ name, api_key: '', base_url: '', model: '', deep_model: '' })
      }
    } catch {
      set('name', name)
    }
  }

  const save = async () => {
    setSaving(true); setMsg('')
    try {
      await api.updateUserConfig({
        name: cfg.name,
        api_key: cfg.api_key || undefined,
        base_url: cfg.base_url || undefined,
        model: cfg.model || undefined,
        deep_model: cfg.deep_model || undefined,
      })
      setMsg('✓ 已保存')
    } catch (e) { setMsg(`✗ ${e.message}`) }
    finally { setSaving(false) }
  }

  const saveSmtp = async () => {
    setSmtpSaving(true); setSmtpMsg('')
    try {
      await api.updateSmtpConfig({
        host: smtp.host || undefined,
        port: smtp.port ? Number(smtp.port) : undefined,
        username: smtp.username || undefined,
        password: smtp.password || undefined,
        from_name: smtp.from_name || undefined,
      })
      setSmtpMsg('✓ 已保存')
    } catch (e) { setSmtpMsg(`✗ ${e.message}`) }
    finally { setSmtpSaving(false) }
  }

  const savePassword = async () => {
    if (!curPwd || !newPwd) return setPwdMsg('✗ 请填写所有密码字段')
    if (newPwd.length < 6) return setPwdMsg('✗ 新密码至少 6 位')
    if (newPwd !== confirmPwd) return setPwdMsg('✗ 两次新密码不一致')
    setPwdSaving(true); setPwdMsg('')
    try {
      const res = await api.changePassword(curPwd, newPwd)
      setPwdMsg(`✓ ${res.message}`)
      setCurPwd(''); setNewPwd(''); setConfirmPwd('')
    } catch (e) { setPwdMsg(`✗ ${e.message}`) }
    finally { setPwdSaving(false) }
  }

  return (
    <div style={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <span style={styles.title}>⚙ 模型配置</span>
          <button style={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        {loading ? (
          <p style={styles.dim}>加载中…</p>
        ) : (
          <div style={styles.body}>
            {/* Provider 选择 */}
            <label style={styles.label}>Provider（个人配置）</label>
            <div style={styles.provRow}>
              {PROVIDERS.map(p => (
                <button key={p.id}
                  style={{ ...styles.provBtn, ...(cfg.name === p.id ? styles.provBtnActive : {}) }}
                  onClick={() => switchProvider(p.id)}
                >{p.label}</button>
              ))}
            </div>

            <label style={styles.label}>API Key</label>
            <input style={styles.input} type="password" placeholder="留空则使用系统配置"
              value={cfg.api_key} onChange={e => set('api_key', e.target.value)} />

            <label style={styles.label}>Base URL <span style={styles.opt}>(可选，代理或兼容接口)</span></label>
            <input style={styles.input} placeholder={prov.baseUrlPlaceholder}
              value={cfg.base_url} onChange={e => set('base_url', e.target.value)} />

            <label style={styles.label}>模型</label>
            <input style={styles.input} placeholder={prov.modelPlaceholder}
              value={cfg.model} onChange={e => set('model', e.target.value)} />

            <label style={styles.label}>深思模型 <span style={styles.opt}>(deep_think≥2)</span></label>
            <input style={styles.input} placeholder={prov.deepPlaceholder}
              value={cfg.deep_model} onChange={e => set('deep_model', e.target.value)} />

            <div style={styles.footer}>
              {msg && <span style={{ color: msg.startsWith('✓') ? 'var(--green)' : 'var(--red)', fontSize: 13 }}>{msg}</span>}
              <button style={styles.saveBtn} onClick={save} disabled={saving}>{saving ? '保存中…' : '保存'}</button>
            </div>

            <div style={styles.divider} />

            {/* ── 修改密码 ── */}
            <button style={styles.sectionToggle} onClick={togglePwd}>
              <span>🔑 修改密码</span>
              <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{pwdOpen ? '▲ 收起' : '▼ 展开'}</span>
            </button>
            {pwdOpen && (
              <div style={styles.smtpBody}>
                <label style={styles.label}>当前密码</label>
                <input style={styles.input} type="password" placeholder="输入当前密码"
                  value={curPwd} onChange={e => setCurPwd(e.target.value)} />
                <label style={styles.label}>新密码</label>
                <input style={styles.input} type="password" placeholder="至少 6 位"
                  value={newPwd} onChange={e => setNewPwd(e.target.value)} />
                <label style={styles.label}>确认新密码</label>
                <input style={styles.input} type="password" placeholder="再次输入新密码"
                  value={confirmPwd} onChange={e => setConfirmPwd(e.target.value)} />
                <div style={styles.footer}>
                  {pwdMsg && <span style={{ color: pwdMsg.startsWith('✓') ? 'var(--green)' : 'var(--red)', fontSize: 13 }}>{pwdMsg}</span>}
                  <button style={styles.saveBtn} onClick={savePassword} disabled={pwdSaving}>
                    {pwdSaving ? '修改中…' : '修改密码'}
                  </button>
                </div>
              </div>
            )}

            <div style={styles.divider} />

            {/* ── SMTP 配置 ── */}
            <button style={styles.sectionToggle} onClick={toggleSmtp}>
              <span>📧 SMTP 邮件配置</span>
              <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{smtpOpen ? '▲ 收起' : '▼ 展开'}</span>
            </button>
            {smtpOpen && (
              <div style={styles.smtpBody}>
                <label style={styles.label}>Host</label>
                <input style={styles.input} placeholder="smtp.qq.com" value={smtp.host} onChange={e => setS('host', e.target.value)} />
                <label style={styles.label}>Port</label>
                <input style={styles.input} placeholder="465" type="number" value={smtp.port} onChange={e => setS('port', e.target.value)} />
                <label style={styles.label}>Username（发件邮箱）</label>
                <input style={styles.input} placeholder="your@qq.com" value={smtp.username} onChange={e => setS('username', e.target.value)} />
                <label style={styles.label}>Password（授权码）</label>
                <input style={styles.input} type="password" placeholder="留空则保持不变" value={smtp.password} onChange={e => setS('password', e.target.value)} />
                <label style={styles.label}>发件人名称</label>
                <input style={styles.input} placeholder="Agent" value={smtp.from_name} onChange={e => setS('from_name', e.target.value)} />
                <div style={styles.footer}>
                  {smtpMsg && <span style={{ color: smtpMsg.startsWith('✓') ? 'var(--green)' : 'var(--red)', fontSize: 13 }}>{smtpMsg}</span>}
                  <button style={styles.saveBtn} onClick={saveSmtp} disabled={smtpSaving}>
                    {smtpSaving ? '保存中…' : '保存 SMTP'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
  },
  modal: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 12, width: 400, maxWidth: '95vw',
    maxHeight: '90vh', overflowY: 'auto',
    boxShadow: '0 20px 60px rgba(0,0,0,.5)',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 18px', borderBottom: '1px solid var(--border)',
    position: 'sticky', top: 0, background: 'var(--surface)', zIndex: 1,
  },
  title: { fontWeight: 700, fontSize: 15 },
  closeBtn: { background: 'transparent', border: 'none', color: 'var(--text-dim)', fontSize: 16, cursor: 'pointer' },
  body: { padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 8 },
  dim: { padding: 18, color: 'var(--text-dim)' },
  label: { color: 'var(--text-dim)', fontSize: 12, fontWeight: 600 },
  opt: { fontWeight: 400, color: 'var(--text-dim)', opacity: .7 },
  provRow: { display: 'flex', gap: 8 },
  provBtn: {
    flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 6, padding: '6px 0', fontSize: 13, cursor: 'pointer',
  },
  provBtnActive: { background: 'var(--accent-dim)', border: '1px solid var(--accent)', color: 'var(--text)', fontWeight: 600 },
  input: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 6, padding: '7px 10px',
    fontSize: 13, outline: 'none', width: '100%',
  },
  footer: { display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12, marginTop: 4 },
  saveBtn: {
    background: 'var(--accent)', color: '#fff', border: 'none',
    borderRadius: 6, padding: '7px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
  divider: { borderTop: '1px solid var(--border)', margin: '4px 0' },
  sectionToggle: {
    background: 'transparent', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 6, padding: '8px 12px', fontSize: 13,
    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%',
  },
  smtpBody: { display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 4 },
}
