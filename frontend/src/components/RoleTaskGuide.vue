<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { can, operations, user } from '../session'
import { localStore } from '../utils/storage'

const route = useRoute()
const preferenceKey = computed(() => `role-task-guide-${user.value?.id}-${[...(user.value?.roles || [user.value?.role])].sort().join(',')}`)
const open = ref(false)
watch([preferenceKey, () => route.query.guide], () => {
  open.value = route.query.guide === 'show' || localStore.get(preferenceKey.value) !== 'hidden'
}, { immediate: true })
function dismiss() { open.value = false; localStore.set(preferenceKey.value, 'hidden') }
const steps = computed(() => [
  ...(operations() ? [{ key: 'tasks', title: '处理我的任务', note: '查看分配给自己的任务，登记工时或完成任务。尚未分配时，请联系项目经理。', to: '/projects?section=tasks', action: '查看我的任务' }] : []),
  ...(can(['admin', 'manager']) ? [{ key: 'projects', title: '安排项目执行', note: '选择负责的项目，维护成员、计划并分配任务。', to: '/projects?section=projects', action: '选择项目' }] : []),
  ...(can(['mechanical_engineer', 'electrical_engineer']) ? [{ key: 'engineering', title: '编制项目用料', note: '选择参与的项目，在 BOM 维护或导入物料清单；图纸与程序放在项目附件。', to: '/bom', action: '维护 BOM' }] : []),
  ...(can(['production_manager']) ? [{ key: 'production', title: '安排生产与售后', note: '选择参与的项目，安排装配、调试、安装及售后任务。', to: '/projects?section=projects', action: '选择生产项目' }] : []),
  ...(can(['admin', 'purchase_manager', 'purchaser']) ? [{ key: 'purchasing', title: '从缺料开始采购', note: '进入采购，使用“从 BOM 多选下单”选择项目和缺料，生成采购草稿。', to: '/purchases?project=all', action: '按 BOM 下单' }] : []),
  ...(can(['admin', 'warehouse']) ? [{ key: 'warehouse', title: '收货、领料与退料', note: '收货选择待收采购；领料选择现有库存；退料选择原领料流水。', to: '/inventory?section=receipts&project=all', action: '进入日常库存操作' }] : []),
  ...(can(['admin', 'finance']) ? [{ key: 'finance', title: '核对后登记收付款', note: '先核对业务单据和对账额度，再从款项登记实际收付款。', to: '/finance?section=reconciliations&project=all', action: '核对业务对账' }] : []),
  ...(can(['admin', 'sales_manager']) ? [{ key: 'sales', title: '建立销售单并报价', note: '进入销售，新建销售单，确认客户和需求后登记报价。', to: '/sales?search=', action: '进入销售' }] : []),
])
</script>

<template>
  <section v-if="steps.length" class="panel role-guide" aria-label="岗位首任务指引">
    <header><h2>从我的岗位开始</h2><el-button v-if="open" text @click="dismiss">暂时跳过</el-button><el-button v-else text @click="open = true">再次查看岗位指引</el-button></header>
    <template v-if="open">
      <p class="muted">按兼任岗位显示可用入口。选择一项开始，也可以稍后从工作台或设置再次查看。</p>
      <ul><li v-for="step in steps" :key="step.key"><h3>{{ step.title }}</h3><p>{{ step.note }}</p><router-link :to="step.to">{{ step.action }} →</router-link></li></ul>
    </template>
  </section>
</template>

<style scoped>
.role-guide header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.role-guide h2 { margin: 0; font-size: 18px; }
.role-guide ul { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; padding: 0; margin-bottom: 0; list-style: none; }
.role-guide li { padding: 16px; border: 1px solid var(--surface-border); border-radius: 8px; }
.role-guide h3 { margin: 0; font-size: 15px; }
.role-guide p { font-size: 14px; line-height: 1.65; }
.role-guide a { display: inline-block; padding: 6px 0; }
</style>
