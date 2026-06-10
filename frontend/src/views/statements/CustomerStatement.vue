<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">客户对账单</h3>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-form :inline="true" :model="form" size="default">
        <el-form-item label="客户">
          <el-select v-model="form.customer_id" clearable filterable placeholder="全部客户" style="width: 200px">
            <el-option label="全部客户" :value="null" />
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对账期间">
          <el-date-picker
            v-model="form.dateRange" type="daterange" range-separator="至"
            start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery" :loading="loading">查询</el-button>
          <el-button @click="handleExport" :loading="exporting" :disabled="!hasData">导出对账单</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="statements.length > 0">
      <template v-for="stmt in statements" :key="stmt.customer_id">
        <div style="margin-bottom: 8px; font-weight: bold; font-size: 15px; padding: 8px 0">
          客户：{{ stmt.customer_name }}
        </div>
        <el-table :data="flattenNotes(stmt.delivery_notes)" stripe style="margin-bottom: 16px" :row-class-name="rowClassName">
          <el-table-column label="序号" width="55">
            <template #default="{ row }">
              {{ row._seq || '' }}
            </template>
          </el-table-column>
          <el-table-column label="日期" width="100">
            <template #default="{ row }">
              {{ row._isHeader ? row.delivery_date : '' }}
            </template>
          </el-table-column>
          <el-table-column label="送货单号" width="160">
            <template #default="{ row }">
              {{ row._isHeader ? row.doc_number : '' }}
            </template>
          </el-table-column>
          <el-table-column label="明细" min-width="240">
            <template #default="{ row }">
              {{ row.detail }}
            </template>
          </el-table-column>
          <el-table-column label="金额" width="110">
            <template #default="{ row }">
              {{ Number(row.amount).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="100">
            <template #default="{ row }">
              {{ row._isHeader ? row.remark : '' }}
            </template>
          </el-table-column>
        </el-table>
        <div style="text-align: right; margin-bottom: 20px; padding: 4px 12px; background: #f5f7fa; font-weight: bold">
          小计：¥{{ Number(stmt.total_amount).toFixed(2) }}
        </div>
      </template>

      <div v-if="statements.length > 1" style="text-align: right; margin-top: 8px; padding: 8px 12px; background: #e6f7ff; font-size: 16px; font-weight: bold">
        总计：¥{{ grandTotal.toFixed(2) }}
      </div>
    </el-card>

    <el-card v-else-if="queried">
      <el-empty description="未查询到相关数据" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { queryStatements, exportStatements } from '../../api/statements'
import { getCustomers } from '../../api/customers'

const loading = ref(false)
const exporting = ref(false)
const queried = ref(false)
const customers = ref([])
const statements = ref([])

const form = reactive({
  customer_id: null,
  dateRange: [],
})

const hasData = computed(() => statements.value.length > 0)
const grandTotal = computed(() => statements.value.reduce((s, stmt) => s + Number(stmt.total_amount), 0))

function flattenNotes(notes) {
  const rows = []
  let seq = 0
  for (const note of notes) {
    seq++
    // Header row
    rows.push({
      _isHeader: true,
      _seq: seq,
      delivery_date: note.delivery_date,
      doc_number: note.doc_number,
      detail: '',
      amount: note.total_amount,
      remark: note.remark,
    })
    // Item sub-rows
    if (note.items && note.items.length > 0) {
      for (const item of note.items) {
        rows.push({
          _isHeader: false,
          _seq: '',
          delivery_date: '',
          doc_number: '',
          detail: `${item.product_name} * ${trimNum(item.unit_price)} * ${trimNum(item.quantity)}`,
          amount: item.subtotal,
          remark: '',
        })
      }
    }
  }
  return rows
}

function trimNum(v) {
  const s = String(v)
  if (s.indexOf('.') !== -1) return s.replace(/\.?0+$/, '')
  return s
}

function rowClassName({ row }) {
  return row._isHeader ? '' : 'statement-item-row'
}

function getDefaultDateRange() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const fmt = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }
  return [fmt(start), fmt(now)]
}

function initForm() {
  form.dateRange = getDefaultDateRange()
}
initForm()

async function loadCustomers() {
  try {
    const res = await getCustomers({ page_size: 999 })
    customers.value = res.data.items
  } catch {}
}

async function handleQuery() {
  if (!form.dateRange || form.dateRange.length !== 2) {
    ElMessage.warning('请选择对账期间')
    return
  }
  loading.value = true
  queried.value = true
  try {
    const payload = {
      customer_id: form.customer_id || null,
      start_date: form.dateRange[0],
      end_date: form.dateRange[1],
    }
    const res = await queryStatements(payload)
    statements.value = res.data.statements || []
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  if (!form.dateRange || form.dateRange.length !== 2) {
    ElMessage.warning('请选择对账期间')
    return
  }
  exporting.value = true
  try {
    const payload = {
      customer_id: form.customer_id || null,
      start_date: form.dateRange[0],
      end_date: form.dateRange[1],
    }
    const res = await exportStatements(payload)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    // Determine filename from response header or build it
    const disposition = res.headers?.['content-disposition'] || ''
    let filename = ''
    if (disposition) {
      const match = disposition.match(/filename="?(.+?)"?$/)
      if (match) filename = match[1]
    }
    if (!filename) {
      const customerLabel = form.customer_id
        ? (customers.value.find(c => c.id === form.customer_id)?.name || '客户')
        : '全部客户'
      filename = `${customerLabel}_${form.dateRange[0]}-${form.dateRange[1]}.xlsx`
    }

    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('对账单已导出')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadCustomers()
  // Auto-query on mount with default month range
  handleQuery()
})
</script>

<style scoped>
.statement-item-row td {
  background-color: #fafafa !important;
  font-size: 12px;
  color: #666;
}
.statement-item-row .el-table__cell {
  border-bottom: none !important;
}
</style>
