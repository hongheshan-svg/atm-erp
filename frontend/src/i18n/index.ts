import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'

/**
 * i18n scaffold (FOUNDATION only).
 *
 * zh-CN is the single source of truth today; additional locales can be added
 * under `./locales/<lang>.json` and registered in `messages` below. Extracting
 * the existing hard-coded 文案 into these dictionaries is a follow-up task.
 *
 * Composition API mode (`legacy: false`) with global injection so `$t` is
 * available in templates and `useI18n()` in `<script setup>`.
 */
export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
  },
})

export default i18n
