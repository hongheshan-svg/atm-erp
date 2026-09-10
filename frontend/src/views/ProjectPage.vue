<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { TabsInstance } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { read } from '../api'
import { money, can } from '../session'
import { actionNames, actionCommand, display } from '../business'
import { message } from '../utils/request'
import type { Row, Command } from '../types'
import ResourcePanel from '../components/ResourcePanel.vue'
import BOMDemand from '../components/BOMDemand.vue'
import BudgetPanel from '../components/BudgetPanel.vue'
import ActionDialog from '../components/ActionDialog.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import { revealActiveTab } from '../utils/tabs'
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
const allowedTabs = ['tasks', 'bom', ...(can(['admin', 'manager', 'purchaser', 'warehouse', 'finance']) ? ['purchases'] : []), 'deliveries', ...(money() ? ['finance', 'cost'] : []), 'documents']
const initialTab = String(route.query.tab || sessionStorage.getItem(`project-tab-${id}`) || 'tasks')
const tab = ref(allowedTabs.includes(initialTab) ? initialTab : 'tasks')
const overview = ref(sessionStorage.getItem('project-overview') !== 'collapsed')
watch(overview, value => sessionStorage.setItem('project-overview', value ? 'expanded' : 'collapsed'))
watch(tab, value => { sessionStorage.setItem(`project-tab-${id}`, value); void router.replace({ query: { ...route.query, tab: value } }) })
watch(() => route.query.tab, value => { if (allowedTabs.includes(String(value))) tab.value = String(value) })
watch(tab, revealTab, { flush: 'post' })
watch(tab, value => { if (value === 'cost') void load() })
const error = ref('')
const command = ref<Command | null>(null)
async function load() {
  try {
    project.value = await read(`/business/projects/${id}/`)
    if (money() && tab.value === 'cost') cost.value = await read(`/business/projects/${id}/cost/`)
    revision.value++
    await revealTab()
  } catch (e) {
    error.value = message(e)
  }
}
async function act(name: string) {
  try {
    command.value = await actionCommand('projects', project.value!, name)
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
          {{ project.customer_name }} · {{ project.manager_name }} · {{ display(project.status) }}
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
        <small>合同金额</small><strong>¥ {{ project.contract_amount }}</strong>
      </div>
    </section>
    <p v-if="project.requirements" class="requirements">{{ project.requirements }}</p>
    </div>
    <el-tabs ref="tabsRef" class="scrollable-tabs" v-model="tab"
      ><el-tab-pane label="任务与工时" name="tasks"
        ><ModuleTabs :parent-tab="tab" v-if="tab === 'tasks'" :tabs="taskTabs" :storage-key="`project-${id}-tasks`"><template #tasks><ResourcePanel
          resource="tasks"
          title="项目任务"
          :allow-create="['active', 'delivering'].includes(project.status)"
          :project-id="id"
          :params="{ project: id }"
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
          :revision="revision"
          @changed="load" /></template><template #lines><ResourcePanel
          resource="bom"
          title="BOM 明细"
          :params="{ project: id }"
          :revision="revision"
          @changed="load" /></template></ModuleTabs></el-tab-pane
      ><el-tab-pane
        v-if="can(['admin', 'manager', 'purchaser', 'warehouse', 'finance'])"
        label="采购"
        name="purchases"
        lazy
        ><ResourcePanel
          resource="purchases"
          title="项目采购"
          :allow-create="['active', 'delivering', 'warranty'].includes(project.status)"
          :params="{ project: id }"
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
