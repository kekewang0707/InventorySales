import request from './request'

/** 向 AI 发送文本指令。 */
export function sendCommand(text) {
  return request.post('/ai/command', { text })
}

/** 确认执行 AI 的写入操作。 */
export function confirmAction(confirmId) {
  return request.post('/ai/confirm', { confirm_id: confirmId })
}
