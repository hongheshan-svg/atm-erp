<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import StatusBadge from '../components/StatusBadge.vue'
import { can } from '../session'
import { message, requestKey } from '../utils/request'
import {
  CATEGORY_LABELS, STATE_LABELS, feedbackPage, getFeedbackSettings, listFeedback, saveFeedbackToken, submitFeedback,
  type FeedbackCategory, type FeedbackItem, type FeedbackState,
} from '../api/feedback'

const route = useRoute()
const admin = computed(() => can(['admin']))
const enabled = ref(false)
const issuesUrl = ref('https://github.com/hongheshan-svg/atm-erp/issues')
const items = ref<FeedbackItem[]>([])
const loading = ref(false)
const loadError = ref('')
const onlyMine = ref(false)
const shown = computed(() => (onlyMine.value ? items.value.filter(item => item.mine) : items.value))

const single = (value: unknown) => (typeof value === 'string' ? value : '')
const blank = () => ({
  category: 'bug' as FeedbackCategory,
  title: '',
  description: '',
  steps: '',
  page: feedbackPage(single(route.query.from)),
  request_id: single(route.query.request_id).slice(0, 64),
})
const draft = ref(blank())
const submitKey = ref(requestKey())
const submitting = ref(false)
const submitError = ref('')
const submitted = ref<FeedbackItem | null>(null)
const canSubmit = computed(() => enabled.value && !submitting.value && !!draft.value.title.trim() && !!draft.value.description.trim())

const configured = ref(false)
const token = ref('')
const tokenKey = ref(requestKey())
const saving = ref(false)
const settingsError = ref('')
const settingsNotice = ref('')

const tones: Record<FeedbackState, string> = { open: 'open', completed: 'done', not_planned: 'cancelled' }
function dateText(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const result = await listFeedback()
    enabled.value = result.enabled
    issuesUrl.value = result.issues_url || issuesUrl.value
    items.value = result.results
  } catch (e) {
    loadError.value = message(e)
  } finally {
    loading.value = false
  }
}
async function loadSettings() {
  if (!admin.value) return
  try { configured.value = (await getFeedbackSettings()).configured }
  catch (e) { settingsError.value = message(e) }
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  submitError.value = ''
  submitted.value = null
  try {
    const client = `${navigator.userAgent.slice(0, 240)} · ${window.innerWidth}×${window.innerHeight}`
    submitted.value = await submitFeedback({ ...draft.value, client }, submitKey.value)
    draft.value = { ...blank(), page: '', request_id: '' }
    submitKey.value = requestKey()
    await load()
  } catch (e) {
    // 保留已填内容和同一操作标识：重试不会在 GitHub 上建出第二个相同的 issue。
    submitError.value = message(e)
  } finally {
    submitting.value = false
  }
}

async function saveToken(clear = false) {
  if (saving.value || (!clear && !token.value.trim())) return
  saving.value = true
  settingsError.value = ''
  settingsNotice.value = ''
  try {
    const result = await saveFeedbackToken(clear ? '' : token.value.trim(), tokenKey.value)
    configured.value = result.configured
    settingsNotice.value = result.configured ? '已保存，员工现在可以提交问题。' : '已停用问题反馈。'
    token.value = ''
    tokenKey.value = requestKey()
    await load()
  } catch (e) {
    settingsError.value = message(e)
  } finally {
    saving.value = false
  }
}

