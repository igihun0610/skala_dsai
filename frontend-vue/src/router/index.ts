import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

// Import views
import Dashboard from '@/views/Dashboard.vue'
import Chat from '@/views/Chat.vue'
import Documents from '@/views/Documents.vue'
import Analytics from '@/views/Analytics.vue'
import Settings from '@/views/Settings.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: {
      title: '대시보드',
      icon: 'dashboard',
      description: '시스템 현황 및 최근 활동 요약'
    }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: Chat,
    meta: {
      title: '질의응답',
      icon: 'chat',
      description: 'AI 어시스턴트와의 대화형 질의응답'
    }
  },
  {
    path: '/documents',
    name: 'Documents',
    component: Documents,
    meta: {
      title: '문서 관리',
      icon: 'folder',
      description: 'PDF 문서 업로드 및 관리'
    }
  },
  {
    path: '/analytics',
    name: 'Analytics',
    component: Analytics,
    meta: {
      title: '분석',
      icon: 'analytics',
      description: '사용량 통계 및 성능 분석'
    }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: {
      title: '설정',
      icon: 'settings',
      description: '시스템 설정 및 사용자 환경설정'
    }
  },
  // Catch-all 404 route
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: {
      title: '페이지를 찾을 수 없음',
      icon: 'error',
      description: '요청한 페이지가 존재하지 않습니다'
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // Restore scroll position when navigating back
    if (savedPosition) {
      return savedPosition
    }
    // Scroll to top for new routes
    return { top: 0, behavior: 'smooth' }
  }
})

// Global navigation guards
router.beforeEach((to, from, next) => {
  // Set document title
  const defaultTitle = '제조업 데이터시트 RAG 시스템'
  document.title = to.meta?.title ? `${to.meta.title} - ${defaultTitle}` : defaultTitle

  // Continue navigation
  next()
})

// Error handling
router.onError((error) => {
  console.error('Router error:', error)
})

export default router