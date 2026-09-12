<script setup lang="ts">
import { computed, provide, ref } from 'vue'
import { user, can, logout } from '../session'
import type { Command } from '../types'
import ResourcePanel from '../components/ResourcePanel.vue'
import ActionDialog from '../components/ActionDialog.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import CodingRules from '../components/CodingRules.vue'
const tabs = computed(() => [
  ...(can(['admin']) ? [
    { key: 'users', label: '用户管理' }, { key: 'company', label: '公司资料' },
    { key: 'codes', label: '编号规则' }, { key: 'audit', label: '操作审计' },
  ] : []),
  { key: 'account', label: '我的账户' },
])
const command = ref<Command | null>(null)
const toolbarTarget = ref<HTMLElement | null>(null)
provide('moduleToolbar', toolbarTarget)
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
  <header class="page-heading"><div><h1>设置</h1><p class="muted">公司资料与人员配置，分模块维护。</p></div><div class="settings-actions"><router-link v-if="can(['admin'])" to="/setup">启用指南</router-link><div ref="toolbarTarget" class="module-toolbar-target" /></div></header>
  <ModuleTabs :tabs="tabs" storage-key="settings">
    <template #account><section class="panel">
    <h2>我的账户</h2>
    <p>{{ user?.username }} · {{ user?.display_name }}</p>
    <el-button @click="password">修改密码</el-button>
    </section></template>
    <template #users><ResourcePanel v-if="can(['admin'])" resource="users" title="用户管理" /></template>
    <template #company><ResourcePanel v-if="can(['admin'])" resource="company" title="公司资料" /></template>
    <template #codes><CodingRules v-if="can(['admin'])" /><ResourcePanel v-if="can(['admin'])" resource="codes" title="编号规则" /></template>
    <template #audit><ResourcePanel v-if="can(['admin'])" resource="audit" title="操作审计" /></template>
  </ModuleTabs>
  <ActionDialog :command="command" @close="command = null" @saved="logout" />
</template>
