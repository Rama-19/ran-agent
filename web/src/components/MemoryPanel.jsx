import { useState } from 'react'

export default function MemoryPanel({ entries, onSet, onDelete, onClear, loading }) {
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')
  const [editKey, setEditKey] = useState(null)
  const [editVal, setEditVal] = useState('')

  const keys = Object.keys(entries)

  const submitNew = () => {
    if (!newKey.trim() || !newVal.trim()) return
    onSet(newKey.trim(), newVal.trim())
    setNewKey('')
    setNewVal('')
  }

  const submitEdit = (key) => {
    onSet(key, editVal)
    setEditKey(null)
  }

  return (
    <div style={styles.wrap}>
      <div style={styles.toolbar}>
        <span style={styles.title}>🧠 记忆</span>
        <span style={styles.badge}>{keys.length}</span>
        {keys.length > 0 && (
          <button style={styles.clearBtn} onClick={onClear} disabled={loading}>
            清空
          </button>
        )}
      </div>

      {/* 新增 */}
      <div style={styles.addRow}>
        <input
          style={styles.keyInput}
          placeholder="key"
          value={newKey}
          onChange={e => setNewKey(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submitNew()}
          disabled={loading}
        />
        <input
          style={styles.valInput}
          placeholder="value"
          value={newVal}
          onChange={e => setNewVal(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submitNew()}
          disabled={loading}
        />
        <button
          style={{ ...styles.addBtn, opacity: newKey && newVal ? 1 : 0.4 }}
          onClick={submitNew}
          disabled={loading || !newKey || !newVal}
        >+</button>
      </div>

      {/* 列表 */}
      {keys.length === 0 ? (
        <p style={styles.empty}>暂无记忆</p>
      ) : (
        <div style={styles.list}>
          {keys.map(k => (
            <div key={k} style={styles.item}>
              <div style={styles.itemKey}>{k}</div>
              {editKey === k ? (
                <div style={styles.editRow}>
                  <input
                    style={styles.editInput}
                    value={editVal}
                    onChange={e => setEditVal(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && submitEdit(k)}
                    autoFocus
                  />
                  <button style={styles.saveBtn} onClick={() => submitEdit(k)}>✓</button>
                  <button style={styles.cancelBtn} onClick={() => setEditKey(null)}>✗</button>
                </div>
              ) : (
                <div style={styles.valRow}>
                  <span style={styles.itemVal}>{String(entries[k])}</span>
                  <button style={styles.editBtn} onClick={() => { setEditKey(k); setEditVal(String(entries[k])) }}>✎</button>
                  <button style={styles.delBtn} onClick={() => onDelete(k)} disabled={loading}>✕</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const styles = {
  wrap: { display: 'flex', flexDirection: 'column', gap: 10, height: '100%', overflowY: 'auto', padding: '4px 2px' },
  toolbar: { display: 'flex', alignItems: 'center', gap: 6 },
  title: { fontWeight: 600, fontSize: 13 },
  badge: {
    background: 'var(--surface2)', color: 'var(--accent)',
    borderRadius: 10, padding: '1px 7px', fontSize: 12, fontWeight: 600,
  },
  clearBtn: {
    marginLeft: 'auto', background: 'transparent', border: '1px solid var(--border)',
    color: 'var(--red)', borderRadius: 4, padding: '2px 8px', fontSize: 11, cursor: 'pointer',
  },
  addRow: { display: 'flex', gap: 6 },
  keyInput: {
    width: 90, background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 5, padding: '5px 7px', fontSize: 12, outline: 'none',
  },
  valInput: {
    flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 5, padding: '5px 7px', fontSize: 12, outline: 'none',
  },
  addBtn: {
    background: 'var(--accent)', color: '#fff', border: 'none',
    borderRadius: 5, width: 28, fontWeight: 700, fontSize: 16, cursor: 'pointer',
  },
  empty: { color: 'var(--text-dim)', fontSize: 12, textAlign: 'center', marginTop: 12 },
  list: { display: 'flex', flexDirection: 'column', gap: 6 },
  item: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    borderRadius: 6, padding: '7px 10px',
  },
  itemKey: { color: 'var(--accent)', fontSize: 11, fontWeight: 600, marginBottom: 3 },
  valRow: { display: 'flex', alignItems: 'flex-start', gap: 6 },
  itemVal: { flex: 1, color: 'var(--text)', fontSize: 12, wordBreak: 'break-word' },
  editBtn: {
    background: 'transparent', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 4, padding: '1px 5px', fontSize: 11, cursor: 'pointer',
  },
  delBtn: {
    background: 'transparent', border: '1px solid transparent',
    color: 'var(--red)', fontSize: 12, cursor: 'pointer', padding: '1px 4px',
  },
  editRow: { display: 'flex', gap: 5, marginTop: 2 },
  editInput: {
    flex: 1, background: 'var(--bg)', border: '1px solid var(--accent)',
    color: 'var(--text)', borderRadius: 4, padding: '3px 6px', fontSize: 12, outline: 'none',
  },
  saveBtn: {
    background: 'var(--green)', color: '#000', border: 'none',
    borderRadius: 4, padding: '3px 8px', fontSize: 12, cursor: 'pointer', fontWeight: 700,
  },
  cancelBtn: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 4, padding: '3px 7px', fontSize: 12, cursor: 'pointer',
  },
}
