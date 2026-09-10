<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { user } from '../session'
import { read } from '../api'
import RemoteSelect from './RemoteSelect.vue'
import { message } from '../utils/request'
import { today } from '../forms'
import type { Row } from '../types'
const props = defineProps<{ title: string; projectFilter?: boolean; requireProject?: boolean }>()
const projects = ref<Row[]>([])
const route = useRoute()
const projectKey = `module-project-${user.value?.id}-${props.title}`
const savedProject = Number(route.query.project || sessionStorage.getItem(projectKey))
const projectId = ref<number | undefined>(Number.isSafeInteger(savedProject) && savedProject > 0 ? savedProject : undefined)
watch(projectId, value => { if (value) sessionStorage.setItem(projectKey, String(value)); else sessionStorage.removeItem(projectKey) })
const revision = ref(0)
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
  <header class="page-heading">
    <div>
      <p class="eyebrow">业务管理 / {{ today() }}</p>
      <h1>{{ title }}</h1>
    </div>
    <el-button @click="loadProjects(); refresh()">刷新</el-button>
  </header>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <label v-if="projectFilter" class="project-filter"
    >项目筛选<RemoteSelect :model-value="projectId" @update:model-value="projectId = $event ? Number($event) : undefined" path="/business/projects/" label="项目筛选" /><small>{{ requireProject ? '请选择项目' : '未选择时显示全部项目' }}</small></label
  >
  <slot :project-id="projectId" :projects="projects" :revision="revision" :refresh="refresh" />
</template>
