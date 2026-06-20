<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Download, Check, Close, RefreshRight, TopRight } from '@element-plus/icons-vue'
import { usePermissionStore } from '@/stores/permission'
import {
  getSystemVersion,
  checkUpdate,
  performUpgrade,
  getUpgradeJob,
  rollbackUpgrade
} from '@/api/system'

const permissionStore = usePermissionStore()
// 仅 system:upgrade 权限者看到检查更新/升级/回滚;其他人只看版本号药丸。
const canUpgrade = computed(() => permissionStore.hasPermission('system:upgrade'))

const currentVersion = ref('')
const latestVersion = ref('')
const hasUpdate = ref(false)
const releaseUrl = ref('') // GitHub 发布页,点击自行查看更新内容
const checking = ref(false)

// 升级预计耗时(秒):用于「正在升级」阶段的倒计时显示。仅估算(真实耗时主要看镜像拉取速度),
// 真正完成/失败由后端轮询决定;倒到 0 仍未完成则显示「即将完成」,不会提前刷新。
const UPGRADE_ETA = 60

const busy = ref(false) // 升级/回滚进行中
const job = ref<any>(null)
const countdown = ref(0) // 升级成功后刷新倒计时
const etaRemain = ref(0) // 正在升级预计剩余秒数(倒计时)
const upgradeError = ref('') // 启动升级失败(如锁冲突/网络),用于展示「升级失败」

let pollTimer: ReturnType<typeof setInterval> | null = null
let checkTimer: ReturnType<typeof setInterval> | null = null
let cdTimer: ReturnType<typeof setInterval> | null = null
let etaTimer: ReturnType<typeof setInterval> | null = null

const jobStatus = computed<string>(() => job.value?.status || '')
const jobFailed = computed(() => !!upgradeError.value || ['failed', 'rolled_back'].includes(jobStatus.value))

