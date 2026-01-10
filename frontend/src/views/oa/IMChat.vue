<template>
  <div class="im-container">
    <div class="im-sidebar">
      <div class="im-header">
        <el-input v-model="searchKeyword" placeholder="搜索会话" prefix-icon="Search" clearable />
        <el-button type="primary" :icon="Plus" circle @click="showNewConversation = true" />
      </div>
      
      <div class="conversation-list" v-loading="loadingConversations">
        <div 
          v-for="conv in conversations" 
          :key="conv.id"
          class="conversation-item"
          :class="{ active: currentConversation?.id === conv.id }"
          @click="selectConversation(conv)"
        >
          <el-badge :value="conv.unread_count" :hidden="!conv.unread_count" :max="99">
            <el-avatar :size="42" :icon="conv.type === 'GROUP' ? UserFilled : User">
              {{ conv.name?.charAt(0) }}
            </el-avatar>
          </el-badge>
          <div class="conv-info">
            <div class="conv-name">
              {{ conv.name || conv.title }}
              <el-tag v-if="conv.type === 'GROUP'" size="small" type="info">群</el-tag>
            </div>
            <div class="conv-preview">{{ conv.last_message?.content || '暂无消息' }}</div>
          </div>
          <div class="conv-time">{{ formatTime(conv.last_message?.created_at) }}</div>
        </div>
        
        <el-empty v-if="!conversations.length" description="暂无会话" :image-size="60" />
      </div>
    </div>
    
    <div class="im-main" v-if="currentConversation">
      <div class="chat-header">
        <div class="chat-title">
          {{ currentConversation.name || currentConversation.title }}
          <span v-if="currentConversation.type === 'GROUP'" class="member-count">
            ({{ currentConversation.members?.length || 0 }}人)
          </span>
        </div>
        <div class="chat-actions">
          <el-dropdown v-if="currentConversation.type === 'GROUP'">
            <el-button :icon="MoreFilled" link />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="showGroupMembers = true">查看成员</el-dropdown-item>
                <el-dropdown-item @click="showAddMembers = true">邀请成员</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
      
      <div class="chat-messages" ref="messagesContainer" @scroll="handleScroll">
        <div v-if="loadingMessages" class="loading-more">
          <el-icon class="is-loading"><Loading /></el-icon>
          加载中...
        </div>
        
        <div 
          v-for="msg in messages" 
          :key="msg.id" 
          class="message-item"
          :class="{ 'my-message': msg.sender?.id === currentUserId }"
        >
          <el-avatar :size="36" v-if="msg.sender?.id !== currentUserId">
            {{ msg.sender?.username?.charAt(0) }}
          </el-avatar>
          <div class="message-content">
            <div class="message-sender" v-if="msg.sender?.id !== currentUserId && currentConversation?.type === 'GROUP'">
              {{ msg.sender?.username }}
            </div>
            <div class="message-bubble" :class="{ file: msg.message_type !== 'TEXT' }">
              <template v-if="msg.message_type === 'TEXT'">
                {{ msg.content }}
              </template>
              <template v-else-if="msg.message_type === 'IMAGE'">
                <el-image :src="msg.file_url" style="max-width: 200px; max-height: 200px" preview />
              </template>
              <template v-else-if="msg.message_type === 'FILE'">
                <el-link :href="msg.file_url" target="_blank">
                  <el-icon><Document /></el-icon>
                  {{ msg.file_name || '文件' }}
                </el-link>
              </template>
            </div>
            <div class="message-time">{{ formatMsgTime(msg.created_at) }}</div>
          </div>
          <el-avatar :size="36" v-if="msg.sender?.id === currentUserId">
            {{ msg.sender?.username?.charAt(0) }}
          </el-avatar>
        </div>
        
        <el-empty v-if="!messages.length" description="暂无消息，开始聊天吧" :image-size="60" />
      </div>
      
      <div class="chat-input">
        <div class="input-toolbar">
          <el-upload
            :show-file-list="false"
            :before-upload="handleFileUpload"
            :action="'#'"
          >
            <el-button :icon="Paperclip" link />
          </el-upload>
        </div>
        <el-input 
          v-model="messageInput" 
          type="textarea"
          :rows="3"
          placeholder="输入消息，按 Enter 发送"
          resize="none"
          @keydown.enter.prevent="sendMessage"
        />
        <el-button type="primary" :icon="Promotion" @click="sendMessage" :loading="sendingMessage">
          发送
        </el-button>
      </div>
    </div>
    
    <div class="im-empty" v-else>
      <el-empty description="选择一个会话开始聊天" :image-size="100" />
    </div>
    
    <!-- 新建会话对话框 -->
    <el-dialog v-model="showNewConversation" title="发起会话" width="500px">
      <el-form label-width="80px">
        <el-form-item label="会话类型">
          <el-radio-group v-model="newConvType">
            <el-radio label="PRIVATE">私聊</el-radio>
            <el-radio label="GROUP">群聊</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="群名称" v-if="newConvType === 'GROUP'">
          <el-input v-model="newConvName" placeholder="请输入群名称" />
        </el-form-item>
        <el-form-item label="选择成员">
          <el-select v-model="selectedMembers" multiple filterable placeholder="搜索并选择成员" style="width: 100%">
            <el-option 
              v-for="user in userList" 
              :key="user.id" 
              :label="user.username" 
              :value="user.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewConversation = false">取消</el-button>
        <el-button type="primary" @click="createConversation" :loading="creatingConversation">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 群成员对话框 -->
    <el-dialog v-model="showGroupMembers" title="群成员" width="400px">
      <el-table :data="currentConversation?.members || []" size="small">
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="role" label="角色" width="80">
          <template #default="{ row }">
            <el-tag :type="row.role === 'ADMIN' ? 'warning' : 'info'" size="small">
              {{ row.role === 'ADMIN' ? '管理员' : '成员' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  Plus, Search, User, UserFilled, MoreFilled, 
  Loading, Document, Paperclip, Promotion
} from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const currentUserId = computed(() => userStore.userInfo?.id)

const searchKeyword = ref('')
const loadingConversations = ref(false)
const conversations = ref([])
const currentConversation = ref(null)
const messages = ref([])
const messageInput = ref('')
const loadingMessages = ref(false)
const sendingMessage = ref(false)
const messagesContainer = ref(null)

const showNewConversation = ref(false)
const showGroupMembers = ref(false)
const showAddMembers = ref(false)
const newConvType = ref('PRIVATE')
const newConvName = ref('')
const selectedMembers = ref([])
const userList = ref([])
const creatingConversation = ref(false)

// 加载会话列表
const loadConversations = async () => {
  loadingConversations.value = true
  try {
    const { data } = await request.get('/core/conversations/')
    conversations.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    loadingConversations.value = false
  }
}

// 选择会话
const selectConversation = async (conv) => {
  currentConversation.value = conv
  await loadMessages(conv.id)
  markAsRead(conv.id)
}

// 加载消息
const loadMessages = async (convId) => {
  loadingMessages.value = true
  try {
    const { data } = await request.get('/core/messages/', {
      params: { conversation: convId, page_size: 50 }
    })
    messages.value = (data.results || data).reverse()
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error(e)
  } finally {
    loadingMessages.value = false
  }
}

// 发送消息
const sendMessage = async () => {
  if (!messageInput.value.trim() || !currentConversation.value) return
  
  sendingMessage.value = true
  try {
    const { data } = await request.post('/core/messages/', {
      conversation: currentConversation.value.id,
      content: messageInput.value.trim(),
      message_type: 'TEXT'
    })
    messages.value.push(data)
    messageInput.value = ''
    await nextTick()
    scrollToBottom()
    
    // 更新会话列表中的最后消息
    const conv = conversations.value.find(c => c.id === currentConversation.value.id)
    if (conv) {
      conv.last_message = data
    }
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    sendingMessage.value = false
  }
}

// 文件上传
const handleFileUpload = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('conversation', currentConversation.value.id)
  formData.append('message_type', file.type.startsWith('image/') ? 'IMAGE' : 'FILE')
  formData.append('content', file.name)
  
  try {
    const { data } = await request.post('/core/messages/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    messages.value.push(data)
    await nextTick()
    scrollToBottom()
    ElMessage.success('文件已发送')
  } catch (e) {
    ElMessage.error('发送失败')
  }
  return false
}

// 标记已读
const markAsRead = async (convId) => {
  try {
    await request.post(`/core/conversations/${convId}/mark_as_read/`)
    const conv = conversations.value.find(c => c.id === convId)
    if (conv) conv.unread_count = 0
  } catch (e) {
    // 忽略
  }
}

// 创建会话
const createConversation = async () => {
  if (selectedMembers.value.length === 0) {
    ElMessage.warning('请选择至少一个成员')
    return
  }
  
  creatingConversation.value = true
  try {
    const { data } = await request.post('/core/conversations/', {
      type: newConvType.value,
      name: newConvType.value === 'GROUP' ? newConvName.value : null,
      members: selectedMembers.value
    })
    conversations.value.unshift(data)
    showNewConversation.value = false
    selectConversation(data)
    ElMessage.success('会话创建成功')
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    creatingConversation.value = false
  }
}

// 加载用户列表
const loadUserList = async () => {
  try {
    const { data } = await request.get('/accounts/users/', { params: { page_size: 200 } })
    userList.value = (data.results || data).filter(u => u.id !== currentUserId.value)
  } catch (e) {
    console.error(e)
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const handleScroll = (e) => {
  // 滚动到顶部时加载更多
  if (e.target.scrollTop < 50) {
    // TODO: loadMore()
  }
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = (now - date) / 1000
  
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`
  return date.toLocaleDateString()
}

const formatMsgTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

// 轮询新消息
let pollTimer = null
const pollNewMessages = () => {
  pollTimer = setInterval(async () => {
    if (currentConversation.value) {
      await loadMessages(currentConversation.value.id)
    }
    await loadConversations()
  }, 10000)
}

onMounted(() => {
  loadConversations()
  loadUserList()
  pollNewMessages()
})

// 组件卸载时清除轮询
import { onUnmounted } from 'vue'
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.im-container {
  display: flex;
  height: calc(100vh - 140px);
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.im-sidebar {
  width: 300px;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
}

.im-header {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #e8e8e8;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  cursor: pointer;
  border-bottom: 1px solid #f5f5f5;
  transition: background .2s;
}

.conversation-item:hover,
.conversation-item.active {
  background: #f0f7ff;
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  display: flex;
  align-items: center;
  gap: 6px;
}

.conv-preview {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 4px;
}

.conv-time {
  font-size: 11px;
  color: #bbb;
}

.im-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.im-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e8e8e8;
}

.chat-title {
  font-size: 16px;
  font-weight: 500;
}

.member-count {
  font-size: 12px;
  color: #999;
  font-weight: normal;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f5f7fa;
}

.loading-more {
  text-align: center;
  padding: 10px;
  color: #999;
}

.message-item {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.message-item.my-message {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 60%;
}

.message-sender {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.my-message .message-sender {
  text-align: right;
}

.message-bubble {
  padding: 10px 14px;
  background: #fff;
  border-radius: 8px;
  word-break: break-word;
  line-height: 1.5;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.my-message .message-bubble {
  background: #409eff;
  color: #fff;
}

.message-bubble.file {
  background: #fff !important;
  color: #333 !important;
}

.message-time {
  font-size: 11px;
  color: #bbb;
  margin-top: 4px;
}

.my-message .message-time {
  text-align: right;
}

.chat-input {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid #e8e8e8;
  background: #fff;
  align-items: flex-end;
}

.input-toolbar {
  padding-bottom: 8px;
}

.chat-input :deep(.el-textarea__inner) {
  border-radius: 8px;
}
</style>
