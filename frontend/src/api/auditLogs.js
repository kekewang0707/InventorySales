import request from './request'

/** 分页查询审计日志。 */
export function getAuditLogs(params) {
  return request.get('/audit-logs', { params })
}
