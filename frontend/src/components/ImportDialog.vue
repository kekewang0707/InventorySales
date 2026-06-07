<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="`导入${typeLabel}`"
    width="800px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <template v-if="step === 'upload'">
      <div style="margin-bottom: 12px">
        <el-button type="primary" link @click="handleDownloadTemplate">
          <el-icon><Download /></el-icon> 下载导入模板
        </el-button>
        <span style="margin-left: 12px; color: #909399; font-size: 13px">
          请先下载模板填写数据，再上传 .xlsx 文件
        </span>
      </div>

      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        accept=".xlsx"
        :limit="1"
        :on-change="handleFileChange"
      >
        <el-button type="primary">
          <el-icon><Upload /></el-icon> 选择 Excel 文件
        </el-button>
        <template #tip>
          <div style="color: #909399; font-size: 12px; margin-top: 4px">仅支持 .xlsx 格式</div>
        </template>
      </el-upload>
    </template>

    <template v-if="step === 'preview'">
      <div style="margin-bottom: 12px">
        <el-alert
          :type="previewResult.valid_count > 0 && previewResult.error_count === 0 ? 'success' : 'warning'"
          show-icon
          :closable="false"
        >
          <template #title>
            <span>共 {{ previewResult.total_rows }} 行，</span>
            <span style="color: #67c23a">有效 {{ previewResult.valid_count }} 行</span>
            <span v-if="previewResult.error_count > 0">，</span>
            <span v-if="previewResult.error_count > 0" style="color: #e6a23c">有误 {{ previewResult.error_count }} 行</span>
          </template>
        </el-alert>
      </div>

      <div v-if="previewResult.errors.length" style="margin-bottom: 12px">
        <el-table :data="previewResult.errors" size="small" border max-height="180">
          <el-table-column prop="row" label="行号" width="60" />
          <el-table-column prop="message" label="错误信息" min-width="300" />
        </el-table>
      </div>

      <el-table
        v-if="previewResult.preview.length"
        :data="previewResult.preview"
        stripe border max-height="320" size="small"
      >
        <el-table-column type="index" label="#" width="50" />
        <el-table-column
          v-for="col in previewColumns" :key="col"
          :prop="col" :label="col" min-width="120" show-overflow-tooltip
        />
      </el-table>
    </template>

    <template #footer>
      <el-button v-if="step === 'preview'" @click="step = 'upload'">返回</el-button>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button
        v-if="step === 'preview'"
        type="primary"
        :loading="importing"
        :disabled="previewResult.valid_count === 0"
        @click="handleConfirm"
      >
        确认导入 ({{ previewResult.valid_count }} 条)
      </el-button>
      <el-button v-else type="primary" :disabled="!selectedFile" @click="handlePreview">
        预览
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadTemplate, previewImport, confirmImport } from '../api/imports'

const props = defineProps({
  visible: Boolean,
  entityType: { type: String, default: 'product' },
})
const emit = defineEmits(['update:visible', 'imported'])

const step = ref('upload')
const selectedFile = ref(null)
const uploadRef = ref(null)
const previewResult = ref({ total_rows: 0, valid_count: 0, error_count: 0, errors: [], preview: [] })
const importing = ref(false)
const sessionId = ref('')

const typeLabel = computed(() => (props.entityType === 'product' ? '产品' : '客户'))
const previewColumns = computed(() => {
  return previewResult.value.preview.length > 0
    ? Object.keys(previewResult.value.preview[0])
    : []
})

function resetForm() {
  step.value = 'upload'
  selectedFile.value = null
  previewResult.value = { total_rows: 0, valid_count: 0, error_count: 0, errors: [], preview: [] }
  uploadRef.value?.clearFiles()
}

function handleDownloadTemplate() {
  downloadTemplate(props.entityType)
}

function handleFileChange(file) {
  selectedFile.value = file.raw
}

async function handlePreview() {
  if (!selectedFile.value) return
  try {
    const res = await previewImport(selectedFile.value, props.entityType)
    previewResult.value = res.data
    sessionId.value = res.data.session_id
    step.value = 'preview'
  } catch {
    // handled by interceptor
  }
}

async function handleConfirm() {
  importing.value = true
  try {
    const res = await confirmImport(sessionId.value)
    if (res.data.all_or_nothing && res.data.failed > 0) {
      ElMessage.error(`导入失败：${res.data.errors?.[0]?.message || '已全部回滚'}`)
    } else {
      ElMessage.success(`导入成功：${res.data.imported} 条`)
      emit('imported')
      emit('update:visible', false)
    }
  } catch {
    // handled by interceptor
  } finally {
    importing.value = false
  }
}

function handleClosed() {
  resetForm()
}
</script>
