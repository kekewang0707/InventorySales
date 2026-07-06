<template>
  <el-dialog
    v-model="dialogVisible"
    title="AI 快捷操作"
    width="780px"
    :close-on-click-modal="false"
    top="6vh"
    @opened="handleOpened"
    @closed="handleClosed"
  >
    <div class="ai-layout">
      <!-- ======== 侧边栏 ======== -->
      <div class="ai-sidebar">
        <div class="ai-new-chat" @click="addTab">
          <el-icon :size="16"><Plus /></el-icon>
          <span>开启新对话</span>
        </div>

        <!-- 7天内 -->
        <div v-if="sortedRecent.length" class="ai-group">
          <div class="ai-group-label">7天内</div>
          <div
            v-for="(tab, idx) in sortedRecent"
            :key="tab.sessionId"
            :class="['ai-session-item', { active: tab.sessionId === activeSessionId }]"
            @click="switchSession(tab.sessionId)"
          >
            <template v-if="renamingId === tab.sessionId">
              <input
                class="ai-rename-input"
                v-model="renameText"
                @keyup.enter="saveRename(tab.sessionId)"
                @keyup.escape="cancelRename"
                @blur="saveRename(tab.sessionId)"
                ref="renameInputRef"
              />
            </template>
            <span v-else class="ai-session-title" :title="tab.title" @dblclick="startRename(tab)">{{ tab.title }}</span>
            <el-icon class="ai-session-del" @click.stop="removeSession(tab.sessionId)">
              <Close />
            </el-icon>
          </div>
        </div>

        <!-- 30天内 -->
        <div v-if="sortedOlder.length" class="ai-group">
          <div class="ai-group-label">30天内</div>
          <div
            v-for="(tab, idx) in sortedOlder"
            :key="tab.sessionId"
            :class="['ai-session-item', { active: tab.sessionId === activeSessionId }]"
            @click="switchSession(tab.sessionId)"
          >
            <template v-if="renamingId === tab.sessionId">
              <input
                class="ai-rename-input"
                v-model="renameText"
                @keyup.enter="saveRename(tab.sessionId)"
                @keyup.escape="cancelRename"
                @blur="saveRename(tab.sessionId)"
                ref="renameInputRef"
              />
            </template>
            <span v-else class="ai-session-title" :title="tab.title" @dblclick="startRename(tab)">{{ tab.title }}</span>
            <el-icon class="ai-session-del" @click.stop="removeSession(tab.sessionId)">
              <Close />
            </el-icon>
          </div>
        </div>

        <div v-if="sessionsLoaded && tabs.length === 0" class="ai-sidebar-empty">
          暂无会话
        </div>
      </div>

      <!-- ======== 对话区域 ======== -->
      <div class="ai-conversation">
        <div v-if="loadingSessions" class="ai-loading-hint">正在加载会话...</div>
        <template v-else>
          <div v-if="!currentTab" class="ai-loading-hint">请选择或创建会话</div>
          <div v-else class="ai-messages" ref="messagesRef">
            <div
              v-for="(msg, idx) in currentTab.messages"
              :key="idx"
              :class="['ai-msg', msg.role]"
            >
              <div class="ai-msg-label">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
              <div class="ai-msg-bubble">
                <div style="white-space: pre-wrap; word-break: break-word">{{ msg.content }}</div>
              </div>
            </div>
            <div v-if="loading" class="ai-msg ai">
              <div class="ai-msg-label">AI</div>
              <div class="ai-msg-bubble"><span class="ai-thinking">思考中...</span></div>
            </div>
          </div>
        </template>

        <div class="ai-input-row">
          <el-input
            ref="inputRef"
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            placeholder="输入指令（Enter 发送，Shift+Enter 换行）"
            :disabled="loading || loadingSessions"
            @keydown.enter.prevent="handleSend"
          />
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!inputText.trim() || loadingSessions"
            @click="handleSend"
            style="margin-left: 8px; flex-shrink: 0;"
          >发送</el-button>
        </div>
      </div>
    </div>
  </el-dialog>

  <el-dialog v-model="confirmVisible" title="确认操作" width="420px" :close-on-click-modal="false">
    <div style="padding: 8px 0">
      <el-alert type="warning" :description="confirmText" show-icon />
    </div>
    <template #footer>
      <el-button @click="confirmVisible = false">取消</el-button>
      <el-button type="primary" :loading="confirmLoading" @click="handleConfirm">确认执行</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { Plus, Close } from '@element-plus/icons-vue'
import { sendCommand, confirmAction, listSessions, getSessionMessages, deleteSession, renameSession } from '../../api/ai.js'

const dialogVisible = ref(false)
const inputText = ref('')
const loading = ref(false)
const loadingSessions = ref(false)
const inputRef = ref(null)
const messagesRef = ref(null)

const confirmVisible = ref(false)
const confirmLoading = ref(false)
const confirmText = ref('')
const pendingConfirmId = ref('')

// ---- 重命名 -------
const renamingId = ref(null)
const renameText = ref('')

