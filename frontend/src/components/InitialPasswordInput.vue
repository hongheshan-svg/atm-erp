<script setup lang="ts">
import { ref } from 'vue'
import { randomPassword } from '../utils/password'
defineProps<{ label: string; required?: boolean; disabled?: boolean }>()
const model = defineModel<string>({ required: true })
const visible = ref(false)
function generate() {
  model.value = randomPassword()
  visible.value = true
}
</script>
<template>
  <div class="initial-password">
    <input v-model="model" :aria-label="label" :type="visible ? 'text' : 'password'" :required="required" :disabled="disabled" autocomplete="new-password" placeholder="手动填写或点击随机生成" />
    <div class="password-actions">
      <button type="button" :disabled="disabled" @click="generate">随机生成</button>
      <button type="button" :disabled="disabled" :aria-pressed="visible" @click="visible = !visible">{{ visible ? '隐藏密码' : '显示密码' }}</button>
    </div>
  </div>
</template>
<style scoped>
.initial-password { display: grid; gap: 8px; min-width: 0; }
.initial-password input { width: 100%; min-width: 0; }
.password-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.password-actions button { padding: 6px 12px; border: 1px solid var(--line); border-radius: 4px; background: #fff; color: var(--brand-ink); cursor: pointer; }
.password-actions button:disabled { cursor: not-allowed; opacity: .5; }
</style>
