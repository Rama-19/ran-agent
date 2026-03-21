import { useState } from 'react'

export default function ConversationPanel({ conversations, currentId, onCreate, onSelect, onDelete, onRename }) {
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [hoverId, setHoverId] = useState(null)

  const startEdit = (conv, e) => {
    e.stopPropagation()
    setEditingId(conv.id)
    setEditTitle(conv.title)
  }

  const confirmEdit = (conv) => {
    if (editTitle.trim() && editTitle.trim() !== conv.title) {
      onRename(conv.id, editTitle.trim())
    }
    setEditingId(null)
  }

  return (
    <aside style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.title}>💬 会话</span>
        <button style={styles.newBtn} onClick={onCreate} title="新建会话">＋</button>
      </div>

      <div style={styles.list}>
        {conversations.length === 0 ? (
          <div style={styles.empty}>点击 ＋ 新建会话</div>
        ) : (
          conversations.map(conv => (
            <div
              key={conv.id}
              style={{
                ...styles.item,
                ...(conv.id === currentId ? styles.itemActive : {}),
                ...(hoverId === conv.id && conv.id !== currentId ? styles.itemHover : {}),
              }}
              onClick={() => onSelect(conv.id)}
              onMouseEnter={() => setHoverId(conv.id)}
              onMouseLeave={() => setHoverId(null)}
            >
              {editingId === conv.id ? (
                <input
                  style={styles.editInput}
                  value={editTitle}
                  autoFocus
                  onChange={e => setEditTitle(e.target.value)}
                  onBlur={() => confirmEdit(conv)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') confirmEdit(conv)
                    if (e.key === 'Escape') setEditingId(null)
                  }}
                  onClick={e => e.stopPropagation()}
                />
              ) : (
                <>
                  <div
                    style={styles.convTitle}
                    onDoubleClick={e => startEdit(conv, e)}
                    title="双击重命名"
                  >
                    {conv.title}
                  </div>
                  <div style={styles.convMeta}>{conv.message_count} 条消息</div>
                  <button
                    style={{
                      ...styles.delBtn,
                      opacity: hoverId === conv.id || conv.id === currentId ? 0.6 : 0,
                    }}
                    onClick={e => { e.stopPropagation(); onDelete(conv.id) }}
                    title="删除会话"
                  >✕</button>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </aside>
  )
}

const styles = {
  panel: {
    width: 180,
    minWidth: 150,
    borderRight: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--surface)',
    flexShrink: 0,
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    padding: '10px 12px',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
    gap: 6,
  },
  title: {
    fontSize: 12,
    fontWeight: 700,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '.05em',
    flex: 1,
  },
  newBtn: {
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    width: 22,
    height: 22,
    fontSize: 15,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    lineHeight: 1,
  },
  list: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px 6px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  item: {
    padding: '8px 8px',
    borderRadius: 6,
    cursor: 'pointer',
    border: '1px solid transparent',
    position: 'relative',
    transition: 'background .1s',
  },
  itemActive: {
    background: 'var(--accent-dim)',
    border: '1px solid var(--accent)',
  },
  itemHover: {
    background: 'var(--surface2)',
  },
  convTitle: {
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--text)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    paddingRight: 18,
  },
  convMeta: {
    fontSize: 11,
    color: 'var(--text-dim)',
    marginTop: 2,
  },
  delBtn: {
    position: 'absolute',
    top: 6,
    right: 6,
    background: 'transparent',
    border: 'none',
    color: 'var(--text-dim)',
    cursor: 'pointer',
    fontSize: 11,
    padding: '1px 3px',
    borderRadius: 3,
    opacity: 0,
  },
  editInput: {
    width: '100%',
    background: 'var(--surface2)',
    border: '1px solid var(--accent)',
    color: 'var(--text)',
    borderRadius: 4,
    padding: '3px 6px',
    fontSize: 12,
    outline: 'none',
    boxSizing: 'border-box',
  },
  empty: {
    color: 'var(--text-dim)',
    fontSize: 12,
    padding: '12px 8px',
    textAlign: 'center',
  },
}
