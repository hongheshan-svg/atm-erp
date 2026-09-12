<script setup lang="ts">
import { provide, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { user } from '../session'
import { read } from '../api'
import RemoteSelect from './RemoteSelect.vue'
import { message } from '../utils/request'
import { today } from '../forms'
import type { Row } from '../types'
const props = defineProps<{ title: string; projectFilter?: boolean; requireProject?: boolean }>()
const descriptions: Record<string, string> = {
  销售: '从需求确认到签约交接。', 项目: '围绕交期推进设计、装配、调试与交付。',
  BOM: '按项目维护物料需求，跟进缺料与采购。', 采购: '从选料下单到合同、收货与结算。',
  库存: '共享库存统一维护，出入库有据可查。', 收付款: '核清业务款项，跟进收付与银行到账。',
  基础资料: '统一物料与往来单位，减少重复维护。',
}
const projects = ref<Row[]>([])
const route = useRoute()
const projectKey = `module-project-${user.value?.id}-${props.title}`
const savedProject = Number(route.query.project || sessionStorage.getItem(projectKey))
const projectId = ref<number | undefined>(Number.isSafeInteger(savedProject) && savedProject > 0 ? savedProject : undefined)
watch(projectId, value => { if (value) sessionStorage.setItem(projectKey, String(value)); else sessionStorage.removeItem(projectKey) })
const revision = ref(0)
const toolbarTarget = ref<HTMLElement | null>(null)
provide('moduleToolbar', toolbarTarget)
const focusedFlow = ref(false)
provide('moduleFocusedFlow', focusedFlow)
const error = ref('')
async function loadProjects() {
  error.value = ''
  try {
    const selected = projectId.value
    const result = selected ? await read(`/business/projects/${selected}/`) : null
    if (selected === projectId.value) projects.value = result ? [result] : []
  } catch (e) {
    error.value = message(e)
  }
}
function refresh() { revision.value++ }
watch(projectId, loadProjects, { immediate: true })
</script>
<template>
  <header v-show="!focusedFlow" class="page-heading">
    <div>
      <p class="eyebrow">业务管理 / {{ today() }}</p>
      <h1>{{ title }}</h1>
      <p class="muted">{{ descriptions[title] }}</p>
    </div>
    <div ref="toolbarTarget" class="module-toolbar-target" />
  </header>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <label v-if="projectFilter" class="project-filter"
    >项目筛选<RemoteSelect :model-value="projectId" @update:model-value="projectId = $event ? Number($event) : undefined" path="/business/projects/" label="项目筛选" /><small>{{ projectId ? '仅显示所选项目' : requireProject ? '请选择项目' : '未选择时显示全部项目' }}</small></label
  >
  <slot :project-id="projectId" :projects="projects" :revision="revision" :refresh="refresh" />
</template>
