import { useState, useEffect } from 'react'
import api from '../api'

const ROLE_ICONS = {
  coordinator: '🎯',
  researcher: '🔍',
  executor: '⚙️',
  reviewer: '🔎',
  summarizer: '📝',
  expert: '🎓',
  custom: '🤖',
}

const ROLE_COLORS = {
  coordinator: '#6c63ff',
  researcher: '#2196f3',
  executor: '#4caf50',
  reviewer: '#ff9800',
  summarizer: '#9c27b0',
  expert: '#00bcd4',
  custom: '#607d8b',
}

export default function CreateGroupModal({ onClose, onCreated, editGroup = null }) {
  const [name, setName] = useState(editGroup?.name || '')
  const [description, setDescription] = useState(editGroup?.description || '')
  const [selectedRoles, setSelectedRoles] = useState(
    editGroup
      ? editGroup.agents.map(a => a.role)
      : ['coordinator', 'researcher', 'executor', 'reviewer', 'summarizer']
  )
  const [roleTemplates, setRoleTemplates] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getAgentRoles().then(setRoleTemplates).catch(() => {})
  }, [])

  const toggleRole = (role) => {
    if (role === 'coordinator') return // coordinator 不可取消
    setSelectedRoles(prev =>
      prev.includes(role) ? prev.filter(r => r !== role) : [...prev, role]
    )
  }

  const handleSubmit = async () => {
    if (!name.trim()) { setError('请输入群组名称'); return }
    setLoading(true)
    setError('')
    try {
      let result
      if (editGroup) {
        result = await api.updateGroup(editGroup.id, { name: name.trim(), description: description.trim() })
      } else {
        result = await api.createGroup({
          name: name.trim(),
          description: description.trim(),
          roles: selectedRoles,
        })
      }
      onCreated(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const allRoles = Object.keys(roleTemplates).length > 0
    ? Object.keys(roleTemplates)
    : ['coordinator', 'researcher', 'executor', 'reviewer', 'summarizer', 'expert', 'custom']

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <span style={styles.title}>{editGroup ? '编辑群组' : '创建多 Agent 群组'}</span>
          <button style={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div style={styles.body}>
          {/* 群组名称 */}
          <div style={styles.field}>
            <label style={styles.label}>群组名称 *</label>
            <input
              style={styles.input}
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="例如：全能协作团队"
            />
          </div>

          {/* 群组描述 */}
          <div style={styles.field}>
            <label style={styles.label}>描述（可选）</label>
            <input
              style={styles.input}
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="描述这个群组的用途"
            />
          </div>

          {/* 角色选择 */}
          {!editGroup && (
            <div style={styles.field}>
              <label style={styles.label}>选择 Agent 角色</label>
              <p style={styles.hint}>协调者（Coordinator）是必须包含的核心角色</p>
              <div style={styles.roleGrid}>
                {allRoles.map(role => {
                  const template = roleTemplates[role] || {}
                  const selected = selectedRoles.includes(role)
                  const isCoord = role === 'coordinator'
                  return (
                    <div
                      key={role}
                      style={{
                        ...styles.roleCard,
                        borderColor: selected ? (ROLE_COLORS[role] || '#666') : 'var(--border)',
                        background: selected ? `${ROLE_COLORS[role]}15` : 'var(--surface)',
                        opacity: isCoord ? 0.85 : 1,
                        cursor: isCoord ? 'default' : 'pointer',
                      }}
                      onClick={() => toggleRole(role)}
                    >
                      <div style={styles.roleIcon}>{ROLE_ICONS[role] || '🤖'}</div>
                      <div style={styles.roleName}>{template.name || role}</div>
                      <div style={styles.roleDesc}>{template.description || ''}</div>
                      {isCoord && (
                        <div style={{ ...styles.roleTag, background: ROLE_COLORS[role] }}>必选</div>
                      )}
                      {selected && !isCoord && (
                        <div style={{ ...styles.roleTag, background: ROLE_COLORS[role] || '#666' }}>✓ 已选</div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {error && <p style={styles.error}>{error}</p>}
        </div>

        <div style={styles.footer}>
          <button style={styles.cancelBtn} onClick={onClose}>取消</button>
          <button
            style={{ ...styles.submitBtn, opacity: loading ? 0.6 : 1 }}
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? '创建中...' : (editGroup ? '保存更改' : `创建群组（${selectedRoles.length} 个 Agent）`)}
          </button>
        </div>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    background: 'var(--bg)', borderRadius: 12, width: 580, maxWidth: '95vw',
    maxHeight: '90vh', display: 'flex', flexDirection: 'column',
    border: '1px solid var(--border)', overflow: 'hidden',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderBottom: '1px solid var(--border)',
  },
  title: { fontSize: 16, fontWeight: 600, color: 'var(--text)' },
  closeBtn: {
    background: 'none', border: 'none', color: 'var(--text-dim)',
    cursor: 'pointer', fontSize: 16, padding: 4,
  },
  body: {
    padding: '20px', overflowY: 'auto', flex: 1,
    display: 'flex', flexDirection: 'column', gap: 16,
  },
  footer: {
    padding: '14px 20px', borderTop: '1px solid var(--border)',
    display: 'flex', justifyContent: 'flex-end', gap: 10,
  },
  field: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontSize: 13, fontWeight: 500, color: 'var(--text)' },
  hint: { fontSize: 12, color: 'var(--text-dim)', margin: 0 },
  input: {
    padding: '8px 12px', borderRadius: 7, border: '1px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text)', fontSize: 14, outline: 'none',
  },
  roleGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10,
    marginTop: 6,
  },
  roleCard: {
    position: 'relative', padding: '12px 10px', borderRadius: 10,
    border: '2px solid', textAlign: 'center', transition: 'all 0.15s',
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
  },
  roleIcon: { fontSize: 24 },
  roleName: { fontSize: 13, fontWeight: 600, color: 'var(--text)' },
  roleDesc: { fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.3 },
  roleTag: {
    position: 'absolute', top: 6, right: 6,
    fontSize: 10, color: '#fff', padding: '2px 5px',
    borderRadius: 4, fontWeight: 600,
  },
  error: { color: '#ef5350', fontSize: 13, margin: 0 },
  cancelBtn: {
    padding: '8px 18px', borderRadius: 7,
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--text)', cursor: 'pointer', fontSize: 14,
  },
  submitBtn: {
    padding: '8px 18px', borderRadius: 7,
    border: 'none', background: 'var(--accent)',
    color: '#fff', cursor: 'pointer', fontSize: 14, fontWeight: 500,
  },
}