// ---- 会话管理 ----
const tabs = ref([])
const activeSessionId = ref(null)
const sessionsLoaded = ref(false)

const currentTab = computed(() => {
  const sid = activeSessionId.value
  if (!sid) return null
  return tabs.value.find(t => t.sessionId === sid) || null
})

// ---- 时间分组（直接用 tabs.value 过滤排序，不经过中间 computed）----
const nowMs = Date.now()
const CUTOFF_7D = nowMs - 7 * 24 * 60 * 60 * 1000
const CUTOFF_30D = nowMs - 30 * 24 * 60 * 60 * 1000

function _getFilteredTabs(minActive, maxActive) {
  return tabs.value
    .filter(t => {
      const a = t.lastActive || Date.now()
      return a >= minActive && a < maxActive
    })
    .sort((a, b) => (b.lastActive || 0) - (a.lastActive || 0))
}

// 使用普通函数（非 computed），在 activeSessionId 变化时模板会重渲染
const sortedRecent  = computed(() => _getFilteredTabs(CUTOFF_7D, Infinity))
const sortedOlder   = computed(() => _getFilteredTabs(CUTOFF_30D, CUTOFF_7D))

// 监听 tabs 变化时重新计算时间边界
// (注意：nowMs 在模块初始化时计算一次，页面生命周期内不变，避免每次过滤都重新计算)
// 这样最近 7/30 天的判定在页面生命周期内是固定的，不影响分组稳定性

const MAX_MESSAGES = 20

// ---- 恢复会话 ----
async function loadExistingSessions() {
  if (sessionsLoaded.value) return
  loadingSessions.value = true
  try {
    const res = await listSessions()
    const sessions = res.data || []
    if (sessions.length > 0) {
      const restored = []
      for (const s of sessions) {
        let msgs = []
        try {
          const r = await getSessionMessages(s.session_id)
          msgs = r.data?.messages || []
        } catch (e) {}
        restored.push({
          sessionId: s.session_id,
          messages: msgs,
          title: s.title || (s.first_message
            ? (s.first_message.length > 15 ? s.first_message.slice(0, 15) + '...' : s.first_message)
            : '会话'),
          lastActive: s.last_active ? new Date(s.last_active).getTime() : Date.now(),
        })
      }
      // 按 lastActive 降序
      restored.sort((a, b) => b.lastActive - a.lastActive)
      tabs.value = restored
      activeSessionId.value = restored[0]?.sessionId || null
    } else {
      const tab = { sessionId: crypto.randomUUID(), messages: [], title: '新会话', lastActive: Date.now() }
      tabs.value = [tab]
      activeSessionId.value = tab.sessionId
    }
    sessionsLoaded.value = true
  } catch (e) {
    const tab = { sessionId: crypto.randomUUID(), messages: [], title: '新会话', lastActive: Date.now() }
    tabs.value = [tab]
    activeSessionId.value = tab.sessionId
    sessionsLoaded.value = true
  } finally {
    loadingSessions.value = false
    scrollToBottom()
  }
}

// ---- 快捷键 ----
function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    dialogVisible.value = !dialogVisible.value
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  loadExistingSessions()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

function handleOpened() {
  scrollToBottom()
  if (inputRef.value) inputRef.value.focus()
}

function handleClosed() {}

// ---- 会话操作 ----
function addTab() {
  const tab = { sessionId: crypto.randomUUID(), messages: [], title: '新会话', lastActive: Date.now() }
  tabs.value.push(tab)
  activeSessionId.value = tab.sessionId
  scrollToBottom()
}

async function removeSession(sessionId) {
  if (tabs.value.length <= 1) return
  const idx = tabs.value.findIndex(t => t.sessionId === sessionId)
  if (idx === -1) return
  tabs.value.splice(idx, 1)
  if (activeSessionId.value === sessionId) {
    activeSessionId.value = tabs.value[0]?.sessionId || null
  }
  try { await deleteSession(sessionId) } catch (e) {}
}

// ---- 重命名 ----
function startRename(tab) {
  renamingId.value = tab.sessionId
  renameText.value = tab.title
  nextTick(() => {
    const el = document.querySelector('.ai-rename-input')
    if (el) { el.focus(); el.select() }
  })
}

async function saveRename(sessionId) {
  const title = renameText.value.trim()
  renamingId.value = null
  if (!title) return
  const tab = tabs.value.find(t => t.sessionId === sessionId)
  if (tab) tab.title = title
  try { await renameSession(sessionId, title) } catch (e) {}
}

function cancelRename() {
  renamingId.value = null
}

