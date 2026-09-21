<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElCheckbox } from 'element-plus'
import { getUpgrade, prepareUpgrade, restartUpgrade, type UpgradeState } from '../api/upgrade'
import { can } from '../session'
import { message, requestKey } from '../utils/request'

const emit = defineEmits<{ opened: [] }>()
const open = ref(false)
const state = ref<Partial<UpgradeState>>({})
const busy = ref(false)
const checking = ref(false)
const error = ref('')
const confirmed = ref(false)
const upgradeKey = ref(requestKey())
const restartKey = ref(requestKey())
const disconnected = ref(false)
const now = ref(Date.now())
const lastSeen = ref(0)
const checkError = ref('')
const manualMode = ref('docker')
const restartTarget = ref('')
const reloadCountdown = ref(0)
let reloadTimer: ReturnType<typeof setInterval> | undefined
const guideUrl = 'https://github.com/hongheshan-svg/atm-erp/blob/main/README.md#升级与备份'
function compareVersions(left: string, right: string) {
  if (![left, right].every(value => /^v?\d+\.\d+\.\d+$/.test(value))) return null
  const a = left.replace(/^v/, '').split('.').map(Number)
  const b = right.replace(/^v/, '').split('.').map(Number)
  for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i]! - b[i]!
  return 0
}
const container = computed(() => state.value.execution === 'container')
const steps = computed(() => ['queued', 'downloading', ...(container.value ? ['ready', 'restarting'] : []), 'backing_up', 'installing', 'verifying', 'succeeded'])
const step = computed(() => steps.value.indexOf(state.value.job?.status || ''))
const elapsed = computed(() => {
  const started = Date.parse(state.value.job?.created_at || '')
  return Number.isFinite(started) ? Math.max(0, Math.floor((now.value - started) / 1000)) : 0
})
let refreshSequence = 0
let timer: ReturnType<typeof setInterval> | undefined
const admin = computed(() => can(['admin']))
const active = computed(() => ['queued', 'downloading', 'ready', 'restarting', 'backing_up', 'installing', 'verifying'].includes(state.value.job?.status || ''))
const needsRestart = computed(() => container.value && state.value.job?.status === 'ready' && state.value.job.need_restart)
const canRestart = computed(() => !!(needsRestart.value && !disconnected.value && state.value.configured && state.value.runner))
const available = computed(() => !checkError.value && !disconnected.value && state.value.available && (compareVersions(state.value.release?.version || '', state.value.current || '') ?? 0) > 0)
const canUpgrade = computed(() => available.value && state.value.runner && state.value.configured && !active.value)
const completed = computed(() => !disconnected.value && state.value.job?.status === 'succeeded' && (compareVersions(state.value.current || '', state.value.job.target || '') ?? -1) >= 0)
const versionStatus = computed(() => {
  if (disconnected.value) return '连接中断，版本状态待确认'
  if (needsRestart.value) return '更新已准备完成，等待重启生效'
  if (checkError.value) return state.value.release ? '检查失败，以下为上次发布信息' : '暂时无法检查新版本'
  if (!state.value.release) return '尚未取得最新发布信息'
  return available.value ? '有新版本可升级' : '当前已是最新版本或更新的开发版本'
})
function dateText(value: string | number) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN')
}
function reloadPage() { window.location.reload() }
const historicalFailure = computed(() => {
  if (state.value.job?.status !== 'failed') return false
  return (compareVersions(state.value.current || '', state.value.job.target || '') ?? -1) >= 0
})
const labels: Record<string, string> = { queued: '等待执行', downloading: '下载并校验', ready: '等待重启', restarting: '重启生效中', backing_up: '备份数据', installing: '安装新版本', verifying: '验证并启动', succeeded: '升级完成', failed: '升级失败' }
async function refresh(check = false, force = false) {
  if (!admin.value) return
  const sequence = ++refreshSequence
  if (check) checking.value = true
  try {
    const result = await getUpgrade(check, force)
    if (sequence !== refreshSequence) return
    state.value = { ...state.value, ...result }
    if (restartTarget.value && result.job?.target === restartTarget.value && ['restarting', 'backing_up', 'installing', 'verifying', 'succeeded'].includes(result.job.status)) error.value = ''
    disconnected.value = false
    now.value = Date.now()
    lastSeen.value = now.value
    if (check) checkError.value = result.check_error || ''
  } catch (e) {
    if (sequence !== refreshSequence) return
    disconnected.value = true
    if (check) checkError.value = message(e)
  } finally { if (check && sequence === refreshSequence) checking.value = false }
}
async function upgrade() {
  if (busy.value || checking.value || (!container.value && !confirmed.value) || !canUpgrade.value || !state.value.release) return
  busy.value = true
  error.value = ''
  try {
    state.value.job = await prepareUpgrade(state.value.release.version, upgradeKey.value)
    confirmed.value = false
    upgradeKey.value = requestKey()
  } catch (e) { error.value = message(e); await refresh() } finally { busy.value = false }
}
async function restart() {
  if (busy.value || !confirmed.value || !canRestart.value || !state.value.job) return
  busy.value = true
  error.value = ''
  restartTarget.value = state.value.job.target
  try {
    state.value.job = await restartUpgrade(state.value.job.id, restartKey.value)
    confirmed.value = false
    restartKey.value = requestKey()
  } catch (e) { error.value = message(e); await refresh() } finally { busy.value = false }
}
watch([open, active], ([visible, running], [wasVisible]) => {
  if (timer) clearInterval(timer)
  if (visible && !wasVisible && !checking.value) void refresh(true)
  if (visible || running) timer = setInterval(() => { now.value = Date.now(); if (!busy.value && !checking.value) void refresh() }, 3000)
})
watch(admin, value => {
  if (value) void refresh(true)
  else { refreshSequence++; checking.value = false; open.value = false; state.value = {}; confirmed.value = false; restartTarget.value = '' }
}, { immediate: true })
watch(() => state.value.release?.version, () => { confirmed.value = false; upgradeKey.value = requestKey() })
watch(canUpgrade, value => { if (!value) confirmed.value = false })
watch(canRestart, () => { confirmed.value = false })
watch(() => state.value.job?.id, () => { restartKey.value = requestKey(); confirmed.value = false })
watch(completed, value => {
  if (reloadTimer) clearInterval(reloadTimer)
  reloadCountdown.value = 0
  if (!value || state.value.job?.target !== restartTarget.value) return
  reloadCountdown.value = 8
  reloadTimer = setInterval(() => {
    if (--reloadCountdown.value <= 0) {
      clearInterval(reloadTimer)
      if (admin.value && completed.value) reloadPage()
    }
  }, 1000)
})
onBeforeUnmount(() => { refreshSequence++; if (timer) clearInterval(timer); if (reloadTimer) clearInterval(reloadTimer) })
</script>

