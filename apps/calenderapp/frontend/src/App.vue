<template>
  <el-container class="app-shell">
    <el-header class="app-header">
      <div class="app-title">
        <el-icon><Calendar /></el-icon>
        <span>A股投研 v5.1</span>
      </div>
      <div style="display: flex; align-items: center; gap: 8px">
        <el-button text @click="$router.push('/')">涨停</el-button>
        <el-button text @click="$router.push('/events')">事件</el-button>
        <el-button text @click="$router.push('/stocks')">股票</el-button>
        <el-button text @click="$router.push('/calendar')">日历</el-button>
        <el-divider direction="vertical" style="height: 18px; border-color: rgba(255,255,255,0.22)" />
        <el-switch
          v-model="isDark"
          inline-prompt
          active-text="暗"
          inactive-text="亮"
          @change="onThemeToggle"
        />
        <el-divider direction="vertical" style="height: 18px; border-color: rgba(255,255,255,0.22)" />
        <el-dropdown @command="handleCommand">
          <el-button text>
            <el-icon><User /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Calendar, User, SwitchButton } from '@element-plus/icons-vue'
import { applyTheme, getTheme } from './utils/theme'
import { logout } from './utils/auth'

const router = useRouter()
const isDark = ref(getTheme() === 'dark')

function onThemeToggle(v) {
  applyTheme(v ? 'dark' : 'light')
}

function handleCommand(command) {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    }).catch(() => {
      // 取消
    })
  }
}
</script>
