<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElCheckbox } from 'element-plus'
import { useRouter } from 'vue-router'
import { read, write } from '../api'
import { message, requestKey } from '../utils/request'
import type { Row } from '../types'
const router = useRouter()
const rows = ref<Row[]>([]), unread = ref(true), count = ref(0), unreadCount = ref(0), page = ref(1)
const loading = ref(false), busy = ref(false), error = ref('')
let generation = 0, timer: ReturnType<typeof setInterval> | undefined
async function load() {
  const current = ++generation
  loading.value = true
  try {
    const result = await read('/business/task-notices/', { unread: unread.value, page: page.value, page_size: 5 })
    if (current !== generation) return
    rows.value = result.results; count.value = result.count; unreadCount.value = result.unread_count; error.value = ''
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) loading.value = false }
}
async function open(row: Row) {
  busy.value = true
  try {
    if (!row.read_at) await write(`/business/task-notices/${row.id}/read/`, {}, requestKey())
    await router.push({ path: `/projects/${row.project}`, query: { tab: 'tasks', section: 'tasks', resource: 'tasks', focus: row.task } })
  } catch (e) { error.value = message(e) }
  finally { busy.value = false }
}
function refreshVisible() { if (document.visibilityState === 'visible' && !busy.value && !loading.value) void load() }
watch(unread, () => { page.value = 1; void load() })
onMounted(() => { void load(); timer = setInterval(refreshVisible, 60000); window.addEventListener('focus', refreshVisible) })
onBeforeUnmount(() => { generation++; clearInterval(timer); window.removeEventListener('focus', refreshVisible) })
</script>
<template>
  <section class="panel task-notices" aria-label="任务提醒">
    <header><h2>任务提醒 <el-tag>{{ unreadCount }} 条未读</el-tag></h2><div class="toolbar"><el-checkbox v-model="unread">只看未读</el-checkbox><el-button :loading="loading" @click="load">刷新提醒</el-button></div></header>
    <p class="muted">任务分配或调整后提醒负责主管。查看提醒不会将任务标为完成。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <ul v-if="rows.length"><li v-for="row in rows" :key="row.id"><div><strong>{{ row.project_name }} · {{ row.task_title }}</strong><p>{{ row.message }}</p><small class="muted">{{ new Date(row.created_at).toLocaleString('zh-CN') }} · {{ row.read_at ? '已读' : '未读' }}</small></div><el-button type="primary" plain :disabled="busy" @click="open(row)">查看并处理</el-button></li></ul>
    <p v-else-if="!loading && !error" class="muted">{{ unread ? '没有未读任务提醒' : '暂无任务提醒' }}</p>
    <el-pagination v-if="count > 5" :current-page="page" :page-size="5" :total="count" layout="prev, pager, next" @current-change="(value: number) => { page = value; load() }" />
  </section>
</template>
<style scoped>
header, li { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
h2 { margin: 0; font-size: 18px; }
ul { list-style: none; padding: 0; margin-bottom: 0; }
li { border-top: 1px solid var(--surface-border); padding: 16px 0; }
li div { min-width: 0; overflow-wrap: anywhere; }
p { line-height: 1.6; }
@media (max-width: 640px) { header, li { align-items: stretch; flex-direction: column; } }
</style>
