import request from './request'

export function getDeliveryNotes(params) {
  return request.get('/delivery-notes', { params })
}

export function getDeliveryNote(id) {
  return request.get(`/delivery-notes/${id}`)
}

export function createDeliveryNote(data) {
  return request.post('/delivery-notes', data)
}

export function updateDeliveryNote(id, data) {
  return request.put(`/delivery-notes/${id}`, data)
}

export function deleteDeliveryNote(id) {
  return request.delete(`/delivery-notes/${id}`)
}

export function advanceStatus(id) {
  return request.put(`/delivery-notes/${id}/status`)
}

export function revertStatus(id) {
  return request.put(`/delivery-notes/${id}/status-revert`)
}

export function printDeliveryNote(id, printerName = '') {
  const formData = new FormData()
  formData.append('printer_name', printerName)
  return request.post(`/delivery-notes/${id}/print`, formData)
}

export function exportDeliveryNote(id) {
  return request.get(`/delivery-notes/${id}/export`, { responseType: 'blob' })
}
