<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">送货单管理</h3>
      <el-button type="primary" @click="$router.push('/delivery/create')">
        <el-icon style="margin-right: 4px"><Plus /></el-icon>新增送货单
      </el-button>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-form :inline="true" :model="searchForm" size="default">
        <el-form-item label="客户">
          <el-select v-model="searchForm.customer_id" clearable filterable placeholder="全部客户" style="width: 200px">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="searchForm.dateRange" type="daterange" range-separator="至"
            start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="doc_number" label="送货单号" width="180" />
        <el-table-column prop="customer_name" label="客户" min-width="140" />
        <el-table-column prop="delivery_date" label="送货日期" width="110" />
        <el-table-column prop="total_amount" label="总金额" width="120">
          <template #default="{ row }">
            {{ row.total_amount ? Number(row.total_amount).toFixed(2) : '0.00' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString() : '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="$router.push(`/delivery/${row.id}`)">查看</el-button>
            <el-button size="small" type="primary" link :disabled="row.status !== 'draft'" @click="$router.push(`/delivery/${row.id}/edit`)">编辑</el-button>
            <el-button size="small" type="success" link :disabled="row.status==='reviewed'" @click="handleAdvance(row)">推进</el-button>
            <el-button size="small" type="warning" link :disabled="row.status==='draft'" @click="handleRevert(row)">回退</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: flex-end; margin-top: 16px">
        <el-pagination
          v-model:current-page="pagination.page" :page-size="pagination.pageSize"
          :total="pagination.total" layout="total, prev, pager, next" @current-change="fetchData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getDeliveryNotes, deleteDeliveryNote, advanceStatus, revertStatus } from '../../api/deliveryNotes'
import { getCustomers } from '../../api/customers'

const loading = ref(false)
const tableData = ref([])
const customers = ref([])

const searchForm = reactive({ customer_id: null, dateRange: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

function statusTag(s) {
  return { draft: 'info', saved: 'warning', reviewed: 'success' }[s] || 'info'
}
function statusLabel(s) {
  return { draft: '草稿', saved: '已保存', reviewed: '已审核' }[s] || s
}

async function fetchData() {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchForm.customer_id) params.customer_id = searchForm.customer_id
    if (searchForm.dateRange?.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }
    const res = await getDeliveryNotes(params)
    tableData.value = res.data.items
    pagination.total = res.data.total
  } finally { loading.value = false }
}

async function loadCustomers() {
  try {
    const res = await getCustomers({ page_size: 999 })
    customers.value = res.data.items
  } catch {}
}

function handleSearch() { pagination.page = 1; fetchData() }
function handleReset() { searchForm.customer_id = null; searchForm.dateRange = null; pagination.page = 1; fetchData() }

async function handleAdvance(row) {
  try { await advanceStatus(row.id); ElMessage.success('状态已推进'); fetchData() } catch {}
}
async function handleRevert(row) {
  try { await revertStatus(row.id); ElMessage.success('状态已回退'); fetchData() } catch {}
}
async function handleDelete(id) {
  try { await deleteDeliveryNote(id); ElMessage.success('已删除'); fetchData() } catch {}
}

onMounted(() => { loadCustomers(); fetchData() })
</script>
