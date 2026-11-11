<script setup lang="ts">
import { computed } from 'vue'
import { pageSize as globalSize, pageSizes as allSizes, setPageSize } from '../pagination'
const props = withDefaults(defineProps<{ page: number; total: number; minSize?: number }>(), { minSize: 0 })
// 调用方给了每页下限时，只提供不低于下限的选项，显示值与实际请求一致。
const pageSizes = computed(() => allSizes.filter(size => size >= props.minSize))
const pageSize = computed(() => Math.max(globalSize.value, props.minSize))
const pages = computed(() => Math.max(1, Math.ceil(props.total / pageSize.value)))
const emit = defineEmits<{ change: [page: number] }>()
</script>
<template>
  <div class="list-pagination">
    <label><span class="page-size-text">每页显示</span>
      <select :value="pageSize" aria-label="每页显示条目" @change="setPageSize(Number(($event.target as HTMLSelectElement).value))">
        <option v-for="size in pageSizes" :key="size" :value="size">{{ size }} 条</option>
      </select>
    </label>
    <div class="pager-compact" role="group" aria-label="翻页">
      <button type="button" :disabled="page <= 1" @click="emit('change', page - 1)">上一页</button>
      <span :title="`共 ${total} 条`">第 {{ page }}/{{ pages }} 页</span>
      <button type="button" :disabled="page >= pages" @click="emit('change', page + 1)">下一页</button>
    </div>
    <el-pagination :current-page="page" :page-size="pageSize" :total="total" :pager-count="5" layout="prev,pager,next,total" @current-change="emit('change', $event)" />
  </div>
</template>
<style scoped>
.pager-compact { display: none; }
@media (max-width: 600px) {
  .list-pagination { flex-wrap: nowrap; gap: 8px; margin-top: 10px; }
  .list-pagination > label { flex: none; }
  .list-pagination select { min-height: 40px; width: 78px; }
  .list-pagination :deep(.el-pagination) { display: none; }
  .pager-compact { display: flex; flex: 1; align-items: center; justify-content: flex-end; gap: 6px; min-width: 0; font-size: 12px; color: var(--ink-4); }
  .pager-compact span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pager-compact button { flex: none; white-space: nowrap; min-height: 40px; min-width: 52px; padding: 0 8px; border: 1px solid var(--field-line); border-radius: 6px; background: #fff; color: var(--ink-2); font: inherit; font-size: 13px; cursor: pointer; }
  .pager-compact button:disabled { opacity: .45; cursor: default; }
}
/* 360 宽且列表放在带内边距的面板里时，省掉「每页显示」字样（下拉自带无障碍名称），把空间留给页码。 */
@media (max-width: 400px) {
  .page-size-text { display: none; }
}
</style>