const etaText = computed(() => {
  const s = etaRemain.value
  if (s <= 0) return ''
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`
})
const currentStep = computed(() => {
  const steps = job.value?.steps
  if (!steps?.length) return '准备中…'
  const last = steps[steps.length - 1]
  return last.message || last.stage || '处理中…'
})

function startEta() {
  etaRemain.value = UPGRADE_ETA
  if (etaTimer) clearInterval(etaTimer)
  etaTimer = setInterval(() => {
    if (etaRemain.value > 0) etaRemain.value--
  }, 1000)
}
function stopEta() {
  if (etaTimer) clearInterval(etaTimer)
  etaTimer = null
}

function pick(res: any, ...keys: string[]) {
  for (const k of keys) if (res && res[k]) return res[k]
  return ''
}

async function loadVersion() {
  try {
    currentVersion.value = pick(await getSystemVersion(), 'version', 'current_version') || currentVersion.value
  } catch {
    /* ignore */
  }
}

async function doCheck(force = false) {
  if (!canUpgrade.value) return
  checking.value = true
  try {
    const res: any = await checkUpdate(force)
    currentVersion.value = res.current_version || currentVersion.value
    latestVersion.value = res.latest_version || ''
    hasUpdate.value = !!res.has_update
    releaseUrl.value = res.release_url || ''
    if (force) ElMessage.success(res.has_update ? `发现新版本 v${res.latest_version}` : '已是最新版本')
  } catch {
    /* ignore */
  } finally {
    checking.value = false
  }
}

async function pollJob(id: string | number) {
  try {
    const data: any = await getUpgradeJob(id)
    job.value = data
    if (['success', 'failed', 'rolled_back'].includes(data.status)) {
      if (pollTimer) clearInterval(pollTimer)
      pollTimer = null
      busy.value = false
      stopEta()
      if (data.status === 'success') startCountdownReload()
    }
  } catch {
    /* ignore */
  }
}

function errMsg(e: any, fallback: string): string {
  return e?.response?.data?.detail || e?.message || fallback
}

async function onUpgrade() {
  if (busy.value) return
  upgradeError.value = ''
  busy.value = true
  job.value = null
  startEta()
  try {
    const data: any = await performUpgrade()
    pollTimer = setInterval(() => pollJob(data.job_id), 4000)
  } catch (e: any) {
    busy.value = false
    stopEta()
    upgradeError.value = errMsg(e, '无法启动升级') // 触发「升级失败」展示
  }
}

async function onRollback() {
  if (busy.value) return
  upgradeError.value = ''
  busy.value = true
  job.value = null
  startEta()
  try {
    const data: any = await rollbackUpgrade()
    pollTimer = setInterval(() => pollJob(data.job_id), 4000)
  } catch (e: any) {
    busy.value = false
    stopEta()
    upgradeError.value = errMsg(e, '无法启动回滚')
  }
}

// 升级成功 → 倒计时 + 健康轮询 → 自动刷新加载新版本前端
function startCountdownReload() {
  countdown.value = 8
  cdTimer = setInterval(async () => {
    countdown.value--
    if (countdown.value <= 0) {
      if (cdTimer) clearInterval(cdTimer)
      cdTimer = null
      for (let i = 0; i < 5; i++) {
        try {
          const r = await fetch('/api/v1/health/', { cache: 'no-cache' })
          if (r.ok) {
            window.location.reload()
            return
          }
        } catch {
          /* 服务重建中 */
        }
        await new Promise((res) => setTimeout(res, 1000))
      }
      window.location.reload()
    }
  }, 1000)
}

onMounted(async () => {
  await loadVersion()
  if (canUpgrade.value) {
    doCheck(false)
    checkTimer = setInterval(() => doCheck(false), 30 * 60 * 1000) // 每 30 分钟静默检查
  }
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (checkTimer) clearInterval(checkTimer)
  if (cdTimer) clearInterval(cdTimer)
  if (etaTimer) clearInterval(etaTimer)
})
</script>

<template>
  <el-popover
    placement="right-start"
    :width="264"
    trigger="click"
    :disabled="!canUpgrade"
    popper-class="vb-popper"
    :show-arrow="false"
  >
    <template #reference>
      <button type="button" class="vb-pill" :class="{ 'has-update': hasUpdate, clickable: canUpgrade }">
        <span class="vb-ver">v{{ currentVersion || '—' }}</span>
        <span v-if="hasUpdate" class="vb-dot">
          <span class="vb-dot-ping"></span>
          <span class="vb-dot-core"></span>
        </span>
      </button>
    </template>

    <div class="vb-card">
      <!-- 头部:标题 + 刷新 -->
      <div class="vb-head">
        <span class="vb-head-title">版本信息</span>
        <button type="button" class="vb-icon-btn" :disabled="checking || busy" @click="doCheck(true)" title="检查更新">
          <el-icon :class="{ spin: checking }"><Refresh /></el-icon>
        </button>
      </div>

      <div class="vb-body">
        <!-- 紧凑版本行(不再居中大字号占据界面中间) -->
        <div class="vb-row">
          <span class="vb-row-k">当前版本</span>
          <span class="vb-row-v">
            v{{ currentVersion || '—' }}
            <span v-if="!hasUpdate && !job && !busy && !upgradeError" class="vb-chip ok">已是最新</span>
          </span>
        </div>

        <!-- 升级进行中:倒计时(预计剩余),倒到 0 显示「即将完成」,完成由后端轮询决定 -->
        <template v-if="busy">
          <div class="vb-alert blue">
            <span class="vb-spinner"></span>
            <div class="vb-alert-main">
              <p class="vb-alert-title">
                正在升级<template v-if="etaRemain > 0"> · 预计剩余 <span class="vb-timer">{{ etaText }}</span></template>
              </p>
              <p class="vb-alert-desc">{{ etaRemain > 0 ? currentStep : '即将完成,请稍候…' }}</p>
            </div>
          </div>
          <div v-if="job?.steps?.length" class="vb-steps">
            <div v-for="(s, i) in job.steps" :key="i" class="vb-step" :class="s.level">
              {{ s.stage }} · {{ s.message }}
            </div>
          </div>
          <p class="vb-hint">完成后将自动刷新,请勿关闭页面</p>
        </template>

        <!-- 升级成功 + 刷新倒计时 -->
        <template v-else-if="jobStatus === 'success'">
          <div class="vb-alert green">
            <el-icon class="vb-alert-ico"><Check /></el-icon>
            <div class="vb-alert-main">
              <p class="vb-alert-title">升级完成</p>
              <p class="vb-alert-desc"><span class="vb-timer">{{ countdown }}s</span> 后自动刷新…</p>
            </div>
          </div>
        </template>

        <!-- 升级失败 / 回滚 -->
        <template v-else-if="jobFailed">
          <div class="vb-alert red">
            <el-icon class="vb-alert-ico"><Close /></el-icon>
            <div class="vb-alert-main">
              <p class="vb-alert-title">{{ jobStatus === 'rolled_back' ? '已回滚' : '升级失败' }}</p>
              <p class="vb-alert-desc">{{ upgradeError || '已恢复到原版本' }}</p>
            </div>
          </div>
          <button type="button" class="vb-btn primary" @click="onUpgrade">
            <el-icon><RefreshRight /></el-icon> 重试
          </button>
        </template>

        <!-- 有新版本(空闲) -->
        <template v-else-if="hasUpdate">
          <div class="vb-alert amber">
            <el-icon class="vb-alert-ico"><Download /></el-icon>
            <div class="vb-alert-main">
              <p class="vb-alert-title">有新版本</p>
              <p class="vb-alert-desc">v{{ latestVersion }}</p>
            </div>
          </div>
          <button type="button" class="vb-btn primary" @click="onUpgrade">
            <el-icon><Download /></el-icon> 立即升级
          </button>
          <a
            v-if="releaseUrl"
            :href="releaseUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="vb-changelog"
          >
            查看更新内容<el-icon><TopRight /></el-icon>
          </a>
        </template>

        <!-- 已是最新:查看发布 + 回滚 -->
        <template v-if="!hasUpdate && !job">
          <a
            v-if="releaseUrl"
            :href="releaseUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="vb-changelog"
          >
            查看发布说明<el-icon><TopRight /></el-icon>
          </a>
          <button type="button" class="vb-link" @click="onRollback">回滚到上一版本</button>
        </template>
      </div>
    </div>
  </el-popover>
</template>

<style scoped>
/* 药丸(站名下方) */
.vb-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.55);
  cursor: default;
  transition: background 0.15s;
}
.vb-pill.clickable {
  cursor: pointer;
}
.vb-pill.clickable:hover {
  background: rgba(255, 255, 255, 0.16);
}
.vb-pill.has-update {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}
.vb-pill.has-update.clickable:hover {
  background: rgba(245, 158, 11, 0.3);
}
.vb-dot {
  position: relative;
  display: inline-flex;
  width: 8px;
  height: 8px;
}
.vb-dot-ping {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: #fbbf24;
  opacity: 0.75;
  animation: vb-ping 1.2s cubic-bezier(0, 0, 0.2, 1) infinite;
}
.vb-dot-core {
  position: relative;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
}
@keyframes vb-ping {
  75%,
  100% {
    transform: scale(2.2);
    opacity: 0;
  }
}

/* 卡片 */
.vb-card {
  font-size: 13px;
}
.vb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.vb-head-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.vb-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: background 0.15s;
}
.vb-icon-btn:hover:not(:disabled) {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}
.vb-icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.vb-icon-btn .spin {
  animation: vb-spin 0.9s linear infinite;
}
@keyframes vb-spin {
  to {
    transform: rotate(360deg);
  }
}

.vb-body {
  padding: 14px;
}
.vb-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.vb-row-k {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.vb-row-v {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.vb-chip {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 999px;
}
.vb-chip.ok {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}

/* 状态卡 */
.vb-alert {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid transparent;
}
.vb-alert.amber {
  background: var(--el-color-warning-light-9);
  border-color: var(--el-color-warning-light-7);
}
.vb-alert.green {
  background: var(--el-color-success-light-9);
  border-color: var(--el-color-success-light-7);
}
.vb-alert.red {
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-7);
}
.vb-alert.blue {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
}
.vb-alert-ico {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
}
.vb-alert.amber .vb-alert-ico {
  background: var(--el-color-warning-light-7);
  color: var(--el-color-warning);
}
.vb-alert.green .vb-alert-ico {
  background: var(--el-color-success-light-7);
  color: var(--el-color-success);
}
.vb-alert.red .vb-alert-ico {
  background: var(--el-color-danger-light-7);
  color: var(--el-color-danger);
}
.vb-alert-main {
  min-width: 0;
  flex: 1;
}
.vb-alert-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.vb-alert-desc {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.vb-spinner {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2.5px solid var(--el-color-primary-light-7);
  border-top-color: var(--el-color-primary);
  animation: vb-spin 0.8s linear infinite;
}
.vb-timer {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
.vb-hint {
  margin: 10px 0 0;
  text-align: center;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.vb-steps {
  margin-top: 8px;
  max-height: 120px;
  overflow-y: auto;
}
.vb-step {
  font-size: 11px;
  padding: 2px 0;
  color: var(--el-text-color-secondary);
}
.vb-step.error {
  color: var(--el-color-danger);
}
.vb-step.warning {
  color: var(--el-color-warning);
}

.vb-changelog {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-decoration: none;
  transition: color 0.15s;
}
.vb-changelog:hover {
  color: var(--el-color-primary);
}
.vb-changelog .el-icon {
  font-size: 13px;
}

.vb-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  margin-top: 12px;
  padding: 8px 12px;
  border: none;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.vb-btn.primary {
  background: var(--el-color-primary);
  color: #fff;
}
.vb-btn.primary:hover {
  background: var(--el-color-primary-dark-2);
}

.vb-link {
  display: block;
  width: 100%;
  margin-top: 12px;
  padding: 4px;
  border: none;
  background: transparent;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  cursor: pointer;
  transition: color 0.15s;
}
.vb-link:hover {
  color: var(--el-color-warning);
}
</style>

<style>
/* 弹层去内边距(内容自带卡片 padding) */
.vb-popper.el-popover.el-popper {
  padding: 0;
  border-radius: 12px;
  overflow: hidden;
}
</style>
