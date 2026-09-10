<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Command, Row } from '../types'
import { defaults, payload } from '../forms'
import { read, write } from '../api'
import { message, recoveryActions } from '../utils/request'
import FormFields from './FormFields.vue'
const props = defineProps<{ command: Command | null }>()
const emit = defineEmits<{ close: []; saved: [result: Row] }>()
const data = ref<Row>({})
const busy = ref(false)
const error = ref('')
const recovery = ref<{ label: string; path: string }[]>([])
const preview = ref<Row | null>(null)
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
  return `新增：${names(after.filter(v => !before.includes(v)))}；移除：${names(before.filter(v => !after.includes(v)))}。保存后按新岗位授权；管理员可管理全系统，财务可读取金额并记账，采购/仓管可跨项目作业，项目经理限负责或参与项目，销售经理限本人销售。移除岗位不会删除原业务记录。`
})
async function previewChange() {
  const c = props.command
  if (!c?.previewPath || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const body = payload(c.fields, data.value)
    preview.value = await write(c.previewPath, c.prepare ? c.prepare(body) : body, crypto.randomUUID())
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
const fieldsContainer = ref<HTMLElement>()
let key = ''
let signature = ''
watch(
  () => props.command,
  (c) => {
    if (c) {
      preview.value = null
      data.value = defaults(c.fields, JSON.parse(JSON.stringify(c.initial || {})))
      error.value = ''
      recovery.value = []
      key = crypto.randomUUID()
      signature = ''
    }
  },
  { immediate: true },
)
async function submit() {
  const c = props.command
  if (!c || c.readonly || busy.value) return
  busy.value = true
  error.value = ''
  recovery.value = []
  try {
    let body = payload(c.fields, data.value)
    if (roleChange.value && !data.value.roles?.length) throw new Error('至少选择一个角色。')
    if (c.prepare) body = c.prepare(body)
    const next = JSON.stringify(body, (_k, v) => (v instanceof File ? [v.name, v.size, v.lastModified] : v))
    if (signature && signature !== next) key = crypto.randomUUID()
    signature = next
    let upload: FormData | undefined
    if (Object.values(body).some((v) => v instanceof File)) {
      upload = new FormData()
      for (const [k, v] of Object.entries(body)) upload.append(k, v instanceof File ? v : String(v))
    }
    const result = await write(c.path, upload || body, key, c.method)
    emit('saved', result)
    emit('close')
    ElMessage.success('已保存')
  } catch (e) {
    error.value = message(e)
    recovery.value = recoveryActions(e)
    await nextTick()
    if (fieldsContainer.value) fieldsContainer.value.scrollTop = 0
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <el-dialog
    class="action-dialog"
    :model-value="Boolean(command)"
    :title="command?.title"
    width="min(760px, 94vw)"
    :close-on-click-modal="false"
    :before-close="
      () => {
        if (!busy) emit('close')
      }
    "
    destroy-on-close
  >
    <form v-if="command" class="action-form" @submit.prevent="submit">
      <div ref="fieldsContainer" class="action-fields">
      <el-alert v-if="command.notice" :title="command.notice.text" :type="command.notice.type" :closable="false" show-icon />
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
      <p v-for="action in recovery" :key="action.path"><router-link :to="action.path" @click="emit('close')">{{ action.label }}</router-link></p>
      <FormFields v-model="data" :fields="command.fields" :disabled="busy || command.readonly" :readonly="command.readonly" />
      <section v-if="similarItems.length" aria-label="相似物料">
        <p>发现相似物料，请核对后优先复用现有编码：</p>
        <p v-for="item in similarItems" :key="item.id"><router-link :to="{ path: '/masterdata', query: { section: 'items', resource: 'items', focus: item.id } }" @click="emit('close')">{{ item.code }} · {{ item.name }} · {{ item.specification }} · {{ item.brand }} · {{ item.unit }}</router-link></p>
      </section>
      <el-alert v-if="roleChange" :title="roleChange" type="warning" :closable="false" role="status" />
      <section v-if="preview" aria-label="变更影响预览">
        <el-alert :title="preview.can_apply ? '本次预览可通过；保存时仍会重新校验。' : preview.blockers.join('；')" :type="preview.can_apply ? 'info' : 'warning'" :closable="false" />
        <el-table :data="preview.items" max-height="300"><el-table-column prop="item_name" label="物料" /><el-table-column prop="quantity" label="变更前" /><el-table-column prop="after" label="变更后" /><el-table-column prop="difference" label="差异" /><el-table-column prop="unresolved_quantity" label="需处理已领/采购数量" /></el-table>
        <router-link v-for="purchase in preview.purchases" :key="purchase.id" :to="{ path: `/projects/${preview.project}`, query: { tab: 'purchases', resource: 'purchases', focus: purchase.id } }" @click="emit('close')">{{ purchase.code }} · 处理关联采购 </router-link>
      </section>
      <p v-if="!command.fields.length">确认执行“{{ command.title }}”。</p>
      </div>
      <div class="dialog-footer">
        <el-button v-if="command.previewPath" :disabled="busy" @click="previewChange">预览变更影响</el-button>
        <el-button v-for="action in command.actions" :key="action.label" :disabled="busy" @click="action.run">{{ action.label }}</el-button>
        <el-button :disabled="busy" @click="emit('close')">{{ command.readonly ? '关闭' : '取消' }}</el-button
        ><el-button v-if="!command.readonly" type="primary" native-type="submit" :loading="busy"
          >保存</el-button
        >
      </div>
    </form>
  </el-dialog>
</template>
