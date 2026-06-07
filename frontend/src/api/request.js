import axios from 'axios'
import { ElMessage } from 'element-plus'

// 现在前端由后端提供，同源访问，直接用 /api
const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request
