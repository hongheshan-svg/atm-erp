<script setup lang="ts">
import { computed, provide, ref } from 'vue'
import { user, can, logout } from '../session'
import type { Command } from '../types'
import ResourcePanel from '../components/ResourcePanel.vue'
import ActionDialog from '../components/ActionDialog.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
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
    <template #codes><p class="muted">产品编码规范：有图 11机加 / 12钣金 / 13特殊工艺 / 19其它，后接两位年份与六位流水；无图 21标准件 / 22耗材辅料 / 23办公用品 / 29其它，年份固定99。选择产品编码类别后按此规则生成，未分类物料沿用下方普通规则；手填编码和历史编号保留。新安装项目默认 ATM＋两位年＋两位流水。</p><ResourcePanel v-if="can(['admin'])" resource="codes" title="编号规则" /></template>
    <template #audit><ResourcePanel v-if="can(['admin'])" resource="audit" title="操作审计" /></template>
  </ModuleTabs>
  <ActionDialog :command="command" @close="command = null" @saved="logout" />
</template>
