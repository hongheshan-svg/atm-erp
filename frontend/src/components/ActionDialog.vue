<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Command, Row } from '../types'
import { defaults, payload } from '../forms'
import { write } from '../api'
import { message } from '../utils/request'
import FormFields from './FormFields.vue'
const props = defineProps<{ command: Command | null }>()
const emit = defineEmits<{ close: []; saved: [result: Row] }>()
const data = ref<Row>({})
const busy = ref(false)
const error = ref('')
const fieldsContainer = ref<HTMLElement>()
let key = ''
let signature = ''
watch(
  () => props.command,
  (c) => {
    if (c) {
      data.value = defaults(c.fields, JSON.parse(JSON.stringify(c.initial || {})))
      error.value = ''
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
  try {
    let body = payload(c.fields, data.value)
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
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
      <FormFields v-model="data" :fields="command.fields" :disabled="busy || command.readonly" />
      <p v-if="!command.fields.length">确认执行“{{ command.title }}”。</p>
      </div>
      <div class="dialog-footer">
        <el-button :disabled="busy" @click="emit('close')">{{ command.readonly ? '关闭' : '取消' }}</el-button
        ><el-button v-if="!command.readonly" type="primary" native-type="submit" :loading="busy"
          >保存</el-button
        >
      </div>
    </form>
  </el-dialog>
</template>
