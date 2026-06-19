<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'
import {
  markAllNotificationsRead,
  markNotificationRead,
  notifyKeys,
  useNotificationsQuery,
  useUnreadCountQuery
} from '@/api/notify'
import type { AppNotification } from '@/types'

const queryClient = useQueryClient()
const { data: unreadData } = useUnreadCountQuery()
const { data: listData, refetch } = useNotificationsQuery()

const unread = computed(() => unreadData.value?.unread ?? 0)
const items = computed<AppNotification[]>(() => listData.value?.results ?? [])

function refresh() {
  void queryClient.invalidateQueries({ queryKey: notifyKeys.unread })
  void refetch()
}

async function readOne(n: AppNotification) {
  if (n.is_read) return
  await markNotificationRead(n.id)
  refresh()
}

async function readAll() {
  if (unread.value === 0) return
  await markAllNotificationsRead()
  ElMessage.success('已全部标记已读')
  refresh()
}

// WebSocket 实时推送:后端 notify 落库即推 {type:'notification'},到达即刷新未读/列表。
// 掉线由 useUnreadCountQuery 的 30s 轮询兜底,简单 5s 重连。
let ws: WebSocket | null = null
let closed = false
let retry: ReturnType<typeof setTimeout> | null = null

function connect() {
  if (closed) return
  const token = localStorage.getItem('access_token')
  if (!token) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  // token 经 Sec-WebSocket-Protocol 子协议传递(["access_token", <jwt>]),不进 URL,避免 access log 泄漏。
  ws = new WebSocket(`${proto}://${location.host}/ws/notifications`, ['access_token', token])
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data) as { type?: string }
      if (msg?.type === 'notification') refresh()
    } catch {
      /* 忽略非 JSON 帧 */
    }
  }
  ws.onclose = () => {
    ws = null
    if (!closed) retry = setTimeout(connect, 5000)
  }
  ws.onerror = () => ws?.close()
}

onMounted(connect)
onBeforeUnmount(() => {
  closed = true
  if (retry) clearTimeout(retry)
  ws?.close()
})
</script>

<template>
  <el-popover placement="bottom" :width="340" trigger="click" @show="refresh">
    <template #reference>
      <el-badge :value="unread" :hidden="unread === 0" :max="99" class="bell">
        <span class="bell__icon" aria-label="通知" role="img">🔔</span>
      </el-badge>
    </template>
    <div class="nlist">
      <div class="nlist__head">
        <span class="nlist__title">通知</span>
        <el-button link type="primary" size="small" :disabled="unread === 0" @click="readAll">
          全部已读
        </el-button>
      </div>
      <el-empty v-if="items.length === 0" description="暂无通知" :image-size="60" />
      <div
        v-for="n in items"
        :key="n.id"
        class="nitem"
        :class="{ 'nitem--unread': !n.is_read }"
        @click="readOne(n)"
      >
        <div class="nitem__title">{{ n.title }}</div>
        <div class="nitem__msg">{{ n.message }}</div>
        <div class="nitem__time">{{ n.created_at }}</div>
      </div>
    </div>
  </el-popover>
</template>

<style scoped>
.bell {
  cursor: pointer;
  display: inline-flex;
}

.bell__icon {
  font-size: 18px;
  line-height: 1;
}

.nlist {
  max-height: 420px;
  overflow-y: auto;
}

.nlist__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.nlist__title {
  font-weight: 700;
}

.nitem {
  padding: 8px 6px;
  border-top: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
}

.nitem--unread {
  background: var(--el-color-primary-light-9);
}

.nitem__title {
  font-weight: 600;
  font-size: 13px;
}

.nitem__msg {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}

.nitem__time {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-top: 2px;
}
</style>
