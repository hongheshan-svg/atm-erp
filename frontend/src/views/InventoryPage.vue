<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import { useRoute } from 'vue-router'
import { can } from '../session'
import { computed } from 'vue'
const route = useRoute()
const tabs = computed(() => [
  { key: 'stocks', label: '现有库存' }, { key: 'moves', label: '库存流水' },
  ...(can(['admin', 'warehouse']) ? [{ key: 'receipts', label: '采购收货' }] : []),
])
const returning = computed(() => route.query.intent === 'return')
const receiptStatus = computed(() => route.query.receipt === 'partial' ? 'partial' : 'approved')
const projectQuery = computed(() => route.query.project || 'all')
</script>
<template>
  <ModulePage :key="String(projectQuery)" title="库存" :project-filter="['moves', 'receipts'].includes(String(route.query.section))" v-slot="{ revision, projectId, refresh }">
    <nav v-if="can(['admin', 'warehouse'])" class="panel daily-actions" aria-label="日常库存操作">
      <router-link :to="{ path: '/inventory', query: { section: 'receipts', project: projectId || 'all' } }">采购收货</router-link>
      <router-link :to="{ path: '/inventory', query: { section: 'stocks', intent: 'issue', project: projectId || 'all' } }">项目领料</router-link>
      <router-link :to="{ path: '/inventory', query: { section: 'moves', intent: 'return', project: projectId || 'all' } }">项目退料</router-link>
    </nav>
    <ModuleTabs :tabs="tabs" storage-key="inventory"><template #stocks><p class="muted">先查找物料与库位，再点该行“领料”选择项目并核对本次数量。现有库存为全公司共享库存。</p><ResourcePanel
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
      <p class="muted">选择采购单后点“收货”，核对待收数量与本次数量；支持部分到货，不合格物料仍走隔离处理。</p>
      <nav class="receipt-states" aria-label="收货进度"><router-link :to="{ path: '/inventory', query: { section: 'receipts', project: projectId || 'all' } }" :aria-current="receiptStatus === 'approved' ? 'page' : undefined">待收货采购</router-link><router-link :to="{ path: '/inventory', query: { section: 'receipts', receipt: 'partial', project: projectId || 'all' } }" :aria-current="receiptStatus === 'partial' ? 'page' : undefined">部分收货采购</router-link></nav>
      <ResourcePanel v-if="can(['admin', 'warehouse'])" :key="receiptStatus" class="daily-filtered-list" resource="purchases" :title="receiptStatus === 'partial' ? '部分收货采购' : '待收货采购'" :params="{ project: projectId, status: receiptStatus }" :project-id="projectId" :allow-create="false" :revision="revision" @changed="refresh" />
    </template></ModuleTabs></ModulePage>
</template>
<style scoped>
.daily-actions, .receipt-states { display: flex; flex-wrap: wrap; gap: 12px 24px; }
.daily-actions a { padding: 8px 0; font-weight: 600; }
.receipt-states { margin-bottom: 16px; }
.receipt-states [aria-current="page"] { font-weight: 600; text-decoration: underline; }
.daily-filtered-list :deep(.resource-status-tabs) { display: none; }
</style>
