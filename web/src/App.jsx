import { useState, useEffect, useCallback, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import api from './api'
import PlanCard from './components/PlanCard'
import OptionsPanel from './components/OptionsPanel'
import BlockedBanner from './components/BlockedBanner'
import MemoryPanel from './components/MemoryPanel'
import SettingsModal from './components/SettingsModal'
import SkillManager from './components/SkillManager'
import ConversationPanel from './components/ConversationPanel'
import AuthModal from './components/AuthModal'
import GroupChatPanel from './components/GroupChatPanel'

// ─── 默认选项 ────────────────────────────────────────────────────────────────
const DEFAULT_OPTIONS = {
  web_mode: 'off',
  deep_think: 0,
  require_citations: false,
  max_search_rounds: 3,
}

// ─── 从 agent 消息文本里提取写入的文件路径 ────────────────────────────────────
const FILE_WRITTEN_RE = /File written:\s*(.+)/g

function extractWrittenFiles(text) {
  const files = []
  let m
  FILE_WRITTEN_RE.lastIndex = 0
  while ((m = FILE_WRITTEN_RE.exec(text)) !== null) {
    const p = m[1].trim()
    if (p) files.push(p)
  }
  return files
}

function DownloadButton({ path }) {
  const name = path.split(/[\\/]/).pop()
  const href = `/api/download?path=${encodeURIComponent(path)}`
  return (
    <a
      href={href}
      download={name}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        marginTop: 6, padding: '3px 10px',
        background: 'var(--surface)', border: '1px solid var(--border)',
        borderRadius: 5, color: 'var(--accent)', fontSize: 12,
        textDecoration: 'none', cursor: 'pointer',
      }}
      title={path}
    >
      ↓ {name}
    </a>
  )
}

// ─── 代码块（带复制按钮）────────────────────────────────────────────────────────
function CodeBlock({ node, inline, className, children, ...props }) {
  const [copied, setCopied] = useState(false)
  const code = String(children).replace(/\n$/, '')
  const lang = (className || '').replace('language-', '') || ''

  if (inline) {
    return <code style={styles.inlineCode} {...props}>{children}</code>
  }

  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div style={styles.codeWrapper}>
      <div style={styles.codeHeader}>
        <span style={styles.codeLang}>{lang || 'code'}</span>
        <button style={styles.codeCopyBtn} onClick={copy}>
          {copied ? '✓ 已复制' : '复制'}
        </button>
      </div>
      <pre style={styles.codePre}><code {...props}>{code}</code></pre>
    </div>
  )
}

const MD_COMPONENTS = { code: CodeBlock }

