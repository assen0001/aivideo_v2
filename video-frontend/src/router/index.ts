/** 路由表 + 守卫（token / needSetup） */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      redirect: '/create',
      children: [
        { path: 'create', name: 'create', component: () => import('@/views/CreateView.vue'), meta: { title: '创作' } },
        { path: 'projects', name: 'projects', component: () => import('@/views/ProjectsView.vue'), meta: { title: '项目' } },
        { path: 'projects/:id', name: 'project-detail', component: () => import('@/views/ProjectDetailView.vue'), meta: { title: '项目详情' } },
        { path: 'assets-list', name: 'assets', component: () => import('@/views/AssetsView.vue'), meta: { title: '资产' } },
        { path: 'tutorials', name: 'tutorials', component: () => import('@/views/TutorialsView.vue'), meta: { title: '教程' } },
        { path: 'tutorials/:id', name: 'tutorial-detail', component: () => import('@/views/TutorialDetailView.vue'), meta: { title: '教程详情' } },
        { path: 'tutorials/edit', name: 'tutorial-edit', component: () => import('@/views/TutorialEditView.vue'), meta: { title: '发布教程' } },
        { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '配置' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/create' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.path !== '/login') {
    if (!auth.token) {
      await auth.init()
      if (!auth.token) {
        return { path: '/login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
      }
    }
  } else if (auth.token) {
    return '/create'
  }
  return true
})

export default router
