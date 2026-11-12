<script setup lang="ts">
import BusinessTable from './BusinessTable.vue'
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useNarrow } from '../utils/media'
import { matchedRouteKey, onBeforeRouteLeave, onBeforeRouteUpdate, routerKey } from 'vue-router'
import { purchaseReader, user } from '../session'
import { clearDraft, draftKey, formSignature, loadDraft, saveDraft, registerFormGuard, submitLabel, wideCommand } from '../form-experience'
import { ElDialog, ElMessage, ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import type { Command, Field, Row } from '../types'
import { defaults, fieldIssues, payload, validateFields, type FieldIssue } from '../forms'
import { industryCommand } from '../industry-forms'
import { read, write } from '../api'
import { message, recoveryActions, requestKey } from '../utils/request'
import FormFields from './FormFields.vue'
import StatusBadge from './StatusBadge.vue'
import ProcessSteps from './ProcessSteps.vue'
import ProjectProgress from './ProjectProgress.vue'
import { quantityText as qty } from '../utils/quantity'
import { primaryActions } from '../row-actions'
const qtyCell = (_row: Row, _column: unknown, value: unknown) => qty(value)
const props = defineProps<{ command: Command | null; inline?: boolean }>()
const command = computed(() => props.command ? industryCommand(props.command) : null)
const emit = defineEmits<{ close: []; saved: [result: Row]; busy: [value: boolean]; replace: [command: Command] }>()
const data = ref<Row>({})
const busy = ref(false), uploading = ref(false)
const locked = computed(() => busy.value || uploading.value)
watch(locked, value => emit('busy', value))
const wide = computed(() => wideCommand(command.value))
// 表格式明细行一行要排下七八列，对话框放到接近整屏宽。
const dense = computed(() => Boolean(command.value?.fields.some(field => field.dense)))
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
// 弹窗专用属性只交给 ElDialog；内嵌详情面板是普通 section，不能落成 title/width 等 DOM 属性（否则整块悬停都冒出原生提示）。
const dialogProps = computed(() => props.inline ? {} : {
  modelValue: Boolean(command.value),
  title: command.value?.title,
  width: dense.value ? 'min(1400px, 96vw)' : wide.value ? 'min(1080px, 96vw)' : 'min(760px, 94vw)',
  appendToBody: true,
  closeOnClickModal: false,
  beforeClose: requestClose,
  destroyOnClose: true,
})
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
  const visit = (fields: Field[], errors: Row, path = '', prefix = ''): FieldIssue[] => fields.flatMap(field => {
    const value = errors[field.key]
    if (value == null) return []
    const key = path ? `${path}.${field.key}` : field.key
    const label = `${prefix}${field.label}`
    if (field.type === 'rows' && typeof value === 'object') {
      const nested = Object.entries(value).flatMap(([index, row]) => /^\d+$/.test(index) && row && typeof row === 'object' && !Array.isArray(row)
        ? visit(field.fields || [], row, `${key}.${index}`, `${label}第 ${Number(index) + 1} 行 · `) : [])
      if (nested.length) return nested
    }
    return [{ path: key, label, message: `${label}：${message(value)}` }]
  })
  serverIssues.value = visit(command.value.fields, response)
  // The single-line BOM editor submits a one-row batch while showing its fields directly.
  if (!serverIssues.value.length && command.value.path.includes('/revise-bom/') && !command.value.fields.some(f => f.key === 'lines') && response.lines?.[0]) {
    serverIssues.value = visit(command.value.fields, response.lines[0])
  }
}
const panelHeading = ref<HTMLElement>()
const panelHeight = ref('calc(100dvh - 36px)')
function fitPanel() {
  const panel = panelHeading.value?.parentElement?.parentElement
  if (props.inline && panel) panelHeight.value = `${Math.max(280, window.innerHeight - Math.max(18, panel.getBoundingClientRect().top) - 18)}px`
}
onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  // 只有内嵌详情面板需要随视口调整高度。
  if (props.inline) {
    window.addEventListener('resize', fitPanel)
    window.addEventListener('scroll', fitPanel, true)
  }
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
    // 手机端详情面板从视口顶部展开，内部滚动区才有足够高度，首条记录不会被底部操作栏压住。
    const top = panel?.getBoundingClientRect().top ?? 0
    // 面板上方还压着其他区块时，可用高度不足以填写表单，直接把面板顶到视口上沿。
    if (panel && (window.innerWidth <= 760 || (top > 96 && window.innerHeight - top < 620))) panel.scrollIntoView({ block: 'start' })
    fitPanel()
    panelHeading.value?.focus({ preventScroll: true })
  } else if (returnFocus?.isConnected) returnFocus.focus()
})
const error = ref('')
const recovery = ref<{ label: string; path: string }[]>([])
// 「打开原单据」指向当前页面，或 BOM 修订这类没有具体原单的冲突时，点了也没反应，不再显示孤零零的一行。
function usefulRecovery(e: unknown) {
  const c = command.value
  if (c && /\/(revise-bom|bom-import-confirm)\/$|^\/business\/bom\//.test(c.path)) return []
  const route = router?.currentRoute.value
  return recoveryActions(e).filter(action => !route || (action.path !== route.path && action.path !== route.fullPath))
}
const preview = ref<Row | null>(null)
const previewedSignature = ref('')
// 预览后又改了填写内容：结果可能已过期，提示重新预览，保存按钮也不再沿用预览里的「新增 N 行」。
const previewStale = computed(() => Boolean(preview.value) && previewedSignature.value !== formSignature(data.value))
const purchaseStatus: Record<string, string> = { draft: '草稿', submitted: '待批准', approved: '待收货', partial: '部分收货' }
// 手机宽度下预览表改成单列摘要，不在对话框里再套一层横向滚动。
const mobile = useNarrow()
const unitText = (row: Row) => `${row.before_unit != null && row.before_unit !== row.assembly_unit ? `${row.before_unit || '未分单元'} → ` : ''}${row.assembly_unit || '未分单元'}`
const purchaseList = computed(() => (preview.value?.purchases || []).map((purchase: Row) => `${purchase.code}（${purchaseStatus[purchase.status] || purchase.status}）`).join('、'))
// 只有被拦截或确有已领/在途要处理时才叫人去找采购；只改日期或单元时采购单仅作参考。
const purchaseAction = computed(() => {
  const result = preview.value
  if (!result) return false
  return !result.can_apply || (result.items || []).some((row: Row) => Number(row.unresolved_quantity) > 0)
})
const submitText = computed(() => {
  const c = command.value
  if (!c) return ''
  const changes: Row[] = preview.value && !previewStale.value ? preview.value.changes || [] : []
  const created = changes.filter(change => change.action === 'create').length
  if (!created || c.submitLabel) return submitLabel(c)
  const updated = changes.length - created
  return `确认新增 ${created} 行${updated ? `、修改 ${updated} 行` : ''}`
})
// 与列表行同一张「下一步」清单（row-actions.ts），详情和列表突出同一个动作；「退料」是纠错动作，详情里不作主按钮。
const primary = computed(() => primaryActions.find(label => label !== '退料' && command.value?.actions?.some(action => action.label === label)))
// 详情底部只留下一步，其余动作收进菜单：十个按钮平铺会把明细挤出面板。
const shownActions = computed(() => {
  const actions = command.value?.actions || []
  if (!command.value?.readonly || actions.length <= 3) return actions
  // 没有约定的下一步时保留第一个动作，面板底部不能只剩一个菜单。
  return actions.filter((action, index) => primary.value ? action.label === primary.value : index === 0)
})
const moreActions = computed(() => (command.value?.actions || []).filter(action => !shownActions.value.includes(action)))
async function runAction(label: string) {
  const action = command.value?.actions?.find(item => item.label === label)
  if (action && await confirmLeave()) await action.run()
}
const similarItems = ref<Row[]>([])
watch(() => [props.command?.path, data.value.name, data.value.specification], async (_, __, onCleanup) => {
  similarItems.value = []
  if (!props.command?.path.startsWith('/business/items/') || (!data.value.name && !data.value.specification)) return
  let active = true
  const timer = setTimeout(async () => {
    try {
      const items = await read('/business/items/similar/', { name: data.value.name, specification: data.value.specification })
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
    attempted.value = true
    serverIssues.value = []
    validateFields(c.fields, data.value)
    const body = payload(c.fields, data.value)
    const signature = formSignature(data.value)
    preview.value = await write(c.previewPath, c.prepare ? c.prepare(body) : body, requestKey())
    previewedSignature.value = signature
  } catch (e) { error.value = message(e); mapServerIssues(e) } finally { busy.value = false }
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
// 远程下拉核对预选值期间点保存，不该让人看到一条「请稍候」再手动重试：等核对结束后继续提交。
let settling = false
async function settleSelections() {
  const pending = () => Array.from(fieldsContainer.value?.querySelectorAll<HTMLInputElement>('input') || []).some(input => input.validationMessage.startsWith('正在核对'))
  for (let i = 0; i < 80 && pending(); i++) await new Promise(resolve => setTimeout(resolve, 100))
}
async function submit() {
  const c = command.value
  if (!c || c.readonly || locked.value || c.blocked || settling) return
  // 等待核对时不锁表单：字段保持可编辑，必填校验状态也不会因禁用而消失。
  settling = true
  try { await settleSelections() } finally { settling = false }
  if (command.value !== c || locked.value) return
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
    const note = c.successNote?.(result || {})
    if (note) ElMessage({ type: 'warning', message: note, duration: 10000, showClose: true, grouping: true })
  } catch (e) {
    error.value = message(e)
    mapServerIssues(e)
    recovery.value = usefulRecovery(e)
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
    :class="[inline ? 'detail-pane' : 'action-dialog', { 'wide-action': wide, 'dense-action': dense }]"
    :style="inline ? { maxHeight: panelHeight } : undefined"
    :role="inline ? 'dialog' : undefined"
    :aria-modal="inline ? 'false' : undefined"
    :aria-label="command?.title"
    v-bind="dialogProps"
  >
    <header v-if="inline" class="detail-pane-heading"><h2 ref="panelHeading" tabindex="-1">{{ command?.title }}</h2><el-button :icon="Close" text :disabled="locked" aria-label="关闭详情" @click="requestClose" /></header>
    <form v-if="command" class="action-form" novalidate @submit.prevent="submit">
      <div ref="fieldsContainer" class="action-fields">
      <div v-if="command.subject" class="record-headline"><strong>{{ command.subject }}</strong><StatusBadge v-if="command.initial?.status" :value="command.initial.status" /></div>
      <details v-if="command.flow" class="compact-flow"><summary>{{ command.flow.label }} · {{ command.flow.nodes[command.flow.current]?.label || command.flow.aborted?.label }} · 查看完整流程</summary><ProcessSteps class="record-flow" :flow="command.flow" /></details>
      <el-alert v-if="command.notice" :title="command.notice.text" :type="command.notice.type" :closable="false" show-icon />
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
      <p v-for="action in recovery" :key="action.path" class="recovery-action"><el-button link type="primary" @click="follow(action.path)">{{ action.label }} →</el-button></p>
      <section v-if="restored" class="draft-notice" aria-label="未提交的填写内容"><span>发现之前暂存的填写内容（附件需重新选择）。</span><el-button @click="restore">恢复填写</el-button><el-button text @click="discardDraft">删除暂存</el-button></section>
      <section v-if="command.blocked" class="action-blocker" role="status"><strong>先完成以下事项</strong><p>{{ command.blocked }}</p></section>
      <p v-for="link in command.links" :key="link.path"><el-button @click="follow(link.path)">{{ link.label }}</el-button></p>
      <section v-if="issues.length" class="field-issues" aria-label="填写问题汇总" role="alert"><strong>请修正以下 {{ issues.length }} 项，其他填写内容已保留：</strong><ul><li v-for="issue in issues" :key="issue.path"><button type="button" @click="fields?.focusPath(issue.path)">{{ issue.message }}</button></li></ul></section>
      <FormFields v-if="!command.blocked" ref="fields" v-model="data" :fields="command.fields" :disabled="locked || command.readonly" :readonly="command.readonly" :issues="issueMap" @touched="touch" @uploading="uploading = $event" />
      <slot v-if="command.readonly" name="context" />
      <ProjectProgress v-if="command.readonly && command.progressProject" :project-id="command.progressProject" />
      <section v-if="similarItems.length" aria-label="相似物料">
        <p>发现名称或型号相似的物料，请核对厂家完整型号后复用编码；系统不会自动合并或改写型号：</p>
        <p v-for="item in similarItems" :key="item.id"><router-link :to="{ path: '/masterdata', query: { section: 'items', resource: 'items', focus: item.id } }">{{ item.code }} · {{ item.name }} · {{ item.specification }} · {{ item.brand }} · {{ item.unit }}</router-link></p>
      </section>
      <el-alert v-if="roleChange" :title="roleChange" type="warning" :closable="false" role="status" />
      <section v-if="preview" class="change-preview" aria-label="变更影响预览">
        <el-alert :title="preview.can_apply ? '本次预览可通过；保存时仍会重新校验。' : preview.blockers.join('；')" :type="preview.can_apply ? 'info' : 'warning'" :closable="false" />
        <el-alert v-if="previewStale" title="预览后又改过填写内容，下方结果可能已过期，请重新预览。" type="warning" :closable="false" />
        <el-alert v-for="warning in preview.warnings || []" :key="warning" :title="warning" type="warning" :closable="false" show-icon role="status" />
        <template v-if="preview.changes?.length">
          <h3 class="preview-heading">本次提交 {{ preview.changes.length }} 行</h3>
          <BusinessTable label="本次提交的行" :data="preview.changes" :numbered="false" :max-height="mobile ? undefined : 220">
            <el-table-column v-if="mobile" label="物料与变化"><template #default="{ row }"><span class="preview-change-head"><el-tag :type="row.action === 'create' ? 'warning' : 'info'" size="small">{{ row.action === 'create' ? '新增' : '修改' }}</el-tag><strong>{{ row.item_code }} {{ row.item_name }}</strong></span><small class="preview-change-line">{{ unitText(row) }} · 数量 {{ qty(row.before ?? '0') }} → {{ qty(row.after) }}</small></template></el-table-column>
            <template v-else>
            <el-table-column label="动作" width="72"><template #default="{ row }"><el-tag :type="row.action === 'create' ? 'warning' : 'info'" size="small">{{ row.action === 'create' ? '新增' : '修改' }}</el-tag></template></el-table-column>
            <el-table-column label="物料" min-width="180"><template #default="{ row }">{{ row.item_code }} {{ row.item_name }}</template></el-table-column>
            <el-table-column label="单元" min-width="140"><template #default="{ row }">{{ unitText(row) }}</template></el-table-column>
            <el-table-column label="数量" min-width="130"><template #default="{ row }">{{ qty(row.before ?? '0') }} → {{ qty(row.after) }}</template></el-table-column>
            </template>
          </BusinessTable>
        </template>
        <template v-if="preview.items?.length">
          <h3 class="preview-heading">数量变化（按物料汇总）</h3>
          <BusinessTable label="变更影响" :data="preview.items" :numbered="!mobile" :max-height="mobile ? undefined : 260"><el-table-column v-if="mobile" label="物料"><template #default="{ row }"><strong>{{ row.item_name }}</strong><small class="preview-change-line">{{ qty(row.quantity) }} → {{ qty(row.after) }}（差异 {{ qty(row.difference) }}）</small><small v-if="Number(row.unresolved_quantity) > 0" class="preview-change-line">需处理已领/采购 {{ qty(row.unresolved_quantity) }}</small><small v-if="Number(row.received_in_stock) > 0" class="preview-change-line">已到货未领 {{ qty(row.received_in_stock) }}</small></template></el-table-column><template v-else><el-table-column prop="item_name" label="物料" min-width="140" /><el-table-column prop="quantity" label="变更前" :formatter="qtyCell" /><el-table-column prop="after" label="变更后" :formatter="qtyCell" /><el-table-column prop="difference" label="差异" :formatter="qtyCell" /><el-table-column prop="unresolved_quantity" label="需处理已领/采购数量" min-width="120" :formatter="qtyCell" /><el-table-column v-if="preview.items.some((row: Row) => Number(row.received_in_stock) > 0)" prop="received_in_stock" label="已到货未领" :formatter="qtyCell" /></template></BusinessTable>
          <p v-if="preview.unchanged_items" class="muted">其余 {{ preview.unchanged_items }} 种物料数量不变，未列出。</p>
        </template>
        <p v-else-if="preview.changes && preview.can_apply" class="muted">本次没有数量变化（仅改了日期、单元或申请信息）。</p>
        <template v-if="preview.purchases?.length">
          <p v-if="purchaseReader()" class="preview-purchases"><router-link v-for="purchase in preview.purchases" :key="purchase.id" :to="{ path: `/projects/${preview.project}`, query: { tab: 'purchases', resource: 'purchases', focus: purchase.id } }">{{ purchase.code }}（{{ purchaseStatus[purchase.status] || purchase.status }}）· {{ purchaseAction ? '处理关联采购' : '查看采购' }}</router-link></p>
          <p v-else-if="purchaseAction" class="muted">涉及采购单 {{ purchaseList }}，请联系采购员处理未收余量后再提交。</p>
          <p v-else class="muted">相关采购单 {{ purchaseList }}，本次变更不需要处理。</p>
        </template>
      </section>
      <p v-if="!command.fields.length && !command.blocked && !command.readonly">确认执行“{{ command.title }}”。</p>
      </div>
      <div class="dialog-footer">
        <el-button v-for="alternative in command.alternatives" :key="alternative.label" :disabled="locked" @click="openAlternative(alternative.open)">{{ alternative.label }}</el-button>
        <el-button v-if="command.previewPath" :disabled="locked" @click="previewChange">预览变更影响</el-button>
        <el-button v-for="action in shownActions" :key="action.label" :type="action.label === primary ? 'primary' : undefined" :disabled="locked" @click="runAction(action.label)">{{ action.label }}</el-button>
        <el-dropdown v-if="moreActions.length" trigger="click" :disabled="locked" @command="(label: string) => runAction(String(label))"><el-button :disabled="locked">更多操作 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="action in moreActions" :key="action.label" :command="action.label">{{ action.label }}</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
        <el-button v-if="dirty && currentDraftKey" :disabled="locked" @click="keepAndClose">暂存并关闭</el-button>
        <el-button :disabled="locked" @click="requestClose">{{ command.readonly ? '关闭' : '取消' }}</el-button
        ><el-button v-if="!command.readonly && !command.blocked" type="primary" native-type="submit" :loading="locked"
          >{{ submitText }}</el-button
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
:is(.action-dialog, .detail-pane) .el-alert__title { overflow-wrap: anywhere; }
.draft-notice { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.draft-notice span { flex: 1 1 240px; }
.change-preview { display: grid; gap: 10px; margin-top: 12px; }
.change-preview .preview-heading { margin: 4px 0 0; font-size: 14px; }
.preview-change-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.preview-change-line { display: block; margin-top: 2px; color: var(--ink-3); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.change-preview .muted { margin: 0; }
.preview-purchases { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 0; }
.recovery-action { margin: 8px 0; }
</style>
<style>
/* 窄屏（手机）：对话框、详情面板与确认框的按钮触控区不小于 40px；详情面板底部取消/确认并排，主次靠颜色区分，避免把破坏性确认放在最顶部整行。 */
@media (max-width: 600px) {
  :is(.action-dialog, .detail-pane, .el-message-box) .el-button:not(.el-button--small):not(.is-text) { min-height: 40px; }
  .detail-pane .detail-pane-heading .el-button.is-text { min-width: 40px; min-height: 40px; }
  .detail-pane .dialog-footer > .el-button--primary { order: initial; flex: 1 1 auto; }
  /* 多选人员标签的删除叉：默认 14px 太小，放大触控区。 */
  :is(.action-dialog, .detail-pane) .el-select__tags .el-tag__close { width: 24px; height: 24px; font-size: 14px; }
}
</style>
