<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import ActionDialog from '../components/ActionDialog.vue'
import { useRoute, useRouter } from 'vue-router'
import { can } from '../session'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { bomIssueCommand } from '../modules/inventory'
import { message } from '../utils/request'
import type { Command } from '../types'
const route = useRoute()
const router = useRouter()
const tabs = computed(() => [
  { key: 'stocks', label: '现有库存' }, { key: 'moves', label: '库存流水' },
  ...(can(['admin', 'warehouse']) ? [{ key: 'receipts', label: '采购收货' }] : []),
])
const returning = computed(() => route.query.intent === 'return')
const receiptStatus = computed(() => route.query.receipt === 'partial' ? 'partial' : 'approved')
const projectQuery = computed(() => route.query.project || 'all')
// BOM 页「按 BOM 领料」跳到 /inventory?project=<id>&issue=bom：直接打开该项目的批量领料。
const bomIssue = computed(() => route.query.issue === 'bom' && can(['admin', 'warehouse']))
const issueProject = computed(() => {
  const id = Number(route.query.project)
  return Number.isSafeInteger(id) && id > 0 ? id : undefined
})
const issueCommand = ref<Command | null>(null)
const issueError = ref('')
let issueGeneration = 0
async function openBomIssue() {
  const current = ++issueGeneration
  issueCommand.value = null; issueError.value = ''
  if (!bomIssue.value) return
  try {
    const next = await bomIssueCommand(issueProject.value)
    if (current === issueGeneration) issueCommand.value = next
  } catch (e) { if (current === issueGeneration) issueError.value = message(e) }
}
watch([bomIssue, issueProject], openBomIssue, { immediate: true })
onBeforeUnmount(() => { issueGeneration++ })
function closeBomIssue() {
  issueGeneration++
  issueCommand.value = null
  const { issue: _issue, ...query } = route.query
  void router.replace({ query })
}
</script>
<template>
  <ModulePage :key="String(projectQuery)" title="库存" :project-filter="['moves', 'receipts'].includes(String(route.query.section)) || bomIssue" v-slot="{ revision, projectId, refresh }">
    <nav v-if="can(['admin', 'warehouse'])" class="panel daily-actions" aria-label="日常库存操作">
      <router-link :to="{ path: '/inventory', query: { section: 'receipts', project: projectId || 'all' } }">采购收货</router-link>
      <router-link :to="{ path: '/inventory', query: { section: 'stocks', intent: 'issue', project: projectId || 'all' } }">项目领料</router-link>
      <router-link :to="{ path: '/inventory', query: { section: 'moves', intent: 'return', project: projectId || 'all' } }">项目退料</router-link>
      <router-link :to="{ path: '/inventory', query: { section: 'stocks', issue: 'bom', project: projectId || 'all' } }">按 BOM 领料</router-link>
    </nav>
    <el-alert v-if="issueError" :title="`按 BOM 领料读取失败：${issueError}`" type="error" :closable="false" show-icon role="alert" />
    <ActionDialog :command="issueCommand" @close="closeBomIssue" @saved="refresh" />
    <ModuleTabs :tabs="tabs" storage-key="inventory"><template #stocks><p class="muted tab-hint"><span class="full-hint">先查找物料与库位，再点该行“领料”选择项目并核对本次数量。整个项目按 BOM 一次领多行请用上方“按 BOM 领料”。现有库存为全公司共享库存。</span><span class="short-hint">点该行“领料”；整项目一次领多行用“按 BOM 领料”。</span></p><ResourcePanel
      resource="stocks"
      title="现有库存"
      :allow-create="false"
      :revision="revision"
      @changed="refresh" /><p v-if="can(['admin'])" class="muted">安装时的期初入库请到 <router-link to="/settings?section=initialization">管理员初始化</router-link>。</p></template><template #moves>
      <p v-if="returning" class="muted">选择原领料流水，点“退料”核对本次退回数量。无记录时先核对项目筛选，或联系仓管确认原领料记录。<router-link :to="{ path: '/inventory', query: { section: 'moves', project: projectId || 'all' } }">查看全部库存流水</router-link></p>
      <ResourcePanel
      :key="returning ? 'returns' : 'moves'"
      :class="{ 'daily-filtered-list': returning }"
      resource="moves"
      :title="returning ? '原领料流水' : '库存流水'"
      :params="{ project: projectId, ...(returning ? { kind: 'issue' } : {}) }"
      :revision="revision"
      @changed="refresh"
    /></template><template #receipts>
      <p class="muted tab-hint"><span class="full-hint">选择采购单后点“收货”，核对待收数量与本次数量；支持部分到货，不合格物料仍走隔离处理。</span><span class="short-hint">点“收货”核对本次数量，支持部分到货。</span></p>
      <nav class="receipt-states" aria-label="收货进度"><router-link :to="{ path: '/inventory', query: { section: 'receipts', project: projectId || 'all' } }" :aria-current="receiptStatus === 'approved' ? 'page' : undefined">待收货采购</router-link><router-link :to="{ path: '/inventory', query: { section: 'receipts', receipt: 'partial', project: projectId || 'all' } }" :aria-current="receiptStatus === 'partial' ? 'page' : undefined">部分收货采购</router-link></nav>
      <ResourcePanel v-if="can(['admin', 'warehouse'])" :key="receiptStatus" class="daily-filtered-list" resource="purchases" :title="receiptStatus === 'partial' ? '部分收货采购' : '待收货采购'" :params="{ project: projectId, status: receiptStatus }" :project-id="projectId" :allow-create="false" :revision="revision" @changed="refresh" />
    </template></ModuleTabs></ModulePage>
</template>
<style scoped>
.daily-actions, .receipt-states { display: flex; flex-wrap: wrap; gap: 12px 24px; }
.daily-actions a { padding: 8px 0; font-weight: 600; }
.receipt-states { margin-bottom: 16px; }
.receipt-states [aria-current="page"] { font-weight: 600; text-decoration: underline; }
.short-hint { display: none; }
/* 手机：快捷入口与工作台一致改 2×2 网格（触控 ≥40px）；页签说明缩成一行短句，收货进度链接压缩间距。 */
@media (max-width: 600px) {
  .daily-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 12px; padding: 8px 16px; }
  .daily-actions a { display: flex; align-items: center; min-height: 40px; padding: 0; }
  .tab-hint { margin: 0 0 6px; font-size: 13px; }
  .tab-hint .full-hint { display: none; }
  .tab-hint .short-hint { display: inline; }
  .receipt-states { gap: 0 20px; margin-bottom: 8px; }
  .receipt-states a { display: inline-flex; align-items: center; min-height: 40px; }
}
.daily-filtered-list :deep(.resource-status-tabs) { display: none; }
</style>
