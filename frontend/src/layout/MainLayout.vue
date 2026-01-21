<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <h2 v-if="!isCollapse">{{ companyShortName || 'ERP' }}</h2>
        <h2 v-else>{{ (companyShortName || 'ERP').charAt(0) }}</h2>
      </div>
      
      <el-menu
        :default-active="$route.path"
        class="sidebar-menu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
      >
        <!-- 仪表盘 -->
        <el-menu-item index="/dashboard" v-if="hasMenuAccess('dashboard')">
          <el-icon><Odometer /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        
        <!-- ==================== CRM 客户关系管理 ==================== -->
        <el-sub-menu index="crm" v-if="hasMenuAccess('crm') || hasMenuAccess('sales')">
          <template #title>
            <el-icon><Avatar /></el-icon>
            <span>CRM客户管理</span>
          </template>
          <el-menu-item index="/sales/leads" v-if="hasMenuAccess('sales:leads')">销售线索</el-menu-item>
          <el-menu-item index="/sales/opportunities" v-if="hasMenuAccess('sales:opportunities')">销售商机</el-menu-item>
          <el-menu-item index="/customers" v-if="hasMenuAccess('masterdata:customers')">客户档案</el-menu-item>
          <el-menu-item index="/masterdata/customer-followups" v-if="hasMenuAccess('masterdata:customer-followups') || hasMenuAccess('masterdata:customers')">客户跟进</el-menu-item>
          <el-menu-item index="/masterdata/customer-credit" v-if="hasMenuAccess('masterdata:credit') || hasMenuAccess('masterdata:customers')">信用管理</el-menu-item>
          <el-menu-item index="/sales/quotations" v-if="hasMenuAccess('sales:quotations')">销售报价</el-menu-item>
          <el-menu-item index="/sales/contracts" v-if="hasMenuAccess('sales:contracts')">销售合同</el-menu-item>
          <el-menu-item index="/sales/analysis" v-if="hasMenuAccess('sales:analysis') || hasMenuAccess('sales')">销售分析</el-menu-item>
          <el-menu-item index="/aftersales/orders" v-if="hasMenuAccess('aftersales:orders') || hasMenuAccess('sales')">售后服务</el-menu-item>
        </el-sub-menu>
        
        <!-- ==================== PLM 产品生命周期管理 ==================== -->
        <el-sub-menu index="plm" v-if="hasMenuAccess('projects')">
          <template #title>
            <el-icon><Briefcase /></el-icon>
            <span>PLM产品研发</span>
          </template>
          <el-menu-item-group title="需求与方案">
            <el-menu-item index="/plm/requirements" v-if="hasMenuAccess('plm:requirements') || hasMenuAccess('projects')">需求管理</el-menu-item>
            <el-menu-item index="/plm/proposals" v-if="hasMenuAccess('plm:proposals') || hasMenuAccess('projects')">方案设计</el-menu-item>
            <el-menu-item index="/plm/configurator" v-if="hasMenuAccess('plm:configurator') || hasMenuAccess('projects')">产品配置器</el-menu-item>
            <el-menu-item index="/plm/agreements" v-if="hasMenuAccess('plm:agreements') || hasMenuAccess('projects')">技术协议</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="项目管理">
            <el-menu-item index="/projects" v-if="hasMenuAccess('projects:list')">项目列表</el-menu-item>
            <el-menu-item index="/projects/dashboard" v-if="hasMenuAccess('projects:dashboard') || hasMenuAccess('projects')">项目仪表盘</el-menu-item>
            <el-menu-item index="/projects/tasks" v-if="hasMenuAccess('projects:tasks')">任务管理</el-menu-item>
            <el-menu-item index="/projects/milestones" v-if="hasMenuAccess('projects:milestones') || hasMenuAccess('projects')">里程碑</el-menu-item>
            <el-menu-item index="/projects/gantt" v-if="hasMenuAccess('projects:gantt')">甘特图</el-menu-item>
            <el-menu-item index="/projects/time-logs" v-if="hasMenuAccess('projects:time-logs')">工时填报</el-menu-item>
            <el-menu-item index="/projects/alerts" v-if="hasMenuAccess('projects:alerts') || hasMenuAccess('projects')">项目预警</el-menu-item>
            <el-menu-item index="/projects/equipment-archives" v-if="hasMenuAccess('projects:equipment-archives') || hasMenuAccess('projects')">设备档案</el-menu-item>
            <el-menu-item index="/projects/acceptances" v-if="hasMenuAccess('projects:acceptances') || hasMenuAccess('projects')">验收管理(FAT/SAT)</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="技术文档">
            <el-menu-item index="/projects/bom" v-if="hasMenuAccess('projects:bom')">BOM管理</el-menu-item>
            <el-menu-item index="/projects/drawings" v-if="hasMenuAccess('projects:drawings') || hasMenuAccess('projects')">图纸管理</el-menu-item>
            <el-menu-item index="/plm/model-viewer" v-if="hasMenuAccess('plm:model-viewer') || hasMenuAccess('projects')">3D模型预览</el-menu-item>
            <el-menu-item index="/projects/ecn" v-if="hasMenuAccess('projects:ecn') || hasMenuAccess('projects')">ECN变更</el-menu-item>
            <el-menu-item index="/projects/bugs" v-if="hasMenuAccess('projects:bugs')">Bug跟踪</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="知识库">
            <el-menu-item index="/knowledge/articles" v-if="hasMenuAccess('knowledge:articles') || hasMenuAccess('projects')">知识文章</el-menu-item>
            <el-menu-item index="/knowledge/issues" v-if="hasMenuAccess('knowledge:issues') || hasMenuAccess('projects')">技术问题</el-menu-item>
            <el-menu-item index="/knowledge/components" v-if="hasMenuAccess('knowledge:components') || hasMenuAccess('projects')">标准部件库</el-menu-item>
            <el-menu-item index="/projects/archives" v-if="hasMenuAccess('projects:archives') || hasMenuAccess('projects')">项目归档</el-menu-item>
          </el-menu-item-group>
        </el-sub-menu>
        
        <!-- ==================== ERP 企业资源管理 ==================== -->
        <el-sub-menu index="erp-sales" v-if="hasMenuAccess('sales')">
          <template #title>
            <el-icon><Sell /></el-icon>
            <span>ERP销售执行</span>
          </template>
          <el-menu-item index="/sales/orders" v-if="hasMenuAccess('sales:orders')">销售订单</el-menu-item>
          <el-menu-item index="/sales/delivery-orders" v-if="hasMenuAccess('sales:delivery-orders')">发货管理</el-menu-item>
          <el-menu-item index="/sales/performance" v-if="hasMenuAccess('sales:performance') || hasMenuAccess('sales')">销售业绩</el-menu-item>
          <el-menu-item index="/finance/ar" v-if="hasMenuAccess('finance:ar')">应收账款</el-menu-item>
          <el-menu-item index="/finance/collection-plans" v-if="hasMenuAccess('finance:collection')">回款计划</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="erp-purchase" v-if="hasMenuAccess('purchase')">
          <template #title>
            <el-icon><ShoppingCart /></el-icon>
            <span>ERP采购管理</span>
          </template>
          <el-menu-item index="/inventory/mrp" v-if="hasMenuAccess('inventory:mrp') || hasMenuAccess('purchase')">MRP需求计划</el-menu-item>
          <el-menu-item index="/purchase/requests" v-if="hasMenuAccess('purchase:requests')">采购申请</el-menu-item>
          <el-menu-item index="/purchase/comparisons" v-if="hasMenuAccess('purchase:comparisons')">比价分析</el-menu-item>
          <el-menu-item index="/purchase/orders" v-if="hasMenuAccess('purchase:orders')">采购订单</el-menu-item>
          <el-menu-item index="/purchase/goods-receipts" v-if="hasMenuAccess('purchase:goods-receipts')">到货质检</el-menu-item>
          <el-menu-item index="/purchase/outsource" v-if="hasMenuAccess('purchase:outsource') || hasMenuAccess('purchase')">外协加工</el-menu-item>
          <el-menu-item index="/purchase/budgets" v-if="hasMenuAccess('purchase:budgets') || hasMenuAccess('purchase')">采购预算</el-menu-item>
          <el-menu-item index="/finance/ap" v-if="hasMenuAccess('finance:ap')">应付账款</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="erp-supplier" v-if="hasMenuAccess('purchase') || hasMenuAccess('masterdata')">
          <template #title>
            <el-icon><OfficeBuilding /></el-icon>
            <span>ERP供应商管理</span>
          </template>
          <el-menu-item index="/suppliers" v-if="hasMenuAccess('masterdata:suppliers')">供应商档案</el-menu-item>
          <el-menu-item index="/purchase/evaluations" v-if="hasMenuAccess('purchase:evaluations') || hasMenuAccess('purchase')">供应商评价</el-menu-item>
          <el-menu-item index="/purchase/blacklist" v-if="hasMenuAccess('purchase:blacklist') || hasMenuAccess('purchase')">供应商黑名单</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="erp-inventory" v-if="hasMenuAccess('inventory')">
          <template #title>
            <el-icon><Box /></el-icon>
            <span>ERP库存管理</span>
          </template>
          <el-menu-item index="/inventory/stocks" v-if="hasMenuAccess('inventory:stocks')">库存查询</el-menu-item>
          <el-menu-item index="/inventory/batches" v-if="hasMenuAccess('inventory:batches')">批次管理</el-menu-item>
          <el-menu-item index="/inventory/moves" v-if="hasMenuAccess('inventory:moves')">库存流水</el-menu-item>
          <el-menu-item index="/inventory/transfer" v-if="hasMenuAccess('inventory:transfer')">库存调拨</el-menu-item>
          <el-menu-item index="/inventory/adjustment" v-if="hasMenuAccess('inventory:adjustment')">库存盘点</el-menu-item>
          <el-menu-item index="/inventory/stock-alerts" v-if="hasMenuAccess('inventory:alerts') || hasMenuAccess('inventory')">库存预警</el-menu-item>
          <el-menu-item index="/inventory/cost-accounting" v-if="hasMenuAccess('inventory:cost-accounting') || hasMenuAccess('inventory')">库存成本</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="erp-finance" v-if="hasMenuAccess('finance')">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>ERP财务管理</span>
          </template>
          <el-menu-item index="/finance/expenses" v-if="hasMenuAccess('finance:expenses')">费用报销</el-menu-item>
          <el-menu-item index="/finance/shared-expenses" v-if="hasMenuAccess('finance:shared-expenses')">公共费用分摊</el-menu-item>
          <el-menu-item index="/finance/invoices" v-if="hasMenuAccess('finance:invoices')">发票管理</el-menu-item>
          <el-menu-item index="/finance/project-costs" v-if="hasMenuAccess('finance:project-costs')">项目成本</el-menu-item>
          <el-menu-item index="/finance/assets" v-if="hasMenuAccess('finance:assets') || hasMenuAccess('finance')">固定资产</el-menu-item>
        </el-sub-menu>
        
        <!-- ==================== MES 制造执行系统 ==================== -->
        <el-sub-menu index="mes" v-if="hasMenuAccess('production') || hasMenuAccess('projects')">
          <template #title>
            <el-icon><Cpu /></el-icon>
            <span>MES生产执行</span>
          </template>
          <el-menu-item-group title="生产计划">
            <el-menu-item index="/production/plans" v-if="hasMenuAccess('production:plans')">生产计划</el-menu-item>
            <el-menu-item index="/mes/scheduling" v-if="hasMenuAccess('mes:scheduling') || hasMenuAccess('production')">APS排程</el-menu-item>
            <el-menu-item index="/projects/work-orders" v-if="hasMenuAccess('projects:work-orders') || hasMenuAccess('production')">工单派工</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="生产执行">
            <el-menu-item index="/production/processes" v-if="hasMenuAccess('production:processes')">生产工序</el-menu-item>
            <el-menu-item index="/production/debug-records" v-if="hasMenuAccess('production:debug-records')">调试记录</el-menu-item>
            <el-menu-item index="/production/serial-numbers" v-if="hasMenuAccess('production:serial-numbers') || hasMenuAccess('production')">序列号管理</el-menu-item>
            <el-menu-item index="/inventory/requisitions" v-if="hasMenuAccess('inventory:requisitions')">生产领料</el-menu-item>
            <el-menu-item index="/inventory/returns" v-if="hasMenuAccess('inventory:returns')">生产退料</el-menu-item>
            <el-menu-item index="/mes/kanban" v-if="hasMenuAccess('mes:kanban') || hasMenuAccess('production')">电子看板</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="质量管理">
            <el-menu-item index="/production/inspections" v-if="hasMenuAccess('production:inspections')">质量检验</el-menu-item>
            <el-menu-item index="/mes/traceability" v-if="hasMenuAccess('mes:traceability') || hasMenuAccess('production')">追溯管理</el-menu-item>
            <el-menu-item index="/mes/spc" v-if="hasMenuAccess('mes:spc') || hasMenuAccess('production')">SPC统计过程控制</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="异常管理">
            <el-menu-item index="/mes/andon" v-if="hasMenuAccess('mes:andon') || hasMenuAccess('production')">安灯系统</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="数据采集">
            <el-menu-item index="/mes/data-acquisition" v-if="hasMenuAccess('mes:data-acquisition') || hasMenuAccess('production')">数据采集监控</el-menu-item>
          </el-menu-item-group>
        </el-sub-menu>
        
        <el-sub-menu index="mes-equipment" v-if="hasMenuAccess('equipment') || hasMenuAccess('projects')">
          <template #title>
            <el-icon><Monitor /></el-icon>
            <span>MES设备管理</span>
          </template>
          <el-menu-item index="/equipment/list" v-if="hasMenuAccess('equipment:list') || hasMenuAccess('projects')">设备台账</el-menu-item>
          <el-menu-item index="/equipment/fixtures" v-if="hasMenuAccess('equipment:fixtures') || hasMenuAccess('projects')">工装夹具</el-menu-item>
          <el-menu-item index="/equipment/inspection" v-if="hasMenuAccess('equipment:inspection') || hasMenuAccess('projects')">设备点检</el-menu-item>
          <el-menu-item index="/equipment/maintenance" v-if="hasMenuAccess('equipment:maintenance') || hasMenuAccess('projects')">维护日历</el-menu-item>
          <el-menu-item index="/equipment/oee" v-if="hasMenuAccess('equipment:oee') || hasMenuAccess('projects')">OEE分析</el-menu-item>
        </el-sub-menu>
        
        <!-- ==================== OA 协同办公 ==================== -->
        <el-sub-menu index="oa" v-if="hasMenuAccess('workflow') || hasMenuAccess('system') || hasMenuAccess('oa')">
          <template #title>
            <el-icon><Coordinate /></el-icon>
            <span>OA协同办公</span>
          </template>
          <el-menu-item-group title="流程审批">
            <el-menu-item index="/workflow/tasks" v-if="hasMenuAccess('workflow:tasks')">待办审批</el-menu-item>
            <el-menu-item index="/workflow/my-submissions" v-if="hasMenuAccess('workflow:my-submissions')">我的提交</el-menu-item>
            <el-menu-item index="/workflow/config" v-if="hasMenuAccess('workflow:config')">流程配置</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="考勤管理">
            <el-menu-item index="/attendance" v-if="hasMenuAccess('accounts:attendance') || hasMenuAccess('oa')">考勤打卡</el-menu-item>
            <el-menu-item index="/oa/attendance-import" v-if="hasMenuAccess('oa:attendance-import') || isAdmin">考勤导入</el-menu-item>
            <el-menu-item index="/oa/leave" v-if="hasMenuAccess('oa:leave') || hasMenuAccess('oa')">请假申请</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="日程会议">
            <el-menu-item index="/oa/schedule" v-if="hasMenuAccess('oa:schedule') || hasMenuAccess('oa')">日程管理</el-menu-item>
            <el-menu-item index="/oa/meeting" v-if="hasMenuAccess('oa:meeting') || hasMenuAccess('oa')">会议管理</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="公告通知">
            <el-menu-item index="/oa/announcement" v-if="hasMenuAccess('oa:announcement') || hasMenuAccess('oa')">公告管理</el-menu-item>
            <el-menu-item index="/system/notifications" v-if="hasMenuAccess('system:notifications')">消息中心</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="车辆管理">
            <el-menu-item index="/oa/vehicles" v-if="hasMenuAccess('oa:vehicles') || hasMenuAccess('oa')">车辆信息</el-menu-item>
            <el-menu-item index="/oa/vehicle-request" v-if="hasMenuAccess('oa:vehicle-request') || hasMenuAccess('oa')">用车申请</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="资产管理">
            <el-menu-item index="/oa/assets" v-if="hasMenuAccess('oa:assets') || hasMenuAccess('oa')">资产台账</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="协作沟通">
            <el-menu-item index="/oa/im" v-if="hasMenuAccess('oa:im') || hasMenuAccess('oa')">即时通讯</el-menu-item>
          </el-menu-item-group>
        </el-sub-menu>
        
        <!-- ==================== 报表中心 ==================== -->
        <el-sub-menu index="reports" v-if="hasMenuAccess('reports')">
          <template #title>
            <el-icon><TrendCharts /></el-icon>
            <span>报表中心</span>
          </template>
          <el-menu-item index="/reports/profitability" v-if="hasMenuAccess('reports:profitability')">项目利润分析</el-menu-item>
          <el-menu-item index="/reports/cost-analysis" v-if="hasMenuAccess('reports:cost-analysis')">项目成本分析</el-menu-item>
          <el-menu-item index="/reports/timelog" v-if="hasMenuAccess('reports:timelog')">工时统计</el-menu-item>
          <el-menu-item index="/reports/cash-flow" v-if="hasMenuAccess('reports:cash-flow')">现金流预测</el-menu-item>
          <el-menu-item index="/reports/inventory-turnover" v-if="hasMenuAccess('reports:inventory-turnover')">库存周转率</el-menu-item>
          <el-menu-item index="/reports/slow-moving" v-if="hasMenuAccess('reports:slow-moving')">呆滞物料分析</el-menu-item>
          <el-menu-item index="/reports/aging" v-if="hasMenuAccess('reports:aging')">账龄分析</el-menu-item>
          <el-menu-item index="/reports/purchase-price-trend" v-if="hasMenuAccess('reports:purchase-price-trend')">采购价格趋势</el-menu-item>
        </el-sub-menu>
        
        <!-- ==================== 基础数据 ==================== -->
        <el-sub-menu index="masterdata" v-if="hasMenuAccess('masterdata')">
          <template #title>
            <el-icon><Files /></el-icon>
            <span>基础数据</span>
          </template>
          <el-menu-item index="/items" v-if="hasMenuAccess('masterdata:items')">物料管理</el-menu-item>
          <el-menu-item index="/warehouses" v-if="hasMenuAccess('masterdata:warehouses')">仓库管理</el-menu-item>
          <el-menu-item index="/locations" v-if="hasMenuAccess('masterdata:locations')">库位管理</el-menu-item>
          <el-menu-item index="/sales/quote-templates" v-if="hasMenuAccess('sales:quote-templates') || hasMenuAccess('sales')">报价单模板</el-menu-item>
          <el-menu-item index="/sales/contract-templates" v-if="hasMenuAccess('sales:contract-templates') || hasMenuAccess('sales')">合同模板</el-menu-item>
        </el-sub-menu>
        
        <!-- ==================== 系统管理 ==================== -->
        <el-sub-menu index="system" v-if="hasMenuAccess('system')">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item-group title="组织架构">
            <el-menu-item index="/users" v-if="hasMenuAccess('system:users')">用户管理</el-menu-item>
            <el-menu-item index="/roles" v-if="hasMenuAccess('system:roles')">角色管理</el-menu-item>
            <el-menu-item index="/departments" v-if="hasMenuAccess('system:departments')">部门管理</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="系统配置">
            <el-menu-item index="/code-rules" v-if="hasMenuAccess('system:code-rules')">编码规则</el-menu-item>
            <el-menu-item index="/system/data-dictionary" v-if="hasMenuAccess('system:data-dictionary') || hasMenuAccess('system')">数据字典</el-menu-item>
            <el-menu-item index="/system/custom-fields" v-if="hasMenuAccess('system:custom-fields') || hasMenuAccess('system')">自定义字段</el-menu-item>
            <el-menu-item index="/system/email-templates" v-if="hasMenuAccess('system:email-templates') || hasMenuAccess('system')">邮件模板</el-menu-item>
            <el-menu-item index="/notification-settings" v-if="hasMenuAccess('system:notifications')">通知设置</el-menu-item>
            <el-menu-item index="/system/webhooks" v-if="hasMenuAccess('system:webhooks')">Webhook管理</el-menu-item>
            <el-menu-item index="/system/dashboard-config" v-if="hasMenuAccess('system:dashboard-config')">仪表盘配置</el-menu-item>
            <el-menu-item index="/system/config" v-if="hasMenuAccess('system:config')">系统配置</el-menu-item>
          </el-menu-item-group>
          <el-menu-item-group title="运维监控">
            <el-menu-item index="/system/monitor" v-if="hasMenuAccess('system:monitor') || hasMenuAccess('system')">系统监控</el-menu-item>
            <el-menu-item index="/system/backup" v-if="hasMenuAccess('system:backup') || hasMenuAccess('system')">数据备份</el-menu-item>
            <el-menu-item index="/system/audit-log" v-if="hasMenuAccess('system:audit-log')">审计日志</el-menu-item>
            <el-menu-item index="/system/login-logs" v-if="hasMenuAccess('system:login-logs')">登录日志</el-menu-item>
            <el-menu-item index="/system/audit-analytics" v-if="hasMenuAccess('system:audit-analytics') || hasMenuAccess('system')">日志分析</el-menu-item>
          </el-menu-item-group>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-icon" @click="toggleCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="$route.meta.title">{{ $route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="username">{{ userStore.userInfo?.username || '用户' }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
      
      <el-footer class="footer">
        <span>Copyright © {{ new Date().getFullYear() }} 深圳市奥特迈智能装备有限公司 版权所有</span>
        <span class="version">v{{ appVersion }}</span>
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  Odometer, Setting, Files, Briefcase, ShoppingCart, Sell, Box, Money, 
  TrendCharts, Fold, Expand, UserFilled, Cpu, Monitor, Avatar, OfficeBuilding,
  Coordinate, Clock
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { APP_VERSION } from '@/config/version'
import { useCompanyConfig } from '@/stores/companyConfig'

const router = useRouter()
const userStore = useUserStore()
const { companyName, companyShortName, loadCompanyConfig } = useCompanyConfig()

const isCollapse = ref(false)
const appVersion = APP_VERSION

// 检查是否有菜单访问权限
const hasMenuAccess = (menuId) => {
  // 超级管理员有所有权限
  if (userStore.userInfo?.is_superuser) {
    return true
  }
  
  // 如果权限列表包含 *:*:* 则有所有权限
  if (userStore.permissions?.includes('*:*:*')) {
    return true
  }
  
  // 获取用户的菜单权限列表
  const menuIds = userStore.menuIds
  
  // 如果 menuIds 为空或未定义，默认显示基本菜单
  if (!menuIds || menuIds.length === 0) {
    return true // 改为true，方便演示
  }
  
  // 检查是否在权限列表中
  if (!menuId.includes(':')) {
    return menuIds.some(id => id === menuId || id.startsWith(menuId + ':'))
  }
  
  return menuIds.includes(menuId)
}

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const handleCommand = (command) => {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      userStore.logout()
    })
  } else if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'password') {
    router.push('/change-password')
  }
}

