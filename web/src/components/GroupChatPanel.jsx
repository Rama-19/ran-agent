import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import api from '../api'
import CreateGroupModal from './CreateGroupModal'

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

// ── Agent 头像 ────────────────────────────────────────────────────────────
function AgentAvatar({ role, name, size = 32 }) {
  const color = ROLE_COLORS[role] || '#607d8b'
  const icon = ROLE_ICONS[role] || '🤖'
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: `${color}22`, border: `2px solid ${color}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.5, flexShrink: 0, title: name,
    }}>
      {icon}
    </div>
  )
}

// ── 单个 Agent 发言气泡 ───────────────────────────────────────────────────
function AgentTurnBubble({ turn }) {
  const [expanded, setExpanded] = useState(turn.role === 'summarizer')
  const color = ROLE_COLORS[turn.role] || '#607d8b'

  return (
    <div style={styles.turnWrapper}>
      <div style={styles.turnHeader}>
        <AgentAvatar role={turn.role} name={turn.agent_name} size={28} />
        <span style={{ ...styles.turnName, color }}>{turn.agent_name}</span>
        <span style={styles.turnRole}>（{turn.role}）</span>
        <span style={styles.turnTask}>→ {turn.subtask}</span>
        <button
          style={styles.expandBtn}
          onClick={() => setExpanded(v => !v)}
        >
          {expanded ? '收起 ▲' : '展开 ▼'}
        </button>
      </div>
      {expanded && (
        <div style={{ ...styles.turnContent, borderLeftColor: color }}>
          {turn.error ? (
            <p style={{ color: '#ef5350', fontSize: 13 }}>[错误] {turn.error}</p>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.output || ''}</ReactMarkdown>
          )}
        </div>
      )}
    </div>
  )
}

// ── 消息组（用户 + 群组回复）─────────────────────────────────────────────
function GroupMessage({ msg, groupName }) {
  const isUser = msg.role === 'user'
  if (isUser) {
    return (
      <div style={styles.userMsg}>
        <div style={styles.userBubble}>{msg.text}</div>
      </div>
    )
  }

  // agent group reply with full structured result (sent in this session)
  const result = msg.groupResult
  if (result) {
    return (
      <div style={styles.groupReply}>
        {/* 群组标签 */}
        {groupName && (
          <div style={styles.groupBadgeRow}>
            <span style={styles.groupBadge}>🤝 多 Agent · {groupName}</span>
          </div>
        )}
        <div style={styles.agentTurns}>
          {result.turns?.map((turn, i) => (
            <AgentTurnBubble key={i} turn={turn} />
          ))}
        </div>
        {result.final_answer && (
          <div style={styles.finalAnswer}>
            <div style={styles.finalLabel}>
              <span style={styles.finalIcon}>✨</span> 最终答案
            </div>
            <div style={styles.finalContent}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.final_answer}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    )
  }

  // Plain text fallback — loaded from conversation history
  return (
    <div style={styles.groupReply}>
      {groupName && (
        <div style={styles.groupBadgeRow}>
          <span style={styles.groupBadge}>🤝 多 Agent · {groupName}</span>
        </div>
      )}
      <div style={styles.finalAnswer}>
        <div style={styles.finalLabel}>
          <span style={styles.finalIcon}>✨</span> 最终答案
        </div>
        <div style={styles.finalContent}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text || ''}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

// ── Agent 编辑弹窗 ────────────────────────────────────────────────────────
function AgentEditModal({ agent, groupId, onClose, onSaved }) {
  const [name, setName] = useState(agent.name)
  const [desc, setDesc] = useState(agent.description)
  const [prompt, setPrompt] = useState(agent.system_prompt)
  const [loading, setLoading] = useState(false)

  const save = async () => {
    setLoading(true)
    try {
      const updated = await api.updateAgent(groupId, agent.id, {
        name, description: desc, system_prompt: prompt,
      })
      onSaved(updated)
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={{ ...styles.modal, width: 520 }} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <span style={styles.title}>编辑 Agent: {agent.name}</span>
          <button style={styles.closeBtn2} onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={styles.label}>名称</label>
          <input style={styles.input} value={name} onChange={e => setName(e.target.value)} />
          <label style={styles.label}>描述</label>
          <input style={styles.input} value={desc} onChange={e => setDesc(e.target.value)} />
          <label style={styles.label}>System Prompt</label>
          <textarea
            style={{ ...styles.input, minHeight: 160, resize: 'vertical', fontFamily: 'inherit' }}
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
          />
        </div>
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button style={styles.cancelBtn} onClick={onClose}>取消</button>
          <button style={{ ...styles.submitBtn, opacity: loading ? 0.6 : 1 }} onClick={save} disabled={loading}>
            {loading ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 主组件 ────────────────────────────────────────────────────────────────
export default function GroupChatPanel({ onConvUpdate, onNewConv }) {
  const [groups, setGroups] = useState([])
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeAgents, setActiveAgents] = useState([]) // 正在工作的 agent 名称
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingAgent, setEditingAgent] = useState(null)
  const [showAddAgent, setShowAddAgent] = useState(false)
  const [addAgentRole, setAddAgentRole] = useState('custom')
  const [addAgentName, setAddAgentName] = useState('')
  const [roleTemplates, setRoleTemplates] = useState({})
  // 每个群组独立记录对应的会话 ID，持久化到 localStorage
  const [groupConvMap, setGroupConvMap] = useState(() => {
    try { return JSON.parse(localStorage.getItem('group_conv_map') || '{}') } catch { return {} }
  })
  const bottomRef = useRef(null)

  useEffect(() => {
    loadGroups()
    api.getAgentRoles().then(setRoleTemplates).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // 记录群组→会话映射，同步到 localStorage
  const saveGroupConv = (groupId, convId) => {
    const next = { ...groupConvMap, [groupId]: convId }
    setGroupConvMap(next)
    try { localStorage.setItem('group_conv_map', JSON.stringify(next)) } catch {}
  }

  // 加载指定群组的历史消息
  const loadGroupMessages = async (groupId) => {
    const savedConvId = groupConvMap[groupId]
    if (!savedConvId) { setMessages([]); return }
    try {
      const data = await api.getConversation(savedConvId)
      if (!data?.messages) { setMessages([]); return }
      setMessages(data.messages.map(m => ({
        id: m.id,
        role: m.role === 'user' ? 'user' : 'agent',
        text: m.text,
      })))
    } catch {
      setMessages([])
    }
  }

  const loadGroups = async () => {
    try {
      const list = await api.getGroups()
      setGroups(list)
      if (list.length > 0 && !selectedGroup) {
        const full = await api.getGroup(list[0].id)
        setSelectedGroup(full)
        await loadGroupMessages(list[0].id)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const selectGroup = async (gId) => {
    try {
      const full = await api.getGroup(gId)
      setSelectedGroup(full)
      await loadGroupMessages(gId)
    } catch (e) {
      alert(e.message)
    }
  }

  const send = async () => {
    if (!input.trim() || loading) return
    if (!selectedGroup) { alert('请先选择或创建一个群组'); return }

    const currentGroupId = selectedGroup.id
    const activeConvId = groupConvMap[currentGroupId] || null

    const userMsg = { role: 'user', text: input.trim(), id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    const task = input.trim()
    setInput('')
    setLoading(true)

    // 显示正在工作的 agent 动画
    const agentNames = selectedGroup.agents
      .filter(a => a.enabled)
      .map(a => a.name)
    setActiveAgents(agentNames)

    try {
      const result = await api.groupChat(selectedGroup.id, task, {}, activeConvId)
      const agentMsg = { role: 'agent', id: Date.now() + 1, groupResult: result }
      setMessages(prev => [...prev, agentMsg])

      // 保存到对话（每个群组独立的会话）
      let newConvId = activeConvId
      if (!newConvId) {
        try {
          const conv = await api.createConversation()
          newConvId = conv.id
          saveGroupConv(currentGroupId, conv.id)
          onNewConv?.(conv)
        } catch {
          newConvId = null
        }
      }
      if (newConvId) {
        await api.appendMessage(newConvId, 'user', task).catch(() => {})
        await api.appendMessage(newConvId, 'agent', result.final_answer || '').catch(() => {})
        onConvUpdate?.()
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'error', text: e.message, id: Date.now() + 1 }])
    } finally {
      setLoading(false)
      setActiveAgents([])
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const toggleAgent = async (groupId, agentId, enabled) => {
    try {
      await api.updateAgent(groupId, agentId, { enabled })
      const updated = await api.getGroup(groupId)
      setSelectedGroup(updated)
      setGroups(prev => prev.map(g => g.id === groupId
        ? { ...g, agents: updated.agents } : g))
    } catch (e) {
      alert(e.message)
    }
  }

  const removeAgent = async (groupId, agentId) => {
    if (!confirm('确认删除该 agent？')) return
    try {
      await api.removeAgent(groupId, agentId)
      const updated = await api.getGroup(groupId)
      setSelectedGroup(updated)
    } catch (e) {
      alert(e.message)
    }
  }

  const handleAddAgent = async () => {
    try {
      await api.addAgent(selectedGroup.id, {
        role: addAgentRole,
        name: addAgentName || (roleTemplates[addAgentRole]?.name || addAgentRole),
      })
      const updated = await api.getGroup(selectedGroup.id)
      setSelectedGroup(updated)
      setShowAddAgent(false)
      setAddAgentName('')
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <div style={styles.root}>
      {/* ── 左侧：群组列表 + Agent 配置 ── */}
      <div style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          <span style={styles.sidebarTitle}>🤝 Agent 群组</span>
          <button style={styles.newGroupBtn} onClick={() => setShowCreateModal(true)}>+ 新建</button>
        </div>

        {/* 群组列表 */}
        <div style={styles.groupList}>
          {groups.length === 0 ? (
            <div style={styles.emptyHint}>
              <p>暂无群组</p>
              <button style={styles.createFirstBtn} onClick={() => setShowCreateModal(true)}>
                创建第一个群组
              </button>
            </div>
          ) : (
            groups.map(g => (
              <div
                key={g.id}
                style={{
                  ...styles.groupItem,
                  borderColor: selectedGroup?.id === g.id ? 'var(--accent)' : 'var(--border)',
                  background: selectedGroup?.id === g.id ? 'var(--accent)12' : 'var(--surface)',
                }}
                onClick={() => selectGroup(g.id)}
              >
                <div style={styles.groupItemName}>{g.name}</div>
                <div style={styles.groupItemMeta}>
                  {g.agents.length} 个 Agent
                </div>
              </div>
            ))
          )}
        </div>

        {/* Agent 列表 */}
        {selectedGroup && (
          <div style={styles.agentSection}>
            <div style={styles.agentSectionTitle}>
              <span>群组成员</span>
              <button style={styles.addAgentBtn} onClick={() => setShowAddAgent(v => !v)}>
                {showAddAgent ? '取消' : '+ 添加'}
              </button>
            </div>

            {showAddAgent && (
              <div style={styles.addAgentForm}>
                <select
                  style={styles.select}
                  value={addAgentRole}
                  onChange={e => setAddAgentRole(e.target.value)}
                >
                  {Object.entries(roleTemplates).map(([r, info]) => (
                    <option key={r} value={r}>{info.name}（{r}）</option>
                  ))}
                </select>
                <input
                  style={styles.input}
                  placeholder="自定义名称（可选）"
                  value={addAgentName}
                  onChange={e => setAddAgentName(e.target.value)}
                />
                <button style={styles.submitBtn} onClick={handleAddAgent}>添加</button>
              </div>
            )}

            {selectedGroup.agents?.map(agent => (
              <div key={agent.id} style={{
                ...styles.agentItem,
                opacity: agent.enabled ? 1 : 0.5,
              }}>
                <AgentAvatar role={agent.role} name={agent.name} size={26} />
                <div style={styles.agentInfo}>
                  <span style={styles.agentName}>{agent.name}</span>
                  <span style={styles.agentRoleLabel}>{agent.role}</span>
                </div>
                <div style={styles.agentActions}>
                  <button
                    style={styles.iconBtn}
                    title="编辑"
                    onClick={() => setEditingAgent(agent)}
                  >✏️</button>
                  {agent.role !== 'coordinator' && (
                    <>
                      <button
                        style={styles.iconBtn}
                        title={agent.enabled ? '禁用' : '启用'}
                        onClick={() => toggleAgent(selectedGroup.id, agent.id, !agent.enabled)}
                      >{agent.enabled ? '⏸' : '▶️'}</button>
                      <button
                        style={styles.iconBtn}
                        title="删除"
                        onClick={() => removeAgent(selectedGroup.id, agent.id)}
                      >🗑</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── 右侧：聊天区域 ── */}
      <div style={styles.chatArea}>
        {/* 聊天头部 */}
        <div style={styles.chatHeader}>
          {selectedGroup ? (
            <>
              <span style={styles.chatTitle}>{selectedGroup.name}</span>
              <div style={styles.chatAgentBadges}>
                {selectedGroup.agents?.filter(a => a.enabled).map(a => (
                  <span
                    key={a.id}
                    style={{
                      ...styles.badge,
                      background: `${ROLE_COLORS[a.role] || '#607d8b'}22`,
                      color: ROLE_COLORS[a.role] || '#607d8b',
                    }}
                  >
                    {ROLE_ICONS[a.role] || '🤖'} {a.name}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <span style={styles.chatTitle}>请选择或创建一个群组</span>
          )}
        </div>

        {/* 消息列表 */}
        <div style={styles.msgList}>
          {messages.length === 0 && !loading && (
            <div style={styles.emptyChat}>
              <div style={styles.emptyChatIcon}>🤝</div>
              <p style={styles.emptyChatText}>
                {selectedGroup
                  ? `${selectedGroup.name} 已就绪，发送消息开始多 agent 协作`
                  : '请先在左侧选择或创建一个 Agent 群组'}
              </p>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id}>
              {msg.role === 'error' ? (
                <div style={styles.errorMsg}>{msg.text}</div>
              ) : (
                <GroupMessage msg={msg} groupName={msg.role !== 'user' ? selectedGroup?.name : undefined} />
              )}
            </div>
          ))}

          {/* 加载动画 */}
          {loading && (
            <div style={styles.loadingWrapper}>
              <div style={styles.loadingTitle}>🤝 多 agent 协作中...</div>
              <div style={styles.loadingAgents}>
                {activeAgents.map((name, i) => (
                  <span key={i} style={{
                    ...styles.loadingAgent,
                    animationDelay: `${i * 0.2}s`,
                  }}>
                    {name}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* 输入框 */}
        <div style={styles.inputArea}>
          <textarea
            style={styles.textarea}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedGroup
                ? `向 ${selectedGroup.name} 发送任务... (Enter 发送, Shift+Enter 换行)`
                : '请先选择或创建一个群组'
            }
            disabled={!selectedGroup || loading}
            rows={2}
          />
          <button
            style={{
              ...styles.sendBtn,
              opacity: (!input.trim() || loading || !selectedGroup) ? 0.5 : 1,
            }}
            onClick={send}
            disabled={!input.trim() || loading || !selectedGroup}
          >
            {loading ? '⏳' : '发送'}
          </button>
        </div>
      </div>

      {/* ── 弹窗 ── */}
      {showCreateModal && (
        <CreateGroupModal
          onClose={() => setShowCreateModal(false)}
          onCreated={async (g) => {
            setShowCreateModal(false)
            await loadGroups()
            const full = await api.getGroup(g.id)
            setSelectedGroup(full)
          }}
        />
      )}

      {editingAgent && (
        <AgentEditModal
          agent={editingAgent}
          groupId={selectedGroup.id}
          onClose={() => setEditingAgent(null)}
          onSaved={async () => {
            setEditingAgent(null)
            const updated = await api.getGroup(selectedGroup.id)
            setSelectedGroup(updated)
          }}
        />
      )}
    </div>
  )
}

// ── 样式 ─────────────────────────────────────────────────────────────────────
const styles = {
  root: {
    display: 'flex', height: '100%', overflow: 'hidden',
    background: 'var(--bg)',
  },
  // Sidebar
  sidebar: {
    width: 240, flexShrink: 0, borderRight: '1px solid var(--border)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    background: 'var(--surface)',
  },
  sidebarHeader: {
    padding: '12px 14px', borderBottom: '1px solid var(--border)',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  sidebarTitle: { fontSize: 14, fontWeight: 600, color: 'var(--text)' },
  newGroupBtn: {
    fontSize: 12, padding: '3px 8px', borderRadius: 5,
    border: '1px solid var(--accent)', background: 'transparent',
    color: 'var(--accent)', cursor: 'pointer',
  },
  groupList: { padding: '8px', display: 'flex', flexDirection: 'column', gap: 4 },
  groupItem: {
    padding: '8px 10px', borderRadius: 7, border: '1.5px solid',
    cursor: 'pointer', transition: 'all 0.15s',
  },
  groupItemName: { fontSize: 13, fontWeight: 500, color: 'var(--text)' },
  groupItemMeta: { fontSize: 11, color: 'var(--text-dim)', marginTop: 2 },
  emptyHint: {
    padding: '20px 14px', textAlign: 'center', color: 'var(--text-dim)', fontSize: 13,
  },
  createFirstBtn: {
    marginTop: 8, padding: '6px 14px', borderRadius: 6,
    border: 'none', background: 'var(--accent)', color: '#fff',
    cursor: 'pointer', fontSize: 12,
  },
  agentSection: {
    flex: 1, overflowY: 'auto', borderTop: '1px solid var(--border)',
    padding: '8px',
  },
  agentSectionTitle: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
    padding: '4px 2px 8px', textTransform: 'uppercase', letterSpacing: 0.5,
  },
  addAgentBtn: {
    fontSize: 11, padding: '2px 6px', borderRadius: 4,
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--text-dim)', cursor: 'pointer',
  },
  addAgentForm: {
    display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8,
    padding: '8px', background: 'var(--bg)', borderRadius: 7,
    border: '1px solid var(--border)',
  },
  agentItem: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '6px 4px', borderRadius: 6, marginBottom: 2,
  },
  agentInfo: { flex: 1, minWidth: 0 },
  agentName: { display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text)' },
  agentRoleLabel: { fontSize: 10, color: 'var(--text-dim)' },
  agentActions: { display: 'flex', gap: 2 },
  iconBtn: {
    background: 'none', border: 'none', cursor: 'pointer',
    fontSize: 13, padding: '2px 3px', borderRadius: 4,
  },
  // Chat area
  chatArea: {
    flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden',
  },
  chatHeader: {
    padding: '12px 20px', borderBottom: '1px solid var(--border)',
    display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
  },
  chatTitle: { fontSize: 15, fontWeight: 600, color: 'var(--text)' },
  chatAgentBadges: { display: 'flex', gap: 6, flexWrap: 'wrap' },
  badge: {
    fontSize: 11, padding: '2px 8px', borderRadius: 12,
    fontWeight: 500,
  },
  msgList: {
    flex: 1, overflowY: 'auto', padding: '16px 20px',
    display: 'flex', flexDirection: 'column', gap: 16,
  },
  emptyChat: {
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', padding: 40, gap: 12,
  },
  emptyChatIcon: { fontSize: 48 },
  emptyChatText: { color: 'var(--text-dim)', textAlign: 'center', fontSize: 14 },
  // User message
  userMsg: { display: 'flex', justifyContent: 'flex-end' },
  userBubble: {
    maxWidth: '70%', padding: '10px 14px',
    background: 'var(--accent)', color: '#fff',
    borderRadius: '16px 16px 4px 16px', fontSize: 14, lineHeight: 1.5,
  },
  // Group reply
  groupReply: { display: 'flex', flexDirection: 'column', gap: 8 },
  groupBadgeRow: { display: 'flex', alignItems: 'center' },
  groupBadge: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    fontSize: 11, fontWeight: 600, padding: '2px 10px',
    borderRadius: 10, border: '1px solid #ff980055',
    background: '#ff980018', color: '#ff9800',
    letterSpacing: 0.3,
  },
  agentTurns: { display: 'flex', flexDirection: 'column', gap: 6 },
  turnWrapper: {
    border: '1px solid var(--border)', borderRadius: 10,
    background: 'var(--surface)', overflow: 'hidden',
  },
  turnHeader: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '8px 12px', background: 'var(--bg)',
    borderBottom: '1px solid var(--border)',
    flexWrap: 'wrap',
  },
  turnName: { fontSize: 13, fontWeight: 600 },
  turnRole: { fontSize: 11, color: 'var(--text-dim)' },
  turnTask: { fontSize: 11, color: 'var(--text-dim)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' },
  expandBtn: {
    fontSize: 11, padding: '2px 7px', borderRadius: 4,
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--text-dim)', cursor: 'pointer', flexShrink: 0,
  },
  turnContent: {
    padding: '10px 14px', fontSize: 13, lineHeight: 1.6,
    borderLeft: '3px solid', color: 'var(--text)',
  },
  finalAnswer: {
    border: '2px solid #9c27b0', borderRadius: 12,
    background: '#9c27b011', overflow: 'hidden',
  },
  finalLabel: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 14px', background: '#9c27b022',
    fontSize: 13, fontWeight: 600, color: '#9c27b0',
  },
  finalIcon: { fontSize: 16 },
  finalContent: {
    padding: '12px 16px', fontSize: 14, lineHeight: 1.7, color: 'var(--text)',
  },
  // Loading
  loadingWrapper: {
    padding: '16px 20px', border: '1px solid var(--border)',
    borderRadius: 10, background: 'var(--surface)',
  },
  loadingTitle: { fontSize: 13, fontWeight: 500, color: 'var(--text-dim)', marginBottom: 8 },
  loadingAgents: { display: 'flex', gap: 8, flexWrap: 'wrap' },
  loadingAgent: {
    fontSize: 12, padding: '3px 10px', borderRadius: 12,
    background: 'var(--accent)22', color: 'var(--accent)',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  errorMsg: {
    padding: '10px 14px', color: '#ef5350', fontSize: 13,
    background: '#ef535011', borderRadius: 8, border: '1px solid #ef535033',
  },
  // Input
  inputArea: {
    padding: '12px 20px', borderTop: '1px solid var(--border)',
    display: 'flex', gap: 10, alignItems: 'flex-end',
  },
  textarea: {
    flex: 1, padding: '10px 14px', borderRadius: 10,
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--text)', fontSize: 14, resize: 'none', outline: 'none',
    lineHeight: 1.5,
  },
  sendBtn: {
    padding: '10px 20px', borderRadius: 10, border: 'none',
    background: 'var(--accent)', color: '#fff', cursor: 'pointer',
    fontSize: 14, fontWeight: 500, alignSelf: 'flex-end',
  },
  // Modals (shared with CreateGroupModal)
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  modal: {
    background: 'var(--bg)', borderRadius: 12, width: 480,
    maxWidth: '95vw', border: '1px solid var(--border)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 20px', borderBottom: '1px solid var(--border)',
  },
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text)' },
  closeBtn2: {
    background: 'none', border: 'none', color: 'var(--text-dim)',
    cursor: 'pointer', fontSize: 16,
  },
  label: { fontSize: 13, fontWeight: 500, color: 'var(--text)' },
  input: {
    padding: '7px 11px', borderRadius: 6, border: '1px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text)', fontSize: 13, outline: 'none',
  },
  select: {
    padding: '7px 11px', borderRadius: 6, border: '1px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text)', fontSize: 13, outline: 'none',
  },
  cancelBtn: {
    padding: '7px 16px', borderRadius: 6,
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--text)', cursor: 'pointer', fontSize: 13,
  },
  submitBtn: {
    padding: '7px 16px', borderRadius: 6, border: 'none',
    background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 13,
  },
}
