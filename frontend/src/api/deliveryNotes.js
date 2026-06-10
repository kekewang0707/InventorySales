import request from './request'

/** 分页查询送货单列表。 */
export function getDeliveryNotes(params) {
  return request.get('/delivery-notes', { params })
}

/** 根据 ID 获取送货单详情。 */
export function getDeliveryNote(id) {
  return request.get(`/delivery-notes/${id}`)
}

/** 创建送货单（含明细行）。 */
export function createDeliveryNote(data) {
  return request.post('/delivery-notes', data)
}

/** 更新送货单基本信息及明细行。 */
export function updateDeliveryNote(id, data) {
  return request.put(`/delivery-notes/${id}`, data)
}

/** 删除送货单。 */
export function deleteDeliveryNote(id) {
  return request.delete(`/delivery-notes/${id}`)
}

/** 推进送货单状态：draft → saved → reviewed。 */
export function advanceStatus(id) {
  return request.put(`/delivery-notes/${id}/status`)
}

/** 回退送货单状态：reviewed → saved → draft。 */
export function revertStatus(id) {
  return request.put(`/delivery-notes/${id}/status-revert`)
}

/** 打印送货单，可选指定打印机名称。 */
export function printDeliveryNote(id, printerName = '') {
  const formData = new FormData()
  formData.append('printer_name', printerName)
  return request.post(`/delivery-notes/${id}/print`, formData)
}

/** 导出送货单为 Excel 文件下载。 */
export function exportDeliveryNote(id) {
  return request.get(`/delivery-notes/${id}/export`, { responseType: 'blob' })
}
