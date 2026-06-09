<template>
  <div>
    <!-- 头部 -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px">
      <el-button @click="$router.push('/delivery')" :icon="ArrowLeft" circle size="small" />
      <h3 style="margin: 0">
        {{ isCreate ? '新增送货单' : isEdit ? '编辑送货单' : '送货单详情' }}
      </h3>
      <el-tag :type="statusTag(note.status || 'draft')" size="small" style="margin-left: 8px">
        {{ statusLabel(note.status || 'draft') }}
      </el-tag>
      <div style="margin-left: auto; display: flex; gap: 8px">
        <!-- 查看模式 -->
        <template v-if="isView">
          <el-button size="small" @click="handleExport" :loading="exporting">
            <el-icon style="margin-right: 4px"><Download /></el-icon>导出
          </el-button>
          <el-button type="primary" size="small" @click="handlePrint" :loading="printing">
            <el-icon style="margin-right: 4px"><Printer /></el-icon>打印
          </el-button>
          <el-button size="small" @click="$router.push(`/delivery/${note.id}/edit`)">
            <el-icon style="margin-right: 4px"><Edit /></el-icon>编辑
          </el-button>
        </template>
        <!-- 创建/编辑模式 -->
        <template v-if="isCreate || isEdit">
          <el-button size="small" type="success" :disabled="isCreate || note.status === 'reviewed'" @click="handleAdvance" :loading="statusLoading">
            推进
          </el-button>
          <el-button size="small" type="warning" :disabled="isCreate || note.status === 'draft'" @click="handleRevert" :loading="statusLoading">
            回退
          </el-button>
          <el-button size="small" type="primary" @click="handleExport" :loading="exporting" v-if="isEdit">
            <el-icon style="margin-right: 4px"><Download /></el-icon>导出
          </el-button>
          <el-button size="small" @click="handlePrint2" :loading="printing" v-if="isEdit">
            <el-icon style="margin-right: 4px"><Printer /></el-icon>打印
          </el-button>
          <el-button @click="cancelEdit" v-if="isEdit">取消编辑</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving" v-if="isCreate || isEdit">
            保存
          </el-button>
        </template>
      </div>
    </div>

    <!-- 查看模式：只读显示 -->
    <template v-if="isView">
      <el-card style="margin-bottom: 16px">
        <el-descriptions :column="2" border size="default">
          <el-descriptions-item label="送货单号">{{ note.doc_number }}</el-descriptions-item>
          <el-descriptions-item label="送货日期">{{ note.delivery_date }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ note.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTag(note.status)" size="small">{{ statusLabel(note.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ note.remark || '—' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
      <el-card>
        <el-table :data="note.items || []" stripe>
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="product_name" label="产品名称" min-width="140" />
          <el-table-column prop="product_model" label="规格" width="140" />
          <el-table-column label="数量" width="100">
            <template #default="{ row }">{{ row.quantity }}</template>
          </el-table-column>
          <el-table-column label="单价" width="100">
            <template #default="{ row }">{{ Number(row.unit_price).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="小计" width="120">
            <template #default="{ row }">{{ Number(row.subtotal).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="120" />
        </el-table>
        <div style="text-align: center; color: #909399; font-size: 12px; padding: 4px 0; border-top: 1px solid #ebeef5">
          [以下为空]
        </div>
        <div style="text-align: right; margin-top: 6px; font-size: 16px">
          合计金额：<strong>{{ note.total_amount ? Number(note.total_amount).toFixed(2) : '0.00' }}</strong>
        </div>
      </el-card>
    </template>

    <!-- 创建/编辑模式：表单 -->
    <template v-if="isCreate || isEdit">
      <el-card>
        <el-form ref="formRef" :model="form" label-width="100px" size="default">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="客户" required>
                <el-select v-model="form.customer_id" filterable placeholder="选择客户" style="width: 100%">
                  <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="送货日期" required>
                <el-date-picker v-model="form.delivery_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="备注">
            <el-input v-model="form.remark" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card style="margin-top: 16px">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span>明细行</span>
            <el-button type="primary" size="small" @click="addItem">
              <el-icon style="margin-right: 4px"><Plus /></el-icon>添加行
            </el-button>
          </div>
        </template>

        <el-table :data="form.items" stripe>
          <el-table-column label="序号" width="60">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="产品" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.product_id" filterable placeholder="选择产品" style="width: 100%" @change="onProductChange(row)">
                <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="规格" width="120">
            <template #default="{ row }">{{ getProductModel(row) }}</template>
          </el-table-column>
          <el-table-column label="数量" width="130">
            <template #default="{ row }">
              <el-input-number v-model="row.quantity" :min="0.01" :precision="2" controls-position="right" @change="calcSubtotal(row)" />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="130">
            <template #default="{ row }">
              <el-input-number v-model="row.unit_price" :min="0" :precision="2" controls-position="right" @change="calcSubtotal(row)" />
            </template>
          </el-table-column>
          <el-table-column label="小计" width="130">
            <template #default="{ row }">{{ row.subtotal ? Number(row.subtotal).toFixed(2) : '0.00' }}</template>
          </el-table-column>
          <el-table-column label="备注" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.remark" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="" width="60">
            <template #default="{ $index }">
              <el-button size="small" type="danger" :icon="Delete" circle @click="removeItem($index)" />
            </template>
          </el-table-column>
        </el-table>

        <div style="text-align: right; margin-top: 16px; font-size: 16px">
          合计：<strong>{{ totalAmount }}</strong>
        </div>
      </el-card>
    </template>

    <!-- 打印机选择对话框 -->
    <el-dialog v-model="printDialogVisible" title="打印预览" width="700px">
      <div style="border: 1px solid #dcdfe6; border-radius: 4px; padding: 12px; margin-bottom: 16px; background: #fff">
        <div style="text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 8px">送货单</div>
        <div style="display: flex; gap: 20px; font-size: 13px; margin-bottom: 6px">
          <span>客户：{{ note.customer_name }}</span>
          <span>日期：{{ note.delivery_date }}</span>
        </div>
        <div style="font-size: 13px; margin-bottom: 10px">单号：{{ note.doc_number }}</div>
        <el-table :data="note.items" size="small" border style="width: 100%" max-height="300px">
          <el-table-column type="index" label="序号" width="50" />
          <el-table-column prop="product_name" label="产品名称" />
          <el-table-column prop="product_model" label="规格" width="100" />
          <el-table-column label="数量" width="70">
            <template #default="{ row }">{{ row.quantity }}</template>
          </el-table-column>
          <el-table-column label="单价" width="80">
            <template #default="{ row }">{{ Number(row.unit_price).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="小计" width="90">
            <template #default="{ row }">{{ Number(row.subtotal).toFixed(2) }}</template>
          </el-table-column>
        </el-table>
        <div style="text-align: center; color: #909399; font-size: 12px; padding: 4px 0; border-top: 1px solid #ebeef5">[以下为空]</div>
        <div style="text-align: right; margin-top: 6px; font-size: 14px; font-weight: bold">
          合计：{{ note.total_amount ? Number(note.total_amount).toFixed(2) : '0.00' }}
        </div>
      </div>
      <el-form label-width="80px">
        <el-form-item label="打印机">
          <el-select v-model="selectedPrinter" placeholder="选择打印机" style="width: 100%">
            <el-option v-for="p in printers" :key="p.name" :label="p.name + (p.is_default ? ' (默认)' : '')" :value="p.name" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="printDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doPrint" :loading="printing">打印</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Plus, Delete, Printer, Download, Edit } from '@element-plus/icons-vue'