onMounted(async () => {
  if (!userStore.userInfo) {
    await userStore.getProfile()
  }
  await loadCompanyConfig()
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background: linear-gradient(180deg, #1a1f36 0%, #0d1117 100%);
  transition: width 0.3s;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.sidebar-menu {
  border-right: none;
  background: transparent;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  color: rgba(255, 255, 255, 0.75);
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background-color: rgba(255, 255, 255, 0.08) !important;
  color: #fff !important;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #409eff 0%, #66b1ff 100%) !important;
  color: #fff !important;
  border-radius: 4px;
  margin: 2px 8px;
  width: calc(100% - 16px);
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item),
.sidebar-menu :deep(.el-menu--inline .el-menu-item) {
  background-color: rgba(0, 0, 0, 0.2) !important;
  color: rgba(255, 255, 255, 0.75) !important;
  padding-left: 50px !important;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item:hover),
.sidebar-menu :deep(.el-menu--inline .el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.1) !important;
  color: #fff !important;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item.is-active),
.sidebar-menu :deep(.el-menu--inline .el-menu-item.is-active) {
  background: linear-gradient(90deg, #409eff 0%, #66b1ff 100%) !important;
  color: #fff !important;
}

/* 确保所有子菜单项文字颜色正确 */
.sidebar-menu :deep(.el-menu) {
  background-color: transparent !important;
}

.sidebar-menu :deep(.el-sub-menu__title),
.sidebar-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.75) !important;
}

.sidebar-menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  color: #fff !important;
}

.sidebar-menu :deep(.el-menu-item-group__title) {
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
  padding-left: 20px;
}

.sidebar-menu::-webkit-scrollbar {
  width: 4px;
}

.sidebar-menu::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}

.sidebar-menu::-webkit-scrollbar-track {
  background-color: transparent;
}

.header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.collapse-icon {
  font-size: 20px;
  cursor: pointer;
  color: #606266;
}

.collapse-icon:hover {
  color: #409eff;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.username {
  font-size: 14px;
  color: #303133;
}

.main-content {
  background-color: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}

.footer {
  height: 40px;
  background-color: #fff;
  border-top: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 12px;
  gap: 20px;
}

.footer .version {
  color: #c0c4cc;
  font-size: 11px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
