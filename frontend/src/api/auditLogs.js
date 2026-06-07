import request from './request'

export function getAuditLogs(params) {
  return request.get('/audit-logs', { params })
}
