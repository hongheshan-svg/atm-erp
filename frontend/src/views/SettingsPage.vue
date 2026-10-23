<script setup lang="ts">
import { computed, provide, ref } from 'vue'
import { user, can, logout } from '../session'
import type { Command } from '../types'
import ResourcePanel from '../components/ResourcePanel.vue'
import TransferTools from '../components/TransferTools.vue'
import ActionDialog from '../components/ActionDialog.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import CodingRules from '../components/CodingRules.vue'
import DataChecks from '../components/DataChecks.vue'
import { createCommand } from '../business'
import { message } from '../utils/request'
const tabs = computed(() => [
  ...(can(['admin']) ? [
    { key: 'users', label: '用户管理' }, { key: 'company', label: '公司资料' },
    { key: 'codes', label: '编号规则' }, { key: 'audit', label: '操作审计' },
    { key: 'initialization', label: '管理员初始化' }, { key: 'data-checks', label: '历史数据核查' },
  ] : []),
  { key: 'account', label: '我的账户' },
])
const command = ref<Command | null>(null)
const error = ref('')
const openingBusy = ref(false)
const savedOpening = ref(false)
async function opening() {
  if (!can(['admin']) || openingBusy.value) return
  openingBusy.value = true; error.value = ''; savedOpening.value = false
  try { command.value = await createCommand('stocks') }
  catch (e) { error.value = message(e) }
  finally { openingBusy.value = false }
}
function saved() {
  if (command.value?.path === '/auth/password/') logout()
  else savedOpening.value = true
}
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
    <p><router-link to="/workbench?guide=show">再次查看岗位首任务指引</router-link></p>
    </section></template>
    <template #users><ResourcePanel v-if="can(['admin'])" resource="users" title="用户管理" /></template>
    <template #company><ResourcePanel v-if="can(['admin'])" resource="company" title="公司资料" /></template>
    <template #codes><CodingRules v-if="can(['admin'])" /><ResourcePanel v-if="can(['admin'])" resource="codes" title="编号规则" /></template>
    <template #audit><ResourcePanel v-if="can(['admin'])" resource="audit" title="操作审计" /></template>
    <template #data-checks><DataChecks v-if="can(['admin'])" /></template>
    <template #initialization><section v-if="can(['admin'])" class="panel" aria-label="管理员初始化"><h2>期初库存</h2><p>首次启用时，按盘点结果登记已有物料、库位、数量与单位成本。日常采购到货请使用库存页的“采购收货”。</p><el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" /><div class="toolbar"><el-button type="primary" :loading="openingBusy" @click="opening">期初入库</el-button><TransferTools resource="stocks" path="/business/stocks/" @changed="savedOpening = true" /></div><p v-if="savedOpening" role="status">期初库存已登记。<router-link to="/inventory?section=stocks">查看现有库存</router-link> · <router-link to="/inventory?section=moves&project=all">查看入库流水</router-link></p></section></template>
  </ModuleTabs>
  <ActionDialog :command="command" @close="command = null" @saved="saved" />
</template>
