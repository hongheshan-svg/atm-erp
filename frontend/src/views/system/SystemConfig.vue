<template>
  <div class="system-config">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统配置</span>
          <el-button type="primary" @click="handleSave" :loading="saving">
            <el-icon><Check /></el-icon> 保存配置
          </el-button>
        </div>
      </template>

      <el-form :model="form" label-width="120px" v-loading="loading" class="config-form">
        <el-divider content-position="left">
          <el-icon><OfficeBuilding /></el-icon> 公司基本信息
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="公司名称" required>
              <el-input v-model="form.company_name" placeholder="请输入公司全称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="公司简称">
              <el-input v-model="form.company_short_name" placeholder="请输入公司简称" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="税号">
              <el-input v-model="form.company_tax_no" placeholder="统一社会信用代码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="法人代表">
              <el-input v-model="form.legal_representative" placeholder="法人代表姓名" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="公司地址">
              <el-input v-model="form.company_address" placeholder="请输入公司地址" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="公司电话">
              <el-input v-model="form.company_phone" placeholder="座机或手机" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="公司邮箱">
              <el-input v-model="form.company_email" placeholder="邮箱地址" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="公司网站">
              <el-input v-model="form.company_website" placeholder="https://" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">
          <el-icon><Money /></el-icon> 银行信息
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开户银行">
              <el-input v-model="form.bank_name" placeholder="开户银行名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="银行账号">
              <el-input v-model="form.bank_account" placeholder="银行账号" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="注册资本">
              <el-input-number 
                v-model="form.registered_capital" 
                :min="0" 
                :precision="2" 
                :controls="false"
                placeholder="注册资本（万元）"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">
          <el-icon><Setting /></el-icon> 系统设置
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="默认货币">
              <el-select v-model="form.default_currency" style="width: 100%;">
                <el-option label="人民币 (CNY)" value="CNY" />
                <el-option label="美元 (USD)" value="USD" />
                <el-option label="欧元 (EUR)" value="EUR" />
                <el-option label="港币 (HKD)" value="HKD" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="财年起始月">
              <el-select v-model="form.fiscal_year_start" style="width: 100%;">
                <el-option v-for="m in 12" :key="m" :label="`${m}月`" :value="m" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider />
        
        <el-alert 
          type="info" 
          :closable="false"
          show-icon
        >
          <template #title>
            发票识别规则说明
          </template>
          <p style="margin: 5px 0 0 0; color: #666;">
            导入发票时，系统会根据公司名称自动识别发票类型：
          </p>
          <ul style="margin: 5px 0; padding-left: 20px; color: #666;">
            <li>购买方为 <strong>{{ form.company_name || '本公司' }}</strong> → 自动识别为 <el-tag type="success" size="small">进项发票</el-tag></li>
            <li>销方为 <strong>{{ form.company_name || '本公司' }}</strong> → 自动识别为 <el-tag type="primary" size="small">销项发票</el-tag></li>
          </ul>
        </el-alert>
        
        <div class="update-info" v-if="form.updated_at">
          <el-text type="info" size="small">
            最后更新：{{ formatDateTime(form.updated_at) }}
            <span v-if="form.updated_by_name">（{{ form.updated_by_name }}）</span>
          </el-text>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, OfficeBuilding, Money, Setting } from '@element-plus/icons-vue'
import { getSystemConfig, saveSystemConfig } from '@/api/system'

const loading = ref(false)
const saving = ref(false)

const form = reactive({
  company_name: '',
  company_short_name: '',
  company_tax_no: '',
  company_address: '',
  company_phone: '',
  company_email: '',
  company_website: '',
  bank_name: '',
  bank_account: '',
  legal_representative: '',
  registered_capital: null,
  default_currency: 'CNY',
  fiscal_year_start: 1,
  updated_at: null,
  updated_by_name: ''
})

const loadConfig = async () => {
  loading.value = true
  try {
    const response = await getSystemConfig()
    Object.assign(form, response)
  } catch (error) {
    console.error('Failed to load system config:', error)
    ElMessage.error('加载系统配置失败')
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  if (!form.company_name) {
    ElMessage.warning('请输入公司名称')
    return
  }
  
  saving.value = true
  try {
    await saveSystemConfig(form)
    ElMessage.success('配置保存成功')
    loadConfig() // 重新加载以获取更新时间
  } catch (error) {
    console.error('Failed to save system config:', error)
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

const formatDateTime = (dt) => {
  if (!dt) return ''
  return new Date(dt).toLocaleString('zh-CN')
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.system-config {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-form {
  max-width: 1000px;
}

.el-divider {
  margin: 24px 0 16px 0;
}

.update-info {
  margin-top: 20px;
  text-align: right;
}
</style>

