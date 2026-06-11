<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <el-icon :size="48" color="#409EFF"><Calendar /></el-icon>
        <h1>A股投研数据平台</h1>
        <p class="version">v5.1</p>
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
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Calendar, Key } from '@element-plus/icons-vue'
import { login, isAuthenticated } from '../utils/auth'

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
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  margin: 16px 0 8px;
  font-size: 24px;
  color: #303133;
}

.login-header .version {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.login-form {
  margin-top: 24px;
}

.login-btn {
  width: 100%;
}

.error-alert {
  margin-top: 16px;
}

/* 暗色模式 */
:root.dark .login-container {
  background: linear-gradient(135deg, #0d0d0d 0%, #1a1a1a 50%, #262626 100%);
}

:root.dark .login-card {
  background: rgba(40, 40, 40, 0.95);
}

:root.dark .login-header h1 {
  color: #e5eaf3;
}

:root.dark .login-header .version {
  color: #6b6b6b;
}
</style>
