<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import { can } from '../session'
import SupplierMonthly from '../components/SupplierMonthly.vue'
const tabs = [{ key: 'entries', label: '应收应付与费用' }, { key: 'reconciliations', label: '业务对账' }, { key: 'monthly', label: '供应商月度对账' }, { key: 'payments', label: '收付款流水' }, ...(can(['admin', 'finance']) ? [{ key: 'bank', label: '银行到账与认领' }] : [])]
</script>
<template>
  <ModulePage title="收付款" project-filter v-slot="{ revision, projectId, refresh }"
    ><p class="muted">CNY 含税经营口径。采购付款及退款先对账，预付款按合同核准；客户到账可先登记。未知项目的银行收入请清除项目筛选后认领。</p>
    <ModuleTabs :tabs="tabs" storage-key="finance"><template #monthly><SupplierMonthly /></template><template #entries><ResourcePanel
      resource="entries"
      title="应收应付与费用"
      :params="{ project: projectId }"
      :project-id="projectId"
      :revision="revision"
      @changed="refresh" /></template><template #payments><ResourcePanel
      resource="payments"
      title="收付款流水"
      :params="{ entry__project: projectId }"
      :revision="revision"
      @changed="refresh"
  /></template><template #reconciliations><p class="muted">从款项操作生成对账单。先查看明细核对差异，再确认；预付款由项目经理或管理员核准。</p><ResourcePanel resource="reconciliations" title="业务对账" :params="{ entry__project: projectId }" :revision="revision" @changed="refresh" /></template><template #bank><ResourcePanel resource="bank-records" title="银行到账与认领" :params="{ project: projectId }" :project-id="projectId" :revision="revision" @changed="refresh" /></template></ModuleTabs></ModulePage>
</template>
