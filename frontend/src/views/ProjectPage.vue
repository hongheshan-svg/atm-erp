<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import type { TabsInstance } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { read } from '../api'
import { money, purchaseReader, productionProject, user, manager } from '../session'
import { actionNames, actionCommand, display } from '../business'
import { message } from '../utils/request'
import { money as formatMoney } from '../utils/money'
import type { Row, Command } from '../types'
import ResourcePanel from '../components/ResourcePanel.vue'
import BOMDemand from '../components/BOMDemand.vue'
import BudgetPanel from '../components/BudgetPanel.vue'
import ActionDialog from '../components/ActionDialog.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ProcessSteps from '../components/ProcessSteps.vue'
import ProjectAttention from '../components/ProjectAttention.vue'
import { revealActiveTab } from '../utils/tabs'
import { localStore, sessionStore } from '../utils/storage'
import { flowFor } from '../flows'
import { confirmFormNavigation } from '../form-experience'
const taskTabs = [{ key: 'tasks', label: '项目任务', resources: ['tasks'] }, { key: 'time', label: '工时记录', resources: ['time'] }]
const bomTabs = [{ key: 'demand', label: 'BOM 与缺料' }, { key: 'lines', label: 'BOM 明细', resources: ['bom'] }]
const deliveryTabs = [{ key: 'deliveries', label: '交付批次', resources: ['deliveries'] }, { key: 'service', label: '售后任务' }]
const financeTabs = [{ key: 'entries', label: '项目款项', resources: ['entries'] }, { key: 'reconciliations', label: '项目对账', resources: ['reconciliations'] }, { key: 'payments', label: '项目收付流水', resources: ['payments'] }]
const costTabs = [{ key: 'budget', label: '预算与预测' }, { key: 'actual', label: '实际成本' }]
const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const project = ref<Row | null>(null)
const cost = ref<Row>({})
const revision = ref(0)
const tabsRef = ref<TabsInstance>()
async function revealTab() {
  await revealActiveTab(() => tabsRef.value)
}
const allowedTabs = ['tasks', 'bom', ...(purchaseReader() ? ['purchases'] : []), 'deliveries', ...(money() ? ['finance', 'cost'] : []), 'documents']
const initialTab = String(route.query.tab || sessionStore.get(`project-tab-${id}`) || 'tasks')
const tab = ref(allowedTabs.includes(initialTab) ? initialTab : 'tasks')
// 概览默认收起，任务 / BOM / 成本紧跟页头；展开过的用户在本机沿用自己的选择（storage 已内置 try/catch）。
const overview = ref(localStore.get('project-overview') === 'expanded')
watch(overview, value => localStore.set('project-overview', value ? 'expanded' : 'collapsed'))
const requirementsOpen = ref(false)
watch(tab, value => { sessionStore.set(`project-tab-${id}`, value); void router.replace({ query: { ...route.query, tab: value } }) })
watch(() => route.query.tab, value => { if (allowedTabs.includes(String(value))) tab.value = String(value) })
watch(tab, revealTab, { flush: 'post' })
watch(tab, value => { if (value === 'cost') void load() })
const error = ref('')
const projectFlow = computed(() => flowFor('projects', project.value))
const amount = (value: unknown) => formatMoney(value, { currency: true, placeholder: '未设置' })
// 收起时的一行摘要；合同金额与四宫格一样只在 money() 通过时才拼进来。
const brief = computed(() => {
  const record = project.value
  if (!record) return ''
  return [
    `${record.equipment_quantity} 台`,
    `交期 ${record.due_date || '未设置'}`,
    ...(money() ? [`合同 ${amount(record.contract_amount)}`] : []),
  ].join(' · ')
})
const command = ref<Command | null>(null)
const attention = computed(() => String(route.query.attention || ''))
const taskAttention = computed(() => tab.value === 'tasks' && (!route.query.section || route.query.section === 'tasks') && ['open-tasks', 'acceptance'].includes(attention.value))
const purchaseAttention = computed(() => tab.value === 'purchases' && ['submitted', 'approved', 'partial'].includes(attention.value))
const taskParams = computed(() => ({ project: id, ...(taskAttention.value ? { status: 'open', ...(attention.value === 'acceptance' ? { kind: 'acceptance' } : {}) } : {}) }))
const purchaseParams = computed(() => ({ project: id, ...(purchaseAttention.value ? { status: attention.value } : {}) }))
const attentionLabel = computed(() => ({ 'open-tasks': '未完成任务', acceptance: '待验收任务', submitted: '待批准采购', approved: '待收货采购', partial: '部分收货采购' }[attention.value]))
function clearAttention() {
  const { attention: _attention, ...query } = route.query
  void router.replace({ query })
}
async function load() {
  error.value = ''
  try {
    project.value = await read(`/business/projects/${id}/`)
    sessionStore.set(`current-project-${user.value?.id}`, String(id))
    if (money() && tab.value === 'cost') cost.value = await read(`/business/projects/${id}/cost/`)
    revision.value++
    await revealTab()
  } catch (e) {
    error.value = message(e)
  }
}
async function act(name: string) {
  try {
    command.value = { ...(await actionCommand('projects', project.value!, name)), flow: flowFor('projects', project.value) }
  } catch (e) {
    error.value = message(e)
  }
}
onMounted(load)
</script>
<template>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" /><template
    v-if="project"
    ><header class="page-heading">
      <div>
        <router-link to="/projects" class="muted">← 项目列表</router-link>
        <p class="eyebrow">{{ project.code }}</p>
        <h1>{{ project.name }}</h1>
        <p class="muted">
          {{ project.customer_name }} · {{ project.manager_name }} <StatusBadge :value="project.status" :text="display(project.status)" />
        </p>
      </div>
      <div class="toolbar">
        <el-button @click="overview = !overview" :aria-expanded="overview">{{ overview ? '收起项目概览' : '展开项目概览' }}</el-button>
        <el-button @click="load">刷新</el-button
        ><el-dropdown
          v-if="actionNames('projects', project).length"
          trigger="click"
          @command="(name: string) => act(String(name))"
          ><el-button type="primary">项目操作 ▾</el-button
          ><template #dropdown
            ><el-dropdown-menu
              ><el-dropdown-item
                v-for="name in actionNames('projects', project)"
                :key="name"
                :command="name"
                >{{ name }}</el-dropdown-item
              ></el-dropdown-menu
            ></template
          ></el-dropdown
        >
      </div>
    </header>
    <p v-if="!overview" class="project-brief muted">{{ brief }}</p>
    <ProcessSteps v-if="projectFlow" class="panel project-flow" :flow="projectFlow" />
    <ProjectAttention :project="project" :revision="revision" />
    <div v-show="overview">
    <section class="project-summary">
      <div>
        <small>设备数量</small><strong>{{ project.equipment_quantity }} 台</strong>
      </div>
      <div>
        <small>计划交期</small><strong>{{ project.due_date || '未设置' }}</strong>
      </div>
      <div>
        <small>质保约定</small><strong>{{ project.warranty_months }} 个月</strong>
      </div>
      <div v-if="money()">
        <small>合同金额</small><strong>{{ amount(project.contract_amount) }}</strong>
      </div>
    </section>
    <div v-if="project.requirements" class="requirements">
      <p class="requirement-text" :class="{ 'requirement-clamped': !requirementsOpen }">{{ project.requirements }}</p>
      <el-button
        link
        type="primary"
        class="requirement-toggle"
        :aria-expanded="requirementsOpen"
        @click="requirementsOpen = !requirementsOpen"
        >{{ requirementsOpen ? '收起' : '展开全文' }}</el-button
      >
    </div>
    </div>
    <p v-if="taskAttention || purchaseAttention" class="attention-filter" role="status">当前项目 · {{ attentionLabel }}<el-button text @click="clearAttention">查看全部</el-button><router-link v-if="taskAttention && attention === 'acceptance' && manager() && project.can_manage !== false" :to="{ path: `/projects/${id}`, query: { tab: 'deliveries', section: 'deliveries' } }">前往交付批次登记验收</router-link></p>
    <el-tabs ref="tabsRef" class="scrollable-tabs" v-model="tab" :before-leave="confirmFormNavigation"
      ><el-tab-pane label="任务与工时" name="tasks"
        ><ModuleTabs :parent-tab="tab" v-if="tab === 'tasks'" :tabs="taskTabs" :storage-key="`project-${id}-tasks`"><template #tasks><ResourcePanel
          resource="tasks"
          :key="`tasks-${attention}`"
          :class="{ 'attention-list': taskAttention }"
          title="项目任务"
          :allow-create="['active', 'delivering'].includes(project.status) && productionProject(project)"
          :project-id="id"
          :params="taskParams"
          :revision="revision"
          @changed="load" /></template><template #time><ResourcePanel
          resource="time"
          title="工时记录"
          :params="{ task__project: id }"
          :revision="revision"
          @changed="load" /></template></ModuleTabs></el-tab-pane
      ><el-tab-pane label="BOM" name="bom" lazy
        ><ModuleTabs :parent-tab="tab" v-if="tab === 'bom'" :tabs="bomTabs" :storage-key="`project-${id}-bom`"><template #demand><BOMDemand
          :project-id="id"
          :status="project.status"
          :can-edit-bom="project.can_edit_bom"
          :revision="revision"
          @changed="load" /></template><template #lines><ResourcePanel
          resource="bom"
          title="BOM 明细"
          :params="{ project: id }"
          :revision="revision"
          @changed="load" /></template></ModuleTabs></el-tab-pane
      ><el-tab-pane
        v-if="purchaseReader()"
        label="采购"
        name="purchases"
        lazy
        ><ResourcePanel
          resource="purchases"
          :key="`purchases-${attention}`"
          :class="{ 'attention-list': purchaseAttention }"
          title="项目采购"
          :allow-create="['active', 'delivering', 'warranty'].includes(project.status)"
          :params="purchaseParams"
          :project-id="id"
          :revision="revision"
          @changed="load" /></el-tab-pane
      ><el-tab-pane label="交付与售后" name="deliveries" lazy
        ><ModuleTabs :parent-tab="tab" v-if="tab === 'deliveries'" :tabs="deliveryTabs" :storage-key="`project-${id}-deliveries`"><template #deliveries><ResourcePanel
          resource="deliveries"
          title="交付批次"
          :params="{ project: id }"
          :revision="revision"
          @changed="load" /></template><template #service><ResourcePanel
          resource="tasks"
          title="售后任务"
          :allow-create="false"
          :params="{ project: id, kind: 'service' }"
          :project-id="id"
          :revision="revision"
          @changed="load" /></template></ModuleTabs></el-tab-pane
      ><el-tab-pane v-if="money()" label="收付款" name="finance" lazy
        ><ModuleTabs :parent-tab="tab" v-if="tab === 'finance'" :tabs="financeTabs" :storage-key="`project-${id}-finance`"><template #entries><ResourcePanel
          resource="entries"
          title="项目款项"
          :allow-create="['active', 'delivering', 'warranty'].includes(project.status)"
          :params="{ project: id }"
          :project-id="id"
          :revision="revision"
          @changed="load" /></template><template #reconciliations><ResourcePanel resource="reconciliations" title="项目对账" :params="{ entry__project: id }" :project-id="id" :revision="revision" @changed="load" /></template><template #payments><ResourcePanel resource="payments" title="项目收付流水" :allow-create="false" :params="{ entry__project: id }" :project-id="id" :revision="revision" @changed="load" /></template></ModuleTabs></el-tab-pane
      ><el-tab-pane v-if="money()" label="成本与预算" name="cost" lazy>
        <ModuleTabs :parent-tab="tab" v-if="tab === 'cost'" :tabs="costTabs" :storage-key="`project-${id}-cost`">
          <template #budget><BudgetPanel :project-id="id" :revision="revision" :status="project.status" :can-manage="project.can_manage" /></template>
          <template #actual><section class="panel cost-panel" aria-label="项目成本">
            <h2>实际成本 <span class="muted">CNY 含税经营口径</span></h2>
            <div class="cost-grid"><div v-for="(label, key) in { materials: '材料', labor: '人工', expenses: '费用', purchase_return_variance: '退货价差', total: '合计' }" :key="key">
              <small>{{ label }}</small><strong>¥ {{ cost[key] ?? '—' }}</strong>
            </div></div>
          </section></template>
        </ModuleTabs>
      </el-tab-pane><el-tab-pane label="附件" name="documents" lazy
        ><ResourcePanel
          resource="documents"
          title="项目附件"
          :params="{ project: id }"
          :project-id="id"
          :revision="revision"
          @changed="load" /></el-tab-pane></el-tabs
    ><ActionDialog :command="command" @close="command = null" @saved="load"
  /></template>
</template>
<style scoped>
.project-summary { gap: 0; border: 1px solid var(--surface-border); border-radius: 8px; overflow: hidden; background: #fff; padding: 18px 0; }
.project-summary > div { border: 0; border-right: 1px solid var(--surface-border); border-radius: 0; box-shadow: none; padding: 0 22px; }
.project-summary > div:last-child { border-right: 0; }
.project-summary strong { font-size: 20px; margin-top: 8px; }
.project-brief { margin: -14px 0 16px; font-variant-numeric: tabular-nums; }
.attention-filter { display: flex; align-items: center; gap: 12px; }
.attention-list :deep(.resource-status-tabs) { display: none; }
.requirements { display: flex; align-items: flex-start; gap: 12px; background: #fff; border-left: 3px solid var(--brand-line); line-height: 1.7; }
.requirement-text { flex: 1; min-width: 0; margin: 0; max-height: 150px; overflow: auto; }
/* 默认只留一行：nowrap 让换行折成空格，省略号提示还有下文。 */
.requirement-clamped { max-height: none; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.requirement-toggle { flex: none; align-self: flex-start; }
@media (max-width: 760px) { .project-summary { row-gap: 20px; } .project-summary > div { padding: 0 16px; } }
</style>
