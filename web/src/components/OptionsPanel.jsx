export default function OptionsPanel({ options, onChange }) {
  const set = (key, val) => onChange({ ...options, [key]: val })

  return (
    <div style={styles.row}>
      {/* web_mode */}
      <label style={styles.group}>
        <span style={styles.label}>联网</span>
        <select
          style={styles.select}
          value={options.web_mode}
          onChange={(e) => set('web_mode', e.target.value)}
        >
          <option value="off">off</option>
          <option value="auto">auto</option>
          <option value="on">on</option>
        </select>
      </label>

      {/* deep_think */}
      <label style={styles.group}>
        <span style={styles.label}>深思</span>
        <select
          style={styles.select}
          value={options.deep_think}
          onChange={(e) => set('deep_think', Number(e.target.value))}
        >
          <option value={0}>关闭</option>
          <option value={1}>轻度</option>
          <option value={2}>中度</option>
          <option value={3}>重度</option>
        </select>
      </label>

      {/* require_citations */}
      <label style={{ ...styles.group, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={options.require_citations}
          onChange={(e) => set('require_citations', e.target.checked)}
          style={{ accentColor: 'var(--accent)' }}
        />
        <span style={styles.label}>引用来源</span>
      </label>

      {/* max_search_rounds */}
      {options.web_mode !== 'off' && (
        <label style={styles.group}>
          <span style={styles.label}>最多搜索</span>
          <input
            type="number"
            min={1}
            max={10}
            value={options.max_search_rounds}
            onChange={(e) => set('max_search_rounds', Number(e.target.value))}
            style={{ ...styles.select, width: 52 }}
          />
        </label>
      )}
    </div>
  )
}

const styles = {
  row: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 12,
    alignItems: 'center',
    padding: '6px 0',
  },
  group: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
  },
  label: {
    color: 'var(--text-dim)',
    fontSize: 12,
  },
  select: {
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    color: 'var(--text)',
    borderRadius: 4,
    padding: '3px 6px',
    fontSize: 12,
    outline: 'none',
  },
}
