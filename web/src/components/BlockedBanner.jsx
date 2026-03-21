import { useState } from 'react'

export default function BlockedBanner({ pending, onReply, onCancel, loading }) {
  const [text, setText] = useState('')

  const submit = () => {
    if (!text.trim()) return
    onReply(text.trim())
    setText('')
  }

  if (!pending) return null

  return (
    <div style={styles.banner}>
      <div style={styles.header}>
        <span style={styles.icon}>⊘</span>
        <span style={styles.title}>计划等待补充信息</span>
        <span style={styles.meta}>
          {pending.plan_id} / {pending.step_id}
        </span>
      </div>
      <p style={styles.question}>{pending.question}</p>
      <div style={styles.inputRow}>
        <input
          style={styles.input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && submit()}
          placeholder="输入补充内容…"
          disabled={loading}
        />
        <button style={styles.btn} onClick={submit} disabled={loading || !text.trim()}>
          {loading ? '…' : '继续'}
        </button>
        <button style={styles.cancelBtn} onClick={onCancel} disabled={loading}>
          取消
        </button>
      </div>
    </div>
  )
}

const styles = {
  banner: {
    background: 'var(--pending-bg)',
    border: '1px solid var(--pending-border)',
    borderRadius: 10,
    padding: '14px 16px',
    marginBottom: 16,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  icon: { color: 'var(--purple)', fontSize: 16 },
  title: { fontWeight: 600, color: 'var(--purple)' },
  meta: { marginLeft: 'auto', fontSize: 11, color: 'var(--text-dim)' },
  question: { color: 'var(--text)', marginBottom: 10, fontSize: 13 },
  inputRow: { display: 'flex', gap: 8 },
  input: {
    flex: 1,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    color: 'var(--text)',
    borderRadius: 6,
    padding: '7px 10px',
    fontSize: 13,
    outline: 'none',
  },
  btn: {
    background: 'var(--purple)',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    padding: '7px 16px',
    fontWeight: 600,
    cursor: 'pointer',
    fontSize: 13,
  },
  cancelBtn: {
    background: 'var(--surface2)',
    color: 'var(--text-dim)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    padding: '7px 14px',
    cursor: 'pointer',
    fontSize: 13,
  },
}
