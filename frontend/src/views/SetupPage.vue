<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { read, write } from '../api'
import { user, logout } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'
const router = useRouter()
const steps = ['管理员账号', '公司资料', '人员与兼岗', '编号规则', '确认启用']
const step = ref(0)
const loaded = ref(false)
const required = ref(true)
const busy = ref(false)
const error = ref('')
const confirmed = ref(false)
const heading = ref<HTMLElement>()
const repeatPassword = ref('')
const form = reactive({ display_name: user.value?.display_name || '', old_password: '', new_password: '', company: { name: '', address: '', phone: '' } })
const team = ref<Row[]>([])
const rules = ref<Row[]>([])
let originalRules: Row[] = []
const roleNames: Record<string, string> = { admin: '管理员', manager: '项目经理', sales_manager: '销售经理', purchaser: '采购员', warehouse: '仓管', finance: '财务', member: '成员' }
const codeNames: Record<string, string> = { project: '项目', sale: '销售单', purchase: '采购单', delivery: '交付单', item: '物料', partner: '往来单位', reconciliation: '对账单' }
const changedRules = computed(() => rules.value.filter((r, i) => ['prefix', 'date_format', 'padding', 'reset_cycle'].some(k => r[k] !== originalRules[i]?.[k])))
async function load() {
  error.value = ''
  try {
    const data = await read('/core/setup/')
    required.value = data.required
    if (user.value) user.value.setup_required = data.required
    Object.assign(form.company, data.company, { name: data.company.name === '我的公司' ? '' : data.company.name })
    rules.value = data.codes
    originalRules = structuredClone(data.codes)
    loaded.value = true
  } catch (e) { error.value = message(e) }
}
onMounted(load)
watch(step, async () => { await nextTick(); heading.value?.focus(); heading.value?.scrollIntoView({ block: 'start' }) })
function addMember() {
  team.value.push({ username: '', display_name: '', password: '', roles: ['member'], hourly_cost: '0.00', management_reports: false })
}
function next() {
  error.value = ''
  if (step.value === 0 && form.new_password !== repeatPassword.value) { error.value = '两次新密码不一致。'; return }
  if (step.value === 0 && form.new_password === form.old_password) { error.value = '新密码必须与初始密码不同。'; return }
  if (step.value === 2 && team.value.some(r => !r.roles.length)) { error.value = '每位人员至少选择一个岗位。'; return }
  step.value++
}
function example(rule: Row) {
  const now = new Date()
  const date = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
  return `${rule.prefix}${date.slice(0, rule.date_format.length)}${String(Number(rule.counter) + 1).padStart(Math.min(10, Math.max(1, Number(rule.padding))), '0')}`
}
async function finish() {
  error.value = ''
  busy.value = true
  try {
    await write('/core/setup/', { ...form, team: team.value, confirmed: confirmed.value, codes: changedRules.value.map(r => ({ id: r.id, prefix: r.prefix, date_format: r.date_format, padding: r.padding, reset_cycle: r.reset_cycle, expected_revision: r.revision, reason: '首次安装配置' })) }, crypto.randomUUID())
    required.value = false
    clearPasswords()
    await router.replace('/login?setup=complete')
    logout()
  } catch (e) { error.value = message(e) + ' 如遇连接中断，请重新登录确认是否已完成；未完成时可重新填写。' }
  finally { busy.value = false }
}
function clearPasswords() { form.old_password = ''; form.new_password = ''; repeatPassword.value = ''; team.value.forEach(r => { r.password = '' }) }
onBeforeRouteLeave(() => { clearPasswords() })
</script>
<template>
  <main class="setup-page">
    <header class="setup-heading"><div class="brand-mark">P</div><div><p class="muted">项目 ERP · 首次使用</p><h1>{{ required ? '快速安装向导' : '配置已就绪' }}</h1></div><el-button text @click="logout">退出登录</el-button></header>
    <el-alert v-if="error" :title="error" type="error" role="alert" :closable="false" />
    <section v-if="!loaded" class="panel"><p>正在读取安装状态…</p><el-button v-if="error" @click="load">重新加载</el-button></section>
    <template v-else-if="required">
      <p class="muted">完成下面五步即可启用。已有默认编号，不需要填写数据库等技术参数。</p>
      <ol class="setup-steps" aria-label="配置进度"><li v-for="(name, i) in steps" :key="name" :class="{ active: i === step, done: i < step }" :aria-current="i === step ? 'step' : undefined"><span>{{ i + 1 }}</span>{{ name }}</li></ol>
      <form class="panel setup-form" @submit.prevent="step < 4 ? next() : finish()">
        <h2 ref="heading" tabindex="-1">{{ steps[step] }}</h2>
        <fieldset :disabled="busy" class="setup-fields">
          <template v-if="step === 0">
            <p>当前账号：{{ user?.username }}。请将安装器生成的初始密码换成自己的密码。</p>
            <label class="field"><span>管理员姓名</span><input v-model="form.display_name" required maxlength="80" autocomplete="name" /></label>
            <label class="field"><span>初始密码</span><input v-model="form.old_password" required type="password" autocomplete="current-password" /></label>
            <label class="field"><span>新密码</span><input v-model="form.new_password" required type="password" minlength="12" autocomplete="new-password" /></label>
            <label class="field"><span>确认新密码</span><input v-model="repeatPassword" required type="password" minlength="12" autocomplete="new-password" /></label>
            <p class="muted">至少12位，避免常见密码和账号信息。填写内容仅保留在当前页面，刷新后密码需重新输入。</p>
          </template>
          <template v-else-if="step === 1">
            <p>这些资料将用于采购合同，请填写实际信息。</p>
            <label class="field"><span>公司名称</span><input v-model="form.company.name" required maxlength="150" autocomplete="organization" /></label>
            <label class="field"><span>公司地址</span><input v-model="form.company.address" required maxlength="250" autocomplete="street-address" /></label>
            <label class="field"><span>联系电话</span><input v-model="form.company.phone" required maxlength="50" autocomplete="tel" /></label>
          </template>
          <template v-else-if="step === 2">
            <p>管理员可直接开始使用。其他人员可现在添加，也可稍后在“设置 → 用户管理”添加；一人可以兼任多个岗位。</p>
            <section v-for="(person, i) in team" :key="i" class="setup-person">
              <h3>人员 {{ i + 1 }}</h3>
              <label class="field"><span>用户名</span><input v-model="person.username" required maxlength="150" autocomplete="off" /></label>
              <label class="field"><span>姓名</span><input v-model="person.display_name" required maxlength="80" autocomplete="off" /></label>
              <label class="field"><span>登录密码</span><input v-model="person.password" required type="password" minlength="12" autocomplete="new-password" /></label>
              <fieldset class="role-checks"><legend>岗位（可多选）</legend><label v-for="(name, role) in roleNames" :key="role"><input v-model="person.roles" type="checkbox" :value="role" @change="person.management_reports = person.roles.includes('manager') && person.management_reports" />{{ name }}</label></fieldset>
              <label v-if="person.roles.includes('manager')"><input v-model="person.management_reports" type="checkbox" />总经理经营报表授权</label>
              <label class="field"><span>小时成本（元）</span><input v-model="person.hourly_cost" required type="number" min="0" step="0.01" /></label>
              <el-button type="danger" plain @click="team.splice(i, 1)">移除此人员</el-button>
            </section>
            <el-button :disabled="team.length >= 50" @click="addMember">添加人员</el-button>
            <p class="muted">总经理报表权限默认关闭。本人申请仍执行审批隔离，兼岗不会取消该限制。</p>
          </template>
          <template v-else-if="step === 3">
            <p>直接使用默认规则即可。物料新增及导入也支持手填编码；实际合同编号在签约时填写。</p>
            <section v-for="rule in rules" :key="rule.id" class="setup-rule"><h3>{{ codeNames[rule.key] }}</h3>
              <div class="setup-grid">
                <label class="field"><span>{{ codeNames[rule.key] }}前缀</span><input v-model="rule.prefix" required pattern="[A-Za-z0-9_\-]{1,10}" maxlength="10" /></label>
                <label class="field"><span>日期格式</span><select v-model="rule.date_format"><option value="">无日期</option><option value="YYYY">年</option><option value="YYYYMM">年月</option><option value="YYYYMMDD">年月日</option></select></label>
                <label class="field"><span>流水位数</span><input v-model.number="rule.padding" type="number" min="1" max="10" required /></label>
                <label class="field"><span>重置周期</span><select v-model="rule.reset_cycle"><option value="never">不重置</option><option value="year">每年</option><option value="month">每月</option><option value="day">每天</option></select></label>
              </div><p class="muted">示例：{{ example(rule) }}（实际编号按服务器日期及已用流水生成）</p>
            </section>
          </template>
          <template v-else>
            <dl class="setup-summary"><dt>管理员</dt><dd>{{ user?.username }} · {{ form.display_name }}（使用新密码）</dd><dt>公司</dt><dd>{{ form.company.name }}<br />{{ form.company.address }}<br />{{ form.company.phone }}</dd><dt>新增人员</dt><dd>{{ team.length ? team.map(r => `${r.display_name}（${r.roles.map((s: string) => roleNames[s]).join('、')}）`).join('；') : '暂不添加，仅管理员开始使用' }}</dd><dt>编号</dt><dd>{{ changedRules.length ? `调整 ${changedRules.length} 项规则` : '使用默认编号规则' }}</dd></dl>
            <p>启用后可新增客户、物料并创建销售单。已有资料可从基础资料导入，不会自动生成示例订单或库存。</p>
            <label><input v-model="confirmed" type="checkbox" required />我已核对以上资料，确认启用</label>
          </template>
        </fieldset>
        <footer class="setup-actions"><el-button v-if="step > 0" :disabled="busy" @click="step--; error = ''">上一步</el-button><span>第 {{ step + 1 }} / 5 步</span><el-button type="primary" native-type="submit" :loading="busy">{{ step === 4 ? '完成配置并启用' : '下一步' }}</el-button></footer>
      </form>
    </template>
    <section v-else class="panel"><h2>开始使用 ERP</h2><p>账号、公司和编号已可使用。按业务需要补充资料后即可开单。</p><div class="setup-links"><router-link to="/masterdata?section=partners">1. 添加客户与供应商</router-link><router-link to="/masterdata?section=items">2. 添加或导入物料</router-link><router-link to="/settings?section=users">3. 维护人员与岗位</router-link><router-link to="/sales">4. 创建第一张销售单</router-link><router-link to="/workbench">进入工作台</router-link></div></section>
  </main>
