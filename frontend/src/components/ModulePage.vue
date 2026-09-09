<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { all } from '../api'
import { message } from '../utils/request'
import { today } from '../forms'
import type { Row } from '../types'
const props = defineProps<{ title: string; projectFilter?: boolean; requireProject?: boolean }>()
const projects = ref<Row[]>([])
const projectId = ref<number>()
const revision = ref(0)
const error = ref('')
async function refresh() {
  error.value = ''
  try {
    if (props.projectFilter) projects.value = await all('/business/projects/')
    revision.value++
  } catch (e) {
    error.value = message(e)
  }
}
onMounted(refresh)
</script>
<template>
  <header class="page-heading">
    <div>
      <p class="eyebrow">业务管理 / {{ today() }}</p>
      <h1>{{ title }}</h1>
    </div>
    <el-button @click="refresh">刷新</el-button>
  </header>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <label v-if="projectFilter" class="project-filter"
    >项目筛选<select v-model="projectId">
      <option :value="undefined">{{ requireProject ? '请选择项目' : '全部项目' }}</option>
      <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.code }} · {{ p.name }}</option>
    </select></label
  >
  <slot :project-id="projectId" :projects="projects" :revision="revision" :refresh="refresh" />
</template>
