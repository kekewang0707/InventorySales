import request from './request'

/** 分页查询客户列表。 */
export function getCustomers(params) {
  return request.get('/customers', { params })
}

/** 根据 ID 获取客户详情。 */
export function getCustomer(id) {
  return request.get(`/customers/${id}`)
}

/** 创建新客户。 */
export function createCustomer(data) {
  return request.post('/customers', data)
}

/** 更新客户信息。 */
export function updateCustomer(id, data) {
  return request.put(`/customers/${id}`, data)
}

/** 删除客户。 */
export function deleteCustomer(id) {
  return request.delete(`/customers/${id}`)
}
