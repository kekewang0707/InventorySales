<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" style="background-color: #304156">
      <div style="height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.1)">
        InventorySales
      </div>
      <el-menu
        :default-active="currentRoute"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        style="border-right: none"
      >
        <el-menu-item index="/products">
          <el-icon><Goods /></el-icon>
          <span>产品管理</span>
        </el-menu-item>
        <el-menu-item index="/customers">
          <el-icon><User /></el-icon>
          <span>客户管理</span>
        </el-menu-item>
        <el-menu-item index="/delivery">
          <el-icon><Document /></el-icon>
          <span>送货单管理</span>
        </el-menu-item>
        <el-menu-item index="/statements">
          <el-icon><List /></el-icon>
          <span>客户对账单</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="height: 50px; line-height: 50px; border-bottom: 1px solid #e6e6e6; background: #fff; padding: 0 20px; font-size: 14px; color: #606266; display: flex; justify-content: space-between; align-items: center">
        <span>工厂销售出库管理系统</span>
        <el-tooltip content="AI 指令（Ctrl+K）" placement="bottom" effect="dark">
          <el-button
            :icon="Aim"
            circle
            size="small"
            @click="aiPanelRef?.toggle()"
          />
        </el-tooltip>
      </el-header>
      <el-main style="background: #f0f2f5; padding: 20px">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <AiCommandPanel ref="aiPanelRef" />
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Aim } from '@element-plus/icons-vue'
import AiCommandPanel from '../views/ai/AiCommandPanel.vue'

const route = useRoute()
const currentRoute = computed(() => route.path)
const aiPanelRef = ref(null)
</script>