// ─── 消息类型 ─────────────────────────────────────────────────────────────────
function Message({ msg, onDelete, onCopy }) {
  const [hovered, setHovered] = useState(false)
  const isUser = msg.role === 'user'
  const isError = msg.role === 'error'
  const isInfo = msg.role === 'info'
  const canAct = isUser || msg.role === 'agent' || msg.role === 'assistant'
  const writtenFiles = (!isUser && !isError && !isInfo) ? extractWrittenFiles(msg.text || '') : []

  return (
    <div
      style={{
        ...styles.msg,
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        background: isUser ? 'var(--accent-dim)' : isError ? 'var(--error-bg)' : 'var(--surface2)',
        borderColor: isUser ? 'var(--accent)' : isError ? 'var(--red)' : 'var(--border)',
        color: isError ? 'var(--red)' : isInfo ? 'var(--text-dim)' : 'var(--text)',
        maxWidth: isUser ? '70%' : '100%',
        position: 'relative',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {!isUser && (
        <div style={styles.msgRole}>
          {isError ? '⚠ 错误' : isInfo ? 'ℹ 提示' : '🤖 Agent'}
        </div>
      )}
      {isUser || isInfo || isError ? (
        <pre style={styles.msgText}>{msg.text}</pre>
      ) : (
        <div className="mdText" style={styles.mdText}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>{msg.text}</ReactMarkdown>
        </div>
      )}
      {writtenFiles.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
          {writtenFiles.map((p, i) => <DownloadButton key={i} path={p} />)}
        </div>
      )}
      {msg.usage && (
        <div style={styles.usageLine}>
          ↑{msg.usage.input.toLocaleString()} ↓{msg.usage.output.toLocaleString()} tokens
          {msg.usage.output > 0 && (
            <span style={{ marginLeft: 8, color: 'var(--accent)', opacity: 0.8 }}>
              ≈¥{((msg.usage.input * 2 + msg.usage.output * 8) / 1e6 * 7.3).toFixed(5)}
            </span>
          )}
        </div>
      )}
      {hovered && canAct && (
        <div style={{
          ...styles.msgActions,
          ...(isUser ? { left: 4, right: 'auto' } : { right: 4, left: 'auto' }),
        }}>
          <button style={styles.actionBtn} onClick={() => onCopy(msg.text)} title="复制">⎘</button>
          <button style={styles.actionBtn} onClick={() => onDelete(msg.id)} title="删除">✕</button>
        </div>
      )}
    </div>
  )
}

// ─── 主应用 ───────────────────────────────────────────────────────────────────
export default function App() {
  const [skills, setSkills] = useState([])
  const [plans, setPlans] = useState([])
  const [pending, setPending] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [options, setOptions] = useState(DEFAULT_OPTIONS)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState('auto')   // 'auto' | 'plan' | 'ask'
  const [tab, setTab] = useState('chat')     // 'chat' | 'plans' | 'memory' | 'skills'
  const tabRef = useRef('chat')
  // keep tabRef in sync so callbacks don't get stale closures
  const [skillsLoading, setSkillsLoading] = useState(true)
  const [memory, setMemory] = useState({})
  const [showSettings, setShowSettings] = useState(false)
  const [attachments, setAttachments] = useState([])   // [{name, path, size, type, preview?}]
  const [uploading, setUploading] = useState(false)
  const bottomRef = useRef(null)
  const fileInputRef = useRef(null)

  // ── 主题 ───────────────────────────────────────────────────────────────────
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
  }, [])

  // ── 认证状态 ───────────────────────────────────────────────────────────────
  const [user, setUser] = useState(null)           // null = 未登录
  const [authChecked, setAuthChecked] = useState(false)  // 防闪烁

  // ── 模型信息 ───────────────────────────────────────────────────────────────
  const [providerInfo, setProviderInfo] = useState(null)

  // ── 会话管理 ───────────────────────────────────────────────────────────────
  const [conversations, setConversations] = useState([])
  const [currentConvId, setCurrentConvId] = useState(null)
  const currentConvIdRef = useRef(null)
  currentConvIdRef.current = currentConvId
  tabRef.current = tab

  // ── 启动时验证 token ───────────────────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (!token) {
      setAuthChecked(true)
      return
    }
    api.getMe()
      .then(u => {
        setUser(u)
        setAuthChecked(true)
      })
      .catch(() => {
        localStorage.removeItem('auth_token')
        setAuthChecked(true)
      })
  }, [])

  // ── 登录成功回调 ───────────────────────────────────────────────────────────
  const handleAuthSuccess = useCallback((token, u) => {
    setUser(u)
  }, [])

  // ── 登出 ───────────────────────────────────────────────────────────────────
  const handleLogout = useCallback(() => {
    localStorage.removeItem('auth_token')
    setUser(null)
    setMessages([])
    setConversations([])
    setCurrentConvId(null)
    setPlans([])
    setMemory({})
  }, [])

  // ── 加载 skills & session ──────────────────────────────────────────────────
  const refresh = useCallback(async () => {
    try {
      const [sk, pl, sess, mem] = await Promise.all([
        api.getSkills(),
        api.getPlans(),
        api.getSession(),
        api.getMemory(),
      ])
      setSkills(sk)
      setPlans(pl)
      setPending(sess.pending)
      setMemory(mem)
    } catch {
      /* ignore on startup */
    } finally {
      setSkillsLoading(false)
    }
  }, [])

  // ── 加载会话列表 ────────────────────────────────────────────────────────────
  const loadConversations = useCallback(async () => {
    try {
      const convs = await api.getConversations()
      setConversations(convs)
      return convs
    } catch {
      return []
    }
  }, [])

  // ── 切换会话（加载消息） ────────────────────────────────────────────────────
  const selectConversation = useCallback(async (convId) => {
    if (convId === currentConvIdRef.current) return
    try {
      const data = await api.getConversation(convId)
      setCurrentConvId(convId)
      if (tabRef.current !== 'group') {
        setMessages(data.messages.map(m => ({ id: m.id, role: m.role, text: m.text })))
        setTab('chat')
      }
    } catch {
      /* ignore */
    }
  }, [])

  // ── 新建会话 ────────────────────────────────────────────────────────────────
  const createConversation = useCallback(async () => {
    const conv = await api.createConversation()
    setMessages([])
    setCurrentConvId(conv.id)
    setConversations(prev => [conv, ...prev])
    setTab('chat')
  }, [])

  // ── 删除会话 ────────────────────────────────────────────────────────────────
  const deleteConversation = useCallback(async (convId) => {
    await api.deleteConversation(convId)
    const next = conversations.filter(c => c.id !== convId)
    setConversations(next)
    if (convId === currentConvIdRef.current) {
      if (next.length > 0) {
        await selectConversation(next[0].id)
      } else {
        setCurrentConvId(null)
        setMessages([])
      }
    }
  }, [conversations, selectConversation])

  // ── 重命名会话 ──────────────────────────────────────────────────────────────
  const renameConversation = useCallback(async (convId, title) => {
    await api.renameConversation(convId, title)
    setConversations(prev => prev.map(c => c.id === convId ? { ...c, title } : c))
  }, [])

  // ── 加载当前模型信息 ────────────────────────────────────────────────────────
  const loadProviderInfo = useCallback(async () => {
    try {
      const info = await api.getCurrentModel()
      setProviderInfo(info)
    } catch { /* ignore */ }
  }, [])

  // ── 切换 Provider ────────────────────────────────────────────────────────────
  const switchProvider = useCallback(async (name) => {
    try {
      await api.updateUserConfig({ name })
      await loadProviderInfo()
    } catch { /* ignore */ }
  }, [loadProviderInfo])

  // ── 向当前会话追加消息（后台静默），localId 用于回填服务端 id ──────────────
  const saveMsg = useCallback((role, text, localId) => {
    const id = currentConvIdRef.current
    if (!id) return
    api.appendMessage(id, role, text).then(res => {
      if (res.id && localId) {
        setMessages(prev => prev.map(m => m.id === localId ? { ...m, id: res.id } : m))
      }
      setConversations(prev => prev.map(c =>
        c.id === id
          ? {
              ...c,
              message_count: c.message_count + 1,
              title: (role === 'user' && c.title === '新会话')
                ? text.slice(0, 30) + (text.length > 30 ? '…' : '')
                : c.title,
            }
          : c
      ))
    }).catch(() => {})
  }, [])

  // 登录后初始化数据
  useEffect(() => {
    if (!user) return
    refresh()
    loadProviderInfo()
    loadConversations().then(convs => {
      if (convs.length > 0) selectConversation(convs[0].id)
    })
  }, [user, refresh, loadProviderInfo, loadConversations, selectConversation])

  // ── 滚动到底部 ─────────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── 推送消息（仅更新 UI），返回本地 id 供后续回填 ──────────────────────────
  const push = (role, text, extra = {}) => {
    const localId = `local_${Date.now()}_${Math.random()}`
    setMessages((prev) => [...prev, { id: localId, role, text, ...extra }])
    return localId
  }

  // ── 发送 ──────────────────────────────────────────────────────────────────
  const send = useCallback(async () => {
    const task = input.trim()
    if ((!task && attachments.length === 0) || loading) return

    // 若没有当前会话，自动新建一个
    let convId = currentConvIdRef.current
    if (!convId) {
      const conv = await api.createConversation()
      convId = conv.id
      setCurrentConvId(convId)
      setConversations(prev => [conv, ...prev])
    }

    const fileNote = attachments.length > 0
      ? '\n\n[已上传文件]\n' + attachments.map(a => `- ${a.name}（路径: ${a.path}）`).join('\n')
      : ''
    const fullTask = (task + fileNote).trim()

    setInput('')
    setAttachments(prev => { prev.forEach(a => { if (a.preview) URL.revokeObjectURL(a.preview) }); return [] })
    setLoading(true)
    const userLocalId = push('user', fullTask)
    saveMsg('user', fullTask, userLocalId)

    try {
      if (mode === 'auto') {
        push('info', '正在生成计划并执行…')
        const res = await api.auto(fullTask, options, convId)
        const lastResult = res.results[res.results.length - 1]
        if (lastResult) {
          const agentLocalId = push('agent', lastResult.message, { usage: res.usage })
          saveMsg('agent', lastResult.message, agentLocalId)
          if (lastResult.need_input) setPending(lastResult.need_input)
        }
        await refresh()
        setTab('plans')

      } else if (mode === 'plan') {
        push('info', '正在生成候选计划…')
        const planList = await api.createPlan(fullTask, options)
        const msg = `已生成 ${planList.length} 个计划，可在「计划」标签查看并执行。`
        const agentLocalId = push('agent', msg)
        saveMsg('agent', msg, agentLocalId)
        await refresh()
        setTab('plans')

      } else if (mode === 'ask') {
        push('info', '正在直接执行…')
        const res = await api.ask(fullTask, options, convId)
        const agentLocalId = push('agent', res.result, { usage: res.usage })
        saveMsg('agent', res.result, agentLocalId)
      }
    } catch (e) {
      push('error', e.message)
    } finally {
      setLoading(false)
    }
  }, [input, attachments, loading, mode, options, refresh, saveMsg])

  // ── 执行指定计划 ──────────────────────────────────────────────────────────
  const runPlan = useCallback(async (planId) => {
    setLoading(true)
    push('info', `执行计划 ${planId}…`)
    try {
      const res = await api.runPlan(planId)
      push('agent', res.message)
      if (res.need_input) setPending(res.need_input)
      await refresh()
    } catch (e) {
      push('error', e.message)
    } finally {
      setLoading(false)
    }
  }, [refresh])

  // ── 删除单个计划 ──────────────────────────────────────────────────────────
  const deletePlan = useCallback(async (planId) => {
    try {
      await api.deletePlan(planId)
      setPlans(prev => prev.filter(p => p.id !== planId))
    } catch (e) {
      push('error', e.message)
    }
  }, [])

  // ── 回复 blocked ──────────────────────────────────────────────────────────
  const handleReply = useCallback(async (reply) => {
    setLoading(true)
    const userLocalId = push('user', `/reply ${reply}`)
    saveMsg('user', `/reply ${reply}`, userLocalId)
    try {
      const res = await api.reply(reply)
      const agentLocalId = push('agent', res.message)
      saveMsg('agent', res.message, agentLocalId)
      if (res.need_input) setPending(res.need_input)
      else setPending(null)
      await refresh()
    } catch (e) {
      push('error', e.message)
    } finally {
      setLoading(false)
    }
  }, [refresh, saveMsg])

  // ── 取消 blocked ──────────────────────────────────────────────────────────
  const handleCancel = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.cancel()
      push('info', res.message)
      setPending(null)
      await refresh()
    } catch (e) {
      push('error', e.message)
    } finally {
      setLoading(false)
    }
  }, [refresh])

  // ── 删除消息 ──────────────────────────────────────────────────────────────
  const handleDeleteMessage = useCallback(async (msgId) => {
    const convId = currentConvIdRef.current
    if (!convId) return
    try {
      const res = await api.deleteMessage(convId, msgId)
      const deletedIds = new Set(res.deleted)
      setMessages(prev => prev.filter(m => !deletedIds.has(m.id)))
      setConversations(prev => prev.map(c =>
        c.id === convId ? { ...c, message_count: Math.max(0, c.message_count - deletedIds.size) } : c
      ))
    } catch {
      // 本地消息（尚未保存到服务端）直接从 UI 移除
      setMessages(prev => prev.filter(m => m.id !== msgId))
    }
  }, [])

  // ── 复制消息 ──────────────────────────────────────────────────────────────
  const handleCopy = useCallback((text) => {
    navigator.clipboard.writeText(text).catch(() => {})
  }, [])

  // ── 上传文件 ──────────────────────────────────────────────────────────────
  const handleFileChange = useCallback(async (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    e.target.value = ''
    setUploading(true)
    try {
      const results = await Promise.all(files.map(f => api.uploadFile(f)))
      setAttachments(prev => [
        ...prev,
        ...results.map((r, i) => ({
          ...r,
          preview: files[i].type.startsWith('image/') ? URL.createObjectURL(files[i]) : null,
        })),
      ])
    } catch (e) {
      push('error', `上传失败: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }, [])

  const removeAttachment = useCallback((idx) => {
    setAttachments(prev => {
      const next = [...prev]
      if (next[idx]?.preview) URL.revokeObjectURL(next[idx].preview)
      next.splice(idx, 1)
      return next
    })
  }, [])

  // ── 键盘 ──────────────────────────────────────────────────────────────────
  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  // ── Auth gate ──────────────────────────────────────────────────────────────
  if (!authChecked) {
    return (
      <div style={styles.loadingScreen}>
        <span style={styles.loadingSpinner}>◌</span>
      </div>
    )
  }

  if (!user) {
    return <AuthModal onSuccess={handleAuthSuccess} />
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={styles.root}>
      {/* ── Header ── */}
      <header style={styles.header}>
        <span style={styles.logo}>✦ Ran Agent</span>
        <span style={styles.headerDim}></span>
        {providerInfo && (
          <span style={styles.modelPill} title="当前模型，点击设置更换" onClick={() => setShowSettings(true)}>
            {providerInfo.provider} · {providerInfo.model}
          </span>
        )}
        {pending && (
          <span style={styles.pendingPill}>⊘ 等待补充</span>
        )}
        <div style={styles.headerRight}>
          <span style={styles.userEmail}>{user.email}</span>
          <button style={styles.refreshBtn} onClick={refresh} title="刷新">↺</button>
          <button style={styles.refreshBtn} onClick={toggleTheme} title={theme === 'dark' ? '切换浅色主题' : '切换深色主题'}>
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          <button style={styles.refreshBtn} onClick={() => setShowSettings(true)} title="模型配置">⚙</button>
          <button style={styles.logoutBtn} onClick={handleLogout} title="登出">登出</button>
        </div>
      </header>

      <div style={styles.body}>
        {/* ── 会话列表 ── */}
        <ConversationPanel
          conversations={conversations}
          currentId={currentConvId}
          onCreate={createConversation}
          onSelect={selectConversation}
          onDelete={deleteConversation}
          onRename={renameConversation}
        />


        {/* ── Main ── */}
        <main style={styles.main}>
          {/* Blocked banner */}
          <BlockedBanner
            pending={pending}
            onReply={handleReply}
            onCancel={handleCancel}
            loading={loading}
          />

          {/* Tabs */}
          <div style={styles.tabs}>
            {[
              { id: 'chat', label: '💬 对话' },
              { id: 'group', label: '🤝 多 Agent' },
              { id: 'plans', label: `📋 计划 (${plans.length})` },
              { id: 'memory', label: `🧠 记忆 (${Object.keys(memory).length})` },
              { id: 'skills', label: '⚡ Skills' },
            ].map(({ id, label }) => (
              <button
                key={id}
                style={{ ...styles.tab, ...(tab === id ? styles.tabActive : {}) }}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div style={tab === 'group' ? { ...styles.content, padding: 0, overflow: 'hidden' } : styles.content}>
            {tab === 'group' ? (
              <GroupChatPanel
                convId={currentConvId}
                onConvUpdate={loadConversations}
                onNewConv={(conv) => {
                  setCurrentConvId(conv.id)
                  setConversations(prev => [conv, ...prev])
                }}
              />
            ) : tab === 'chat' ? (
              <div style={styles.chatArea}>
                {messages.length === 0 ? (
                  <div style={styles.empty}>
                    <div style={{ fontSize: 32, marginBottom: 12 }}>⚡</div>
                    <div>输入任务，agent 将自动规划并执行</div>
                    <div style={styles.tips}>
                      <code>/auto</code> 自动计划+执行 &nbsp;|&nbsp;
                      <code>/plan</code> 仅生成计划 &nbsp;|&nbsp;
                      <code>/ask</code> 直接执行
                    </div>
                  </div>
                ) : (
                  messages.map((m) => (
                    <Message key={m.id} msg={m} onDelete={handleDeleteMessage} onCopy={handleCopy} />
                  ))
                )}
                <div ref={bottomRef} />
              </div>
            ) : tab === 'plans' ? (
              <div style={styles.planArea}>
                {plans.length === 0 ? (
                  <div style={styles.empty}>暂无计划，发送任务后自动生成</div>
                ) : (
                  [...plans].reverse().map((p) => (
                    <PlanCard key={p.id} plan={p} onRun={runPlan} onDelete={deletePlan} />
                  ))
                )}
              </div>
            ) : tab === 'skills' ? (
              <div style={{ height: '100%', overflow: 'hidden' }}>
                <SkillManager />
              </div>
            ) : (
              <div style={{ ...styles.planArea }}>
                <MemoryPanel
                  entries={memory}
                  loading={loading}
                  onSet={async (k, v) => {
                    await api.setMemory(k, v)
                    setMemory(await api.getMemory())
                  }}
                  onDelete={async (k) => {
                    await api.deleteMemory(k)
                    setMemory(await api.getMemory())
                  }}
                  onClear={async () => {
                    await api.clearMemory()
                    setMemory({})
                  }}
                />
              </div>
            )}
          </div>

          {/* Input — hidden on group tab */}
          {tab !== 'group' && <div style={styles.inputBox}>
            {/* Mode selector */}
            <div style={styles.modeRow}>
              {[
                { id: 'auto', label: '⚡ Auto', tip: '自动生成计划并执行' },
                { id: 'plan', label: '📋 Plan', tip: '仅生成候选计划' },
                { id: 'ask', label: '🤖 Ask', tip: '跳过 planner，直接执行' },
              ].map((m) => (
                <button
                  key={m.id}
                  title={m.tip}
                  style={{ ...styles.modeBtn, ...(mode === m.id ? styles.modeBtnActive : {}) }}
                  onClick={() => setMode(m.id)}
                >
                  {m.label}
                </button>
              ))}
              <div style={styles.providerRow}>
                {[
                  { id: 'openai', label: 'OpenAI' },
                  { id: 'anthropic', label: 'Anthropic' },
                  { id: 'ollama', label: 'Ollama' },
                ].map(p => (
                  <button
                    key={p.id}
                    title={`切换到 ${p.id}`}
                    style={{
                      ...styles.modeBtn,
                      ...(providerInfo?.provider === p.id ? styles.modeBtnActive : {}),
                    }}
                    onClick={() => switchProvider(p.id)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div style={{ marginLeft: 'auto' }}>
                <OptionsPanel options={options} onChange={setOptions} />
              </div>
            </div>

            {/* Attachment chips */}
            {attachments.length > 0 && (
              <div style={styles.attachRow}>
                {attachments.map((att, i) => (
                  <div key={i} style={styles.attachChip}>
                    {att.preview
                      ? <img src={att.preview} style={styles.attThumb} alt={att.name} />
                      : <span style={styles.attIcon}>📄</span>
                    }
                    <span style={styles.attName} title={att.name}>{att.name}</span>
                    <button style={styles.attRemove} onClick={() => removeAttachment(i)}>✕</button>
                  </div>
                ))}
              </div>
            )}

            {/* Text input */}
            <div style={styles.textRow}>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <button
                style={{ ...styles.uploadBtn, opacity: uploading ? 0.5 : 1 }}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || loading}
                title="上传文件或图片"
              >
                {uploading ? <span style={styles.spinner}>◌</span> : '⊕'}
              </button>
              <textarea
                style={styles.textarea}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder={
                  mode === 'auto' ? '描述你的任务，按 Enter 发送…' :
                  mode === 'plan' ? '描述任务，生成候选计划…' :
                  '直接让 agent 执行任务…'
                }
                rows={2}
                disabled={loading}
              />
              <button
                style={{ ...styles.sendBtn, opacity: loading || (!input.trim() && attachments.length === 0) ? 0.5 : 1 }}
                onClick={send}
                disabled={loading || (!input.trim() && attachments.length === 0)}
              >
                {loading ? (
                  <span style={styles.spinner}>◌</span>
                ) : '▶'}
              </button>
            </div>
          </div>}
        </main>
      </div>
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  )
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = {
  loadingScreen: {
    height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'var(--bg)',
  },
  loadingSpinner: {
    fontSize: 36, color: 'var(--accent)', animation: 'spin 1s linear infinite',
  },
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '0 20px',
    height: 48,
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
  },
  logo: { fontWeight: 700, fontSize: 15, color: 'var(--accent)' },
  headerDim: { color: 'var(--text-dim)', fontSize: 12 },
  modelPill: {
    background: 'var(--surface2)',
    color: 'var(--text-dim)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: '2px 10px',
    fontSize: 11,
    fontWeight: 500,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  pendingPill: {
    marginLeft: 8,
    background: 'var(--pending-bg)',
    color: 'var(--purple)',
    border: '1px solid var(--pending-border)',
    borderRadius: 10,
    padding: '2px 10px',
    fontSize: 12,
    fontWeight: 600,
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  headerRight: {
    marginLeft: 'auto',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  userEmail: {
    color: 'var(--text-dim)',
    fontSize: 12,
    maxWidth: 160,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  refreshBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--text-dim)',
    borderRadius: 6,
    width: 30,
    height: 30,
    fontSize: 16,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoutBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--text-dim)',
    borderRadius: 6,
    padding: '0 10px',
    height: 30,
    fontSize: 12,
    cursor: 'pointer',
  },
  body: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    padding: '16px',
    gap: 12,
  },
  tabs: {
    display: 'flex',
    gap: 4,
    flexShrink: 0,
  },
  tab: {
    background: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--text-dim)',
    borderRadius: 6,
    padding: '6px 14px',
    fontSize: 13,
    cursor: 'pointer',
    fontWeight: 500,
  },
  tabActive: {
    background: 'var(--surface)',
    color: 'var(--text)',
    borderColor: 'var(--accent)',
  },
  content: {
    flex: 1,
    overflow: 'hidden',
    borderRadius: 10,
    border: '1px solid var(--border)',
    background: 'var(--surface)',
  },
  chatArea: {
    height: '100%',
    overflowY: 'auto',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  planArea: {
    height: '100%',
    overflowY: 'auto',
    padding: '16px',
  },
  empty: {
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--text-dim)',
    fontSize: 14,
    gap: 6,
  },
  tips: {
    marginTop: 8,
    fontSize: 12,
    color: 'var(--text-dim)',
  },
  msg: {
    border: '1px solid',
    borderRadius: 8,
    padding: '8px 12px',
  },
  msgRole: {
    fontSize: 11,
    color: 'var(--text-dim)',
    fontWeight: 600,
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  msgText: {
    fontFamily: 'var(--font)',
    fontSize: 13,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    lineHeight: 1.6,
  },
  mdText: {
    fontSize: 13,
    lineHeight: 1.7,
    wordBreak: 'break-word',
  },
  codeWrapper: {
    margin: '8px 0',
    borderRadius: 7,
    border: '1px solid var(--border)',
    overflow: 'hidden',
    background: 'var(--surface)',
  },
  codeHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '4px 12px',
    background: 'var(--surface2)',
    borderBottom: '1px solid var(--border)',
  },
  codeLang: {
    fontSize: 11,
    color: 'var(--text-dim)',
    fontFamily: 'var(--font)',
    textTransform: 'lowercase',
  },
  codeCopyBtn: {
    background: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--text-dim)',
    borderRadius: 4,
    padding: '2px 8px',
    fontSize: 11,
    cursor: 'pointer',
    transition: 'color .15s, border-color .15s',
  },
  codePre: {
    margin: 0,
    padding: '10px 14px',
    overflowX: 'auto',
    fontSize: 12.5,
    lineHeight: 1.55,
    fontFamily: 'var(--font)',
    background: 'var(--surface)',
  },
  inlineCode: {
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 3,
    padding: '1px 5px',
    fontSize: '0.9em',
    fontFamily: 'var(--font)',
  },
  inputBox: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    flexShrink: 0,
  },
  modeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    flexWrap: 'wrap',
  },
  providerRow: {
    display: 'flex',
    gap: 4,
    marginLeft: 8,
    paddingLeft: 8,
    borderLeft: '1px solid var(--border)',
  },
  usageLine: {
    marginTop: 6,
    fontSize: 11,
    color: 'var(--text-dim)',
    opacity: 0.7,
    userSelect: 'none',
  },
  msgActions: {
    position: 'absolute',
    top: 6,
    display: 'flex',
    gap: 4,
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 7,
    padding: '3px 5px',
    zIndex: 10,
    boxShadow: '0 2px 8px rgba(0,0,0,.2)',
  },
  actionBtn: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-dim)',
    cursor: 'pointer',
    fontSize: 15,
    padding: '2px 7px',
    borderRadius: 4,
    lineHeight: 1.4,
    display: 'flex',
    alignItems: 'center',
  },
  modeBtn: {
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    color: 'var(--text-dim)',
    borderRadius: 5,
    padding: '4px 10px',
    fontSize: 12,
    cursor: 'pointer',
    fontWeight: 500,
  },
  modeBtnActive: {
    background: 'var(--accent-dim)',
    border: '1px solid var(--accent)',
    color: 'var(--text)',
  },
  attachRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    padding: '2px 0',
  },
  attachChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    borderRadius: 6,
    padding: '3px 7px',
    fontSize: 12,
    maxWidth: 180,
  },
  attThumb: {
    width: 28,
    height: 28,
    objectFit: 'cover',
    borderRadius: 3,
    flexShrink: 0,
  },
  attIcon: { fontSize: 16, flexShrink: 0 },
  attName: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: 'var(--text)',
  },
  attRemove: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-dim)',
    cursor: 'pointer',
    fontSize: 11,
    padding: '0 2px',
    flexShrink: 0,
  },
  uploadBtn: {
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    color: 'var(--text-dim)',
    borderRadius: 6,
    width: 36,
    height: 40,
    fontSize: 20,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  textRow: {
    display: 'flex',
    gap: 8,
    alignItems: 'flex-end',
  },
  textarea: {
    flex: 1,
    background: 'var(--surface2)',
    border: '1px solid var(--border)',
    color: 'var(--text)',
    borderRadius: 6,
    padding: '8px 10px',
    fontSize: 13,
    resize: 'none',
    outline: 'none',
    fontFamily: 'var(--font)',
    lineHeight: 1.5,
  },
  sendBtn: {
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    width: 40,
    height: 40,
    fontSize: 16,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  spinner: {
    display: 'inline-block',
    animation: 'spin 1s linear infinite',
  },
}
