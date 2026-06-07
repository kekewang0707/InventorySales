<template>
  <div>
    <el-card shadow="never">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
        <div style="display: flex; gap: 12px">
          <el-input
            v-model="searchQuery"
            placeholder="搜索客户名称/电话"
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
        <div style="display: flex; gap: 8px">
          <el-button @click="openImport">
            <el-icon><Upload /></el-icon>导入
          </el-button>
          <el-button @click="openAuditLog">
            <el-icon><Tickets /></el-icon>日志
          </el-button>
          <el-button type="primary" @click="openCreate">
            <el-icon><Plus /></el-icon>新增客户
          </el-button>
        </div>
      </div>

      <el-table :data="customers" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="客户名称" min-width="180" />
        <el-table-column prop="contact_person" label="联系人" width="130" />
        <el-table-column prop="phone" label="联系电话" width="140" />
        <el-table-column prop="address" label="地址" min-width="220" show-overflow-tooltip />
        <el-table-column prop="remark" label="备注" width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该客户？" @confirm="handleDelete(row.id)">
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
          @current-change="fetchCustomers"
        />
      </div>
    </el-card>

    <CustomerForm
      v-model:visible="dialogVisible"
      :customer="editingCustomer"
      @saved="fetchCustomers"
    />

    <ImportDialog entity-type="customer"
      v-model:visible="importDialogVisible"
      @imported="fetchCustomers"
    />

    <AuditLogSidebar
      v-model:visible="auditLogVisible"
      entity-type="customer"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCustomers, deleteCustomer } from '../../api/customers'
import CustomerForm from './CustomerForm.vue'
import ImportDialog from '../../components/ImportDialog.vue'
import AuditLogSidebar from '../../components/AuditLogSidebar.vue'

const customers = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const editingCustomer = ref(null)
const importDialogVisible = ref(false)
const auditLogVisible = ref(false)

async function fetchCustomers() {
  loading.value = true
  try {
    const res = await getCustomers({
      search: searchQuery.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    customers.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchCustomers()
}

function openCreate() {
  editingCustomer.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  editingCustomer.value = { ...row }
  dialogVisible.value = true
}

function openImport() {
  importDialogVisible.value = true
}

function openAuditLog() {
  auditLogVisible.value = true
}

async function handleDelete(id) {
  try {
    await deleteCustomer(id)
    fetchCustomers()
  } catch {
    // handled by interceptor
  }
}

onMounted(fetchCustomers)
</script>
