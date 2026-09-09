<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElCheckbox } from 'element-plus'
import { read, write } from '../api'
import { user } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'

const emit = defineEmits<{ opened: [] }>()
const open = ref(false)
const state = ref<Row>({})
const busy = ref(false)
const error = ref('')
const confirmed = ref(false)
const requestKey = ref(crypto.randomUUID())
let timer: ReturnType<typeof setInterval> | undefined
const admin = computed(() => user.value?.role === 'admin')
const active = computed(() => ['queued', 'downloading', 'backing_up', 'installing', 'verifying'].includes(state.value.job?.status))
const labels: Record<string, string> = { queued: '等待执行', downloading: '下载与校验', backing_up: '备份数据', installing: '安装新版本', verifying: '验证并启动', succeeded: '升级完成', failed: '升级失败' }
async function refresh(check = false) {
  if (!admin.value) return
  if (check) busy.value = true
  try {
    const result = await read('/core/upgrade/', check ? { check: '1' } : {})
    state.value = { ...state.value, ...result }
    if (state.value.release?.version?.replace(/^v/, '') === state.value.current) state.value.available = false
    error.value = result.check_error || ''
  } catch (e) {
    error.value = active.value ? '服务正在重启或暂时无法连接，将自动重试。若长时间未恢复，请查看宿主机升级日志。' : message(e)
  } finally { if (check) busy.value = false }
}
async function upgrade() {
  if (busy.value || !confirmed.value || active.value) return
  busy.value = true
  error.value = ''
  try {
    state.value.job = await write('/core/upgrade/', { target: state.value.release.version, confirmed: true }, requestKey.value)
    confirmed.value = false
    requestKey.value = crypto.randomUUID()
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
watch(open, value => {
  if (timer) clearInterval(timer)
  if (value) {
    void refresh(true)
    timer = setInterval(() => { if (!busy.value) void refresh() }, 5000)
  }
})
watch(admin, value => {
  if (value) void refresh()
  else { open.value = false; state.value = {}; confirmed.value = false }
}, { immediate: true })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <button v-if="admin" class="system-upgrade-entry" @click="open = true; emit('opened')">
    <span>版本与升级</span><small v-if="state.current">v{{ state.current }}</small>
  </button>
  <el-dialog v-if="admin" v-model="open" title="ERP 版本与升级" width="min(640px, calc(100vw - 24px))" :close-on-click-modal="false" append-to-body>
    <div class="upgrade-summary">
      <span>当前版本 <strong>{{ state.current ? `v${state.current}` : '读取中…' }}</strong></span>
      <el-button :loading="busy" @click="refresh(true)">检查新版本</el-button>
    </div>
    <p v-if="state.release">最新正式版 <strong>{{ state.release.version }}</strong> · {{ state.available ? '有新版本可升级' : '当前已是最新版本或更新的开发版本' }}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="!state.runner && !active" title="宿主机升级执行器未连接" type="info" :closable="false">
      先按 README 的“在线升级”章节启动执行器。原生与 Docker 部署均需配置一次，连接后可在此发起升级。
    </el-alert>
    <p v-if="state.runner">执行器已连接：{{ state.runner.platform }} / {{ state.runner.mode === 'docker' ? 'Docker' : '原生部署' }}</p>
    <section v-if="state.job" class="upgrade-job" aria-label="升级进度">
      <strong>{{ labels[state.job.status] || state.job.status }} · {{ state.job.target }}</strong>
      <p>{{ state.job.detail }}</p>
      <p v-if="state.job.backup">备份位置：{{ state.job.backup }}</p>
      <p v-if="active">升级时会短暂中断服务，可保留此窗口等待重连。</p>
    </section>
    <details v-if="state.release" class="upgrade-notes">
      <summary>查看版本更新内容</summary>
      <p class="upgrade-notes-text">{{ state.release.notes || '此版本没有更新说明。' }}</p>
      <a :href="state.release.url" target="_blank" rel="noopener noreferrer">查看发布页面</a>
    </details>
    <el-checkbox v-if="state.available && !active" v-model="confirmed">我已通知使用者暂停操作，同意备份后升级并短暂停机</el-checkbox>
    <template #footer>
      <el-button @click="open = false">关闭</el-button>
      <el-button type="primary" :loading="busy" :disabled="!state.available || !state.runner || !state.configured || !confirmed || active" @click="upgrade">备份并升级</el-button>
    </template>
  </el-dialog>
</template>
