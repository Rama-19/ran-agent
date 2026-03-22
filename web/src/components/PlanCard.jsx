import { useState } from 'react'

const STATUS_COLOR = {
  pending: 'var(--text-dim)',
  running: 'var(--yellow)',
  done: 'var(--green)',
  blocked: 'var(--purple)',
  failed: 'var(--red)',
}

const STATUS_ICON = {
  pending: '○',
  running: '◌',
  done: '✓',
  blocked: '⊘',
  failed: '✗',
}

function StepRow({ step }) {
  const [open, setOpen] = useState(false)
  const color = STATUS_COLOR[step.status] || 'var(--text-dim)'

  return (
    <div style={styles.step}>
      <div style={styles.stepHeader} onClick={() => setOpen(!open)}>
        <span style={{ color, fontWeight: 700, fontSize: 14 }}>
          {STATUS_ICON[step.status] || '○'}
        </span>
        <span style={styles.stepTitle}>{step.title}</span>
        {step.skill_hint && (
          <span style={styles.hint}>{step.skill_hint}</span>
        )}
        <span style={{ color, fontSize: 11, marginLeft: 'auto', flexShrink: 0 }}>
          {step.status}
        </span>
        <span style={styles.toggle}>{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <div style={styles.stepBody}>
          <div style={styles.label}>指令</div>
          <pre style={styles.pre}>{step.instruction}</pre>
          {step.output && (
            <>
              <div style={{ ...styles.label, marginTop: 8 }}>输出</div>
              <pre style={{ ...styles.pre, color: 'var(--text)' }}>{step.output}</pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function PlanCard({ plan, onRun, onDelete }) {
  const statusColor = STATUS_COLOR[plan.status] || 'var(--text-dim)'

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.cardHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
          <span style={{ color: statusColor, fontWeight: 700, fontSize: 16 }}>
            {STATUS_ICON[plan.status] || '○'}
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={styles.planTitle}>{plan.title}</div>
            <div style={styles.planGoal}>{plan.goal}</div>
          </div>
        </div>
        <div style={styles.cardActions}>
          <span style={{ ...styles.statusTag, color: statusColor, borderColor: statusColor }}>
            {plan.status}
          </span>
          {(plan.status === 'pending' || plan.status === 'failed') && onRun && (
            <button style={styles.runBtn} onClick={() => onRun(plan.id)}>
              ▶ 执行
            </button>
          )}
          {onDelete && (
            <button style={styles.deleteBtn} onClick={() => onDelete(plan.id)} title="删除计划">
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Steps */}
      <div style={styles.steps}>
        {plan.steps.map((s) => (
          <StepRow key={s.id} step={s} />
        ))}
      </div>

      {/* Blocked hint */}
      {plan.awaiting_user_input && plan.pending_question && (
        <div style={styles.blockedBar}>
          <span style={{ color: 'var(--purple)', marginRight: 6 }}>⊘</span>
          {plan.pending_question}
        </div>
      )}
    </div>
  )
}

const styles = {
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    overflow: 'hidden',
    marginBottom: 12,
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 12,
    padding: '12px 14px',
    borderBottom: '1px solid var(--border)',
  },
  planTitle: { fontWeight: 600, fontSize: 14 },
  planGoal: { color: 'var(--text-dim)', fontSize: 12, marginTop: 2 },
  cardActions: { display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 },
  statusTag: {
    border: '1px solid',
    borderRadius: 4,
    padding: '1px 8px',
    fontSize: 11,
    fontWeight: 600,
  },
  runBtn: {
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: 5,
    padding: '4px 12px',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  deleteBtn: {
    background: 'transparent',
    color: 'var(--text-dim)',
    border: '1px solid var(--border)',
    borderRadius: 5,
    padding: '4px 8px',
    fontSize: 13,
    cursor: 'pointer',
  },
  steps: { padding: '8px 14px', display: 'flex', flexDirection: 'column', gap: 4 },
  step: {
    borderRadius: 6,
    overflow: 'hidden',
    border: '1px solid var(--border)',
  },
  stepHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '7px 10px',
    cursor: 'pointer',
    background: 'var(--surface2)',
    userSelect: 'none',
  },
  stepTitle: { flex: 1, fontSize: 13, fontWeight: 500 },
  hint: {
    background: 'var(--surface)',
    color: 'var(--accent)',
    border: '1px solid var(--accent-dim)',
    borderRadius: 4,
    padding: '0 6px',
    fontSize: 11,
  },
  toggle: { color: 'var(--text-dim)', fontSize: 10 },
  stepBody: { padding: '8px 10px', background: 'var(--bg)' },
  label: { fontSize: 11, color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' },
  pre: {
    fontFamily: 'var(--mono)',
    fontSize: 12,
    color: 'var(--text-dim)',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    marginTop: 4,
    lineHeight: 1.6,
  },
  blockedBar: {
    background: 'var(--pending-bg)',
    borderTop: '1px solid var(--pending-border)',
    padding: '8px 14px',
    fontSize: 13,
    color: 'var(--text)',
  },
}
