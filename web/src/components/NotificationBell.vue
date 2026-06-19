<script setup lang="ts">
import { computed } from 'vue'
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
