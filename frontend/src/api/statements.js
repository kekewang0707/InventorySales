import request from './request'

/** 查询客户对账单（按客户和时间范围）。 */
export function queryStatements(data) {
  return request.post('/statements', data)
}

/** 导出对账单为 Excel 文件下载。 */
export function exportStatements(data) {
  return request.post('/statements/export', data, { responseType: 'blob' })
}
