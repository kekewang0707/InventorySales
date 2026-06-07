import request from './request'

/**
 * 下载模板文件。
 * QWebEngineView 接管了 Content-Disposition: attachment 请求，
 * 直接导航到该 URL 触发 Qt 的下载处理器保存文件。
 */
export function downloadTemplate(entityType) {
  const link = document.createElement('a')
  link.href = `/api/import/template?entity_type=${entityType}`
  link.download = `${entityType === "product" ? "产品" : "客户"}_导入模板.xlsx`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export function previewImport(file, entityType) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('entity_type', entityType)
  return request.post('/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
}

export function confirmImport(sessionId) {
  return request.post('/import/confirm', { session_id: sessionId })
}
