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
const lastSeen = ref(0)
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
const labels: Record<string, string> = { queued: '等待执行', downloading: '下载并校验', backing_up: '备份数据', installing: '安装新版本', verifying: '验证并启动', succeeded: '升级完成', failed: '升级失败' }
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
    lastSeen.value = now.value
    if (state.value.release?.version?.replace(/^v/, '') === state.value.current) state.value.available = false
    error.value = result.check_error || ''
  } catch (e) {
    if (sequence !== refreshSequence) return
    disconnected.value = true
    error.value = active.value ? '' : message(e)
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
    <el-alert v-if="!state.runner && !active && !disconnected" title="宿主机升级执行器未连接" type="info" :closable="false">
      安装器会自动启动升级服务，正在等待连接。若持续未连接，请检查宿主机服务状态；旧版安装请使用新版安装器接入自动服务，现有数据会保留。
    </el-alert>
    <p v-if="state.runner && !disconnected && !active">执行器已连接：{{ state.runner.platform }} / {{ state.runner.mode === 'docker' ? 'Docker' : '原生部署' }}</p>
    <section v-if="state.job" class="upgrade-job" aria-label="升级进度">
      <strong>{{ disconnected && active ? '正在重新连接' : (labels[state.job.status] || state.job.status) }} · {{ state.job.target }}</strong>
      <p v-if="disconnected && active" role="status">暂时无法获取最新进度，将自动重连。下面是上次收到的状态，不代表任务仍停在该步骤。</p>
      <p v-if="disconnected && active" class="upgrade-timing">上次更新 {{ lastSeen ? new Date(lastSeen).toLocaleTimeString() : '—' }} · {{ labels[state.job.status] }}</p>
      <p v-if="state.job.status !== 'failed'" role="status" aria-live="polite">{{ disconnected && active ? '上次记录：' : '' }}{{ state.job.detail }}</p>
      <p v-else role="status">本次自动升级未完成{{ state.job.backup ? '，完整备份已保留' : '' }}。原因可展开查看。</p>
      <p v-if="state.job.status === 'failed' && state.current === state.job.target?.replace(/^v/, '')">当前服务已运行目标版本。此次升级的失败记录仍保留，便于追溯。</p>
      <p v-if="active" class="upgrade-timing"><span v-if="!disconnected" class="upgrade-pulse" aria-hidden="true" />任务已用时 {{ Math.floor(elapsed / 60) }} 分 {{ elapsed % 60 }} 秒<span v-if="!disconnected"> · 步骤 {{ step + 1 }} / {{ steps.length }}</span></p>
      <p v-if="active && !disconnected" class="upgrade-hint">{{ state.job.status === 'downloading' ? '正在准备新版本，通常需要数分钟，期间可继续使用。完成后会自动备份并短暂停机。' : '正在完成升级，服务恢复后会自动更新结果。' }}</p>
      <details class="upgrade-stage-details">
        <summary>查看步骤与详情</summary>
        <div class="upgrade-steps" role="list" aria-label="升级步骤">
          <div v-for="(status, index) in steps" :key="status" role="listitem" :class="{ complete: step > index, current: step === index && !disconnected }" :aria-current="step === index ? 'step' : undefined"><span>{{ index + 1 }}</span>{{ labels[status] }}</div>
        </div>
        <p v-if="state.job.status === 'failed'">{{ state.job.detail }}</p>
        <p v-if="state.job.backup">备份位置：{{ state.job.backup }}</p>
      </details>
      <p v-if="active" class="upgrade-hint">关闭窗口后仍会继续升级。</p>
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
.upgrade-steps > div { display: flex; align-items: center; gap: 7px; padding: 8px; border: 1px solid #dce3ed; border-radius: 8px; color: #596b82; font-size: 12px; }
.upgrade-steps > div > span { display: grid; place-items: center; width: 22px; height: 22px; flex-shrink: 0; border-radius: 50%; background: #e3e9f1; }
.upgrade-hint, .upgrade-stage-details { color: #596b82; font-size: 13px; }
.upgrade-stage-details summary { cursor: pointer; }
.upgrade-job { margin-top: 16px; padding: 16px; background: #f5f7fb; border: 1px solid #dce3ed; border-radius: 8px; }
.upgrade-job p { overflow-wrap: anywhere; }
.upgrade-steps .current { color: #245fc7; border-color: #245fc7; background: #edf3ff; font-weight: 600; }
.upgrade-steps .complete { color: #28684e; border-color: #91b7a6; }
.upgrade-timing { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.upgrade-pulse { width: 10px; height: 10px; background: #245fc7; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .upgrade-pulse { animation: none; } }
@media (max-width: 480px) { .upgrade-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
