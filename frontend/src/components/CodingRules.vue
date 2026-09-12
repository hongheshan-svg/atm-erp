<script setup lang="ts">
import { productCategories } from '../product-categories'
const year = String(new Date().getFullYear()).slice(-2)
</script>

<template>
  <section class="panel coding-rules" aria-label="设备命名与编码规范">
    <h2>设备命名与编码规范</h2>
    <p class="muted">以 Word《产品文件编码规则》QP-001 A/00 为准；Excel 中 A2605 等作为历史编号保留。设备名称按销售合同。</p>
    <dl>
      <dt>设备名称</dt><dd>按销售合同中的设备 / 产线名称原文填写；销售签约生成项目时沿用名称。不自动拼接客户、型号或编号。独立项目尚无合同时填写暂定名称，在需求说明中注明待合同确认。</dd>
      <dt>项目编号</dt><dd><strong>ATM＋两位年＋两位流水</strong>，例如 ATM{{ year }}01。每年 01–99，满额停止取号；新项目不采用 A{{ year }}01 缩写，历史项目号不自动转换。下方项目规则可通过“应用项目规范”设置，新编号继续沿用已用流水。</dd>
      <dt>物料编码</dt><dd><strong>两位类别＋两位年＋六位流水</strong>，共 10 位。有图按当前年份，无图固定 99；按类别及年份独立取号。同物料优先复用，BOM 导入可留空编码并在确认时生成。自定义编码继续保留，普通规则仅用于未分类物料。</dd>
      <dt>型号与版本</dt><dd>型号 / 规格由研发提供，与图号、版本分别填写。已分类物料升级版本需新建物料、使用对应新型号并修订 BOM，保留旧编码与历史记录。</dd>
    </dl>
    <details>
      <summary>查看八类物料编码与工程图号</summary>
      <div class="category-grid"><div v-for="(label, code) in productCategories" :key="code"><strong>{{ code }} · {{ label }}</strong><span>示例 {{ code }}{{ String(code).startsWith('1') ? year : '99' }}000001</span></div></div>
      <p>工程图号：A＋两位年－E/T－两位项目序号－A/P－六位图档流水，例如 A{{ year }}-E-01-A-000001。E 为设备、T 为模具，A 为组件、P 为零件。</p>
      <p>模具 / 工装子图：ATM-T序号-A/P-六位流水，例如 ATM-T1-P-000001。图号由研发给出，不能用物料流水推算；旧图号保留。</p>
    </details>
  </section>
</template>

<style scoped>
.coding-rules { margin-bottom: 20px; }
dl { display: grid; grid-template-columns: 100px 1fr; gap: 14px 20px; line-height: 1.7; }
dt { font-weight: 600; }
dd { margin: 0; }
summary { cursor: pointer; padding: 8px 0; }
.category-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0; }
.category-grid span { display: block; margin-top: 4px; }
@media (max-width: 600px) { dl { grid-template-columns: 1fr; gap: 6px; } dd { margin-bottom: 12px; } }
</style>
