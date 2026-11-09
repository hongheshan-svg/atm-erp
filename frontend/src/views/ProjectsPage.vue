<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import ModulePage from '../components/ModulePage.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import { user } from '../session'
// 任务和工时以前只能从单个项目里进，工作台的「我的待办」点进来也只是一张项目列表。
const tabs = [
  { key: 'projects', label: '项目列表', resources: ['projects'] },
  { key: 'tasks', label: '任务', resources: ['tasks'] },
  { key: 'time', label: '工时记录', resources: ['time'] },
]
const route = useRoute()
const mine = ref(true)
const supervised = computed(() => route.query.supervisor === String(user.value?.id))
</script>
<template>
  <ModulePage title="项目" v-slot="{ revision, refresh }">
    <ModuleTabs :tabs="tabs" storage-key="projects">
      <template #projects
        ><ResourcePanel resource="projects" title="项目列表" :revision="revision" @changed="refresh"
      /></template>
      <template #tasks>
        <p v-if="supervised" class="task-scope">我负责确认的任务 · 按专业主管归属显示 <router-link to="/projects?section=tasks">查看其他任务</router-link></p>
        <label v-else class="inline-check task-scope"
          ><input v-model="mine" type="checkbox" />只看分配给我的任务</label
        >
        <ResourcePanel
          resource="tasks"
          title="任务"
          :allow-create="false"
          :params="supervised ? { supervisor: user?.id } : mine ? { assignee: user?.id } : {}"
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
