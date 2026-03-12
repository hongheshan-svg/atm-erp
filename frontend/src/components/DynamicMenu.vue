<template>
  <template v-for="menu in menus" :key="menu.code">
    <!-- 有子菜单 -->
    <el-sub-menu v-if="menu.children && menu.children.length > 0" :index="menu.code">
      <template #title>
        <el-icon v-if="menu.icon">
          <component :is="menu.icon" />
        </el-icon>
        <span>{{ menu.name }}</span>
      </template>
      <DynamicMenu :menus="menu.children" />
    </el-sub-menu>

    <!-- 无子菜单 -->
    <el-menu-item v-else :index="menu.route">
      <el-icon v-if="menu.icon">
        <component :is="menu.icon" />
      </el-icon>
      <span>{{ menu.name }}</span>
    </el-menu-item>
  </template>
</template>

<script setup>
import { defineProps } from 'vue'

defineProps({
  menus: {
    type: Array,
    default: () => []
  }
})
</script>