import { getProducts } from '../../api/products'
import { getCustomers } from '../../api/customers'
import {
  getDeliveryNote, createDeliveryNote, updateDeliveryNote,
  exportDeliveryNote, printDeliveryNote,
} from '../../api/deliveryNotes'
import request from '../../api/request'

const route = useRoute()
const router = useRouter()

const isCreate = computed(() => route.name === 'DeliveryNoteCreate')
const isEdit = computed(() => route.name === 'DeliveryNoteEdit')
const isView = computed(() => route.name === 'DeliveryNoteDetail')

const saving = ref(false)
const printing = ref(false)
const exporting = ref(false)
const statusLoading = ref(false)
const printDialogVisible = ref(false)
const selectedPrinter = ref('')
const printers = ref([])

const products = ref([])
const customers = ref([])

const note = ref({ items: [], status: 'draft' })

const form = reactive({
  customer_id: null,
  delivery_date: null,
  remark: '',
  status: 'draft',
  items: [],
})

// ---- 状态辅助 ----
function statusTag(s) { return { draft: 'info', saved: 'warning', reviewed: 'success' }[s] || 'info' }
function statusLabel(s) { return { draft: '草稿', saved: '已保存', reviewed: '已审核' }[s] || s }

// ---- 明细行操作 ----
function emptyItem() { return { product_id: null, quantity: 0, unit_price: 0, subtotal: 0, remark: '' } }
function addItem() { form.items.push(emptyItem()) }
function removeItem(idx) { form.items.splice(idx, 1) }
function getProductModel(row) { const p = products.value.find(x => x.id === row.product_id); return p ? p.model : '' }
function onProductChange(row) { const p = products.value.find(x => x.id === row.product_id); if (p?.default_price) row.unit_price = Number(p.default_price); calcSubtotal(row) }
function calcSubtotal(row) { row.subtotal = Math.round((row.quantity || 0) * (row.unit_price || 0) * 100) / 100 }
const totalAmount = computed(() => form.items.reduce((s, i) => s + (i.subtotal || 0), 0).toFixed(2))

