<template>
  <div>
    <el-card shadow="never">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
        <div style="display: flex; gap: 12px">
          <el-input
            v-model="searchQuery"
            placeholder="搜索产品名称/型号"
            style="width: 280px"
            clearable
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </div>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>新增产品
        </el-button>
      </div>

      <el-table :data="products" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="产品名称" min-width="180" />
        <el-table-column prop="model" label="规格型号" min-width="180" />
        <el-table-column prop="default_price" label="默认单价" width="130">
          <template #default="{ row }">
            {{ row.default_price ? `¥${row.default_price}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该产品？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: flex-end; margin-top: 16px">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchProducts"
        />
      </div>
    </el-card>

    <ProductForm
      v-model:visible="dialogVisible"
      :product="editingProduct"
      @saved="fetchProducts"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getProducts, deleteProduct } from '../../api/products'
import ProductForm from './ProductForm.vue'

const products = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const editingProduct = ref(null)

async function fetchProducts() {
  loading.value = true
  try {
    const res = await getProducts({
      search: searchQuery.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    products.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchProducts()
}

function openCreate() {
  editingProduct.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  editingProduct.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(id) {
  try {
    await deleteProduct(id)
    fetchProducts()
  } catch {
    // error handled by interceptor
  }
}

onMounted(fetchProducts)
</script>
