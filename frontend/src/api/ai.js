import request from './request'

export function sendCommand(text) {
  return request.post('/ai/command', { text })
}

export function confirmAction(confirmId) {
  return request.post('/ai/confirm', { confirm_id: confirmId })
}