// ---- 数据加载 ----
async function loadData() {
  const [pRes, cRes] = await Promise.all([getProducts({ page_size: 999 }), getCustomers({ page_size: 999 })])
  products.value = pRes.data.items
  customers.value = cRes.data.items
}

async function loadNote() {
  const res = await getDeliveryNote(route.params.id)
  const n = res.data
  note.value = n
  form.customer_id = n.customer_id
  form.delivery_date = n.delivery_date
  form.remark = n.remark || ''
  form.status = n.status
  form.items = (n.items || []).map(item => ({
    product_id: item.product_id,
    quantity: Number(item.quantity),
    unit_price: Number(item.unit_price),
    subtotal: Number(item.subtotal),
    remark: item.remark || '',
  }))
}

async function loadPrinters() {
  try {
    const res = await request.get('/delivery-notes/printers')
    printers.value = res.data.printers || []
    selectedPrinter.value = res.data.default || ''
  } catch {}
}

// ---- 保存 ----
async function handleSave() {
  if (!form.customer_id) { ElMessage.warning('请选择客户'); return }
  if (!form.delivery_date) { ElMessage.warning('请选择日期'); return }
  if (form.items.length === 0) { ElMessage.warning('至少添加一行明细'); return }
  for (const item of form.items) {
    if (!item.product_id) { ElMessage.warning('请选择产品'); return }
    if (!item.quantity || item.quantity <= 0) { ElMessage.warning('数量必须大于0'); return }
  }
  const payload = {
    customer_id: form.customer_id,
    delivery_date: form.delivery_date,
    remark: form.remark || null,
    items: form.items.map(item => ({
      product_id: item.product_id,
      quantity: item.quantity,
      unit_price: item.unit_price,
      remark: item.remark || null,
    })),
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await updateDeliveryNote(route.params.id, payload)
      ElMessage.success('已更新')
      router.replace(`/delivery/${route.params.id}`)
    } else {
      const res = await createDeliveryNote(payload)
      ElMessage.success('已创建')
      router.replace(`/delivery/${res.data.id}/edit`)
    }
  } catch {} finally { saving.value = false }
}

function cancelEdit() {
  router.replace(`/delivery/${route.params.id}`)
}

// ---- 状态流转 ----
async function handleAdvance() {
  statusLoading.value = true
  try {
    const { advanceStatus } = await import('../../api/deliveryNotes')
    await advanceStatus(route.params.id)
    form.status = form.status === 'draft' ? 'saved' : 'reviewed'
    note.value.status = form.status
    ElMessage.success('状态已推进')
  } catch {} finally { statusLoading.value = false }
}

async function handleRevert() {
  statusLoading.value = true
  try {
    const { revertStatus } = await import('../../api/deliveryNotes')
    await revertStatus(route.params.id)
    form.status = form.status === 'reviewed' ? 'saved' : 'draft'
    note.value.status = form.status
    ElMessage.success('状态已回退')
  } catch {} finally { statusLoading.value = false }
}

// ---- 导出 ----
async function handleExport() {
  exporting.value = true
  try {
    const id = isView.value ? note.value.id : route.params.id
    const res = await exportDeliveryNote(id)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `${note.value.doc_number || 'delivery'}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载完成')
  } catch {} finally { exporting.value = false }
}

// ---- 打印 ----
async function handlePrint() { await handlePrint2() }
async function handlePrint2() {
  const id = isView.value ? note.value.id : route.params.id
  if (isView.value || isEdit.value) {
    const res = await getDeliveryNote(id)
    note.value = res.data
  }
  await loadPrinters()
  printDialogVisible.value = true
}

async function doPrint() {
  printing.value = true
  try {
    const formData = new FormData()
    formData.append('printer_name', selectedPrinter.value)
    await request.post(`/delivery-notes/${note.value.id}/print`, formData)
    printDialogVisible.value = false
    ElMessage.success('已发送到打印机')
  } catch {} finally { printing.value = false }
}

// ---- 初始化 ----
onMounted(async () => {
  await loadData()
  if (isEdit.value || isView.value) {
    await loadNote()
    if (isEdit.value && note.value.status !== 'draft') {
      ElMessage.warning('已审核或已保存的送货单不可编辑')
      router.replace(`/delivery/${route.params.id}`)
      return
    }
  }
  if ((isCreate.value || isEdit.value) && form.items.length === 0) addItem()
})
</script>
