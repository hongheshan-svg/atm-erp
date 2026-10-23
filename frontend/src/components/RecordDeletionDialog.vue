<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Row } from '../types'
import { read, write } from '../api'
import { columns, display } from '../business'
import { deletionLabel, deletionNotice, canDeleteRecords, canRestoreRecords, restoreNotice } from '../modules/deletions'
import { message, requestKey } from '../utils/request'
import ListPagination from './ListPagination.vue'
import { pageSize } from '../pagination'
const props = withDefaults(defineProps<{ resource: string; title: string; rows?: Row[]; projectId?: number; saleId?: number; purchaseId?: number; showOriginal?: boolean }>(), { showOriginal: true })
const emit = defineEmits<{ close: []; saved: []; open: [number] }>()
const history = computed(() => props.rows === undefined)
const reason = ref(''), confirmed = ref(false), busy = ref(false), error = ref('')
const records = ref<Row[]>([]), detail = ref<Row | null>(null), page = ref(1), count = ref(0)
let key = requestKey(), generation = 0
onBeforeUnmount(() => { generation++ })
watch(reason, () => { key = requestKey() })
async function load() {
  if (!history.value) return
  const current = ++generation
  busy.value = true; error.value = ''
  try {
    const result = await read('/business/record-deletions/', { resource: props.resource, ...(props.projectId ? { project: props.projectId } : {}), ...(props.saleId ? { sale: props.saleId } : {}), ...(props.purchaseId ? { purchase: props.purchaseId } : {}), page: page.value, page_size: pageSize.value })
    if (current !== generation) return
    records.value = result.results; count.value = result.count
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) busy.value = false }
}
watch([() => props.resource, () => props.projectId, () => props.saleId, () => props.purchaseId, history], () => { page.value = 1; detail.value = null; void load() }, { immediate: true })
watch(pageSize, () => { page.value = 1; void load() })
async function submit() {
  if (busy.value || !canDeleteRecords(props.resource)) return
  if (!props.rows?.length || !reason.value.trim() || !confirmed.value) { error.value = '请填写删除原因，并勾选确认。'; return }
  busy.value = true; error.value = ''
  try {
    await write('/business/record-deletions/', { resource: props.resource, ids: props.rows.map(row => row.id), reason: reason.value.trim() }, key)
    emit('saved'); emit('close')
  } catch (e) { error.value = message(e) }
  finally { busy.value = false }
}
// 恢复只针对账号：恢复后仍停用，需管理员在用户管理中确认角色后再启用。
const restoring = ref<Row | null>(null), restoreReason = ref('')
let restoreKey = requestKey()
watch(restoreReason, () => { restoreKey = requestKey() })
const time = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false })
function startRestore(record: Row) { restoring.value = record; restoreReason.value = ''; restoreKey = requestKey(); error.value = '' }
async function restore() {
  const record = restoring.value
  if (busy.value || !record || !canRestoreRecords(props.resource)) return
  if (!restoreReason.value.trim()) { error.value = '请填写恢复原因。'; return }
  busy.value = true; error.value = ''
  let done = false
  try {
    await write('/business/record-deletions/restore/', { resource: props.resource, id: record.detail.record.id, reason: restoreReason.value.trim() }, restoreKey)
    done = true
  } catch (e) { error.value = message(e) }
  finally { busy.value = false }
  if (!done) return
  restoring.value = null; restoreReason.value = ''
  emit('saved')
  await load()
}
function close() { if (!busy.value) emit('close') }
</script>
<template>
  <el-dialog :model-value="true" :title="history ? `${title} · 已删除记录` : `确认删除 ${rows?.length || 0} 条${title}`" width="min(900px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @close="close">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
    <template v-if="!history">
      <el-alert :title="deletionNotice(resource)" type="warning" :closable="false" show-icon />
      <p>仅删除下列已勾选记录；任何一条不能处理，整批都不会删除。</p>
      <ul class="deletion-records"><li v-for="row in rows" :key="row.id">{{ deletionLabel(row) }}</li></ul>
      <form class="deletion-form" @submit.prevent="submit">
        <label for="deletion-reason">删除原因</label>
        <textarea id="deletion-reason" v-model="reason" maxlength="500" rows="3" :disabled="busy" placeholder="说明为什么删除，便于以后追溯" required />
        <label class="deletion-confirm"><input v-model="confirmed" type="checkbox" :disabled="busy" />{{ resource === 'users' ? '我已核对所选账号，了解删除后不能通过普通编辑恢复，原用户名不能再次使用；误删需在“已删除记录”中恢复账号' : '我已核对所选记录，并了解本次删除的影响' }}</label>
        <div class="deletion-buttons"><el-button :disabled="busy" @click="close">取消</el-button><el-button type="danger" native-type="submit" :loading="busy" :disabled="!reason.trim() || !confirmed">确认删除 {{ rows?.length }} 条</el-button></div>
      </form>
    </template>
    <template v-else>
      <p>保留删除时的内容、操作人、时间和原因。历史流水继续参与库存、账款及成本核算。</p>
      <p v-if="busy" role="status">正在加载…</p>
      <p v-else-if="!records.length && !error">暂无已删除记录。</p>
      <article v-for="record in records" :key="record.id" class="deletion-history">
        <strong>{{ deletionLabel(record.detail.record) }}</strong>
        <p>{{ record.actor_name }} · {{ time(record.created_at) }}</p>
        <p>删除原因：{{ record.detail.reason }}</p>
        <p v-if="record.restored" class="deletion-restored">已恢复 · {{ record.restored_by }} · {{ time(record.restored_at) }}</p>
        <el-button @click="detail = detail?.id === record.id ? null : record">{{ detail?.id === record.id ? '收起内容' : '查看删除时内容' }}</el-button>
        <el-button v-if="showOriginal && record.detail.mode === 'archive'" @click="emit('open', record.detail.record.id)">查看原始记录</el-button>
        <el-button v-if="!record.restored && canRestoreRecords(resource)" type="primary" plain :disabled="busy" @click="startRestore(record)">恢复账号</el-button>
        <form v-if="restoring?.id === record.id" class="deletion-form" @submit.prevent="restore">
          <el-alert :title="restoreNotice" type="info" :closable="false" show-icon />
          <label :for="`restore-reason-${record.id}`">恢复原因</label>
          <textarea :id="`restore-reason-${record.id}`" v-model="restoreReason" maxlength="500" rows="3" :disabled="busy" placeholder="说明为什么恢复，便于以后追溯" required />
          <div class="deletion-buttons"><el-button :disabled="busy" @click="restoring = null">取消</el-button><el-button type="primary" native-type="submit" :loading="busy" :disabled="!restoreReason.trim()">确认恢复</el-button></div>
        </form>
        <dl v-if="detail?.id === record.id" class="deletion-details"><template v-for="col in columns[resource]" :key="col.key"><dt>{{ col.label }}</dt><dd>{{ col.format ? col.format(record.detail.record) : display(record.detail.record[col.key], col.key) }}</dd></template></dl>
      </article>
      <ListPagination :page="page" :total="count" @change="page = $event; load()" />
    </template>
  </el-dialog>
</template>
<style scoped>
.deletion-records { max-height: 220px; overflow: auto; padding-left: 24px; }
.deletion-records li { padding: 4px 0; overflow-wrap: anywhere; }
.deletion-form { display: grid; gap: 12px; margin-top: 16px; }
.deletion-form textarea { width: 100%; box-sizing: border-box; padding: 10px; font: inherit; }
.deletion-confirm { display: flex; gap: 8px; align-items: start; }
.deletion-buttons { display: flex; justify-content: flex-end; gap: 8px; }
.deletion-history { padding: 14px 0; border-bottom: 1px solid var(--field-line); overflow-wrap: anywhere; }
.deletion-history p { margin: 8px 0; }
.deletion-restored { color: var(--el-color-success); }
.deletion-details { display: grid; grid-template-columns: minmax(80px, 130px) minmax(0, 1fr); gap: 8px; }
.deletion-details dd { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
