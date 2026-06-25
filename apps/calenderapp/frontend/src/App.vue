<template>
  <!-- 登录页：纯全屏布局，不套导航栏壳 -->
  <router-view v-if="isBareLayout" />

  <!-- 其它页面：带顶部导航栏的完整布局 -->
  <template v-else>
    <el-container class="app-shell">
      <el-header class="app-header">
        <div class="app-title">
          <img src="/eventra_icon.png" alt="Eventra" class="app-title-logo" />
          <span>Eventra 投研平台</span>
        </div>
        <div class="app-header-actions">
          <div class="app-primary-nav">
            <el-button text @click="$router.push('/')">涨停</el-button>
            <el-button text @click="$router.push('/announcements')">公告</el-button>
            <el-button text @click="$router.push('/events')">事件</el-button>
            <el-button text @click="$router.push('/stocks')">股票</el-button>
            <el-button text @click="$router.push('/calendar')">日历</el-button>
          </div>
          <el-divider direction="vertical" class="app-header-divider" />
          <el-button text class="analysis-button" aria-label="Eventra" @click="openAnalysisDrawer">
            <span class="analysis-button-text">Eventra</span>
          </el-button>
          <el-divider direction="vertical" class="app-header-divider" />
          <el-switch
            v-model="isDark"
            inline-prompt
            active-text="暗"
            inactive-text="亮"
            @change="onThemeToggle"
          />
          <el-divider direction="vertical" class="app-header-divider" />
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
    <AnalysisDrawer ref="analysisDrawerRef" />
  </template>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, SwitchButton } from '@element-plus/icons-vue'
import AnalysisDrawer from './components/AnalysisDrawer.vue'
import { applyTheme, getTheme } from './utils/theme'
import { logout } from './utils/auth'

const router = useRouter()
const route = useRoute()

// 登录页等"无壳"路由：不渲染顶部导航栏，用全屏独立布局。
// 这样未登录用户看不到导航栏，也不暴露系统有哪些功能模块。
const isBareLayout = computed(() => route.name === 'login')

const isDark = ref(getTheme() === 'dark')
const analysisDrawerRef = ref(null)

function onThemeToggle(v) {
  applyTheme(v ? 'dark' : 'light')
}

function openAnalysisDrawer() {
  analysisDrawerRef.value?.openDrawer?.()
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

<style scoped>
.app-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-primary-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-header-divider {
  height: 18px;
  margin: 0 8px;
  border-color: var(--el-border-color);
}

.analysis-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  padding: 8px;
}

.analysis-button-text {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.app-header-actions :deep(.el-button.is-text) {
  color: rgba(255, 255, 255, 0.88);
}

.app-header-actions :deep(.el-button.is-text:hover),
.app-header-actions :deep(.el-button.is-text:focus-visible) {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}

.app-header-actions :deep(.el-button.is-text .el-icon) {
  color: inherit;
}

.app-header-actions :deep(.el-switch__label) {
  color: rgba(255, 255, 255, 0.78);
}

.app-header-actions :deep(.el-switch__label.is-active) {
  color: #ffffff;
}
</style>
