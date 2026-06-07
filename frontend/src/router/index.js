import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/products',
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('../views/products/ProductList.vue'),
  },
  {
    path: '/customers',
    name: 'Customers',
    component: () => import('../views/customers/CustomerList.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
