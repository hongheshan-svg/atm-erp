<template>
  <div class="upgrade-page">
    <!-- 当前版本信息 -->
    <el-card>
      <template #header>系统升级</template>
      <p>
        当前版本：<el-tag>{{ version }}</el-tag>
        <span data-test="version-display">{{ version }}</span>
        &nbsp;&nbsp;部署模式：<el-tag type="info">{{ deployMode }}</el-tag>
      </p>
      <el-button data-test="check-btn" :loading="checking" @click="onCheck">检查更新</el-button>

      <div v-if="info" style="margin-top: 16px">
        <p v-if="info.warning" class="warn">{{ info.warning }}</p>
        <template v-if="info.has_update">
          <el-tag type="success">发现新版本 {{ info.latest_version }}</el-tag>
          <pre class="notes">{{ info.release_notes_md }}</pre>
          <el-button
            type="primary"
            data-test="upgrade-btn"
            :loading="upgrading"
            style="margin-top: 8px"
            @click="onUpgrade"
          >
            立即升级（将重启服务，已自动备份数据库）
          </el-button>
        </template>
        <el-tag v-else type="info">已是最新版本</el-tag>
      </div>
    </el-card>

    <!-- 升级进度 -->
    <el-card v-if="job" style="margin-top: 16px">
      <template #header>升级进度（{{ job.status }}）</template>
      <ul>
        <li v-for="(s, i) in job.steps" :key="i" :class="s.level">[{{ s.stage }}] {{ s.message }}</li>
      </ul>
    </el-card>

    <!-- 升级历史 & 回滚 -->
    <el-card style="margin-top: 16px">
      <template #header>升级历史</template>
      <el-table :data="history">
        <el-table-column prop="target_version" label="目标版本" />
        <el-table-column prop="action" label="动作" />
        <el-table-column prop="status" label="状态" />
        <el-table-column prop="created_at" label="时间" />
      </el-table>
      <el-button data-test="rollback-btn" style="margin-top: 8px" @click="onRollback">
        回滚到上一个版本
      </el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSystemVersion,
  checkUpdate,
  performUpgrade,
  getUpgradeJob,
  listUpgradeJobs,
  rollbackUpgrade,
} from '@/api/system'

const version = ref('')
const deployMode = ref('')
const checking = ref(false)
const upgrading = ref(false)
const info = ref<any>(null)
const job = ref<any>(null)
const history = ref<any[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadVersion() {
  try {
    const data = await getSystemVersion()
    version.value = data.version
    deployMode.value = data.deploy_mode
  } catch {
    // ignore
  }
}

async function loadHistory() {
  try {
    const data = await listUpgradeJobs()
    history.value = Array.isArray(data) ? data : []
  } catch {
    // ignore
  }
}

async function onCheck() {
  checking.value = true
  try {
    const data = await checkUpdate(true)
    info.value = data
  } finally {
    checking.value = false
  }
}

async function pollJob(id: string | number) {
  try {
    const data = await getUpgradeJob(id)
    job.value = data
    if (['success', 'failed', 'rolled_back'].includes(data.status)) {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
      loadVersion()
      loadHistory()
      ElMessage[data.status === 'success' ? 'success' : 'warning'](`升级${data.status}`)
    }
  } catch {
    // ignore transient errors during restart
  }
}

async function onUpgrade() {
  await ElMessageBox.confirm('升级会重启服务并可能中断访问，确认继续？', '确认升级', {
    type: 'warning',
  })
  upgrading.value = true
  try {
    const data = await performUpgrade()
    const jobId = data.job_id
    pollTimer = setInterval(() => pollJob(jobId), 4000)
  } finally {
    upgrading.value = false
  }
}

async function onRollback() {
  await ElMessageBox.confirm('确认回滚到上一个版本？', '确认回滚', { type: 'warning' })
  const data = await rollbackUpgrade()
  const jobId = data.job_id
  pollTimer = setInterval(() => pollJob(jobId), 4000)
}

onMounted(() => {
  loadVersion()
  loadHistory()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.notes {
  background: #f5f5f5;
  padding: 8px;
  white-space: pre-wrap;
  border-radius: 4px;
  margin-top: 8px;
}
.warn {
  color: #e6a23c;
}
li.error {
  color: #f56c6c;
}
li.warning {
  color: #e6a23c;
}
</style>
