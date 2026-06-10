import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/products' },
  { path: '/products', name: 'Products', component: () => import('../views/products/ProductList.vue') },
  { path: '/customers', name: 'Customers', component: () => import('../views/customers/CustomerList.vue') },
  { path: '/delivery', name: 'DeliveryNotes', component: () => import('../views/delivery/DeliveryNoteList.vue') },
  { path: '/delivery/create', name: 'DeliveryNoteCreate', component: () => import('../views/delivery/DeliveryNotePage.vue') },
  { path: '/delivery/:id', name: 'DeliveryNoteDetail', component: () => import('../views/delivery/DeliveryNotePage.vue') },
  { path: '/delivery/:id/edit', name: 'DeliveryNoteEdit', component: () => import('../views/delivery/DeliveryNotePage.vue') },
  { path: '/statements', name: 'CustomerStatement', component: () => import('../views/statements/CustomerStatement.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
