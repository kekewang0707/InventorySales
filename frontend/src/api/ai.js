import request from './request'

/** 向 AI 发送文本指令。 */
export function sendCommand(text, sessionId = '') {
  return request.post('/ai/command', { text, session_id: sessionId })
}

/** 确认执行 AI 的写入操作。 */
export function confirmAction(confirmId) {
  return request.post('/ai/confirm', { confirm_id: confirmId })
}

/** 列出所有活跃会话。 */
export function listSessions() {
  return request.get('/ai/sessions')
}

/** 删除指定会话。 */
export function deleteSession(sessionId) {
  return request.delete(`/ai/sessions/${sessionId}`)
}

/** 获取指定会话的消息列表。 */
export function getSessionMessages(sessionId) {
  return request.get(`/ai/sessions/${sessionId}/messages`)
}

/** 修改会话标题。 */
export function renameSession(sessionId, title) {
  return request.patch(`/ai/sessions/${sessionId}/title`, { title })
}


