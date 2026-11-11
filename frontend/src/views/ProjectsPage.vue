<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import ModulePage from '../components/ModulePage.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import { user } from '../session'
import { labels } from '../modules/shared'
// 任务和工时以前只能从单个项目里进，工作台的「我的待办」点进来也只是一张项目列表。
const tabs = [
  { key: 'projects', label: '项目列表', resources: ['projects'] },
  { key: 'tasks', label: '任务', resources: ['tasks'] },
  { key: 'time', label: '工时记录', resources: ['time'] },
]
const route = useRoute()
const mine = ref(true)
const supervised = computed(() => route.query.supervisor === String(user.value?.id))
// 工作台「生产与售后派工」带 mine=0、kinds=装配等任务类型进来：列出参与项目里这几类任务，与工作台计数同一口径。
watch(() => route.query.mine, value => { mine.value = value !== '0' }, { immediate: true })
const kinds = computed(() => typeof route.query.kinds === 'string' && /^[a-z_]+(,[a-z_]+)*$/.test(route.query.kinds) ? route.query.kinds : '')
const kindText = computed(() => kinds.value.split(',').map(kind => labels[kind] || kind).join('、'))
const taskParams = computed(() => supervised.value ? { supervisor: user.value?.id } : { ...(mine.value ? { assignee: user.value?.id } : {}), ...(kinds.value ? { kind__in: kinds.value } : {}) })
</script>
<template>
  <ModulePage title="项目" v-slot="{ revision, refresh }">
    <ModuleTabs :tabs="tabs" storage-key="projects">
      <template #projects
        ><ResourcePanel resource="projects" title="项目列表" :revision="revision" @changed="refresh"
      /></template>
      <template #tasks>
        <p v-if="supervised" class="task-scope">我负责确认的任务 · 按专业主管归属显示 <router-link to="/projects?section=tasks">查看其他任务</router-link></p>
        <template v-else>
          <p v-if="kinds" class="task-scope">只显示{{ kindText }}任务 <router-link :to="{ path: '/projects', query: { section: 'tasks', mine: '0' } }">查看全部类型任务</router-link></p>
          <label class="inline-check task-scope"
            ><input v-model="mine" type="checkbox" />只看分配给我的任务</label
          >
        </template>
        <ResourcePanel
          resource="tasks"
          title="任务"
          :allow-create="false"
          :params="taskParams"
          :revision="revision"
          @changed="refresh"
        />
      </template>
      <template #time
        ><ResourcePanel resource="time" title="工时记录" :revision="revision" @changed="refresh"
      /></template>
    </ModuleTabs>
  </ModulePage>
</template>
<style scoped>
.task-scope { margin-bottom: 12px; }
</style>
