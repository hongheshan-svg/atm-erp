import { onBeforeUnmount, ref, type Ref } from 'vue'

// 窄屏判断的唯一实现：跟随 CSS 媒体查询（与样式表断点同一写法），组件卸载时解除监听。
// 默认 600px 是手机断点；没有 matchMedia 的环境（单元测试、旧浏览器）按宽屏处理。须在组件 setup 中调用。
export function useNarrow(query = '(max-width: 600px)'): Ref<boolean> {
  const media = typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(query) : null
  const narrow = ref(Boolean(media?.matches))
  if (media) {
    const sync = () => { narrow.value = Boolean(media.matches) }
    media.addEventListener?.('change', sync)
    onBeforeUnmount(() => media.removeEventListener?.('change', sync))
  }
  return narrow
}
