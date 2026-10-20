<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { matchedRouteKey, onBeforeRouteLeave, onBeforeRouteUpdate, routerKey } from 'vue-router'
import { user } from '../session'
import { clearDraft, draftKey, formSignature, loadDraft, saveDraft, registerFormGuard, submitLabel, wideCommand } from '../form-experience'
import { ElDialog, ElMessage, ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import type { Command, Row } from '../types'
import { defaults, fieldIssues, payload, validateFields, type FieldIssue } from '../forms'
import { industryCommand } from '../industry-forms'
import { read, write } from '../api'
import { message, recoveryActions, requestKey } from '../utils/request'
import FormFields from './FormFields.vue'
import StatusBadge from './StatusBadge.vue'
import ProcessSteps from './ProcessSteps.vue'
const props = defineProps<{ command: Command | null; inline?: boolean }>()
const command = computed(() => props.command ? industryCommand(props.command) : null)
const emit = defineEmits<{ close: []; saved: [result: Row]; busy: [value: boolean]; replace: [command: Command] }>()
const data = ref<Row>({})
const busy = ref(false), uploading = ref(false)
const locked = computed(() => busy.value || uploading.value)
watch(locked, value => emit('busy', value))
const wide = computed(() => wideCommand(command.value))
const fields = ref<{ focusPath: (path: string) => Promise<void> }>()
const attempted = ref(false), touched = ref<Set<string>>(new Set())
const serverIssues = ref<FieldIssue[]>([])
const issues = computed(() => command.value ? [...fieldIssues(command.value.fields, data.value).filter(issue => attempted.value || touched.value.has(issue.path)), ...serverIssues.value] : [])
const issueMap = computed(() => Object.fromEntries(issues.value.map(issue => [issue.path, issue.message])))
const baseline = ref(''), restored = ref<Row | null>(null)
const dirty = computed(() => !!command.value && !command.value.readonly && baseline.value !== formSignature(data.value))
const currentDraftKey = computed(() => command.value ? draftKey(command.value, user.value?.id) : '')
const router = inject(routerKey, undefined)
let draftTimer: ReturnType<typeof setTimeout> | undefined
function rememberDraft() { return command.value && dirty.value ? saveDraft(currentDraftKey.value, command.value, data.value) : true }
watch(data, () => {
  serverIssues.value = []
  clearTimeout(draftTimer)
  if (dirty.value) draftTimer = setTimeout(rememberDraft, 350)
}, { deep: true })
function touch(path: string) { touched.value = new Set([...touched.value, path]) }
async function confirmLeave(keep = true) {
  if (!command.value) return true
  if (locked.value) return false
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm(keep && currentDraftKey.value ? '填写内容尚未提交。离开前可以暂存，返回后继续填写。' : '填写内容尚未保存，放弃后需要重新填写。', '内容尚未保存', {
      confirmButtonText: keep && currentDraftKey.value ? '暂存并离开' : '放弃修改', cancelButtonText: '继续填写', type: 'warning', closeOnClickModal: false,
    })
    clearTimeout(draftTimer)
    if (keep && currentDraftKey.value) { if (!rememberDraft()) { ElMessage.error('浏览器未能暂存，请保留此页面或提交后再离开。'); return false } }
    else clearDraft(currentDraftKey.value)
    baseline.value = formSignature(data.value)
    return true
  } catch { return false }
}
async function openAlternative(open: () => Promise<Command>) {
  if (!(await confirmLeave())) return
  busy.value = true
  try { emit('replace', await open()) } catch (e) { error.value = message(e) } finally { busy.value = false }
}
async function requestClose() { if (await confirmLeave(false)) emit('close') }
function keepAndClose() {
  if (!rememberDraft()) { ElMessage.error('浏览器未能暂存，请保留此页面或提交后再关闭。'); return }
  baseline.value = formSignature(data.value); emit('close')
  ElMessage.success('填写内容已暂存，返回此操作可继续填写。')
}
function restore() {
  if (!restored.value || !command.value) return
  data.value = defaults(command.value.fields, { ...data.value, ...restored.value }); restored.value = null
}
function discardDraft() { clearDraft(currentDraftKey.value); restored.value = null }
function beforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value && !locked.value) return
  rememberDraft(); event.preventDefault(); event.returnValue = ''
}
if (inject(matchedRouteKey, undefined)) { onBeforeRouteLeave(() => confirmLeave()); onBeforeRouteUpdate(() => confirmLeave()) }
const unregisterGuard = registerFormGuard(() => confirmLeave())
defineExpose({ confirmLeave })
async function follow(path: string) { if (await confirmLeave()) { emit('close'); await router?.push(path) } }
function mapServerIssues(error: unknown) {
  const response = (error as { response?: { data?: Row } })?.response?.data
  if (!response || !command.value) return
  serverIssues.value = command.value.fields.filter(field => response[field.key] != null).map(field => ({ path: field.key, label: field.label, message: `${field.label}：${message(response[field.key])}` }))
}
const panelHeading = ref<HTMLElement>()
const panelHeight = ref('calc(100dvh - 36px)')
function fitPanel() {
  const panel = panelHeading.value?.parentElement?.parentElement
  if (props.inline && panel) panelHeight.value = `${Math.max(280, window.innerHeight - Math.max(18, panel.getBoundingClientRect().top) - 18)}px`
}
onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  window.addEventListener('resize', fitPanel)
  window.addEventListener('scroll', fitPanel, true)
})
onBeforeUnmount(() => {
  unregisterGuard()
  clearTimeout(draftTimer)
  rememberDraft()
  window.removeEventListener('beforeunload', beforeUnload)
  window.removeEventListener('resize', fitPanel)
  window.removeEventListener('scroll', fitPanel, true)
})
let returnFocus: HTMLElement | null = null
watch(() => props.command, async (value, old) => {
  if (!props.inline) return
  if (value) {
    if (!old) returnFocus = document.activeElement as HTMLElement
    await nextTick()
    const panel = panelHeading.value?.parentElement?.parentElement
    if (panel && panel.getBoundingClientRect().top > window.innerHeight - 360) panel.scrollIntoView({ block: 'start' })
    fitPanel()
    panelHeading.value?.focus({ preventScroll: true })
  } else if (returnFocus?.isConnected) returnFocus.focus()
})
const error = ref('')
const recovery = ref<{ label: string; path: string }[]>([])
const preview = ref<Row | null>(null)
const primary = computed(() => ['签约', '收货', '批准采购', '登记收付款', '领料', '完成任务', '提交采购'].find(label => command.value?.actions?.some(action => action.label === label)))
const similarItems = ref<Row[]>([])
watch(() => [props.command?.path, data.value.name], async (_, __, onCleanup) => {
  similarItems.value = []
  if (!props.command?.path.startsWith('/business/items/') || !data.value.name) return
  let active = true
  const timer = setTimeout(async () => {
    try {
      const items = await read('/business/items/similar/', { name: data.value.name })
      if (active) similarItems.value = items.filter((item: Row) => item.id !== props.command?.initial?.id)
    } catch { /* Suggestions are optional; saving still validates duplicates on the server. */ }
  }, 300)
  onCleanup(() => { active = false; clearTimeout(timer) })
})
const roleChange = computed(() => {
  const field = props.command?.fields.find(f => f.key === 'roles' && f.type === 'checks')
  if (!field) return ''
  const before: string[] = props.command?.initial?.roles ?? (props.command?.initial?.role ? [props.command.initial.role] : [])
  const after: string[] = data.value.roles ?? []
  const names = (values: string[]) => values.map(v => field.options?.find(o => o.value === v)?.label || v).join('、') || '无'
  return `新增：${names(after.filter(v => !before.includes(v)))}；移除：${names(before.filter(v => !after.includes(v)))}。保存后按新岗位授权；管理员可管理全系统，财务可读取金额并记账，采购/仓管可跨项目作业，项目经理限负责或参与项目，销售经理限本人销售。机械/电气工程师与生产经理限参与项目，生产经理负责生产及售后派工，不获得成本或财务权限。移除岗位不会删除原业务记录。`
})
async function previewChange() {
  const c = command.value
  if (!c?.previewPath || busy.value) return
  busy.value = true
  error.value = ''
  try {
    validateFields(c.fields, data.value)
    const body = payload(c.fields, data.value)
    preview.value = await write(c.previewPath, c.prepare ? c.prepare(body) : body, requestKey())
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
const fieldsContainer = ref<HTMLElement>()
let key = ''
let signature = ''
watch(
  () => command.value,
  (c) => {
    if (c) {
      clearTimeout(draftTimer)
      attempted.value = false; touched.value = new Set(); serverIssues.value = []
      preview.value = null
      data.value = defaults(c.fields, JSON.parse(JSON.stringify(c.initial || {})))
      baseline.value = formSignature(data.value)
      restored.value = loadDraft(draftKey(c, user.value?.id), c)
      error.value = ''
      recovery.value = []
      key = requestKey()
      signature = ''
    }
  },
  { immediate: true },
)
async function submit() {
  const c = command.value
  if (!c || c.readonly || locked.value || c.blocked) return
  busy.value = true
  error.value = ''
  recovery.value = []
  try {
    attempted.value = true
    serverIssues.value = []
    serverIssues.value = Array.from(fieldsContainer.value?.querySelectorAll<HTMLInputElement>('input,select,textarea') || []).filter(input => input.validity?.customError).map(input => ({ path: input.closest<HTMLElement>('[data-field-path]')?.dataset.fieldPath || '', label: input.getAttribute('aria-label') || '', message: input.validationMessage })).filter(issue => issue.path)
    if (fieldIssues(c.fields, data.value).length || serverIssues.value.length) {
      await nextTick(); if (fieldsContainer.value) fieldsContainer.value.scrollTop = 0
      return
    }
    let body = payload(c.fields, data.value)
    if (roleChange.value && !data.value.roles?.length) throw new Error('至少选择一个角色。')
    if (c.prepare) body = c.prepare(body)
    const next = JSON.stringify(body, (_k, v) => (v instanceof File ? [v.name, v.size, v.lastModified] : v))
    if (signature && signature !== next) key = requestKey()
    signature = next
    let upload: FormData | undefined
    if (Object.values(body).some((v) => v instanceof File)) {
      upload = new FormData()
      for (const [k, v] of Object.entries(body)) upload.append(k, v instanceof File ? v : String(v))
    }
    const result = await write(c.path, upload || body, key, c.method)
    clearTimeout(draftTimer); clearDraft(currentDraftKey.value)
    baseline.value = formSignature(data.value)
    emit('saved', result)
    emit('close')
    ElMessage.success(`${c.title}成功${result?.code ? ` · ${result.code}` : ''}`)
  } catch (e) {
    error.value = message(e)
    mapServerIssues(e)
    recovery.value = recoveryActions(e)
    await nextTick()
    if (fieldsContainer.value) fieldsContainer.value.scrollTop = 0
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <component
    :is="inline ? 'section' : ElDialog"
    v-if="!inline || command"
    :class="[inline ? 'detail-pane' : 'action-dialog', { 'wide-action': wide }]"
    :style="inline ? { maxHeight: panelHeight } : undefined"
    :role="inline ? 'dialog' : undefined"
    :aria-modal="inline ? 'false' : undefined"
    :aria-label="command?.title"
    :model-value="Boolean(command)"
    :title="command?.title"
    :width="wide ? 'min(1080px, 96vw)' : 'min(760px, 94vw)'"
    append-to-body
    :close-on-click-modal="false"
    :before-close="requestClose"
    destroy-on-close
  >
    <header v-if="inline" class="detail-pane-heading"><h2 ref="panelHeading" tabindex="-1">{{ command?.title }}</h2><el-button :icon="Close" text :disabled="locked" aria-label="关闭详情" @click="requestClose" /></header>
    <form v-if="command" class="action-form" novalidate @submit.prevent="submit">
      <div ref="fieldsContainer" class="action-fields">
      <div v-if="command.subject" class="record-headline"><strong>{{ command.subject }}</strong><StatusBadge v-if="command.initial?.status" :value="command.initial.status" /></div>
      <details v-if="command.flow" class="compact-flow"><summary>{{ command.flow.label }} · {{ command.flow.nodes[command.flow.current]?.label || command.flow.aborted?.label }} · 查看完整流程</summary><ProcessSteps class="record-flow" :flow="command.flow" /></details>
      <el-alert v-if="command.notice" :title="command.notice.text" :type="command.notice.type" :closable="false" show-icon />
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
      <p v-for="action in recovery" :key="action.path"><el-button link @click="follow(action.path)">{{ action.label }}</el-button></p>
      <section v-if="restored" class="draft-notice" aria-label="未提交的填写内容"><span>发现之前暂存的填写内容（附件需重新选择）。</span><el-button @click="restore">恢复填写</el-button><el-button text @click="discardDraft">删除暂存</el-button></section>
      <section v-if="command.blocked" class="action-blocker" role="status"><strong>先完成以下事项</strong><p>{{ command.blocked }}</p></section>
      <p v-for="link in command.links" :key="link.path"><el-button @click="follow(link.path)">{{ link.label }}</el-button></p>
      <section v-if="issues.length" class="field-issues" aria-label="填写问题汇总" role="alert"><strong>请修正以下 {{ issues.length }} 项，其他填写内容已保留：</strong><ul><li v-for="issue in issues" :key="issue.path"><button type="button" @click="fields?.focusPath(issue.path)">{{ issue.message }}</button></li></ul></section>
      <FormFields v-if="!command.blocked" ref="fields" v-model="data" :fields="command.fields" :disabled="locked || command.readonly" :readonly="command.readonly" :issues="issueMap" @touched="touch" @uploading="uploading = $event" />
      <slot v-if="command.readonly" name="context" />
      <section v-if="similarItems.length" aria-label="相似物料">
        <p>发现相似物料，请核对后优先复用现有编码：</p>
        <p v-for="item in similarItems" :key="item.id"><router-link :to="{ path: '/masterdata', query: { section: 'items', resource: 'items', focus: item.id } }">{{ item.code }} · {{ item.name }} · {{ item.specification }} · {{ item.brand }} · {{ item.unit }}</router-link></p>
      </section>
      <el-alert v-if="roleChange" :title="roleChange" type="warning" :closable="false" role="status" />
      <section v-if="preview" aria-label="变更影响预览">
        <el-alert :title="preview.can_apply ? '本次预览可通过；保存时仍会重新校验。' : preview.blockers.join('；')" :type="preview.can_apply ? 'info' : 'warning'" :closable="false" />
        <el-table :data="preview.items" max-height="300"><el-table-column prop="item_name" label="物料" /><el-table-column prop="quantity" label="变更前" /><el-table-column prop="after" label="变更后" /><el-table-column prop="difference" label="差异" /><el-table-column prop="unresolved_quantity" label="需处理已领/采购数量" /></el-table>
        <router-link v-for="purchase in preview.purchases" :key="purchase.id" :to="{ path: `/projects/${preview.project}`, query: { tab: 'purchases', resource: 'purchases', focus: purchase.id } }">{{ purchase.code }} · 处理关联采购 </router-link>
      </section>
      <p v-if="!command.fields.length && !command.blocked && !command.readonly">确认执行“{{ command.title }}”。</p>
      </div>
      <div class="dialog-footer">
        <el-button v-for="alternative in command.alternatives" :key="alternative.label" :disabled="locked" @click="openAlternative(alternative.open)">{{ alternative.label }}</el-button>
        <el-button v-if="command.previewPath" :disabled="locked" @click="previewChange">预览变更影响</el-button>
        <el-button v-for="action in command.actions" :key="action.label" :type="action.label === primary ? 'primary' : undefined" :disabled="locked" @click="async () => { if (await confirmLeave()) await action.run() }">{{ action.label }}</el-button>
        <el-button v-if="dirty && currentDraftKey" :disabled="locked" @click="keepAndClose">暂存并关闭</el-button>
        <el-button :disabled="locked" @click="requestClose">{{ command.readonly ? '关闭' : '取消' }}</el-button
        ><el-button v-if="!command.readonly && !command.blocked" type="primary" native-type="submit" :loading="locked"
          >{{ submitLabel(command) }}</el-button
        >
      </div>
    </form>
  </component>
</template>

<style scoped>
.compact-flow { margin: 0 0 16px; color: var(--ink-3); font-size: 13px; }
.compact-flow summary { cursor: pointer; padding: 8px 0; }
.field-issues, .draft-notice, .action-blocker { padding: 12px 16px; margin-bottom: 16px; border: 1px solid var(--field-line); border-radius: 8px; background: var(--subtle-2); }
.field-issues { color: var(--risk); }
.field-issues button { border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; padding: 6px 0; text-decoration: underline; }
.field-issues ul { padding-left: 18px; margin: 6px 0; }
.draft-notice { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.draft-notice span { flex: 1 1 240px; }
</style>
