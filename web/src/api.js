const BASE = '/api'

async function request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }

  const token = localStorage.getItem('auth_token')
  if (token) {
    opts.headers['Authorization'] = `Bearer ${token}`
  }

  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(BASE + path, opts)

  if (res.status === 401) {
    localStorage.removeItem('auth_token')
    window.location.reload()
    throw new Error('未授权，请重新登录')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

const api = {
  // Auth
  register: (email, password) => request('POST', '/auth/register', { email, password }),
  verifyCode: (email, code) => request('POST', '/auth/verify', { email, code }),
  login: (email, password) => request('POST', '/auth/login', { email, password }),
  getMe: () => request('GET', '/auth/me'),
  changePassword: (currentPassword, newPassword) =>
    request('POST', '/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
  forgotPassword: (email) => request('POST', '/auth/forgot-password', { email }),
  resetPassword: (email, code, newPassword) =>
    request('POST', '/auth/reset-password', { email, code, new_password: newPassword }),
  // User-specific provider config
  getUserConfig: (provider) => request('GET', provider ? `/auth/user-config?provider=${provider}` : '/auth/user-config'),
  updateUserConfig: (cfg) => request('POST', '/auth/user-config', cfg),
  // SMTP config (admin)
  getSmtpConfig: () => request('GET', '/auth/smtp-config'),
  updateSmtpConfig: (cfg) => request('POST', '/auth/smtp-config', cfg),

  // Skills (sidebar)
  getSkills: () => request('GET', '/skills'),

  // Skill management
  getAllSkills: () => request('GET', '/skills/all'),
  getSkillDetail: (name) => request('GET', `/skills/${encodeURIComponent(name)}`),
  createSkill: (name, content) => request('POST', '/skills', { name, content }),
  updateSkill: (name, content) => request('PUT', `/skills/${encodeURIComponent(name)}`, { content }),
  toggleSkill: (name, enabled) => request('PATCH', `/skills/${encodeURIComponent(name)}/enabled`, { enabled }),
  deleteSkill: (name) => request('DELETE', `/skills/${encodeURIComponent(name)}`),
  generateReadme: (name) => request('POST', `/skills/${encodeURIComponent(name)}/readme`),
  saveReadme: (name, content) => request('PUT', `/skills/${encodeURIComponent(name)}/readme`, { content }),

  // Plans / session
  getPlans: () => request('GET', '/plans'),
  getPlan: (id) => request('GET', `/plans/${id}`),
  getSession: () => request('GET', '/session'),
  createPlan: (task, options) => request('POST', '/plan', { task, options }),
  runPlan: (planId) => request('POST', `/run/${planId}`),
  auto: (task, options, conv_id) => request('POST', '/auto', { task, options, conv_id }),
  ask: (task, options, conv_id) => request('POST', '/ask', { task, options, conv_id }),
  reply: (reply) => request('POST', '/reply', { reply }),
  cancel: () => request('POST', '/cancel'),
  clearPlans: () => request('DELETE', '/plans'),

  // Memory
  getMemory: () => request('GET', '/memory'),
  setMemory: (key, value) => request('PUT', `/memory/${encodeURIComponent(key)}`, { value }),
  deleteMemory: (key) => request('DELETE', `/memory/${encodeURIComponent(key)}`),
  clearMemory: () => request('DELETE', '/memory'),

  // Config
  getConfig: (provider) => request('GET', provider ? `/config?provider=${provider}` : '/config'),
  updateConfig: (cfg) => request('POST', '/config', cfg),

  // Conversations
  getConversations: () => request('GET', '/conversations'),
  createConversation: (title = '') => request('POST', '/conversations', { title }),
  getConversation: (id) => request('GET', `/conversations/${id}`),
  deleteConversation: (id) => request('DELETE', `/conversations/${id}`),
  appendMessage: (id, role, text) => request('POST', `/conversations/${id}/messages`, { role, text }),
  deleteMessage: (convId, msgId) => request('DELETE', `/conversations/${convId}/messages/${encodeURIComponent(msgId)}`),
  renameConversation: (id, title) => request('PATCH', `/conversations/${id}`, { title }),

  // Model info
  getCurrentModel: () => request('GET', '/current-model'),

  // File upload (multipart)
  uploadFile: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('auth_token')
    return fetch(BASE + '/upload', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    }).then(async res => {
      if (res.status === 401) { localStorage.removeItem('auth_token'); window.location.reload() }
      if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail || res.statusText) }
      return res.json()
    })
  },
}

export default api
