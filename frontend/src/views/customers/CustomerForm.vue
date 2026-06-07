<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑客户' : '新增客户'"
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
      <el-form-item label="客户名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入客户名称" />
      </el-form-item>
      <el-form-item label="联系人" prop="contact_person">
        <el-input v-model="form.contact_person" placeholder="请输入联系人" />
      </el-form-item>
      <el-form-item label="联系电话" prop="phone">
        <el-input v-model="form.phone" placeholder="请输入联系电话" />
      </el-form-item>
      <el-form-item label="地址" prop="address">
        <el-input
          v-model="form.address"
          type="textarea"
          :rows="2"
          placeholder="请输入地址"
        />
      </el-form-item>
      <el-form-item label="备注" prop="remark">
        <el-input
          v-model="form.remark"
          type="textarea"
          :rows="2"
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
import { createCustomer, updateCustomer } from '../../api/customers'

const props = defineProps({
  visible: Boolean,
  customer: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['update:visible', 'saved'])

const formRef = ref(null)
const submitting = ref(false)
const form = ref({ name: '', contact_person: '', phone: '', address: '', remark: '' })
const isEdit = ref(false)

const rules = {
  name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }],
}

watch(
  () => props.customer,
  (val) => {
    if (val) {
      isEdit.value = true
      form.value = {
        name: val.name || '',
        contact_person: val.contact_person || '',
        phone: val.phone || '',
        address: val.address || '',
        remark: val.remark || '',
      }
    } else {
      isEdit.value = false
      form.value = { name: '', contact_person: '', phone: '', address: '', remark: '' }
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
    if (isEdit.value) {
      await updateCustomer(props.customer.id, form.value)
      ElMessage.success('客户已更新')
    } else {
      await createCustomer(form.value)
      ElMessage.success('客户已创建')
    }
    emit('update:visible', false)
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>
