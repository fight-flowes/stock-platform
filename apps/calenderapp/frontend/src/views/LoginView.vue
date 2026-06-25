<template>
  <div class="login-page">
    <!-- 全局背景光晕（整页统一深色） -->
    <div class="page-bg-glow glow-1"></div>
    <div class="page-bg-glow glow-2"></div>

    <!-- 左侧：品牌展示区 -->
    <div class="brand-panel">
      <div class="brand-content">
        <div class="brand-top">
          <img :src="iconUrl" alt="Eventra" class="brand-logo-img" />
          <span class="brand-name">Eventra 投研平台</span>
        </div>

        <div class="brand-hero">
          <h2>以事件驱动，重构 A 股投研工作流</h2>
          <p class="brand-slogan">
            从涨停异动到事件核查，把分散的市场信号汇成可追溯的研究线索。
          </p>
        </div>

        <ul class="brand-features">
          <li>
            <span class="feature-icon">📊</span>
            <div class="feature-text">
              <div class="feature-title">涨停分析</div>
              <div class="feature-desc">连板、龙头、资金流向与概念热度全景</div>
            </div>
          </li>
          <li>
            <span class="feature-icon">🔍</span>
            <div class="feature-text">
              <div class="feature-title">AI 事件核查</div>
              <div class="feature-desc">联网检索 + 多维度验证事件真实性</div>
            </div>
          </li>
          <li>
            <span class="feature-icon">📅</span>
            <div class="feature-text">
              <div class="feature-title">交易日历</div>
              <div class="feature-desc">交易日、事件提醒与投研节奏管理</div>
            </div>
          </li>
        </ul>
      </div>
    </div>

    <!-- 右侧：登录表单区 -->
    <div class="form-panel">
      <div class="login-card">
        <div class="login-header">
          <div class="login-logo">
            <img :src="iconUrl" alt="Eventra" class="login-logo-img" />
          </div>
          <h1>欢迎回来</h1>
          <p class="subtitle">请输入访问 Token 登录平台</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="login-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="token">
            <el-input
              v-model="form.token"
              type="password"
              placeholder="请输入访问 Token"
              size="large"
              :prefix-icon="Key"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="login-btn"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <el-alert
          v-if="errorMsg"
          :title="errorMsg"
          type="error"
          :closable="false"
          show-icon
          class="error-alert"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Key } from '@element-plus/icons-vue'
import { login, isAuthenticated } from '../utils/auth'

// icon 位于 public/，按根路径引用
const iconUrl = '/eventra_icon.png'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  token: ''
})

const rules = {
  token: [
    { required: true, message: '请输入访问 Token', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    loading.value = true
    errorMsg.value = ''
    
    try {
      const result = login(form.token)
      
      if (result.success) {
        ElMessage.success('登录成功')
        router.push('/')
      } else {
        errorMsg.value = result.message
      }
    } catch (e) {
      errorMsg.value = '登录失败，请重试'
    } finally {
      loading.value = false
    }
  })
}

// 已登录则跳转首页
if (isAuthenticated()) {
  router.replace('/')
}
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  overflow: hidden;
  /* 整页统一浅色渐变背景 */
  background: linear-gradient(135deg, #f0f4f9 0%, #e6edf5 50%, #dde8f3 100%);
  color: #1f2d3d;
}

/* 整页背景光晕：让大面积渐变不死板 */
.page-bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.22;
  pointer-events: none;
  z-index: 0;
}

/* ===== 左侧品牌区 ===== */
.brand-panel {
  position: relative;
  z-index: 1;
  flex: 1.15;
  display: flex;
  align-items: center;
}

.glow-1 {
  width: 380px;
  height: 380px;
  background: #409eff;
  top: -120px;
  right: 28%;
}

.glow-2 {
  width: 300px;
  height: 300px;
  background: #2f7ed8;
  bottom: -100px;
  left: -60px;
  opacity: 0.18;
}

.brand-content {
  position: relative;
  z-index: 1;
  padding: 56px 64px;
  margin-left: auto;
  max-width: 660px;
  width: 100%;
}

.brand-top {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 64px;
}

.brand-logo-img {
  width: 76px;
  height: 76px;
  border-radius: 16px;
  display: block;
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.25);
}

.brand-name {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #1f2d3d;
}

.brand-hero h2 {
  font-size: 36px;
  font-weight: 800;
  line-height: 1.3;
  margin: 0 0 22px;
  color: #1a2a3a;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.brand-slogan {
  font-size: 16px;
  line-height: 1.85;
  color: rgba(31, 45, 61, 0.7);
  margin: 0 0 56px;
  white-space: nowrap;
}

.brand-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.brand-features li {
  display: flex;
  align-items: center;
  gap: 18px;
}

.feature-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  border-radius: 13px;
  background: rgba(64, 158, 255, 0.12);
}

.feature-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2d3d;
}

.feature-desc {
  margin-top: 3px;
  font-size: 13.5px;
  color: rgba(31, 45, 61, 0.55);
}

/* ===== 右侧表单区 ===== */
.form-panel {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.login-card {
  width: 380px;
  max-width: 100%;
  padding: 40px 36px;
  /* 白色实体卡片 */
  background: #ffffff;
  border: 1px solid rgba(31, 45, 61, 0.06);
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(53, 93, 138, 0.15);
}

.login-header {
  text-align: center;
  margin-bottom: 28px;
}

.login-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 16px;
  margin-bottom: 12px;
  overflow: hidden;
  box-shadow: 0 8px 20px rgba(64, 158, 255, 0.25);
}

.login-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.login-header h1 {
  margin: 8px 0 6px;
  font-size: 24px;
  font-weight: 700;
  color: #1f2d3d;
}

.login-header .subtitle {
  margin: 0;
  font-size: 13px;
  color: rgba(31, 45, 61, 0.55);
}

.login-form {
  margin-top: 8px;
}

.login-btn {
  width: 100%;
}

.error-alert {
  margin-top: 16px;
}

/* ===== 窄屏：隐藏品牌区，表单居中全屏 ===== */
@media (max-width: 860px) {
  .brand-panel {
    display: none;
  }

  .form-panel {
    flex: 1;
  }
}
</style>
