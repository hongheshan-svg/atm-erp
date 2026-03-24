<template>
  <div class="dashboard-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>仪表盘配置</span>
          <div>
            <el-button type="primary" @click="saveConfig" :loading="saving">
              <el-icon><Check /></el-icon> 保存配置
            </el-button>
            <el-button @click="resetToDefault">重置默认</el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="组件选择" name="widgets">
          <el-alert type="info" :closable="false" style="margin-bottom: 20px">
            拖拽或勾选下方组件来自定义您的仪表盘
          </el-alert>
          
          <el-row :gutter="16">
            <el-col :span="8" v-for="widget in availableWidgets" :key="widget.key">
              <el-card shadow="hover" class="widget-card" :class="{ active: isWidgetEnabled(widget.key) }">
                <div class="widget-header">
                  <el-checkbox 
                    :model-value="isWidgetEnabled(widget.key)"
                    @change="toggleWidget(widget.key)"
                  >
                    {{ widget.name }}
                  </el-checkbox>
                </div>
                <div class="widget-desc">{{ widget.description }}</div>
                <div class="widget-category">
                  <el-tag size="small" :type="getCategoryType(widget.category)">
                    {{ widget.category }}
                  </el-tag>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="布局配置" name="layout">
          <el-form label-width="120px">
            <el-form-item label="每行显示列数">
              <el-radio-group v-model="layoutConfig.columns">
                <el-radio-button :value="2">2列</el-radio-button>
                <el-radio-button :value="3">3列</el-radio-button>
                <el-radio-button :value="4">4列</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="自动刷新">
              <el-switch v-model="layoutConfig.autoRefresh" />
              <span v-if="layoutConfig.autoRefresh" style="margin-left: 16px">
                每
                <el-input-number 
                  v-model="layoutConfig.refreshInterval" 
                  :min="30" 
                  :max="600" 
                  :step="30" 
                  size="small"
                  style="width: 100px"
                />
                秒
              </span>
            </el-form-item>
            <el-form-item label="显示欢迎语">
              <el-switch v-model="layoutConfig.showWelcome" />
            </el-form-item>
            <el-form-item label="主题色调">
              <el-radio-group v-model="layoutConfig.theme">
                <el-radio-button value="light">浅色</el-radio-button>
                <el-radio-button value="dark">深色</el-radio-button>
                <el-radio-button value="auto">跟随系统</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="组件排序" name="order">
          <el-alert type="info" :closable="false" style="margin-bottom: 20px">
            点击上下箭头调整组件在仪表盘中的显示顺序
          </el-alert>
          
          <div class="widget-order-list">
            <div v-for="(element, index) in enabledWidgets" :key="element.key" class="order-item">
              <div class="order-actions">
                <el-button 
                  :icon="ArrowUp" 
                  size="small" 
                  :disabled="index === 0"
                  @click="moveWidget(index, -1)"
                />
                <el-button 
                  :icon="ArrowDown" 
                  size="small" 
                  :disabled="index === enabledWidgets.length - 1"
                  @click="moveWidget(index, 1)"
                />
              </div>
              <span class="order-index">{{ index + 1 }}</span>
              <span class="order-name">{{ element.name }}</span>
              <el-tag size="small">{{ element.category }}</el-tag>
            </div>
          </div>
          
          <el-empty v-if="enabledWidgets.length === 0" description="请先在组件选择中勾选组件" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 预览 -->
    <el-card style="margin-top: 20px">
      <template #header>仪表盘预览</template>
      <div class="preview-container" :class="`cols-${layoutConfig.columns}`">
        <div 
          v-for="widget in enabledWidgets" 
          :key="widget.key"
          class="preview-widget"
        >
          <el-icon><component :is="widget.icon || 'DataLine'" /></el-icon>
          <span>{{ widget.name }}</span>
        </div>
      </div>
      <el-empty v-if="enabledWidgets.length === 0" description="暂无已启用的组件" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, ArrowUp, ArrowDown, DataLine } from '@element-plus/icons-vue'
import request from '@/utils/request'

const activeTab = ref('widgets')
const saving = ref(false)

const availableWidgets = ref([
  { key: 'project_stats', name: '项目统计', description: '显示进行中、已完成、已验收项目数量', category: '项目', icon: 'Management' },
  { key: 'sales_stats', name: '销售统计', description: '显示本月销售额、订单数量', category: '销售', icon: 'Sell' },
  { key: 'purchase_stats', name: '采购统计', description: '显示本月采购额、待收货订单', category: '采购', icon: 'ShoppingCart' },
  { key: 'inventory_alert', name: '库存预警', description: '显示库存不足和积压物料', category: '库存', icon: 'Warning' },
  { key: 'finance_summary', name: '财务概览', description: '显示应收应付账款余额', category: '财务', icon: 'Money' },
  { key: 'pending_approvals', name: '待办审批', description: '显示待处理的审批任务', category: '审批', icon: 'Checked' },
  { key: 'recent_activities', name: '最近动态', description: '显示系统最近操作记录', category: '系统', icon: 'List' },
  { key: 'project_timeline', name: '项目进度', description: '显示项目甘特图概览', category: '项目', icon: 'Calendar' },
  { key: 'sales_chart', name: '销售趋势', description: '显示近期销售趋势图表', category: '销售', icon: 'TrendCharts' },
  { key: 'task_summary', name: '任务概览', description: '显示我的任务完成情况', category: '项目', icon: 'List' },
  { key: 'notification_center', name: '通知中心', description: '显示最新系统通知', category: '系统', icon: 'Bell' },
  { key: 'quick_actions', name: '快捷操作', description: '常用功能快捷入口', category: '系统', icon: 'Grid' },
])

