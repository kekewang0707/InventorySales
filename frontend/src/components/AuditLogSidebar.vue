<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="`${typeLabel}操作日志`"
    direction="rtl"
    size="600px"
    @closed="handleClosed"
  >
    <div style="display: flex; gap: 8px; margin-bottom: 12px">
      <el-select v-model="actionFilter" placeholder="操作类型" clearable style="width: 120px" @change="fetchLogs" size="small">
        <el-option label="创建" value="create" />
        <el-option label="修改" value="update" />
        <el-option label="删除" value="delete" />
        <el-option label="导入" value="import" />
      </el-select>
      <el-button size="small" type="primary" @click="fetchLogs">查询</el-button>
    </div>

    <div v-loading="loading">
      <div v-for="log in logs" :key="log.id" style="margin-bottom: 8px">
        <el-card shadow="never" size="small">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px">
            <el-tag :type="actionTagType(log.action)" size="small">
              {{ actionLabel(log.action) }}
            </el-tag>
            <span style="font-size: 12px; color: #909399">{{ log.created_at }}</span>
          </div>
          <div v-if="log.action === 'import'" style="font-size: 13px; color: #606266">
            导入 {{ log.new_values?.imported_count || 0 }} 条数据
          </div>
          <div v-else style="font-size: 13px; color: #606266">
            <div v-if="log.action === 'create' || log.action === 'update'">
              <span v-if="log.new_values">
                <template v-for="(v, k) in log.new_values" :key="k">
                  <span style="display: inline-block; margin-right: 12px">
                    <span style="color: #909399">{{ fieldLabel(k) }}:</span>
                    <span>{{ v ?? '(空)' }}</span>
                  </span>
                </template>
              </span>
            </div>
            <div v-else-if="log.action === 'delete'">
              <span style="color: #999">(数据已删除)</span>
            </div>
          </div>
          <div style="margin-top: 4px; font-size: 11px; color: #c0c4cc">
            ID: {{ log.entity_id }}
          </div>
        </el-card>
      </div>
      <el-empty v-if="!loading && logs.length === 0" description="暂无日志" />
      <div style="text-align: center; margin-top: 12px">
        <el-button v-if="hasMore" size="small" text @click="loadMore">加载更多</el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { getAuditLogs } from '../api/auditLogs'

const props = defineProps({
  visible: Boolean,
  entityType: {
    type: String,
    default: '',
  },
})
const emit = defineEmits(['update:visible'])

const logs = ref([])
const page = ref(1)
const total = ref(0)
const loading = ref(false)
const actionFilter = ref(null)
const pageSize = 20

const typeLabel = computed(() => {
  return { product: '产品', customer: '客户' }[props.entityType] || ''
})
const hasMore = computed(() => logs.value.length < total.value)

function fieldLabel(k) {
  const map = {
    name: '名称', model: '型号', default_price: '单价', remark: '备注',
    contact_person: '联系人', phone: '电话', address: '地址',
  }
  return map[k] || k
}
function actionLabel(a) {
  return { create: '创建', update: '修改', delete: '删除', import: '导入' }[a] || a
}
function actionTagType(a) {
  return { create: 'success', update: 'warning', delete: 'danger', import: 'info' }[a] || ''
}

async function fetchLogs() {
  if (!props.entityType) return
  loading.value = true
  page.value = 1
  try {
    const res = await getAuditLogs({
      entity_type: props.entityType,
      action: actionFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    logs.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  page.value += 1
  try {
    const res = await getAuditLogs({
      entity_type: props.entityType || undefined,
      action: actionFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    logs.value.push(...res.data.items)
  } catch {
    page.value -= 1
  }
}

function handleClosed() {
  logs.value = []
  page.value = 1
  total.value = 0
  actionFilter.value = null
}

watch(() => props.visible, (val) => {
  if (val) fetchLogs()
})
</script>
