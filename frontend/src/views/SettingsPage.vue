<script setup lang="ts">
import { ref } from 'vue'
import { user, can, logout } from '../session'
import type { Command } from '../types'
import ResourcePanel from '../components/ResourcePanel.vue'
import ActionDialog from '../components/ActionDialog.vue'
import DeferredSection from '../components/DeferredSection.vue'
const command = ref<Command | null>(null)
function password() {
  command.value = {
    title: '修改密码',
    path: '/auth/password/',
    fields: [
      { key: 'old_password', label: '原密码', type: 'password' },
      {
        key: 'new_password',
        label: '新密码',
        type: 'password',
        hint: '至少 12 位；修改后需重新登录。',
      },
    ],
  }
}
</script>
<template>
  <header class="page-heading"><h1>设置</h1></header>
  <section class="panel">
    <h2>我的账户</h2>
    <p>{{ user?.username }} · {{ user?.display_name }}</p>
    <el-button @click="password">修改密码</el-button>
  </section>
  <template v-if="can(['admin'])">
    <ResourcePanel resource="users" title="用户管理" />
    <DeferredSection title="公司资料"><ResourcePanel resource="company" title="公司资料" /></DeferredSection>
    <DeferredSection title="编号规则"><ResourcePanel resource="codes" title="编号规则" /></DeferredSection>
    <DeferredSection title="操作审计"><ResourcePanel resource="audit" title="操作审计" /></DeferredSection>
  </template>
  <ActionDialog :command="command" @close="command = null" @saved="logout" />
</template>