function switchSession(sessionId) {
  if (sessionId === activeSessionId.value) return
  activeSessionId.value = sessionId
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ---- 发送 ----
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value || !currentTab.value) return

  const tab = currentTab.value
  tab.lastActive = Date.now()
  tab.messages.push({ role: 'user', content: text })
  if (tab.messages.length > MAX_MESSAGES) tab.messages = tab.messages.slice(-MAX_MESSAGES)

  const userMsgCount = tab.messages.filter(m => m.role === 'user').length
  if (userMsgCount === 1) tab.title = text.length > 12 ? text.slice(0, 12) + '...' : text

  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const res = await sendCommand(text, tab.sessionId)
    const data = res.data
    if (data.session_id) tab.sessionId = data.session_id

    if (data.action === 'queried') {
      tab.messages.push({ role: 'ai', content: data.reply })
    } else if (data.action === 'needs_confirm') {
      tab.messages.push({ role: 'ai', content: data.reply })
      confirmText.value = data.reply
      pendingConfirmId.value = data.confirm_id
      confirmVisible.value = true
    } else if (data.action === 'executed') {
      tab.messages.push({ role: 'ai', content: data.reply })
    } else {
      tab.messages.push({ role: 'ai', content: data.reply || '操作失败，请重试' })
    }
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    tab.messages.push({ role: 'ai', content: `出错了: ${msg}` })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// ---- 确认 ----
async function handleConfirm() {
  if (!pendingConfirmId.value) return
  confirmLoading.value = true
  try {
    const res = await confirmAction(pendingConfirmId.value)
    const data = res.data
    confirmVisible.value = false
    if (currentTab.value) {
      currentTab.value.lastActive = Date.now()
      currentTab.value.messages.push({ role: 'ai', content: data.action === 'executed' ? data.reply : (data.reply || '操作失败') })
    }
    scrollToBottom()
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '确认失败'
    if (currentTab.value) currentTab.value.messages.push({ role: 'ai', content: `确认失败: ${msg}` })
  } finally {
    confirmLoading.value = false
    pendingConfirmId.value = ''
  }
}

function toggle() { dialogVisible.value = !dialogVisible.value }

defineExpose({ toggle })
</script>

<style scoped>
.ai-layout { display: flex; gap: 0; min-height: 420px; }

/* 侧边栏 */
.ai-sidebar { width: 220px; flex-shrink: 0; border-right: 1px solid #ebeef5; padding: 0 8px 12px; overflow-y: auto; max-height: 480px; }
.ai-new-chat { display: flex; align-items: center; gap: 6px; padding: 10px 12px; margin: 4px 0 12px; border: 1px dashed #409eff; border-radius: 6px; color: #409eff; font-size: 14px; cursor: pointer; transition: all .2s; user-select: none; }
.ai-new-chat:hover { background: #ecf5ff; border-style: solid; }
.ai-group { margin-bottom: 8px; }
.ai-group-label { font-size: 12px; color: #909399; padding: 4px 12px 6px; font-weight: 500; }
.ai-session-item { display: flex; align-items: center; padding: 7px 10px; margin: 1px 0; border-radius: 4px; font-size: 13px; color: #303133; cursor: pointer; transition: background .15s; user-select: none; }
.ai-session-item:hover { background: #f0f2f5; }
.ai-session-item.active { background: #ecf5ff; color: #409eff; font-weight: 500; }
.ai-rename-input {
  flex: 1;
  min-width: 0;
  height: 24px;
  padding: 1px 6px;
  border: 1px solid #409eff;
  border-radius: 3px;
  outline: none;
  font-size: 13px;
  background: #fff;
}
.ai-session-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ai-session-del { font-size: 12px; flex-shrink: 0; margin-left: 4px; border-radius: 50%; padding: 2px; opacity: 0; transition: opacity .15s; color: #c0c4cc; }
.ai-session-item:hover .ai-session-del { opacity: 1; }
.ai-session-del:hover { color: #f56c6c; background: rgba(0,0,0,.05); }
.ai-sidebar-empty { padding: 24px 12px; text-align: center; color: #c0c4cc; font-size: 13px; }

/* 对话 */
.ai-conversation { flex: 1; display: flex; flex-direction: column; padding-left: 12px; min-width: 0; }
.ai-messages { flex: 1; max-height: 380px; overflow-y: auto; padding: 4px 0 8px; }
.ai-msg { display: flex; gap: 8px; margin-bottom: 12px; }
.ai-msg.user { flex-direction: row-reverse; }
.ai-msg-label { flex-shrink: 0; width: 30px; height: 30px; line-height: 30px; text-align: center; border-radius: 50%; font-size: 11px; font-weight: 600; color: #fff; }
.ai-msg.ai .ai-msg-label { background-color: #409eff; }
.ai-msg.user .ai-msg-label { background-color: #67c23a; }
.ai-msg-bubble { max-width: 420px; padding: 9px 13px; border-radius: 8px; font-size: 14px; line-height: 1.6; color: #303133; }
.ai-msg.ai .ai-msg-bubble { background-color: #f0f2f5; }
.ai-msg.user .ai-msg-bubble { background-color: #ecf5ff; color: #303133; }
.ai-thinking { color: #909399; font-style: italic; }
.ai-loading-hint { text-align: center; color: #909399; padding: 60px 0; font-size: 14px; }
.ai-input-row { display: flex; align-items: flex-start; padding-top: 8px; border-top: 1px solid #ebeef5; }
</style>
