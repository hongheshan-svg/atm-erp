<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import StatusBadge from '../components/StatusBadge.vue'
import { can } from '../session'
import { message, requestKey } from '../utils/request'
import {
  CATEGORY_LABELS, DEFAULT_LIMITS, FILE_TYPES, FREQUENCY_LABELS, IMAGE_TYPES, IMPACT_LABELS, STATE_LABELS,
  checkFiles, extension, feedbackPage, getFeedbackSettings, listFeedback, saveFeedbackToken, submitFeedback,
  type FeedbackCategory, type FeedbackFrequency, type FeedbackImpact, type FeedbackItem, type FeedbackLimits,
  type FeedbackSettings, type FeedbackState,
} from '../api/feedback'

const route = useRoute()
const admin = computed(() => can(['admin']))
const enabled = ref(false)
const limits = ref<FeedbackLimits>(DEFAULT_LIMITS)
const issuesUrl = ref('https://github.com/hongheshan-svg/atm-erp-feedback/issues')
const items = ref<FeedbackItem[]>([])
const loading = ref(false)
const loadError = ref('')
const onlyMine = ref(false)
const shown = computed(() => (onlyMine.value ? items.value.filter(item => item.mine) : items.value))

const single = (value: unknown) => (typeof value === 'string' ? value : '')
const blank = () => ({
  category: 'bug' as FeedbackCategory,
  impact: '' as FeedbackImpact,
  frequency: '' as FeedbackFrequency,
  title: '',
  description: '',
  steps: '',
  expected: '',
  page: feedbackPage(single(route.query.from)),
  request_id: single(route.query.request_id).slice(0, 64),
})
const draft = ref(blank())
const submitKey = ref(requestKey())
const submitting = ref(false)
const submitError = ref('')
const submitted = ref<FeedbackItem | null>(null)

type Picked = { file: File; preview: string }
const picked = ref<Picked[]>([])
const fileError = ref('')
const dragging = ref(false)
const accept = FILE_TYPES.join(',')
const canSubmit = computed(() =>
  enabled.value && !submitting.value && !!draft.value.title.trim() && !!draft.value.description.trim(),
)

const settings = ref<FeedbackSettings>({ configured: false, repository: 'hongheshan-svg/atm-erp-feedback' })
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
function sizeText(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const result = await listFeedback()
    enabled.value = result.enabled
    limits.value = result.limits || DEFAULT_LIMITS
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
  try { settings.value = await getFeedbackSettings() }
  catch (e) { settingsError.value = message(e) }
}

