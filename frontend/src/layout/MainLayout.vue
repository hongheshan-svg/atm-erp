<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '200px'" class="sidebar">
      <div class="logo">
        <h2 v-if="!isCollapse">ERP</h2>
        <h2 v-else>E</h2>
      </div>
      
      <el-menu
        :default-active="$route.path"
        class="sidebar-menu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
      >
        <el-menu-item index="/dashboard" v-if="hasMenuAccess('dashboard')">
          <el-icon><DataAnalysis /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        
        <el-sub-menu index="workflow" v-if="hasMenuAccess('workflow')">
          <template #title>
            <el-icon><Checked /></el-icon>
            <span>审批中心</span>
          </template>
          <el-menu-item index="/workflow/tasks" v-if="hasMenuAccess('workflow:tasks')">待办审批</el-menu-item>
          <el-menu-item index="/workflow/my-submissions" v-if="hasMenuAccess('workflow:my-submissions')">我的提交</el-menu-item>
          <el-menu-item index="/workflow/config" v-if="hasMenuAccess('workflow:config')">流程配置</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system" v-if="hasMenuAccess('system')">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/users" v-if="hasMenuAccess('system:users')">用户管理</el-menu-item>
          <el-menu-item index="/roles" v-if="hasMenuAccess('system:roles')">角色管理</el-menu-item>
          <el-menu-item index="/departments" v-if="hasMenuAccess('system:departments')">部门管理</el-menu-item>
          <el-menu-item index="/code-rules" v-if="hasMenuAccess('system:code-rules')">编码规则</el-menu-item>
          <el-menu-item index="/notification-settings" v-if="hasMenuAccess('system:notifications')">通知设置</el-menu-item>
          <el-menu-item index="/system/audit-log" v-if="hasMenuAccess('system:audit-log')">审计日志</el-menu-item>
          <el-menu-item index="/system/notifications" v-if="hasMenuAccess('system:notifications')">通知中心</el-menu-item>
          <el-menu-item index="/system/login-logs" v-if="hasMenuAccess('system:login-logs')">登录日志</el-menu-item>
          <el-menu-item index="/system/webhooks" v-if="hasMenuAccess('system:webhooks')">Webhook管理</el-menu-item>
          <el-menu-item index="/system/dashboard-config" v-if="hasMenuAccess('system:dashboard-config')">仪表盘配置</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="masterdata" v-if="hasMenuAccess('masterdata')">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>基础数据</span>
          </template>
          <el-menu-item index="/items" v-if="hasMenuAccess('masterdata:items')">物料管理</el-menu-item>
          <el-menu-item index="/customers" v-if="hasMenuAccess('masterdata:customers')">客户管理</el-menu-item>
          <el-menu-item index="/suppliers" v-if="hasMenuAccess('masterdata:suppliers')">供应商管理</el-menu-item>
          <el-menu-item index="/warehouses" v-if="hasMenuAccess('masterdata:warehouses')">仓库管理</el-menu-item>
          <el-menu-item index="/locations" v-if="hasMenuAccess('masterdata:locations')">库位管理</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="projects" v-if="hasMenuAccess('projects')">
          <template #title>
            <el-icon><Management /></el-icon>
            <span>项目管理</span>
          </template>
          <el-menu-item index="/projects" v-if="hasMenuAccess('projects:list')">项目列表</el-menu-item>
          <el-menu-item index="/projects/tasks" v-if="hasMenuAccess('projects:tasks')">任务管理</el-menu-item>
          <el-menu-item index="/projects/members" v-if="hasMenuAccess('projects:members')">成员管理</el-menu-item>
          <el-menu-item index="/projects/bom" v-if="hasMenuAccess('projects:bom')">BOM清单</el-menu-item>
          <el-menu-item index="/projects/time-logs" v-if="hasMenuAccess('projects:time-logs')">工时填报</el-menu-item>
          <el-menu-item index="/projects/gantt" v-if="hasMenuAccess('projects:gantt')">甘特图</el-menu-item>
          <el-menu-item index="/projects/ecn" v-if="hasMenuAccess('projects:list') || hasMenuAccess('projects:ecn')">ECN变更</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="aftersales" v-if="hasMenuAccess('aftersales') || hasMenuAccess('projects')">
          <template #title>
            <el-icon><Service /></el-icon>
            <span>售后管理</span>
          </template>
          <el-menu-item index="/aftersales/orders" v-if="hasMenuAccess('aftersales:orders') || hasMenuAccess('projects:list')">售后工单</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="purchase" v-if="hasMenuAccess('purchase')">
          <template #title>
            <el-icon><ShoppingCart /></el-icon>
            <span>采购管理</span>
          </template>
          <el-menu-item index="/purchase/requests" v-if="hasMenuAccess('purchase:requests')">采购申请</el-menu-item>
          <el-menu-item index="/purchase/orders" v-if="hasMenuAccess('purchase:orders')">采购订单</el-menu-item>
          <el-menu-item index="/purchase/goods-receipts" v-if="hasMenuAccess('purchase:goods-receipts')">到货质检</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="sales" v-if="hasMenuAccess('sales')">
          <template #title>
            <el-icon><Sell /></el-icon>
            <span>销售管理</span>
          </template>
          <el-menu-item index="/sales/quotations" v-if="hasMenuAccess('sales:quotations')">销售报价</el-menu-item>
          <el-menu-item index="/sales/orders" v-if="hasMenuAccess('sales:orders')">销售订单</el-menu-item>
          <el-menu-item index="/sales/delivery-orders" v-if="hasMenuAccess('sales:delivery-orders')">发货单</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="inventory" v-if="hasMenuAccess('inventory')">
          <template #title>
            <el-icon><Goods /></el-icon>
            <span>库存管理</span>
          </template>
          <el-menu-item index="/inventory/stocks" v-if="hasMenuAccess('inventory:stocks')">库存查询</el-menu-item>
          <el-menu-item index="/inventory/batches" v-if="hasMenuAccess('inventory:batches')">批次管理</el-menu-item>
          <el-menu-item index="/inventory/moves" v-if="hasMenuAccess('inventory:moves')">库存流水</el-menu-item>
          <el-menu-item index="/inventory/transfer" v-if="hasMenuAccess('inventory:transfer')">库存调拨</el-menu-item>
          <el-menu-item index="/inventory/adjustment" v-if="hasMenuAccess('inventory:adjustment')">库存盘点</el-menu-item>
          <el-menu-item index="/inventory/alert" v-if="hasMenuAccess('inventory:alert')">库存预警</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="finance" v-if="hasMenuAccess('finance')">
          <template #title>
            <el-icon><Money /></el-icon>
            <span>财务管理</span>
          </template>
          <el-menu-item index="/finance/expenses" v-if="hasMenuAccess('finance:expenses')">费用报销</el-menu-item>
          <el-menu-item index="/finance/shared-expenses" v-if="hasMenuAccess('finance:shared-expenses')">公共费用分摊</el-menu-item>
          <el-menu-item index="/finance/ar" v-if="hasMenuAccess('finance:ar')">应收账款</el-menu-item>
          <el-menu-item index="/finance/ap" v-if="hasMenuAccess('finance:ap')">应付账款</el-menu-item>
          <el-menu-item index="/finance/invoices" v-if="hasMenuAccess('finance:invoices')">发票管理</el-menu-item>
          <el-menu-item index="/finance/project-costs" v-if="hasMenuAccess('finance:project-costs')">项目成本核算</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="reports" v-if="hasMenuAccess('reports')">
          <template #title>
            <el-icon><TrendCharts /></el-icon>
            <span>报表中心</span>
          </template>
          <el-menu-item index="/reports/profitability" v-if="hasMenuAccess('reports:profitability')">项目利润分析</el-menu-item>
          <el-menu-item index="/reports/cash-flow" v-if="hasMenuAccess('reports:cash-flow')">现金流预测</el-menu-item>
          <el-menu-item index="/reports/inventory-turnover" v-if="hasMenuAccess('reports:inventory-turnover')">库存周转率</el-menu-item>
          <el-menu-item index="/reports/slow-moving" v-if="hasMenuAccess('reports:slow-moving')">呆滞物料分析</el-menu-item>
          <el-menu-item index="/reports/aging" v-if="hasMenuAccess('reports:aging')">账龄分析</el-menu-item>
          <el-menu-item index="/reports/purchase-price-trend" v-if="hasMenuAccess('reports:purchase-price-trend')">采购价格趋势</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="analytics" v-if="hasMenuAccess('analytics')">
          <template #title>
            <el-icon><DataLine /></el-icon>
            <span>数据分析</span>
          </template>
          <el-menu-item index="/analytics/project" v-if="hasMenuAccess('analytics:project')">项目分析</el-menu-item>
          <el-menu-item index="/analytics/inventory" v-if="hasMenuAccess('analytics:inventory')">库存分析</el-menu-item>
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
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  DataAnalysis, Setting, Document, Management, ShoppingCart,
  Sell, Goods, Money, TrendCharts, Fold, Expand, UserFilled, DataLine, Checked, Service
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)

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
  
  // 如果 menuIds 为空或未定义，表示没有配置权限，不显示任何菜单
  if (!menuIds || menuIds.length === 0) {
    return false
  }
  
  // 检查是否在权限列表中
  // 对于父菜单，检查是否有任何子菜单的权限
  if (!menuId.includes(':')) {
    // 这是父菜单，检查是否有任何以该前缀开头的子菜单权限
    return menuIds.some(id => id === menuId || id.startsWith(menuId + ':'))
  }
  
  // 子菜单直接检查
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
  // Load user profile if not loaded
  if (!userStore.userInfo) {
    await userStore.getProfile()
  }
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
  transition: width 0.3s;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: bold;
}

.sidebar-menu {
  border-right: none;
  background-color: #304156;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  color: #bfcbd9;
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background-color: #263445 !important;
  color: #fff !important;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background-color: #409eff !important;
  color: #fff !important;
}

/* 修复子菜单颜色对比度问题 */
.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  background-color: #1f2d3d !important;
  color: #bfcbd9;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item:hover) {
  background-color: #001528 !important;
  color: #fff !important;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item.is-active) {
  background-color: #409eff !important;
  color: #fff !important;
}

/* 滚动条样式 */
.sidebar-menu::-webkit-scrollbar {
  width: 6px;
}

.sidebar-menu::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
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
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.collapse-icon {
  font-size: 20px;
  cursor: pointer;
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
}

.main-content {
  background-color: #f0f2f5;
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
