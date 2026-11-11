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
import ProjectProgress from '../components/ProjectProgress.vue'
import ProjectTaskSupervisors from '../components/ProjectTaskSupervisors.vue'
import ProjectMilestones from '../components/ProjectMilestones.vue'
import ProjectReadiness from '../components/ProjectReadiness.vue'
import FinanceTotals from '../components/FinanceTotals.vue'
import { revealActiveTab } from '../utils/tabs'
import { localStore, sessionStore } from '../utils/storage'
import { flowFor } from '../flows'
import { confirmFormNavigation } from '../form-experience'
const taskTabs = [{ key: 'tasks', label: '项目任务', resources: ['tasks'] }, { key: 'time', label: '工时记录', resources: ['time'] }]
const deliveryTabs = [{ key: 'deliveries', label: '交付批次', resources: ['deliveries'] }, { key: 'service', label: '售后任务' }]
const financeTabs = [{ key: 'entries', label: '项目款项', resources: ['entries'] }, { key: 'reconciliations', label: '项目对账', resources: ['reconciliations'] }, { key: 'payments', label: '项目收付流水', resources: ['payments'] }]
const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const project = ref<Row | null>(null)
const revision = ref(0)
const tabsRef = ref<TabsInstance>()
async function revealTab() {
  await revealActiveTab(() => tabsRef.value)
}
const allowedTabs = ['progress', 'tasks', 'bom', ...(purchaseReader() ? ['purchases'] : []), 'deliveries', ...(money() ? ['finance', 'cost'] : []), 'documents']
const initialTab = String(route.query.tab || sessionStore.get(`project-tab-${id}`) || 'tasks')
const tab = ref(allowedTabs.includes(initialTab) ? initialTab : 'tasks')
// 概览默认收起，任务 / BOM / 成本紧跟页头；展开过的用户在本机沿用自己的选择（storage 已内置 try/catch）。
const overview = ref(localStore.get('project-overview') === 'expanded')
watch(overview, value => localStore.set('project-overview', value ? 'expanded' : 'collapsed'))
const requirementsOpen = ref(false)
watch(tab, value => { sessionStore.set(`project-tab-${id}`, value); void router.replace({ query: { ...route.query, tab: value } }) })
watch(() => route.query.tab, value => { if (allowedTabs.includes(String(value))) tab.value = String(value) })
watch(tab, revealTab, { flush: 'post' })
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
// 推进检查只给能发货、结项的项目经理看；其他角色不请求，避免无权限报错。
const readinessVisible = computed(() => Boolean(project.value && manager() && project.value.can_manage !== false && ['active', 'delivering', 'warranty'].includes(project.value.status)))
// 交付页签里的「登记发货」与页头「项目操作」同一条件。
const canShip = computed(() => Boolean(project.value && actionNames('projects', project.value).includes('发货')))
const deliveryEmpty = computed(() => canShip.value
  ? '尚未发货。完成设计、装配、调试任务后在此登记发货；每批发货会自动生成安装和验收任务。'
  : '尚未发货。发货由项目经理登记，每批发货会自动生成安装和验收任务。')
