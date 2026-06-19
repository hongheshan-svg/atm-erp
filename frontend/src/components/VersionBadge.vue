<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { usePermissionStore } from '@/stores/permission'
import {
  getSystemVersion,
  checkUpdate,
  performUpgrade,
  getUpgradeJob,
  rollbackUpgrade
} from '@/api/system'

const props = defineProps<{ collapsed?: boolean }>()

const permissionStore = usePermissionStore()
// 仅 system:upgrade 权限者看到检查更新/升级/回滚;其他人只看版本号。
const canUpgrade = computed(() => permissionStore.hasPermission('system:upgrade'))

const currentVersion = ref('')
const latestVersion = ref('')
const hasUpdate = ref(false)
const releaseNotes = ref('')
const checking = ref(false)

const busy = ref(false) // 升级/回滚进行中
const job = ref<any>(null)
const countdown = ref(0)

let pollTimer: ReturnType<typeof setInterval> | null = null
let checkTimer: ReturnType<typeof setInterval> | null = null
let cdTimer: ReturnType<typeof setInterval> | null = null

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
    releaseNotes.value = res.release_notes_md || ''
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
      if (data.status === 'success') startCountdownReload()
      else if (data.status === 'failed') ElMessage.error('升级失败,已回滚到原版本')
      else if (data.status === 'rolled_back') ElMessage.warning('已回滚')
    }
  } catch {
    /* ignore */
  }
}

async function onUpgrade() {
  if (busy.value) return
  busy.value = true
  job.value = null
  try {
    const data: any = await performUpgrade()
    pollTimer = setInterval(() => pollJob(data.job_id), 4000)
  } catch {
    busy.value = false
  }
}

async function onRollback() {
  if (busy.value) return
  busy.value = true
  job.value = null
  try {
    const data: any = await rollbackUpgrade()
    pollTimer = setInterval(() => pollJob(data.job_id), 4000)
  } catch {
    busy.value = false
  }
}

// 升级成功 → 倒计时 + 健康轮询 → 自动刷新加载新版本前端
function startCountdownReload() {
  ElMessage.success('升级成功,即将刷新页面')
  countdown.value = 8
  cdTimer = setInterval(async () => {
    countdown.value--
    if (countdown.value <= 0) {
      if (cdTimer) clearInterval(cdTimer)
      cdTimer = null
      // 服务就绪再刷新(最多试几次,无论如何最后强制刷新)
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
})
</script>

<template>
  <el-popover placement="right-start" :width="320" trigger="click" :disabled="!canUpgrade">
    <template #reference>
      <div class="version-badge" :class="{ 'has-update': hasUpdate, clickable: canUpgrade }">
        <span v-if="!props.collapsed" class="vb-text">v{{ currentVersion || '—' }}</span>
        <span v-else class="vb-text vb-text--mini">{{ currentVersion ? currentVersion.split('.').slice(0, 2).join('.') : '' }}</span>
        <span v-if="hasUpdate" class="vb-dot"></span>
      </div>
    </template>

    <div class="vb-pop">
      <div class="vb-row"><span>当前版本</span><b>v{{ currentVersion || '—' }}</b></div>
      <div class="vb-row">
        <span>最新版本</span>
        <b :class="{ amber: hasUpdate }">v{{ latestVersion || currentVersion || '—' }}</b>
      </div>

      <div v-if="hasUpdate" class="vb-notes">{{ releaseNotes }}</div>

      <template v-if="hasUpdate && !job">
        <el-button type="primary" size="small" style="width: 100%" :loading="busy" @click="onUpgrade">
          {{ busy ? '升级中…' : '立即升级' }}
        </el-button>
      </template>
      <div v-else-if="!hasUpdate && !job" class="vb-uptodate">
        <span>已是最新版本</span>
        <el-button link size="small" :loading="checking" @click="doCheck(true)">重新检查</el-button>
      </div>

      <div v-if="job" class="vb-progress">
        <div v-for="(s, i) in job.steps || []" :key="i" class="vb-step" :class="s.level">
          {{ s.stage }}:{{ s.message }}
        </div>
        <div v-if="countdown > 0" class="vb-countdown">升级成功,{{ countdown }}s 后自动刷新…</div>
      </div>

      <el-button
        v-if="!hasUpdate && !busy && !countdown"
        link
        type="warning"
        size="small"
        class="vb-rollback"
        @click="onRollback"
      >
        回滚到上一版本
      </el-button>
    </div>
  </el-popover>
</template>

<style scoped>
.version-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.6;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.55);
  user-select: none;
}
.version-badge.clickable {
  cursor: pointer;
}
.version-badge.has-update {
  background: rgba(245, 158, 11, 0.18);
  color: #f59e0b;
}
.vb-text--mini {
  font-size: 11px;
}
.vb-dot {
  position: relative;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #f59e0b;
}
.vb-dot::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: #f59e0b;
  animation: vb-ping 1.2s cubic-bezier(0, 0, 0.2, 1) infinite;
}
@keyframes vb-ping {
  75%,
  100% {
    transform: scale(2.2);
    opacity: 0;
  }
}

.vb-pop {
  font-size: 13px;
}
.vb-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  color: var(--el-text-color-regular);
}
.vb-row b.amber {
  color: #f59e0b;
}
.vb-notes {
  max-height: 160px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  padding: 8px;
  margin: 8px 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.vb-uptodate {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--el-text-color-secondary);
  padding: 4px 0;
}
.vb-progress {
  margin-top: 8px;
  max-height: 180px;
  overflow-y: auto;
}
.vb-step {
  font-size: 12px;
  padding: 2px 0;
  color: var(--el-text-color-secondary);
}
.vb-step.error {
  color: var(--el-color-danger);
}
.vb-step.warning {
  color: var(--el-color-warning);
}
.vb-countdown {
  margin-top: 6px;
  font-weight: 600;
  color: var(--el-color-success);
}
.vb-rollback {
  margin-top: 6px;
}
</style>
