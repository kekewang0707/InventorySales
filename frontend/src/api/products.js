import request from './request'

/** 分页查询产品列表。 */
export function getProducts(params) {
  return request.get('/products', { params })
}

/** 根据 ID 获取产品详情。 */
export function getProduct(id) {
  return request.get(`/products/${id}`)
}

/** 创建新产品。 */
export function createProduct(data) {
  return request.post('/products', data)
}

/** 更新产品信息。 */
export function updateProduct(id, data) {
  return request.put(`/products/${id}`, data)
}

/** 删除产品。 */
export function deleteProduct(id) {
  return request.delete(`/products/${id}`)
}
