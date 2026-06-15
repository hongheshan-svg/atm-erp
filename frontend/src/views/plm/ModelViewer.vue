<template>
  <div class="model-viewer-container">
    <div class="page-header">
      <h2>3D模型预览</h2>
      <div class="header-actions">
        <el-upload
          ref="uploadRef"
          :action="uploadUrl"
          :headers="uploadHeaders"
          :on-success="handleUploadSuccess"
          :before-upload="beforeUpload"
          :show-file-list="false"
          accept=".stl,.obj,.gltf,.glb,.step,.stp"
        >
          <el-button type="primary" :icon="Upload">上传模型</el-button>
        </el-upload>
      </div>
    </div>
    
    <el-row :gutter="16">
      <!-- 模型列表 -->
      <el-col :span="6">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>模型文件</span>
              <el-input 
                v-model="searchKeyword" 
                placeholder="搜索模型..." 
                size="small"
                style="width: 120px"
                clearable
              />
            </div>
          </template>
          
          <el-tree
            :data="modelTree"
            :props="treeProps"
            node-key="id"
            highlight-current
            @node-click="handleNodeClick"
            v-loading="loading"
          >
            <template #default="{ node, data }">
              <div class="tree-node">
                <el-icon v-if="data.type === 'folder'"><Folder /></el-icon>
                <el-icon v-else :style="{ color: getFileColor(data.file_type) }">
                  <Document />
                </el-icon>
                <span class="node-label">{{ node.label }}</span>
              </div>
            </template>
          </el-tree>
        </el-card>
        
        <!-- 模型信息 -->
        <el-card shadow="never" class="info-card" v-if="currentModel">
          <template #header>模型信息</template>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="文件名">{{ currentModel.name }}</el-descriptions-item>
            <el-descriptions-item label="格式">{{ currentModel.file_type }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ formatSize(currentModel.file_size) }}</el-descriptions-item>
            <el-descriptions-item label="上传时间">{{ formatDate(currentModel.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="上传者">{{ currentModel.created_by_name }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      
      <!-- 3D预览区域 -->
      <el-col :span="18">
        <el-card shadow="never" class="viewer-card">
          <template #header>
            <div class="viewer-header">
              <span>{{ currentModel?.name || '请选择模型文件' }}</span>
              <div class="viewer-tools" v-if="currentModel">
                <el-button-group>
                  <el-tooltip content="重置视图">
                    <el-button :icon="RefreshRight" @click="resetCamera" />
                  </el-tooltip>
                  <el-tooltip content="俯视图">
                    <el-button @click="setViewAngle('top')">顶</el-button>
                  </el-tooltip>
                  <el-tooltip content="正视图">
                    <el-button @click="setViewAngle('front')">前</el-button>
                  </el-tooltip>
                  <el-tooltip content="侧视图">
                    <el-button @click="setViewAngle('side')">侧</el-button>
                  </el-tooltip>
                  <el-tooltip content="切换线框">
                    <el-button :icon="Grid" @click="toggleWireframe" :type="wireframe ? 'primary' : ''" />
                  </el-tooltip>
                  <el-tooltip content="全屏">
                    <el-button :icon="FullScreen" @click="toggleFullscreen" />
                  </el-tooltip>
                </el-button-group>
                
                <el-dropdown>
                  <el-button :icon="Download">导出</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="exportScreenshot">导出截图</el-dropdown-item>
                      <el-dropdown-item @click="downloadModel">下载模型</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </template>
          
          <div class="viewer-container" ref="viewerContainer">
            <div v-if="!currentModel" class="empty-viewer">
              <el-icon :size="64"><View /></el-icon>
              <p>请从左侧选择模型文件进行预览</p>
              <p class="tips">支持格式: STL, OBJ, GLTF, GLB, STEP</p>
            </div>
            
            <div v-else-if="loadingModel" class="loading-viewer">
              <el-icon class="is-loading" :size="48"><Loading /></el-icon>
              <p>正在加载模型...</p>
            </div>
            
            <canvas ref="canvas" class="model-canvas" v-show="currentModel && !loadingModel"></canvas>
            
            <!-- 颜色选择器 -->
            <div class="color-panel" v-if="currentModel && !loadingModel">
              <el-tooltip content="模型颜色">
                <el-color-picker v-model="modelColor" @change="updateModelColor" size="small" />
              </el-tooltip>
              <el-tooltip content="背景颜色">
                <el-color-picker v-model="bgColor" @change="updateBgColor" size="small" />
              </el-tooltip>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { getDrawingList } from '@/api/projects/drawing'
import { ElMessage } from 'element-plus'
import { 
  Upload, Folder, Document, RefreshRight, Grid, FullScreen, 
  Download, View, Loading 
} from '@element-plus/icons-vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'

// 数据
const loading = ref(false)
const loadingModel = ref(false)
const searchKeyword = ref('')
const modelTree = ref<any[]>([])
const currentModel = ref(null)
const wireframe = ref(false)
const modelColor = ref('#4a90d9')
const bgColor = ref('#1a1a2e')

// DOM refs
const viewerContainer = ref(null)
const canvas = ref(null)

// Three.js 变量
let scene, camera, renderer, controls, model
let animationId = null

// Tree配置
const treeProps = {
  label: 'name',
  children: 'children'
}

// 上传配置
const uploadUrl = '/api/projects/drawings/'
const uploadHeaders = {
  Authorization: `Bearer ${localStorage.getItem('access_token')}`
}

// 格式化方法
const formatSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('zh-CN')
}

const getFileColor = (type) => {
  const colors = {
    'stl': '#e74c3c',
    'obj': '#3498db',
    'gltf': '#2ecc71',
    'glb': '#2ecc71',
    'step': '#9b59b6',
    'stp': '#9b59b6'
  }
  return colors[type?.toLowerCase()] || '#909399'
}

// 3D 可预览文件类型白名单（Drawing 无 drawing_type 字段，按 file_type 本地过滤）
const MODEL_FILE_TYPES = ['stl', 'obj', 'gltf', 'glb', 'step', 'stp', 'iges', 'igs']

// 加载模型列表
const fetchModels = async () => {
  loading.value = true
  try {
    const data = await getDrawingList({
        search: searchKeyword.value
      })

    // 仅保留 3D 模型类文件，避免 PDF/DWG 等混入
    const allItems = data.results || data
    const items = (allItems || []).filter(item =>
      MODEL_FILE_TYPES.includes((item.file_type || '').toLowerCase())
    )

    // 按项目分组
    const grouped = {}
    items.forEach(item => {
      const projectName = item.project_name || '未分类'
      if (!grouped[projectName]) {
        grouped[projectName] = {
          id: `project-${projectName}`,
          name: projectName,
          type: 'folder',
          children: []
        }
      }
      grouped[projectName].children.push({
        ...item,
        type: 'file'
      })
    })
    
    modelTree.value = Object.values(grouped)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 处理节点点击
const handleNodeClick = (data) => {
  if (data.type === 'file') {
    currentModel.value = data
    loadModel(data)
  }
}

// 初始化Three.js场景
const initScene = () => {
  if (!canvas.value || !viewerContainer.value) return
  
  const container = viewerContainer.value
  const width = Math.max(container.clientWidth || 100, 100)
  const height = Math.max((container.clientHeight || 100) - 60, 100)
  
  // 防止尺寸为0或负数
  if (width <= 0 || height <= 0) {
    console.warn('ModelViewer: Invalid container dimensions, retrying...')
    setTimeout(initScene, 100)
    return
  }
  
  // 场景
  scene = new THREE.Scene()
  scene.background = new THREE.Color(bgColor.value)
  
  // 相机
  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 10000)
  camera.position.set(100, 100, 100)
  
  // 渲染器
  renderer = new THREE.WebGLRenderer({ 
    canvas: canvas.value,
    antialias: true,
    preserveDrawingBuffer: true
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  
  // 控制器
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  
  // 灯光
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)
  
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight.position.set(100, 100, 100)
  directionalLight.castShadow = true
  scene.add(directionalLight)
  
  const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.4)
  directionalLight2.position.set(-100, 100, -100)
  scene.add(directionalLight2)
  
  // 网格辅助
  const gridHelper = new THREE.GridHelper(200, 20, 0x444444, 0x333333)
  scene.add(gridHelper)
  
  // 坐标轴
  const axesHelper = new THREE.AxesHelper(50)
  scene.add(axesHelper)
  
  // 开始渲染循环
  animate()
}

// 渲染循环
const animate = () => {
  animationId = requestAnimationFrame(animate)
  
  // 检查渲染器和相机是否有效
  if (!renderer || !camera || !scene) return
  
  // 检查渲染器尺寸是否有效
  const size = renderer.getSize(new THREE.Vector2())
  if (size.x <= 0 || size.y <= 0) return
  
  controls?.update()
  renderer.render(scene, camera)
}

// 加载3D模型
const loadModel = async (modelData) => {
  loadingModel.value = true
  
  // 清除旧模型
  if (model) {
    scene.remove(model)
    model = null
  }
  
  try {
    const fileUrl = modelData.file_url || modelData.file
    const fileType = modelData.file_type?.toLowerCase() || 
                     fileUrl.split('.').pop().toLowerCase()
    
    let loader
    switch (fileType) {
      case 'stl':
        loader = new STLLoader()
        break
      case 'obj':
        loader = new OBJLoader()
        break
      case 'gltf':
      case 'glb':
        loader = new GLTFLoader()
        break
      default:
        ElMessage.warning(`暂不支持 ${fileType} 格式预览`)
        loadingModel.value = false
        return
    }
    
    loader.load(
      fileUrl,
      (result) => {
        if (fileType === 'stl') {
          const geometry = result
          const material = new THREE.MeshStandardMaterial({ 
            color: modelColor.value,
            metalness: 0.3,
            roughness: 0.5,
            wireframe: wireframe.value
          })
          model = new THREE.Mesh(geometry, material)
        } else if (fileType === 'gltf' || fileType === 'glb') {
          model = result.scene
        } else {
          model = result
        }
        
        // 居中模型
        const box = new THREE.Box3().setFromObject(model)
        const center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        
        model.position.sub(center)
        
        // 调整相机位置
        const maxDim = Math.max(size.x, size.y, size.z)
        camera.position.set(maxDim * 1.5, maxDim * 1.5, maxDim * 1.5)
        camera.lookAt(0, 0, 0)
        controls.target.set(0, 0, 0)
        controls.update()
        
        scene.add(model)
        loadingModel.value = false
      },
      (progress) => {
        // 加载进度
      },
      (error) => {
        console.error('模型加载失败:', error)
        ElMessage.error('模型加载失败')
        loadingModel.value = false
      }
    )
  } catch (e) {
    console.error(e)
    loadingModel.value = false
  }
}

// 重置相机
const resetCamera = () => {
  if (!model) return
  
  const box = new THREE.Box3().setFromObject(model)
  const size = box.getSize(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z)
  
  camera.position.set(maxDim * 1.5, maxDim * 1.5, maxDim * 1.5)
  camera.lookAt(0, 0, 0)
  controls.target.set(0, 0, 0)
  controls.update()
}

// 设置视角
const setViewAngle = (view) => {
  if (!model) return
  
  const box = new THREE.Box3().setFromObject(model)
  const size = box.getSize(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z) * 2
  
  switch (view) {
    case 'top':
      camera.position.set(0, maxDim, 0)
      break
    case 'front':
      camera.position.set(0, 0, maxDim)
      break
    case 'side':
      camera.position.set(maxDim, 0, 0)
      break
  }
  
  camera.lookAt(0, 0, 0)
  controls.update()
}

// 切换线框模式
const toggleWireframe = () => {
  wireframe.value = !wireframe.value
  if (model && model.material) {
    model.material.wireframe = wireframe.value
  } else if (model) {
    model.traverse((child) => {
      if (child.isMesh && child.material) {
        child.material.wireframe = wireframe.value
      }
    })
  }
}

// 更新模型颜色
const updateModelColor = (color) => {
  if (model && model.material) {
    model.material.color.set(color)
  } else if (model) {
    model.traverse((child) => {
      if (child.isMesh && child.material) {
        child.material.color.set(color)
      }
    })
  }
}

// 更新背景颜色
const updateBgColor = (color) => {
  if (scene) {
    scene.background = new THREE.Color(color)
  }
}

// 全屏
const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    viewerContainer.value.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 导出截图
const exportScreenshot = () => {
  if (!renderer) return
  
  const dataUrl = renderer.domElement.toDataURL('image/png')
  const link = document.createElement('a')
  link.download = `${currentModel.value?.name || 'model'}_screenshot.png`
  link.href = dataUrl
  link.click()
}

// 下载模型
const downloadModel = () => {
  if (!currentModel.value?.file_url) return
  window.open(currentModel.value.file_url, '_blank')
}

// 上传处理
const beforeUpload = (file) => {
  const allowedTypes = ['stl', 'obj', 'gltf', 'glb', 'step', 'stp']
  const ext = file.name.split('.').pop().toLowerCase()
  if (!allowedTypes.includes(ext)) {
    ElMessage.error('不支持的文件格式')
    return false
  }
  return true
}

const handleUploadSuccess = () => {
  ElMessage.success('模型上传成功')
  fetchModels()
}

// 窗口大小调整
const handleResize = () => {
  if (!renderer || !camera || !viewerContainer.value) return
  
  const width = Math.max(viewerContainer.value.clientWidth || 100, 100)
  const height = Math.max((viewerContainer.value.clientHeight || 100) - 60, 100)
  
  // 防止尺寸为0或负数导致WebGL错误
  if (width <= 0 || height <= 0) return
  
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

// 生命周期
onMounted(() => {
  fetchModels()
  nextTick(() => {
    initScene()
    window.addEventListener('resize', handleResize)
  })
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
  window.removeEventListener('resize', handleResize)
  
  // 清理Three.js资源
  if (renderer) {
    renderer.dispose()
  }
  if (controls) {
    controls.dispose()
  }
})
</script>

<style scoped>
.model-viewer-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
}

.node-label {
  font-size: 13px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-card {
  margin-top: 16px;
}

.viewer-card {
  height: calc(100vh - 180px);
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.viewer-tools {
  display: flex;
  gap: 12px;
}

.viewer-container {
  position: relative;
  height: calc(100% - 20px);
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 8px;
  overflow: hidden;
}

.empty-viewer,
.loading-viewer {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #909399;
}

.empty-viewer p,
.loading-viewer p {
  margin: 16px 0 0;
}

.empty-viewer .tips {
  font-size: 12px;
  color: #606266;
}

.model-canvas {
  width: 100%;
  height: 100%;
}

.color-panel {
  position: absolute;
  bottom: 16px;
  right: 16px;
  display: flex;
  gap: 8px;
  background: rgba(0, 0, 0, 0.5);
  padding: 8px;
  border-radius: 8px;
}

:deep(.el-card__body) {
  padding: 12px;
}
</style>
