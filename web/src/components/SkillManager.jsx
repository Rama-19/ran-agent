import { useState, useEffect, useCallback } from 'react'
import api from '../api'

// ─── SKILL.md 模板生成（纯前端）──────────────────────────────────────────────

function buildTemplate(name, description, always, bins, envVars) {
  const binsLine = bins.length
    ? `\n      bins: [${bins.map(b => `"${b}"`).join(', ')}]`
    : ''
  const envLine = envVars.length
    ? `\n      env: [${envVars.map(e => `"${e}"`).join(', ')}]`
    : ''
  const requires = binsLine || envLine ? `\n    requires:${binsLine}${envLine}` : ''

  return `---
name: ${name}
description: "${description}"
metadata:
  openclaw:
    always: ${always}${requires}
---

## 概述

${description}

## 使用说明

在这里描述该 skill 的具体执行逻辑和步骤。

## 参数

<!-- 如果 skill 需要参数，在此列出 -->

## 示例

\`\`\`
示例输入或调用方式
\`\`\`

## 备注

<!-- 其他注意事项 -->
`.trimStart()
}

// ─── 状态标签 ─────────────────────────────────────────────────────────────────

function Badge({ label, color }) {
  return (
    <span style={{
      border: `1px solid ${color}`, color, borderRadius: 4,
      padding: '1px 6px', fontSize: 10, fontWeight: 600,
    }}>{label}</span>
  )
}

// ─── 新增 Skill 弹窗 ──────────────────────────────────────────────────────────

function AddSkillModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [always, setAlways] = useState(true)
  const [bins, setBins] = useState('')
  const [envVars, setEnvVars] = useState('')
  const [content, setContent] = useState('')
  const [tab, setTab] = useState('form')  // 'form' | 'preview'
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const preview = buildTemplate(
    name || 'my-skill',
    description || '描述此 skill 的功能',
    always,
    bins.split(',').map(s => s.trim()).filter(Boolean),
    envVars.split(',').map(s => s.trim()).filter(Boolean),
  )

  const submit = async () => {
    if (!name.trim()) return setError('name 不能为空')
    if (!/^[a-z0-9_-]+$/.test(name)) return setError('name 只能包含小写字母、数字、_ 和 -')
    setSaving(true)
    setError('')
    try {
      await api.createSkill(name.trim(), tab === 'preview' ? content || preview : preview)
      onCreated()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={ms.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={ms.modal}>
        <div style={ms.header}>
          <span style={ms.title}>⚡ 新增 Skill</span>
          <button style={ms.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div style={ms.tabs}>
          {[['form', '配置'], ['preview', '编辑 SKILL.md']].map(([id, label]) => (
            <button key={id}
              style={{ ...ms.tab, ...(tab === id ? ms.tabActive : {}) }}
              onClick={() => { setTab(id); if (id === 'preview') setContent(preview) }}
            >{label}</button>
          ))}
        </div>

        {tab === 'form' ? (
          <div style={ms.body}>
            <label style={ms.label}>Name <span style={ms.hint}>(slug: 小写字母/数字/-/_)</span></label>
            <input style={ms.input} value={name} onChange={e => setName(e.target.value)} placeholder="my-skill" />

            <label style={ms.label}>Description</label>
            <input style={ms.input} value={description} onChange={e => setDescription(e.target.value)} placeholder="简短描述此 skill 的功能" />

            <label style={ms.label}>Required Bins <span style={ms.hint}>(逗号分隔，可选)</span></label>
            <input style={ms.input} value={bins} onChange={e => setBins(e.target.value)} placeholder="python, node" />

            <label style={ms.label}>Required Env Vars <span style={ms.hint}>(逗号分隔，可选)</span></label>
            <input style={ms.input} value={envVars} onChange={e => setEnvVars(e.target.value)} placeholder="API_KEY, TOKEN" />

            <label style={{ ...ms.label, display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={always} onChange={e => setAlways(e.target.checked)}
                style={{ accentColor: 'var(--accent)' }} />
              Always enabled（无论环境条件）
            </label>

            <details style={ms.previewBox}>
              <summary style={{ cursor: 'pointer', color: 'var(--text-dim)', fontSize: 12 }}>预览 SKILL.md</summary>
              <pre style={ms.pre}>{preview}</pre>
            </details>
          </div>
        ) : (
          <div style={ms.body}>
            <label style={ms.label}>直接编辑 SKILL.md 内容</label>
            <textarea
              style={ms.textarea}
              value={content || preview}
              onChange={e => setContent(e.target.value)}
              rows={18}
              spellCheck={false}
            />
          </div>
        )}

        {error && <p style={ms.error}>{error}</p>}

        <div style={ms.footer}>
          <button style={ms.cancelBtn} onClick={onClose}>取消</button>
          <button style={ms.saveBtn} onClick={submit} disabled={saving || !name}>
            {saving ? '创建中…' : '创建 Skill'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Skill 列表项 ─────────────────────────────────────────────────────────────

function SkillItem({ skill, selected, onSelect, onToggle }) {
  return (
    <div
      style={{ ...ss.item, ...(selected ? ss.itemSelected : {}) }}
      onClick={onSelect}
    >
      <div style={ss.itemTop}>
        <span style={ss.itemName}>{skill.name}</span>
        <button
          style={{ ...ss.toggle, color: skill.enabled ? 'var(--green)' : 'var(--text-dim)' }}
          onClick={e => { e.stopPropagation(); onToggle() }}
          title={skill.enabled ? '点击禁用' : '点击启用'}
        >
          {skill.enabled ? '● 启用' : '○ 禁用'}
        </button>
      </div>
      <div style={ss.itemDesc}>{skill.description}</div>
      <div style={ss.itemBadges}>
        {skill.eligible
          ? <Badge label="可用" color="var(--green)" />
          : <Badge label="不可用" color="var(--text-dim)" />
        }
        {skill.has_readme && <Badge label="README" color="var(--accent)" />}
        {skill.deletable && <Badge label="可编辑" color="var(--yellow)" />}
      </div>
    </div>
  )
}

// ─── Skill 详情面板 ───────────────────────────────────────────────────────────

function SkillDetail({ skill, onUpdated, onDeleted, onToggle }) {
  const [tab, setTab] = useState('skillmd')
  const [content, setContent] = useState(skill.content)
  const [readmeContent, setReadmeContent] = useState(skill.readme || '')
  const [saving, setSaving] = useState(false)
  const [savingReadme, setSavingReadme] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [msg, setMsg] = useState('')

  // skill 切换时重置
  useEffect(() => {
    setContent(skill.content)
    setReadmeContent(skill.readme || '')
    setMsg('')
  }, [skill.name])

  const saveSkillMd = async () => {
    setSaving(true); setMsg('')
    try {
      await api.updateSkill(skill.name, content)
      setMsg('✓ SKILL.md 已保存')
      onUpdated()
    } catch (e) { setMsg(`✗ ${e.message}`) }
    finally { setSaving(false) }
  }

  const saveReadme = async () => {
    setSavingReadme(true); setMsg('')
    try {
      await api.saveReadme(skill.name, readmeContent)
      setMsg('✓ README.md 已保存')
      onUpdated()
    } catch (e) { setMsg(`✗ ${e.message}`) }
    finally { setSavingReadme(false) }
  }

  const genReadme = async () => {
    setGenerating(true); setMsg('正在生成 README.md…')
    try {
      const res = await api.generateReadme(skill.name)
      setReadmeContent(res.readme)
      setTab('readme')
      setMsg('✓ README.md 已生成并保存')
      onUpdated()
    } catch (e) { setMsg(`✗ ${e.message}`) }
    finally { setGenerating(false) }
  }

  const handleDelete = async () => {
    if (!window.confirm(`确定删除 skill "${skill.name}"？此操作不可恢复。`)) return
    try {
      await api.deleteSkill(skill.name)
      onDeleted()
    } catch (e) { setMsg(`✗ ${e.message}`) }
  }

  return (
    <div style={ds.wrap}>
      {/* Header */}
      <div style={ds.header}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={ds.name}>{skill.name}</div>
          <div style={ds.desc}>{skill.description}</div>
          <div style={ds.meta}>
            <span style={ds.loc} title={skill.location}>📁 {skill.location}</span>
          </div>
        </div>
        <div style={ds.actions}>
          <button
            style={{ ...ds.toggleBtn, color: skill.enabled ? 'var(--green)' : 'var(--text-dim)', borderColor: skill.enabled ? 'var(--green)' : 'var(--border)' }}
            onClick={onToggle}
          >
            {skill.enabled ? '● 启用中' : '○ 已禁用'}
          </button>
          {skill.deletable && (
            <button style={ds.deleteBtn} onClick={handleDelete}>🗑 删除</button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={ds.tabs}>
        {[['skillmd', 'SKILL.md'], ['readme', 'README.md']].map(([id, label]) => (
          <button key={id}
            style={{ ...ds.tab, ...(tab === id ? ds.tabActive : {}) }}
            onClick={() => setTab(id)}
          >{label}</button>
        ))}
        <button
          style={ds.genBtn}
          onClick={genReadme}
          disabled={generating}
          title="用 LLM 自动生成 README.md"
        >
          {generating ? '⏳ 生成中…' : '✨ 生成 README'}
        </button>
      </div>

      {/* Content */}
      <div style={ds.editorWrap}>
        {tab === 'skillmd' ? (
          <textarea
            style={ds.editor}
            value={content}
            onChange={e => setContent(e.target.value)}
            spellCheck={false}
          />
        ) : (
          <textarea
            style={ds.editor}
            value={readmeContent}
            onChange={e => setReadmeContent(e.target.value)}
            placeholder="暂无 README.md，可点击「✨ 生成 README」自动生成，或手动编辑。"
            spellCheck={false}
          />
        )}
      </div>

      {/* Footer */}
      <div style={ds.footer}>
        {msg && (
          <span style={{ fontSize: 13, color: msg.startsWith('✓') ? 'var(--green)' : msg.startsWith('正') ? 'var(--yellow)' : 'var(--red)' }}>
            {msg}
          </span>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {tab === 'skillmd' ? (
            <>
              <button style={ds.resetBtn} onClick={() => setContent(skill.content)}>重置</button>
              <button style={ds.saveBtn} onClick={saveSkillMd} disabled={saving}>
                {saving ? '保存中…' : '保存 SKILL.md'}
              </button>
            </>
          ) : (
            <>
              <button style={ds.resetBtn} onClick={() => setReadmeContent(skill.readme || '')}>重置</button>
              <button style={ds.saveBtn} onClick={saveReadme} disabled={savingReadme}>
                {savingReadme ? '保存中…' : '保存 README.md'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── 主组件 ───────────────────────────────────────────────────────────────────

export default function SkillManager() {
  const [skills, setSkills] = useState([])
  const [selected, setSelected] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')  // 'all' | 'enabled' | 'disabled'

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getAllSkills()
      setSkills(data)
      // 如果当前选中的 skill 有更新，刷新详情
      setSelected(prev => prev ? (data.find(s => s.name === prev.name) || null) : null)
    } catch (e) {
      console.error('load skills failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = skills.filter(s => {
    const q = search.toLowerCase()
    const matchSearch = !q || s.name.includes(q) || s.description.toLowerCase().includes(q)
    const matchFilter =
      filter === 'all' ||
      (filter === 'enabled' && s.enabled) ||
      (filter === 'disabled' && !s.enabled)
    return matchSearch && matchFilter
  })

  return (
    <div style={root.wrap}>
      {/* 左侧列表 */}
      <div style={root.left}>
        <div style={root.toolbar}>
          <input
            style={root.search}
            placeholder="搜索 skill…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <button style={root.addBtn} onClick={() => setShowAdd(true)}>+ 新增</button>
        </div>

        <div style={root.filterRow}>
          {[['all', `全部 (${skills.length})`], ['enabled', '启用'], ['disabled', '禁用']].map(([id, label]) => (
            <button key={id}
              style={{ ...root.filterBtn, ...(filter === id ? root.filterActive : {}) }}
              onClick={() => setFilter(id)}
            >{label}</button>
          ))}
        </div>

        <div style={root.list}>
          {loading ? (
            <p style={root.dim}>加载中…</p>
          ) : filtered.length === 0 ? (
            <p style={root.dim}>未找到匹配的 skill</p>
          ) : (
            filtered.map(s => (
              <SkillItem
                key={s.name}
                skill={s}
                selected={selected?.name === s.name}
                onSelect={() => setSelected(s)}
                onToggle={async () => {
                  await api.toggleSkill(s.name, !s.enabled)
                  await load()
                }}
              />
            ))
          )}
        </div>
      </div>

      {/* 右侧详情 */}
      <div style={root.right}>
        {selected ? (
          <SkillDetail
            key={selected.name}
            skill={selected}
            onUpdated={load}
            onDeleted={() => { setSelected(null); load() }}
            onToggle={async () => {
              await api.toggleSkill(selected.name, !selected.enabled)
              await load()
            }}
          />
        ) : (
          <div style={root.empty}>
            <div style={{ fontSize: 32, marginBottom: 10 }}>⚡</div>
            <div>选择一个 skill 查看详情</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>
              或点击「+ 新增」创建新的 skill
            </div>
          </div>
        )}
      </div>

      {showAdd && (
        <AddSkillModal
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); load() }}
        />
      )}
    </div>
  )
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const root = {
  wrap: { display: 'flex', height: '100%', overflow: 'hidden' },
  left: {
    width: 240, minWidth: 200, borderRight: '1px solid var(--border)',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
  },
  right: { flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' },
  toolbar: { display: 'flex', gap: 6, padding: '10px 10px 6px', flexShrink: 0 },
  search: {
    flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 5, padding: '5px 8px', fontSize: 12, outline: 'none',
  },
  addBtn: {
    background: 'var(--accent)', color: '#fff', border: 'none',
    borderRadius: 5, padding: '5px 10px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  filterRow: { display: 'flex', gap: 4, padding: '0 10px 8px', flexShrink: 0 },
  filterBtn: {
    flex: 1, background: 'transparent', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 4, padding: '3px 0', fontSize: 11, cursor: 'pointer',
  },
  filterActive: { background: 'var(--surface2)', color: 'var(--text)', borderColor: 'var(--accent)' },
  list: { flex: 1, overflowY: 'auto', padding: '0 8px 8px', display: 'flex', flexDirection: 'column', gap: 6 },
  dim: { color: 'var(--text-dim)', fontSize: 12, textAlign: 'center', padding: 16 },
  empty: {
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    color: 'var(--text-dim)', fontSize: 14,
  },
}

const ss = {
  item: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    borderRadius: 7, padding: '8px 10px', cursor: 'pointer',
    transition: 'border-color .15s',
  },
  itemSelected: { borderColor: 'var(--accent)', background: 'var(--surface)' },
  itemTop: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  itemName: { fontWeight: 600, fontSize: 13, color: 'var(--text)' },
  itemDesc: { fontSize: 11, color: 'var(--text-dim)', margin: '3px 0' },
  itemBadges: { display: 'flex', gap: 4 },
  toggle: { background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600 },
}

const ds = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'flex-start', gap: 12,
    padding: '14px 16px 10px', borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  name: { fontWeight: 700, fontSize: 16 },
  desc: { color: 'var(--text-dim)', fontSize: 12, marginTop: 2 },
  meta: { marginTop: 4 },
  loc: { fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--mono)' },
  actions: { display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 },
  toggleBtn: {
    background: 'transparent', border: '1px solid', borderRadius: 5,
    padding: '4px 10px', fontSize: 11, fontWeight: 600, cursor: 'pointer',
  },
  deleteBtn: {
    background: 'transparent', border: '1px solid var(--red)', color: 'var(--red)',
    borderRadius: 5, padding: '4px 10px', fontSize: 11, cursor: 'pointer',
  },
  tabs: {
    display: 'flex', alignItems: 'center', gap: 4,
    padding: '8px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  tab: {
    background: 'transparent', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 5, padding: '5px 12px',
    fontSize: 12, cursor: 'pointer',
  },
  tabActive: { background: 'var(--surface2)', color: 'var(--text)', borderColor: 'var(--accent)' },
  genBtn: {
    marginLeft: 'auto', background: 'var(--surface2)', border: '1px solid var(--purple)',
    color: 'var(--purple)', borderRadius: 5, padding: '5px 12px',
    fontSize: 12, fontWeight: 600, cursor: 'pointer',
  },
  editorWrap: { flex: 1, overflow: 'hidden', padding: '10px 16px 0' },
  editor: {
    width: '100%', height: '100%', background: 'var(--bg)',
    border: '1px solid var(--border)', color: 'var(--text)',
    borderRadius: 6, padding: '10px 12px', fontSize: 12,
    fontFamily: 'var(--mono)', resize: 'none', outline: 'none',
    lineHeight: 1.6,
  },
  footer: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '10px 16px', borderTop: '1px solid var(--border)', flexShrink: 0,
  },
  saveBtn: {
    background: 'var(--accent)', color: '#fff', border: 'none',
    borderRadius: 6, padding: '6px 16px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
  },
  resetBtn: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 6, padding: '6px 12px', fontSize: 12, cursor: 'pointer',
  },
}

// ── AddSkillModal styles ──────────────────────────────────────────────────────

const ms = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
  },
  modal: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 12, width: 560, maxWidth: '95vw', maxHeight: '90vh',
    display: 'flex', flexDirection: 'column', boxShadow: '0 20px 60px rgba(0,0,0,.5)',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 18px', borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  title: { fontWeight: 700, fontSize: 15 },
  closeBtn: { background: 'transparent', border: 'none', color: 'var(--text-dim)', fontSize: 16, cursor: 'pointer' },
  tabs: {
    display: 'flex', gap: 4, padding: '8px 18px',
    borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  tab: {
    background: 'transparent', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 5, padding: '4px 12px', fontSize: 12, cursor: 'pointer',
  },
  tabActive: { background: 'var(--surface2)', color: 'var(--text)', borderColor: 'var(--accent)' },
  body: {
    padding: '14px 18px', display: 'flex', flexDirection: 'column',
    gap: 8, overflowY: 'auto', flex: 1,
  },
  label: { color: 'var(--text-dim)', fontSize: 12, fontWeight: 600 },
  hint: { fontWeight: 400, color: 'var(--text-dim)', opacity: .7 },
  input: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 6, padding: '7px 10px', fontSize: 13, outline: 'none',
  },
  previewBox: {
    background: 'var(--bg)', border: '1px solid var(--border)',
    borderRadius: 6, padding: '8px 10px', marginTop: 4,
  },
  pre: { fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 6, whiteSpace: 'pre-wrap' },
  textarea: {
    width: '100%', background: 'var(--bg)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: 6, padding: '8px 10px',
    fontSize: 12, fontFamily: 'var(--mono)', resize: 'vertical', outline: 'none', lineHeight: 1.6,
  },
  error: { color: 'var(--red)', fontSize: 12, padding: '0 18px' },
  footer: {
    display: 'flex', justifyContent: 'flex-end', gap: 8,
    padding: '12px 18px', borderTop: '1px solid var(--border)', flexShrink: 0,
  },
  cancelBtn: {
    background: 'var(--surface2)', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: 6, padding: '7px 16px', fontSize: 13, cursor: 'pointer',
  },
  saveBtn: {
    background: 'var(--accent)', color: '#fff', border: 'none',
    borderRadius: 6, padding: '7px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
  },
}
