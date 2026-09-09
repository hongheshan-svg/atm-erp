<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { read } from '../api'
import { user } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'
const work = ref<Row>({})
const error = ref('')
const bucketLabels: Record<string, string> = {
  tasks: '我的待办',
  approvals: '待批准采购',
  receipts: '待收货',
  drafts: '采购草稿',
  settlements: '到期收付 / 待退款',
}
async function load() {
  error.value = ''
  try {
    work.value = await read('/business/workbench/')
  } catch (e) {
    error.value = message(e)
  }
}
onMounted(load)
</script>
<template>
  <header class="page-heading">
    <div>
      <h1>工作台</h1>
      <p class="muted">{{ user?.display_name }}，从待办开始今天的协作。</p>
    </div>
    <el-button @click="load">刷新</el-button>
  </header>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <div class="workbench-grid">
    <section v-for="(bucket, key) in work" :key="key" class="panel">
      <h2>
        {{ bucketLabels[key] }} <el-tag>{{ bucket.count }}</el-tag>
      </h2>
      <p v-if="!bucket.results.length" class="muted empty">暂无待办</p>
      <router-link
        v-for="row in bucket.results"
        :key="row.id"
        :to="`/projects/${row.project}`"
        class="work-item"
        ><strong>{{ row.title || row.code }}</strong
        ><span
          >{{ row.project_name || row.assignee_name }} · {{ row.due_date || '未设期限' }}</span
        ></router-link
      ><router-link
        v-if="bucket.count > 20"
        :to="key === 'tasks' ? '/projects' : key === 'settlements' ? '/finance' : '/purchases'"
        >查看全部 {{ bucket.count }} 条</router-link
      >
    </section>
  </div>
</template>