function addFiles(files: File[]) {
  if (!files.length || !enabled.value) return
  fileError.value = checkFiles([...picked.value.map(item => item.file), ...files], limits.value)
  if (fileError.value) return
  picked.value.push(...files.map(file => ({ file, preview: IMAGE_TYPES.includes(extension(file.name)) ? URL.createObjectURL(file) : '' })))
}
function removeFile(index: number) {
  const [item] = picked.value.splice(index, 1)
  if (item?.preview) URL.revokeObjectURL(item.preview)
  fileError.value = ''
}
function clearFiles() {
  for (const item of picked.value) if (item.preview) URL.revokeObjectURL(item.preview)
  picked.value = []
}
function choose(event: Event) {
  const input = event.target as HTMLInputElement
  addFiles([...(input.files ?? [])])
  input.value = ''
}
function drop(event: DragEvent) {
  dragging.value = false
  addFiles([...(event.dataTransfer?.files ?? [])])
}
// 在表单里按 Ctrl+V 粘贴截图；粘贴文字不受影响。
function paste(event: ClipboardEvent) {
  const images = [...(event.clipboardData?.files ?? [])].filter(file => file.type.startsWith('image/'))
  if (!images.length) return
  event.preventDefault()
  const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14)
  addFiles(images.map((file, index) => {
    const type = file.type === 'image/jpeg' ? 'jpg' : file.type.slice(6)
    return new File([file], `截图-${stamp}${images.length > 1 ? `-${index + 1}` : ''}.${type}`, { type: file.type })
  }))
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  submitError.value = ''
  submitted.value = null
  try {
    const client = `${navigator.userAgent.slice(0, 240)} · ${window.innerWidth}×${window.innerHeight}`
    submitted.value = await submitFeedback({ ...draft.value, client }, picked.value.map(item => item.file), submitKey.value)
    draft.value = { ...blank(), page: '', request_id: '' }
    clearFiles()
    submitKey.value = requestKey()
    await load()
  } catch (e) {
    // 保留已填内容、附件和同一操作标识：重试不会在 GitHub 上建出第二个相同的 issue。
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
    settings.value = await saveFeedbackToken(clear ? '' : token.value.trim(), tokenKey.value)
    settingsNotice.value = clear ? '已停用 GitHub 连接。' : '令牌已保存。'
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
onBeforeUnmount(clearFiles)
</script>
<template>
  <header class="page-heading">
    <div>
      <h1>问题反馈</h1>
      <p class="muted">遇到错误或有改进建议，在这里提交；提交后登记到维护者的私有 GitHub 仓库，处理进度会同步回这里。</p>
    </div>
    <a v-if="admin" :href="issuesUrl" target="_blank" rel="noopener noreferrer">在 GitHub 查看全部</a>
  </header>

  <section class="panel feedback-form" aria-label="提交问题" @paste="paste">
    <h2>提交问题</h2>
    <el-alert
      v-if="!loading && !loadError && !enabled"
      type="warning"
      :closable="false"
      :title="admin ? '尚未配置 GitHub 连接，请先在页面下方填写令牌。' : '管理员尚未配置 GitHub 连接，暂时无法提交，请联系管理员。'"
    />
    <el-alert type="info" :closable="false" title="提交的文字、截图和文件保存在私有 GitHub 仓库，只有系统维护者能看到。">
      不要填写或截入账号、密码；与问题无关的客户名称、金额、联系方式尽量不填或遮挡。你的姓名不会写进 GitHub，只记录在本系统的操作审计里。
    </el-alert>
    <form @submit.prevent="submit">
      <div class="fields">
        <div class="field">
          <label for="feedback-category">问题类型</label>
          <select id="feedback-category" v-model="draft.category">
            <option v-for="(label, value) in CATEGORY_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <div class="field">
          <label for="feedback-impact">影响程度<small>（选填）</small></label>
          <select id="feedback-impact" v-model="draft.impact">
            <option value="">请选择</option>
            <option v-for="(label, value) in IMPACT_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <div class="field">
          <label for="feedback-frequency">出现频率<small>（选填）</small></label>
          <select id="feedback-frequency" v-model="draft.frequency">
            <option value="">请选择</option>
            <option v-for="(label, value) in FREQUENCY_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <div class="field field-wide">
          <label for="feedback-title">标题</label>
          <input id="feedback-title" v-model="draft.title" maxlength="80" required autocomplete="off" placeholder="一句话说明问题，如：采购收货后库存数量没有增加" />
        </div>
        <div class="field field-wide">
          <label for="feedback-description">问题描述</label>
          <textarea id="feedback-description" v-model="draft.description" rows="5" maxlength="5000" required placeholder="发生了什么？在哪个页面、点了哪个按钮、看到什么提示，实际结果是什么。" />
        </div>
        <div class="field field-wide">
          <label for="feedback-steps">操作步骤<small>（选填）</small></label>
          <textarea id="feedback-steps" v-model="draft.steps" rows="3" maxlength="3000" placeholder="1. 打开…  2. 选择…  3. 点击…" />
        </div>
        <div class="field field-wide">
          <label for="feedback-expected">期望结果<small>（选填）</small></label>
          <textarea id="feedback-expected" v-model="draft.expected" rows="2" maxlength="2000" placeholder="正常情况下应该看到什么。" />
        </div>
        <div class="field">
          <label for="feedback-page">相关页面<small>（选填）</small></label>
          <input id="feedback-page" v-model="draft.page" maxlength="200" autocomplete="off" placeholder="/purchases" />
        </div>
        <div class="field">
          <label for="feedback-request-id">错误编号<small>（选填）</small></label>
          <input id="feedback-request-id" v-model="draft.request_id" maxlength="64" autocomplete="off" placeholder="错误提示里的“错误编号”" />
        </div>
        <div class="field field-wide">
          <label for="feedback-files">截图与附件<small>（选填）</small></label>
          <div class="feedback-drop" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="drop">
            <input id="feedback-files" type="file" multiple :accept="accept" :disabled="!enabled" @change="choose" />
            <small>可选择或拖入文件，也可在本表单内按 Ctrl+V 粘贴截图。最多 {{ limits.files }} 个，单个不超过 {{ limits.file_mb }} MB，合计不超过 {{ limits.total_mb }} MB；支持图片、PDF、Excel、Word、文本和 mp4/mov 录屏。</small>
          </div>
          <small v-if="fileError" class="field-error" role="alert">{{ fileError }}</small>
          <ul v-if="picked.length" class="feedback-files" aria-label="已选附件">
            <li v-for="(item, index) in picked" :key="index">
              <img v-if="item.preview" :src="item.preview" alt="" />
              <span class="feedback-file-name">{{ item.file.name }}</span>
              <small>{{ sizeText(item.file.size) }}</small>
              <el-button text :aria-label="`移除 ${item.file.name}`" @click="removeFile(index)">移除</el-button>
            </li>
          </ul>
        </div>
      </div>
      <el-alert v-if="submitError" type="error" :closable="false" role="alert" :title="submitError" />
      <p v-if="submitted" role="status" class="feedback-done">
        已提交为 <a v-if="admin" :href="submitted.issue_url" target="_blank" rel="noopener noreferrer">#{{ submitted.issue_number }}</a><template v-else>#{{ submitted.issue_number }}</template>，处理进度会显示在下方列表。
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
          <a v-if="admin" :href="item.issue_url" target="_blank" rel="noopener noreferrer">#{{ item.issue_number }}</a>
          <span v-else class="muted">#{{ item.issue_number }}</span>
          <span>{{ item.title }}</span>
        </div>
        <div class="feedback-info">
          <StatusBadge :value="tones[item.state] || item.state" :text="STATE_LABELS[item.state] || item.state" />
          <span class="muted">{{ CATEGORY_LABELS[item.category] || item.category }} · {{ item.submitter }} · {{ dateText(item.created_at) }}</span>
        </div>
        <div v-if="item.attachments?.length" class="feedback-attachments">
          附件：<template v-if="admin"><a v-for="file in item.attachments" :key="file.url" :href="file.url" target="_blank" rel="noopener noreferrer">{{ file.name }}</a></template>
          <template v-else><span v-for="file in item.attachments" :key="file.url">{{ file.name }}</span></template>
        </div>
      </li>
    </ul>
  </section>

  <section v-if="admin" class="panel" aria-label="GitHub 连接">
    <h2>GitHub 连接</h2>
    <p class="muted">问题和附件都存放在私有仓库 {{ settings.repository }}，只有维护者能看到。令牌只保存在服务器，保存后不再显示。</p>
    <ol class="muted feedback-help">
      <li>在 GitHub 打开 Settings → Developer settings → Fine-grained tokens，新建令牌。</li>
      <li>Repository access 只选 {{ settings.repository }}；Repository permissions 只给 Issues：Read and write 和 Contents：Read and write。</li>
      <li>把生成的 github_pat_… 粘贴到下面保存；令牌过期后在这里换新的。</li>
    </ol>
    <el-alert v-if="settingsError" type="error" :closable="false" role="alert" :title="settingsError" />
    <p v-if="settingsNotice" role="status">{{ settingsNotice }}</p>
    <div class="toolbar feedback-token-row">
      <span class="muted">{{ settings.configured ? '已配置' : '未配置' }}</span>
      <input v-model="token" type="password" autocomplete="off" placeholder="github_pat_…" aria-label="GitHub 令牌" class="feedback-token" />
      <el-button type="primary" :loading="saving" :disabled="saving || !token.trim()" @click="saveToken()">保存</el-button>
      <el-button v-if="settings.configured" :disabled="saving" @click="saveToken(true)">停用</el-button>
    </div>
  </section>
</template>
<style scoped>
.feedback-form .el-alert { margin-bottom: 14px; }
.feedback-form .fields { margin-bottom: 14px; }
.feedback-drop { display: grid; gap: 6px; padding: 12px; border: 1px dashed var(--check-line, #c9d2e0); border-radius: 8px; }
.feedback-drop.dragging { border-color: var(--brand); background: var(--brand-wash); }
.feedback-files { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 6px; }
.feedback-files li { display: flex; align-items: center; gap: 10px; min-width: 0; }
.feedback-files img { width: 56px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid var(--line-2); flex: none; }
.feedback-file-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feedback-done { margin: 0 0 12px; }
.feedback-mine { display: inline-flex; align-items: center; gap: 6px; }
.feedback-list { list-style: none; margin: 0; padding: 0; }
.feedback-list li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 16px; padding: 12px 0; border-bottom: 1px solid var(--line-2); }
.feedback-list li:last-child { border-bottom: 0; }
.feedback-title { display: flex; gap: 8px; min-width: 0; overflow-wrap: anywhere; }
.feedback-info { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.feedback-attachments { flex-basis: 100%; display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; overflow-wrap: anywhere; }
.feedback-help { padding-left: 20px; line-height: 1.8; }
.feedback-token-row { align-items: center; flex-wrap: wrap; }
.feedback-token { flex: 1 1 240px; max-width: 420px; }
</style>
