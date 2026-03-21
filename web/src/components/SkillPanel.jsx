export default function SkillPanel({ skills, loading }) {
  return (
    <aside style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.icon}>⚡</span>
        <span>Skills</span>
        <span style={styles.badge}>{skills.length}</span>
      </div>

      {loading ? (
        <p style={styles.dim}>加载中…</p>
      ) : skills.length === 0 ? (
        <p style={styles.dim}>暂无可用 skill</p>
      ) : (
        <ul style={styles.list}>
          {skills.map((s) => (
            <li key={s.name} style={styles.item}>
              <div style={styles.skillName}>{s.name}</div>
              <div style={styles.skillDesc}>{s.description}</div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}

const styles = {
  panel: {
    width: 240,
    minWidth: 200,
    borderRight: '1px solid var(--border)',
    padding: '16px 12px',
    overflowY: 'auto',
    background: 'var(--surface)',
    flexShrink: 0,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontWeight: 600,
    fontSize: 13,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '.05em',
    marginBottom: 12,
  },
  icon: { fontSize: 14 },
  badge: {
    marginLeft: 'auto',
    background: 'var(--surface2)',
    color: 'var(--accent)',
    borderRadius: 10,
    padding: '1px 7px',
    fontSize: 12,
    fontWeight: 600,
  },
  list: { listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 },
  item: {
    background: 'var(--surface2)',
    borderRadius: 'var(--radius)',
    padding: '8px 10px',
    border: '1px solid var(--border)',
  },
  skillName: { fontWeight: 600, color: 'var(--accent)', fontSize: 13 },
  skillDesc: { color: 'var(--text-dim)', fontSize: 12, marginTop: 2 },
  dim: { color: 'var(--text-dim)', fontSize: 13 },
}