const command = ref<Command | null>(null)
const attention = computed(() => String(route.query.attention || ''))
const taskAttention = computed(() => tab.value === 'tasks' && (!route.query.section || route.query.section === 'tasks') && ['open-tasks', 'acceptance'].includes(attention.value))
const purchaseAttention = computed(() => tab.value === 'purchases' && ['draft', 'submitted', 'approved', 'partial'].includes(attention.value))
// 阶段筛选跟随地址，推进检查里的「装配阶段」等链接可以直接落到对应任务。
const phase = ref(String(route.query.phase || ''))
watch(() => route.query.phase, value => { phase.value = String(value || '') })
function selectPhase(value: string) {
  const { attention: _attention, phase: _phase, ...query } = route.query
  phase.value = value
  void router.replace({ query: { ...query, ...(value ? { phase: value } : {}) } })
}
const taskParams = computed(() => ({ project: id, ...(phase.value ? { phase: phase.value } : {}), ...(taskAttention.value ? { status: 'open', ...(attention.value === 'acceptance' ? { kind: 'acceptance' } : {}) } : {}) }))
const purchaseParams = computed(() => ({ project: id, ...(purchaseAttention.value ? { status: attention.value } : {}) }))
const attentionLabel = computed(() => ({ 'open-tasks': '未完成任务', acceptance: '待验收任务', draft: '采购草稿', submitted: '待批准采购', approved: '待收货采购', partial: '部分收货采购' }[attention.value]))
function clearAttention() {
  const { attention: _attention, ...query } = route.query
  void router.replace({ query })
}
async function load() {
  error.value = ''
  try {
    project.value = await read(`/business/projects/${id}/`)
    sessionStore.set(`current-project-${user.value?.id}`, String(id))
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
    ><header class="page-heading project-heading">
      <div>
        <p class="project-crumb">
          <span class="project-back"><router-link to="/projects" class="muted">← 项目列表</router-link><span class="eyebrow">{{ project.code }}</span></span
          ><span class="project-meta">{{ project.customer_name }} · {{ project.manager_name }}<template v-if="!overview"> · <span class="project-brief">{{ brief }}</span></template></span>
        </p>
        <div class="project-name"><h1>{{ project.name }}</h1><StatusBadge :value="project.status" :text="display(project.status)" /></div>
      </div>
      <div class="toolbar">
        <!-- 手机上按钮与返回同一行：概览按钮显示短字，读屏和按名称查找仍用完整名称。 -->
        <el-button @click="overview = !overview" :aria-expanded="overview" :aria-label="overview ? '收起项目概览' : '展开项目概览'"><span class="label-full">{{ overview ? '收起项目概览' : '展开项目概览' }}</span><span class="label-short" aria-hidden="true">概览 {{ overview ? '▴' : '▾' }}</span></el-button>
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
    <!-- 状态、下一步和待办合成一块：流程条压成一行步骤，推进检查紧跟其后，首屏留给任务表。 -->
    <section class="panel project-status" aria-label="项目推进">
      <ProcessSteps v-if="projectFlow" class="project-flow" :flow="projectFlow" inline />
      <ProjectReadiness v-if="readinessVisible" :project="project" :revision="revision" @act="act" />
      <ProjectAttention v-if="tab !== 'progress'" :project="project" :revision="revision" />
    </section>
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
    <el-tabs ref="tabsRef" class="scrollable-tabs project-tabs" v-model="tab" :before-leave="confirmFormNavigation"
      ><el-tab-pane label="流程进度" name="progress" lazy><ProjectProgress v-if="tab === 'progress'" :project-id="id" :revision="revision" /></el-tab-pane><el-tab-pane label="任务与工时" name="tasks"
        ><ModuleTabs :parent-tab="tab" v-if="tab === 'tasks'" :tabs="taskTabs" :storage-key="`project-${id}-tasks`"><template #tasks><ProjectMilestones :project-id="id" :revision="revision" :phase="phase" @phase="selectPhase" @changed="load" /><ResourcePanel
          resource="tasks"
          :key="`tasks-${attention}`"
          :class="{ 'attention-list': taskAttention }"
          title="项目任务"
          :allow-create="['active', 'delivering'].includes(project.status) && productionProject(project)"
          :project-id="id"
          :params="taskParams"
          :revision="revision"
          @changed="load" /><ProjectTaskSupervisors :project="project" @changed="load" /></template><template #time><ResourcePanel
          resource="time"
          title="工时记录"
          :params="{ task__project: id }"
          :revision="revision"
          @changed="load" /></template></ModuleTabs></el-tab-pane
      ><el-tab-pane label="BOM" name="bom" lazy
        ><BOMDemand
          v-if="tab === 'bom'"
          :project-id="id"
          :status="project.status"
          :can-edit-bom="project.can_edit_bom"
          :revision="revision"
          @changed="load" /></el-tab-pane
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
        ><ModuleTabs :parent-tab="tab" v-if="tab === 'deliveries'" :tabs="deliveryTabs" :storage-key="`project-${id}-deliveries`"><template #deliveries><div v-if="canShip" class="tab-actions"><el-button type="primary" @click="act('发货')">登记发货</el-button><span class="muted">每批发货自动生成本批安装和验收任务；安装完成后在下方批次上登记验收。</span></div><ResourcePanel
          resource="deliveries"
          title="交付批次"
          :params="{ project: id }"
          :empty-hint="deliveryEmpty"
          hide-contact-hint
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
        ><FinanceTotals v-if="tab === 'finance'" project :project-id="id" :revision="revision" /><ModuleTabs :parent-tab="tab" v-if="tab === 'finance'" :tabs="financeTabs" :storage-key="`project-${id}-finance`"><template #entries><ResourcePanel
          resource="entries"
          title="项目款项"
          :allow-create="['active', 'delivering', 'warranty'].includes(project.status)"
          :params="{ project: id }"
          :project-id="id"
          :revision="revision"
          @changed="load" /></template><template #reconciliations><ResourcePanel resource="reconciliations" title="项目对账" :params="{ entry__project: id }" :project-id="id" :revision="revision" @changed="load" /></template><template #payments><ResourcePanel resource="payments" title="项目收付流水" :allow-create="false" :params="{ entry__project: id }" :project-id="id" :revision="revision" @changed="load" /></template></ModuleTabs></el-tab-pane
      ><el-tab-pane v-if="money()" label="成本与预算" name="cost" lazy>
        <BudgetPanel v-if="tab === 'cost'" :project-id="id" :revision="revision" :status="project.status" :can-manage="project.can_manage" :contract="project.contract_amount" />
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
/* 页头两行：返回、编号、客户·负责人·摘要一行，名称与状态一行。 */
.project-heading { margin-bottom: 10px; }
.project-crumb { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; margin: 0; font-size: 13px; }
.project-crumb .muted { margin: 0; }
.project-meta { color: var(--mute); min-width: 0; }
.project-name { display: flex; align-items: center; gap: 10px; min-width: 0; }
.project-name h1 { margin: 2px 0 0; font-size: 22px; min-width: 0; overflow-wrap: anywhere; }
.project-brief { font-variant-numeric: tabular-nums; }
.project-status { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 8px 16px; padding: 8px 14px; margin-bottom: 8px; }
.project-status .project-flow { flex: none; margin: 2px 0 0; }
.project-status :deep(.project-readiness) { flex: 1 1 520px; }
.project-status :deep(.project-attention) { flex: 1 1 auto; margin: 0; padding: 0; border: 0; border-radius: 0; box-shadow: none; background: transparent; }
/* 主页签和「项目任务 / 工时记录」子页签压窄，任务表尽量进首屏。 */
.project-tabs > :deep(.el-tabs__header) { margin-bottom: 8px; }
.project-tabs :deep(.module-tabs > .el-tabs__header) { margin-bottom: 8px; }
.project-tabs :deep(.module-tabs > .el-tabs__header .el-tabs__item) { height: 32px; line-height: 32px; font-size: 13px; }
.tab-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-bottom: 10px; }
.tab-actions .muted { font-size: 12px; }
.attention-filter { display: flex; align-items: center; gap: 12px; }
.attention-list :deep(.resource-status-tabs) { display: none; }
.requirements { display: flex; align-items: flex-start; gap: 12px; background: #fff; border-left: 3px solid var(--brand-line); line-height: 1.7; }
.requirement-text { flex: 1; min-width: 0; margin: 0; max-height: 150px; overflow: auto; }
/* 默认只留一行：nowrap 让换行折成空格，省略号提示还有下文。 */
.requirement-clamped { max-height: none; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.requirement-toggle { flex: none; align-self: flex-start; }
@media (max-width: 760px) { .project-summary { row-gap: 20px; } .project-summary > div { padding: 0 16px; } }
.project-back { display: contents; }
.label-short { display: none; }
/* 手机：返回与按钮一行，名称最多两行，客户·负责人·交期最多两行；推进块压紧，任务表尽量进首屏。 */
@media (max-width: 600px) {
  .project-heading { display: grid; grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: 'back tools' 'name name' 'meta meta'; align-items: center; gap: 2px 8px; margin-bottom: 8px; }
  .project-heading > div:first-child, .project-crumb { display: contents; }
  .project-back { grid-area: back; display: flex; align-items: baseline; gap: 8px; min-width: 0; font-size: 13px; white-space: nowrap; }
  .project-back .eyebrow { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  .project-name { grid-area: name; margin-top: 2px; }
  .project-name h1 { margin: 0; font-size: 18px; line-height: 1.35; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden; }
  .project-meta { grid-area: meta; font-size: 12px; line-height: 1.5; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden; }
  .project-heading > .toolbar { grid-area: tools; display: flex; flex-wrap: nowrap; align-items: center; gap: 4px; margin: 0; }
  .project-heading > .toolbar :deep(.el-button) { height: 30px; min-height: 30px; padding: 4px 8px; margin: 0; font-size: 12px; }
  .label-full { display: none; }
  .label-short { display: inline; }
  .project-status { gap: 6px 10px; padding: 8px 12px; }
  .project-status :deep(.project-readiness), .project-status :deep(.project-attention) { flex-basis: 100%; }
}
</style>
