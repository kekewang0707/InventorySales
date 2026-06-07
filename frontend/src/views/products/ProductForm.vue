<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑产品' : '新增产品'"
    width="520px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      style="padding-right: 20px"
    >
      <el-form-item label="产品名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入产品名称" />
      </el-form-item>
      <el-form-item label="规格型号" prop="model">
        <el-input v-model="form.model" placeholder="请输入规格型号" />
      </el-form-item>
      <el-form-item label="默认单价" prop="default_price">
        <el-input-number
          v-model="form.default_price"
          :min="0"
          :precision="2"
          :step="1"
          style="width: 100%"
          placeholder="请输入默认单价"
        />
      </el-form-item>
      <el-form-item label="备注" prop="remark">
        <el-input
          v-model="form.remark"
          type="textarea"
          :rows="3"
          placeholder="请输入备注"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createProduct, updateProduct } from '../../api/products'

const props = defineProps({
  visible: Boolean,
  product: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:visible', 'saved'])

const formRef = ref(null)
const submitting = ref(false)
const form = ref({ name: '', model: '', default_price: null, remark: '' })

const isEdit = ref(false)

const rules = {
  name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
}

watch(
  () => props.product,
  (val) => {
    if (val) {
      isEdit.value = true
      form.value = {
        name: val.name || '',
        model: val.model || '',
        default_price: val.default_price ?? null,
        remark: val.remark || '',
      }
    } else {
      isEdit.value = false
      form.value = { name: '', model: '', default_price: null, remark: '' }
    }
  },
  { immediate: true }
)

function handleClosed() {
  formRef.value?.resetFields()
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = { ...form.value }
    if (payload.default_price === null || payload.default_price === undefined) {
      delete payload.default_price
    }
    if (isEdit.value) {
      await updateProduct(props.product.id, payload)
      ElMessage.success('产品已更新')
    } else {
      await createProduct(payload)
      ElMessage.success('产品已创建')
    }
    emit('update:visible', false)
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>