const userConfig = ref({
  enabled_widgets: ['project_stats', 'sales_stats', 'pending_approvals', 'inventory_alert'],
  widget_order: [],
})

const layoutConfig = ref({
  columns: 3,
  autoRefresh: false,
  refreshInterval: 60,
  showWelcome: true,
  theme: 'light'
})

const enabledWidgets = computed({
  get() {
    const order = userConfig.value.widget_order.length > 0 
      ? userConfig.value.widget_order 
      : userConfig.value.enabled_widgets
    
    return order
      .filter(key => userConfig.value.enabled_widgets.includes(key))
      .map(key => availableWidgets.value.find(w => w.key === key))
      .filter(Boolean)
  },
  set(newValue) {
    userConfig.value.widget_order = newValue.map(w => w.key)
  }
})

const isWidgetEnabled = (key) => {
  return userConfig.value.enabled_widgets.includes(key)
}

const toggleWidget = (key) => {
  const index = userConfig.value.enabled_widgets.indexOf(key)
  if (index > -1) {
    userConfig.value.enabled_widgets.splice(index, 1)
    userConfig.value.widget_order = userConfig.value.widget_order.filter(k => k !== key)
  } else {
    userConfig.value.enabled_widgets.push(key)
    userConfig.value.widget_order.push(key)
  }
}

const getCategoryType = (category) => {
  const types = {
    '项目': 'primary',
    '销售': 'success',
    '采购': 'warning',
    '库存': 'info',
    '财务': 'danger',
    '审批': '',
    '系统': 'info'
  }
  return types[category] || ''
}

const fetchConfig = async () => {
  try {
    const res = await request({ url: '/core/user-dashboard/my_dashboard/', method: 'get' })
    if (res.data) {
      if (res.data.enabled_widgets) {
        userConfig.value.enabled_widgets = res.data.enabled_widgets
      }
      if (res.data.widget_order) {
        userConfig.value.widget_order = res.data.widget_order
      }
      if (res.data.layout) {
        Object.assign(layoutConfig.value, res.data.layout)
      }
    }
  } catch (error) {
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    await request({
      url: '/core/user-dashboard/',
      method: 'post',
      data: {
        enabled_widgets: userConfig.value.enabled_widgets,
        widget_order: userConfig.value.widget_order,
        layout: layoutConfig.value
      }
    })
    ElMessage.success('配置保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const resetToDefault = () => {
  userConfig.value = {
    enabled_widgets: ['project_stats', 'sales_stats', 'pending_approvals', 'inventory_alert'],
    widget_order: [],
  }
  layoutConfig.value = {
    columns: 3,
    autoRefresh: false,
    refreshInterval: 60,
    showWelcome: true,
    theme: 'light'
  }
  ElMessage.success('已重置为默认配置')
}

const moveWidget = (index, direction) => {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= userConfig.value.widget_order.length) return
  
  const order = [...userConfig.value.widget_order]
  const [item] = order.splice(index, 1)
  order.splice(newIndex, 0, item)
  userConfig.value.widget_order = order
}

onMounted(() => {
  fetchConfig()
})
</script>

<style scoped>
.dashboard-config {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.widget-card {
  margin-bottom: 16px;
  cursor: pointer;
  transition: all 0.3s;
}
.widget-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.widget-card.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}
.widget-header {
  font-weight: bold;
  margin-bottom: 8px;
}
.widget-desc {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  min-height: 36px;
}
.widget-category {
  text-align: right;
}
.widget-order-list {
  max-width: 600px;
}
.order-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 8px;
}
.order-actions {
  display: flex;
  gap: 4px;
}
.order-index {
  width: 24px;
  height: 24px;
  background: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.order-name {
  flex: 1;
  font-weight: 500;
}
.preview-container {
  display: grid;
  gap: 16px;
}
.preview-container.cols-2 { grid-template-columns: repeat(2, 1fr); }
.preview-container.cols-3 { grid-template-columns: repeat(3, 1fr); }
.preview-container.cols-4 { grid-template-columns: repeat(4, 1fr); }
.preview-widget {
  padding: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.preview-widget .el-icon {
  font-size: 24px;
}
</style>
