<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import type { Row } from '../types'
import { write } from '../api'
import { message, requestKey } from '../utils/request'

// 上传人（或项目经理）撤回误传的附件：记录与文件本体保留，只移出列表；已作为收付款、对账或合同依据的会被服务端拦截。
// 与 RecordDeletionDialog 同一结构：填写原因并勾选核对后才能确认，按钮在底部，请求进行中不能关闭。
const props = defineProps<{ rows: Row[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const reason = ref(''), confirmed = ref(false), busy = ref(false), error = ref('')
let key = requestKey(), closed = false
onBeforeUnmount(() => { closed = true })
watch(reason, () => { key = requestKey() })
// 删除请求发出后不能关闭：否则请求成功了列表也不刷新，已删的附件还留在弹窗里。
function close() { if (!busy.value) emit('close') }
async function submit() {
  if (busy.value) return
  if (!props.rows.length || !reason.value.trim() || !confirmed.value) { error.value = '请填写删除原因，并勾选确认。'; return }
  busy.value = true; error.value = ''
  try {
    await write('/business/documents/remove-batch/', { documents: props.rows.map(row => row.id), reason: reason.value.trim() }, key)
    if (!closed) { emit('saved'); emit('close') }
  } catch (e) { if (!closed) error.value = message(e) }
  finally { busy.value = false }
}
</script>
<template>
  <el-dialog class="transfer-dialog" :model-value="true" :title="`删除附件（${rows.length}）`" width="min(520px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @close="close">
    <el-alert type="warning" :closable="false" title="所选附件将移出附件列表，文件本体和上传审计仍然保留；已作为收付款、对账或合同依据的附件不能删除，且任一份被拦截时整批都不会删除。" />
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" class="removal-error" />
    <ol class="removal-files" aria-label="将删除的附件">
      <li v-for="row in rows" :key="row.id">{{ row.original_name }}</li>
    </ol>
    <form class="removal-form" @submit.prevent="submit">
      <label for="attachment-removal-reason">删除原因（整批共用）</label>
      <textarea id="attachment-removal-reason" v-model="reason" maxlength="500" rows="2" :disabled="busy" placeholder="例如：比价表传错了" required />
      <label class="removal-confirm"><input v-model="confirmed" type="checkbox" :disabled="busy" />我已核对所选附件，并了解删除后将移出附件列表</label>
    </form>
    <template #footer>
      <el-button :disabled="busy" @click="close">取消</el-button>
      <el-button type="danger" :loading="busy" :disabled="!reason.trim() || !confirmed" @click="submit">确认删除</el-button>
    </template>
  </el-dialog>
</template>
<style scoped>
.removal-error { margin-top: 10px; }
.removal-files { margin: 12px 0; padding-left: 22px; max-height: 180px; overflow-y: auto; }
.removal-form { display: grid; gap: 6px; }
.removal-form textarea { width: 100%; box-sizing: border-box; padding: 10px; font: inherit; }
.removal-confirm { display: flex; gap: 8px; align-items: start; margin-top: 6px; }
.removal-files li { overflow-wrap: anywhere; }
@media (max-width: 600px) {
  :global(.transfer-dialog .el-dialog__footer .el-button) { min-height: 40px; }
}
</style>