</template>
<style scoped>
.setup-page { max-width: 960px; margin: 0 auto; padding: 32px 24px; }
.setup-heading { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.setup-heading h1, .setup-heading p { margin: 0 0 6px; }
.setup-heading > button { margin-left: auto; }
.setup-steps { display: flex; gap: 12px; list-style: none; padding: 0; margin: 24px 0; flex-wrap: wrap; }
.setup-steps li { display: flex; align-items: center; gap: 7px; color: #64748b; }
.setup-steps span { display: grid; place-items: center; border-radius: 50%; background: #e2e8f0; width: 28px; height: 28px; }
.setup-steps .active { color: #255ac2; font-weight: 700; }
.setup-steps .active span, .setup-steps .done span { background: #255ac2; color: white; }
.setup-fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.setup-fields > .field { max-width: 580px; }
.setup-person, .setup-rule { padding: 16px 0; border-bottom: 1px solid #e2e8f0; }
.setup-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.setup-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-top: 20px; margin-top: 20px; border-top: 1px solid #e2e8f0; }
.setup-summary dt { color: #64748b; margin-top: 16px; }
.setup-summary dd { margin: 6px 0; overflow-wrap: anywhere; }
.setup-links { display: grid; gap: 20px; padding: 12px 0; }
@media(max-width: 600px) { .setup-page { padding: 20px 12px; } .setup-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .setup-heading h1 { font-size: 24px; } .setup-steps { font-size: 12px; } }
</style>
