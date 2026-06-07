<template>
  <div>
    <el-card shadow="never">
      <div style="display: flex; gap: 12px; margin-bottom: 16px">
        <el-select v-model="entityTypeFilter" placeholder="对象类型" clearable style="width: 140px" @change="fetchLogs">
          <el-option label="产品" value="product" />
          <el-option label="客户" value="customer" />
        </el-select>
        <el-select v-model="actionFilter" placeholder="操作类型" clearable style="width: 140px" @change="fetchLogs">
          <el-option label="创建" value="create" />
          <el-option label="修改" value="update" />
          <el-option label="删除" value="delete" />
          <el-option label="导入" value="import" />
        </el-select>
        <el-button type="primary" @click="fetchLogs">查询</el-button>
      </div>

      <el-table :data="logs" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="对象类型" width="100">
          <template #default="{ row }">
            {{ entityTypeLabel(row.entity_type) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small">
              {{ actionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="entity_id" label="对象 ID" width="80" />
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column prop="created_at" label="操作时间" width="180" />
        <el-table-column label="数据详情" min-width="200">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="showDetail(row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: flex-end; margin-top: 16px">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchLogs"
        />
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="数据详情" width="700px">
      <div v-if="detailRow">
        <div style="margin-bottom: 12px">
          <strong>旧数据：</strong>
          <pre style="background: #f5f7fa; padding: 12px; border-radius: 4px; margin-top: 4px; font-size: 13px; max-height: 200px; overflow: auto">{{ formatJSON(detailRow.old_values) }}</pre>
        </div>
        <div>
          <strong>新数据：</strong>
          <pre style="background: #f5f7fa; padding: 12px; border-radius: 4px; margin-top: 4px; font-size: 13px; max-height: 200px; overflow: auto">{{ formatJSON(detailRow.new_values) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getAuditLogs } from '../../api/auditLogs'

const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const entityTypeFilter = ref(null)
const actionFilter = ref(null)
const detailVisible = ref(false)
const detailRow = ref(null)

function entityTypeLabel(t) {
  return { product: '产品', customer: '客户' }[t] || t
}
function actionLabel(a) {
  return { create: '创建', update: '修改', delete: '删除', import: '导入' }[a] || a
}
function actionTagType(a) {
  return { create: 'success', update: 'warning', delete: 'danger', import: 'info' }[a] || ''
}
function formatJSON(val) {
  if (!val) return '(无)'
  return JSON.stringify(val, null, 2)
}
function showDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

async function fetchLogs() {
  loading.value = true
  try {
    const res = await getAuditLogs({
      entity_type: entityTypeFilter.value || undefined,
      action: actionFilter.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    logs.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

onMounted(fetchLogs)
</script>
