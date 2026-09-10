<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElCheckbox } from 'element-plus'
import { read, write } from '../api'
import { can } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'

const emit = defineEmits<{ opened: [] }>()
const open = ref(false)
const state = ref<Row>({})
const busy = ref(false)
const error = ref('')
const confirmed = ref(false)
const requestKey = ref(crypto.randomUUID())
const disconnected = ref(false)
const now = ref(Date.now())
const steps = ['queued', 'downloading', 'backing_up', 'installing', 'verifying', 'succeeded']
const step = computed(() => steps.indexOf(state.value.job?.status))
const elapsed = computed(() => {
  const started = Date.parse(state.value.job?.created_at || '')
  return Number.isFinite(started) ? Math.max(0, Math.floor((now.value - started) / 1000)) : 0
})
let refreshSequence = 0
let timer: ReturnType<typeof setInterval> | undefined
const admin = computed(() => can(['admin']))
const active = computed(() => ['queued', 'downloading', 'backing_up', 'installing', 'verifying'].includes(state.value.job?.status))
const labels: Record<string, string> = { queued: '等待执行', downloading: '下载、校验与构建', backing_up: '备份数据', installing: '安装新版本', verifying: '验证并启动', succeeded: '升级完成', failed: '升级失败' }
async function refresh(check = false) {
  if (!admin.value) return
  const sequence = ++refreshSequence
  if (check) busy.value = true
  try {
    const result = await read('/core/upgrade/', check ? { check: '1' } : {})
    if (sequence !== refreshSequence) return
    state.value = { ...state.value, ...result }
    disconnected.value = false
    now.value = Date.now()
    if (state.value.release?.version?.replace(/^v/, '') === state.value.current) state.value.available = false
    error.value = result.check_error || ''
  } catch (e) {
    if (sequence !== refreshSequence) return
    disconnected.value = true
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
watch([open, active], ([visible, running], [wasVisible]) => {
  if (timer) clearInterval(timer)
  if (visible && !wasVisible) void refresh(true)
  if (visible || running) timer = setInterval(() => { now.value = Date.now(); if (!busy.value) void refresh() }, 3000)
})
watch(admin, value => {
  if (value) void refresh()
  else { open.value = false; state.value = {}; confirmed.value = false }
}, { immediate: true })
onBeforeUnmount(() => { refreshSequence++; if (timer) clearInterval(timer) })
</script>

<template>
  <button v-if="admin" class="system-upgrade-entry" @click="open = true; emit('opened')">
    <span>{{ active ? '升级进行中' : '版本与升级' }}</span><small v-if="state.current">{{ active ? labels[state.job.status] : `v${state.current}` }}</small>
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
      <ol class="upgrade-steps" aria-label="升级步骤">
        <li v-for="(status, index) in steps" :key="status" :class="{ complete: step > index, current: step === index }" :aria-current="step === index ? 'step' : undefined"><span>{{ index + 1 }}</span>{{ labels[status] }}</li>
      </ol>
      <p role="status" aria-live="polite">{{ state.job.detail }}</p>
      <p v-if="active" class="upgrade-timing"><span class="upgrade-pulse" aria-hidden="true" />已用时 {{ Math.floor(elapsed / 60) }} 分 {{ elapsed % 60 }} 秒 · 每 3 秒检查进度</p>
      <p v-if="disconnected && active">服务暂不可用，以上为最后确认的进度。实际进度将在服务恢复后同步，不代表任务已停止。</p>
      <p v-if="state.job.backup">备份位置：{{ state.job.backup }}（早期执行器的失败任务请以目录内实际文件为准）</p>
      <p v-if="active">下载与构建时原系统继续运行；备份和安装时会短暂中断服务。关闭窗口后仍会继续升级。</p>
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
<style scoped>
.upgrade-steps { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }
.upgrade-steps li { display: flex; align-items: center; gap: 7px; padding: 8px; border: 1px solid #dce3ed; border-radius: 8px; color: #596b82; font-size: 12px; }
.upgrade-steps li > span { display: grid; place-items: center; width: 22px; height: 22px; flex-shrink: 0; border-radius: 50%; background: #e3e9f1; }
.upgrade-steps .current { color: #245fc7; border-color: #245fc7; background: #edf3ff; font-weight: 600; }
.upgrade-steps .complete { color: #28684e; border-color: #91b7a6; }
.upgrade-timing { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.upgrade-pulse { width: 10px; height: 10px; background: #245fc7; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .upgrade-pulse { animation: none; } }
@media (max-width: 480px) { .upgrade-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
