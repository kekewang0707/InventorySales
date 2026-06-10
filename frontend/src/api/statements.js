import request from './request'

export function queryStatements(data) {
  return request.post('/statements', data)
}

export function exportStatements(data) {
  return request.post('/statements/export', data, { responseType: 'blob' })
}