onMounted(() => { void load(); void loadSettings() })
</script>
<template>
  <header class="page-heading">
    <div>
      <h1>问题反馈</h1>
      <p class="muted">遇到错误或有改进建议，在这里提交；提交后在 GitHub 公开登记，处理进度会同步回这里。</p>
    </div>
    <a :href="issuesUrl" target="_blank" rel="noopener noreferrer">在 GitHub 查看全部</a>
  </header>

  <section class="panel feedback-form" aria-label="提交问题">
    <h2>提交问题</h2>
    <el-alert
      v-if="!loading && !loadError && !enabled"
      type="warning"
      :closable="false"
      :title="admin ? '尚未配置 GitHub 连接，请先在页面下方填写令牌。' : '管理员尚未配置 GitHub 连接，暂时无法提交，请联系管理员。'"
    />
    <el-alert type="info" :closable="false" title="提交内容会公开显示在 GitHub，任何人都能看到。">
      请勿填写客户名称、金额、联系方式、账号或密码等敏感信息；你的姓名不会公开，只记录在本系统的操作审计里。
    </el-alert>
    <form @submit.prevent="submit">
      <div class="fields">
        <div class="field">
          <label for="feedback-category">问题类型</label>
          <select id="feedback-category" v-model="draft.category">
            <option v-for="(label, value) in CATEGORY_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <div class="field field-wide">
          <label for="feedback-title">标题</label>
          <input id="feedback-title" v-model="draft.title" maxlength="80" required autocomplete="off" placeholder="一句话说明问题，如：采购收货后库存数量没有增加" />
        </div>
        <div class="field field-wide">
          <label for="feedback-description">问题描述</label>
          <textarea id="feedback-description" v-model="draft.description" rows="5" maxlength="5000" required placeholder="发生了什么？在哪个页面、点了哪个按钮、看到什么提示。" />
        </div>
        <div class="field field-wide">
          <label for="feedback-steps">复现步骤与期望结果<small>（选填）</small></label>
          <textarea id="feedback-steps" v-model="draft.steps" rows="3" maxlength="3000" placeholder="1. 打开…  2. 点击…  期望看到…，实际看到…" />
        </div>
        <div class="field">
          <label for="feedback-page">相关页面<small>（选填）</small></label>
          <input id="feedback-page" v-model="draft.page" maxlength="200" autocomplete="off" placeholder="/purchases" />
        </div>
        <div class="field">
          <label for="feedback-request-id">错误编号<small>（选填）</small></label>
          <input id="feedback-request-id" v-model="draft.request_id" maxlength="64" autocomplete="off" placeholder="错误提示里的“错误编号”" />
        </div>
      </div>
      <el-alert v-if="submitError" type="error" :closable="false" role="alert" :title="submitError" />
      <p v-if="submitted" role="status" class="feedback-done">
        已提交为 <a :href="submitted.issue_url" target="_blank" rel="noopener noreferrer">#{{ submitted.issue_number }}</a>，处理进度会显示在下方列表。
      </p>
      <el-button type="primary" native-type="submit" :loading="submitting" :disabled="!canSubmit">提交</el-button>
    </form>
  </section>

  <section class="panel" aria-label="已提交的问题">
    <div class="panel-heading">
      <h2>已提交的问题</h2>
      <label class="feedback-mine"><input v-model="onlyMine" type="checkbox" /> 只看我提交的</label>
    </div>
    <el-alert v-if="loadError" type="error" :closable="false" role="alert" :title="loadError" />
    <p v-else-if="loading && !items.length" class="muted">正在加载…</p>
    <p v-else-if="!shown.length" class="muted">{{ onlyMine ? '你还没有提交过问题。' : '还没有人提交问题。' }}</p>
    <ul v-else class="feedback-list">
      <li v-for="item in shown" :key="item.id">
        <div class="feedback-title">
          <a :href="item.issue_url" target="_blank" rel="noopener noreferrer">#{{ item.issue_number }}</a>
          <span>{{ item.title }}</span>
        </div>
        <div class="feedback-info">
          <StatusBadge :value="tones[item.state] || item.state" :text="STATE_LABELS[item.state] || item.state" />
          <span class="muted">{{ CATEGORY_LABELS[item.category] || item.category }} · {{ item.submitter }} · {{ dateText(item.created_at) }}</span>
        </div>
      </li>
    </ul>
  </section>

  <section v-if="admin" class="panel" aria-label="GitHub 连接">
    <h2>GitHub 连接</h2>
    <p>
      当前状态：<strong>{{ configured ? '已配置' : '未配置' }}</strong>。令牌只保存在服务器，保存后不再显示。
    </p>
    <ol class="muted feedback-help">
      <li>在 GitHub 打开 Settings → Developer settings → Fine-grained tokens，新建令牌。</li>
      <li>Repository access 只选 hongheshan-svg/atm-erp；Repository permissions 只给 Issues：Read and write。</li>
      <li>把生成的 github_pat_… 粘贴到下面保存；令牌过期后在这里换新的。</li>
    </ol>
    <el-alert v-if="settingsError" type="error" :closable="false" role="alert" :title="settingsError" />
    <p v-if="settingsNotice" role="status">{{ settingsNotice }}</p>
    <div class="toolbar">
      <input v-model="token" type="password" autocomplete="off" placeholder="github_pat_…" aria-label="GitHub 令牌" class="feedback-token" />
      <el-button type="primary" :loading="saving" :disabled="!token.trim()" @click="saveToken()">保存令牌</el-button>
      <el-button v-if="configured" :disabled="saving" @click="saveToken(true)">停用</el-button>
    </div>
  </section>
</template>
<style scoped>
.feedback-form .el-alert { margin-bottom: 14px; }
.feedback-form .fields { margin-bottom: 14px; }
.feedback-done { margin: 0 0 12px; }
.feedback-mine { display: inline-flex; align-items: center; gap: 6px; }
.feedback-list { list-style: none; margin: 0; padding: 0; }
.feedback-list li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 16px; padding: 12px 0; border-bottom: 1px solid var(--line-2); }
.feedback-list li:last-child { border-bottom: 0; }
.feedback-title { display: flex; gap: 8px; min-width: 0; overflow-wrap: anywhere; }
.feedback-info { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.feedback-help { padding-left: 20px; line-height: 1.8; }
.feedback-token { flex: 1 1 260px; max-width: 420px; }
</style>