<template>
  <button v-if="admin" class="system-upgrade-entry" @click="open = true; emit('opened')">
    <span>{{ needsRestart ? '更新已准备' : active ? '升级进行中' : '版本与升级' }}<span v-if="available && !active" class="upgrade-dot" aria-label="有新版本" /></span><small v-if="state.current">{{ active ? labels[state.job?.status || ''] : `v${state.current}` }}</small>
  </button>
  <el-dialog v-if="admin" v-model="open" class="upgrade-dialog" title="ERP 版本与升级" width="min(640px, calc(100vw - 24px))" :close-on-click-modal="false" append-to-body>
    <div class="upgrade-header">
      <span>正式版本 · 安全升级</span>
      <el-button :loading="checking" :disabled="busy || checking || active" @click="error = ''; refresh(true, true)">检查新版本</el-button>
    </div>
    <div class="upgrade-version-grid">
      <div><small>当前运行版本</small><strong>{{ state.current ? `v${state.current}` : '读取中…' }}</strong></div>
      <div :class="{ 'upgrade-new': available }"><small>最新正式版</small><strong>{{ state.release?.version || '待检查' }}</strong></div>
    </div>
    <p role="status" class="upgrade-version-status">{{ versionStatus }}</p>
    <p v-if="state.checked_at" class="upgrade-hint">检查时间：{{ dateText(state.checked_at * 1000) }}{{ state.cached ? ' · 缓存结果' : '' }}</p>
    <el-alert v-if="checkError" :title="checkError" type="warning" :closable="false" />
    <el-alert v-if="disconnected && !active" title="暂时无法连接 ERP，正在自动重试。连接恢复前不能发起升级。" type="warning" :closable="false" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="state.configured === false && !active && !disconnected" title="网页一键升级未启用" type="info" :closable="false">
      ERP 可正常使用，也可通过命令行备份后升级。需要网页一键升级时，再配置密钥并安装宿主机升级服务。
    </el-alert>
    <el-alert v-else-if="state.configured && !state.runner && !active && !disconnected" :title="state.execution === 'container' ? '容器内升级服务正在连接' : '宿主机升级执行器未连接'" type="warning" :closable="false">
      <template v-if="state.execution === 'container'">升级进程随应用容器自动启动，无需安装宿主机执行器。持续未连接时检查 app 容器日志；请勿删除 runtime、数据库或附件卷。</template>
      <template v-else>最近未收到有效心跳。请在部署 ERP 的宿主机检查升级服务状态及日志，核对地址、端口和认证配置；此页面不能启动宿主机服务。请勿清库或删除数据卷。</template>
    </el-alert>
    <p v-if="state.runner && !disconnected && !active">{{ state.runner.execution === 'container' ? '容器内升级已就绪 · 无需宿主机执行器' : `执行器已连接：${state.runner.platform} / ${state.runner.mode === 'docker' ? 'Docker' : '原生部署'}` }}</p>
    <section v-if="needsRestart" class="upgrade-success" aria-label="等待重启">
      <strong>更新已准备完成 · {{ state.job?.target }} · 重启后生效</strong>
      <p>当前仍运行 v{{ state.current }}，可继续使用。点击“重启服务”后才会停机、完整备份、迁移并切换新版本。</p>
      <p v-if="!canRestart">正在等待升级服务连接，恢复后可重启。</p>
    </section>
    <section v-if="completed" class="upgrade-success" aria-label="升级成功">
      <strong>新版本已就绪</strong><p>服务已恢复并确认目标版本。刷新页面以加载新版界面。</p>
      <p v-if="reloadCountdown" role="status">{{ reloadCountdown }} 秒后自动刷新页面</p>
      <el-button type="primary" @click="reloadPage">刷新页面</el-button>
    </section>
    <details v-if="historicalFailure && state.job" class="upgrade-job upgrade-history">
      <summary>历史升级记录 · {{ state.job.target }} · 当时失败</summary>
      <p>当前服务已达到或超过该任务的目标版本；这不是当前版本的升级失败。原记录保留供追溯，不改写为成功。</p>
      <p>{{ state.job.detail }}</p>
      <p v-if="state.job.backup">备份位置：{{ state.job.backup }}</p>
    </details>
    <section v-else-if="state.job && !needsRestart" class="upgrade-job" aria-label="升级进度">
      <strong>{{ disconnected && active ? '正在重新连接' : (labels[state.job.status] || state.job.status) }} · {{ state.job.target }}</strong>
      <p v-if="disconnected && active" role="status">暂时无法获取最新进度，将自动重连。下面是上次收到的状态，不代表任务仍停在该步骤。</p>
      <p v-if="disconnected && active" class="upgrade-timing">上次更新 {{ lastSeen ? new Date(lastSeen).toLocaleTimeString() : '—' }} · {{ labels[state.job.status] }}</p>
      <p v-if="state.job.status !== 'failed'" role="status" aria-live="polite">{{ disconnected && active ? '上次记录：' : '' }}{{ state.job.detail }}</p>
      <p v-else role="status">本次自动升级未完成{{ state.job.backup ? '，完整备份已保留' : '' }}。原因可展开查看。</p>
      <p v-if="active" class="upgrade-timing"><span v-if="!disconnected" class="upgrade-pulse" aria-hidden="true" />任务已用时 {{ Math.floor(elapsed / 60) }} 分 {{ elapsed % 60 }} 秒<span v-if="!disconnected"> · 步骤 {{ step + 1 }} / {{ steps.length }}</span></p>
      <p v-if="active && !disconnected" class="upgrade-hint">{{ state.job.status === 'downloading' ? (container ? '正在准备新版本，期间可继续使用。完成后需点击重启服务才会生效。' : '正在准备新版本，完成后会自动备份并短暂停机。') : '正在完成升级，服务恢复后会自动更新结果。' }}</p>
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
    <details v-if="state.release" class="upgrade-notes" :open="available">
      <summary>查看版本更新内容</summary>
      <p v-if="state.release.published_at" class="upgrade-hint">发布时间：{{ dateText(state.release.published_at) }}</p>
      <p class="upgrade-notes-text">{{ state.release.notes || '此版本没有更新说明。' }}</p>
      <a :href="state.release.url" target="_blank" rel="noopener noreferrer">查看发布页面</a>
    </details>
    <details v-if="!active" class="upgrade-manual" :open="state.configured === false">
      <summary>手动升级与部署说明</summary>
      <div class="upgrade-mode" role="group" aria-label="选择部署方式">
        <button v-for="mode in ['docker', 'native']" :key="mode" :aria-pressed="manualMode === mode" @click="manualMode = mode">{{ mode === 'docker' ? 'Docker Compose' : '原生部署' }}</button>
      </div>
      <p v-if="manualMode === 'docker'">先按安装文档备份数据库、附件及配置，再使用目标正式版安装包和其中固定的镜像 digest。沿用原项目名、数据卷及 .env（旧版为 .env.lean），不要直接覆盖配置或执行 down -v。</p>
      <p v-else>先停止原生服务并完整备份，再使用目标正式版安装包，沿用原配置和数据目录安装；Linux 由 systemd 管理服务。不要将旧程序连接已迁移的数据库。</p>
      <a :href="guideUrl" target="_blank" rel="noopener noreferrer">打开完整升级与备份指南 ↗</a>
    </details>
    <p v-if="container && canUpgrade" class="upgrade-hint">下载更新不会停机；准备完成后，由管理员决定何时重启生效。</p>
    <el-checkbox v-if="canRestart || (!container && canUpgrade)" v-model="confirmed">我已通知使用者暂停操作，同意备份后升级并短暂停机</el-checkbox>
    <template #footer>
      <el-button @click="open = false">关闭</el-button>
      <el-button v-if="needsRestart" type="success" :loading="busy" :disabled="!canRestart || !confirmed || busy" @click="restart">重启服务</el-button>
      <el-button v-else type="primary" :loading="busy" :disabled="!canUpgrade || (!container && !confirmed) || busy || checking" @click="upgrade">{{ container ? '立即更新' : '备份并升级' }}</el-button>
    </template>
  </el-dialog>
