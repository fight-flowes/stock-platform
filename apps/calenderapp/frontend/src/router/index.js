import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../utils/auth'
import CalendarView from '../views/CalendarView.vue'
import EventsView from '../views/EventsView.vue'
import StocksView from '../views/StocksView.vue'
import LimitUpView from '../views/LimitUpView.vue'
import LoginView from '../views/LoginView.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'limit-up',
    component: LimitUpView,
    meta: { requiresAuth: true }
  },
  {
    path: '/calendar',
    name: 'calendar',
    component: CalendarView,
    meta: { requiresAuth: true }
  },
  {
    path: '/events',
    name: 'events',
    component: EventsView,
    meta: { requiresAuth: true }
  },
  {
    path: '/stocks',
    name: 'stocks',
    component: StocksView,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录跳转到登录页
router.beforeEach((to, from, next) => {
  const requiresAuth = to.meta.requiresAuth !== false
  
  if (requiresAuth && !isAuthenticated()) {
    // 未登录，跳转到登录页
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (to.name === 'login' && isAuthenticated()) {
    // 已登录访问登录页，跳转到首页（涨停）
    next({ name: 'limit-up' })
  } else {
    next()
  }
})

export default router
