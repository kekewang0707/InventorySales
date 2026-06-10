<template>
  <!-- AI 指令面板 -->
  <el-dialog
    v-model="dialogVisible"
    title="AI 快捷操作"
    width="560px"
    :close-on-click-modal="false"
    top="10vh"
    destroy-on-close
    @closed="handleClosed"
  >
    <div class="ai-messages" ref="messagesRef">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="['ai-msg', msg.role]"
      >
        <div class="ai-msg-label">
          {{ msg.role === 'user' ? '你' : 'AI' }}
        </div>
        <div class="ai-msg-bubble">
          <div style="white-space: pre-wrap; word-break: break-word">{{ msg.content }}</div>
        </div>
      </div>
      <div v-if="loading" class="ai-msg ai">
        <div class="ai-msg-label">AI</div>
        <div class="ai-msg-bubble">
          <span class="ai-thinking">思考中...</span>
        </div>
      </div>
    </div>

    <div class="ai-input-row">
      <el-input
        ref="inputRef"
        v-model="inputText"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 4 }"
        placeholder="输入指令（Enter 发送，Shift+Enter 换行）"
        :disabled="loading"
        @keydown.enter.prevent="handleSend"
      />
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!inputText.trim()"
        @click="handleSend"
        style="margin-left: 8px"
      >
        发送
      </el-button>
    </div>
  </el-dialog>

  <!-- 确认对话框 -->
  <el-dialog
    v-model="confirmVisible"
    title="确认操作"
    width="420px"
    :close-on-click-modal="false"
  >
    <div style="padding: 8px 0">
      <el-alert type="warning" :description="confirmText" show-icon />
    </div>
    <template #footer>
      <el-button @click="confirmVisible = false">取消</el-button>
      <el-button type="primary" :loading="confirmLoading" @click="handleConfirm">
        确认执行
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { sendCommand, confirmAction } from '../../api/ai.js'

const dialogVisible = ref(false)
const inputText = ref('')
const loading = ref(false)
const messages = ref([])
const inputRef = ref(null)
const messagesRef = ref(null)

// 确认对话框
const confirmVisible = ref(false)
const confirmLoading = ref(false)
const confirmText = ref('')
const pendingConfirmId = ref('')

// 最多保留消息数
const MAX_MESSAGES = 20

// 快捷键
function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    dialogVisible.value = !dialogVisible.value
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// 滚动到底部
function scrollToBottom() {
  nextTick(() => {
    const el = messagesRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

// 发送消息
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  if (messages.value.length > MAX_MESSAGES) {
    messages.value = messages.value.slice(-MAX_MESSAGES)
  }
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const res = await sendCommand(text)
    const data = res.data

    if (data.action === 'queried') {
      messages.value.push({ role: 'ai', content: data.reply })
    } else if (data.action === 'needs_confirm') {
      messages.value.push({ role: 'ai', content: data.reply })
      confirmText.value = data.reply
      pendingConfirmId.value = data.confirm_id
      confirmVisible.value = true
    } else if (data.action === 'executed') {
      messages.value.push({ role: 'ai', content: data.reply })
    } else {
      messages.value.push({ role: 'ai', content: data.reply || '操作失败，请重试' })
    }
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    messages.value.push({ role: 'ai', content: `出错了: ${msg}` })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// 确认操作
async function handleConfirm() {
  if (!pendingConfirmId.value) return
  confirmLoading.value = true
  try {
    const res = await confirmAction(pendingConfirmId.value)
    const data = res.data
    confirmVisible.value = false
    if (data.action === 'executed') {
      messages.value.push({ role: 'ai', content: data.reply })
    } else {
      messages.value.push({ role: 'ai', content: data.reply || '操作失败' })
    }
    scrollToBottom()
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '确认失败'
    messages.value.push({ role: 'ai', content: `确认失败: ${msg}` })
  } finally {
    confirmLoading.value = false
    pendingConfirmId.value = ''
  }
}

function handleClosed() {
  // 保留消息历史
}

// 暴露 toggle 方法给父组件
function toggle() {
  dialogVisible.value = !dialogVisible.value
}

defineExpose({ toggle })
</script>

<style scoped>
.ai-messages {
  max-height: 420px;
  overflow-y: auto;
  padding: 8px 0;
  margin-bottom: 12px;
}

.ai-msg {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.ai-msg.user {
  flex-direction: row-reverse;
}

.ai-msg-label {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  line-height: 32px;
  text-align: center;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}

.ai-msg.ai .ai-msg-label {
  background-color: #409eff;
}

.ai-msg.user .ai-msg-label {
  background-color: #67c23a;
}

.ai-msg-bubble {
  max-width: 380px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
}

.ai-msg.ai .ai-msg-bubble {
  background-color: #f0f2f5;
}

.ai-msg.user .ai-msg-bubble {
  background-color: #ecf5ff;
  color: #303133;
}

.ai-thinking {
  color: #909399;
  font-style: italic;
}

.ai-input-row {
  display: flex;
  align-items: flex-start;
}
</style>