</template>
<style scoped>
:global(.el-dialog.upgrade-dialog) { display: flex; flex-direction: column; max-height: calc(100dvh - 40px); margin: 20px auto; }
:global(.upgrade-dialog .el-dialog__body) { overflow: auto; min-height: 0; }
:global(.upgrade-dialog .el-dialog__header), :global(.upgrade-dialog .el-dialog__footer) { flex-shrink: 0; }
.upgrade-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--ink-4); margin-bottom: 16px; }
.upgrade-version-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.upgrade-version-grid > div { display: grid; gap: 8px; padding: 18px; border: 1px solid var(--field-line); border-radius: 10px; background: var(--subtle); }
.upgrade-version-grid strong { font-size: 24px; overflow-wrap: anywhere; }
.upgrade-version-grid small { color: var(--ink-4); }
.upgrade-version-grid .upgrade-new { border-color: var(--brand-ink); background: var(--brand-wash); }
.upgrade-version-status { font-weight: 600; }
.upgrade-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--brand-ink); margin-left: 6px; }
.upgrade-success { padding: 16px; border: 1px solid var(--ok-line); border-radius: 8px; color: var(--ok); margin-top: 16px; }
.upgrade-notes, .upgrade-manual { margin: 16px 0; padding: 14px; border: 1px solid var(--field-line); border-radius: 8px; }
.upgrade-notes summary, .upgrade-manual summary { cursor: pointer; font-weight: 600; }
.upgrade-notes-text { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 240px; overflow: auto; line-height: 1.7; }
.upgrade-manual p { font-size: 13px; line-height: 1.7; }
.upgrade-mode { display: flex; gap: 8px; margin-top: 12px; }
.upgrade-mode button { border: 1px solid var(--field-line); border-radius: 6px; padding: 6px 10px; background: var(--subtle); color: inherit; cursor: pointer; }
.upgrade-mode button[aria-pressed="true"] { color: var(--brand-ink); border-color: var(--brand-ink); background: var(--brand-wash); }
:deep(.el-checkbox) { height: auto; white-space: normal; align-items: flex-start; }
:deep(.el-checkbox__label) { white-space: normal; line-height: 1.5; }
.upgrade-steps { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }
.upgrade-steps > div { display: flex; align-items: center; gap: 7px; padding: 8px; border: 1px solid var(--field-line); border-radius: 8px; color: var(--ink-4); font-size: 12px; }
.upgrade-steps > div > span { display: grid; place-items: center; width: 22px; height: 22px; flex-shrink: 0; border-radius: 50%; background: var(--line); }
.upgrade-hint, .upgrade-stage-details { color: var(--ink-4); font-size: 13px; }
.upgrade-stage-details summary { cursor: pointer; }
.upgrade-job { margin-top: 16px; padding: 16px; background: var(--subtle); border: 1px solid var(--field-line); border-radius: 8px; }
.upgrade-job p { overflow-wrap: anywhere; }
.upgrade-steps .current { color: var(--brand-ink); border-color: var(--brand-ink); background: var(--brand-wash); font-weight: 600; }
.upgrade-steps .complete { color: var(--ok); border-color: var(--ok-line); }
.upgrade-timing { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.upgrade-pulse { width: 10px; height: 10px; background: var(--brand-ink); border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .upgrade-pulse { animation: none; } }
@media (max-width: 480px) { .upgrade-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
