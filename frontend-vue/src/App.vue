<template>
  <q-layout view="lHh Lpr lFf" class="bg-grey-1">
    <!-- Header -->
    <q-header elevated class="bg-primary text-white" height-hint="64">
      <q-toolbar>
        <q-btn
          flat
          dense
          round
          icon="menu"
          aria-label="Menu"
          @click="toggleLeftDrawer"
        />

        <q-toolbar-title class="text-h6">
          <q-icon name="memory" class="q-mr-sm" size="sm" />
          제조업 데이터시트 RAG 시스템
        </q-toolbar-title>

        <!-- System Status Indicator -->
        <div class="q-mr-md">
          <q-chip
            :color="systemStore.statusColor"
            text-color="white"
            :icon="systemStore.statusIcon"
            size="sm"
          >
            {{ systemStore.statusText }}
          </q-chip>
        </div>

        <!-- User Role Selector -->
        <q-select
          v-model="userStore.currentRole"
          :options="userStore.roleOptions"
          outlined
          dense
          dark
          class="q-mr-md"
          style="min-width: 120px"
          emit-value
          map-options
          @update:model-value="onRoleChange"
        />

        <!-- Theme Toggle -->
        <q-btn
          flat
          dense
          round
          :icon="$q.dark.isActive ? 'light_mode' : 'dark_mode'"
          @click="toggleTheme"
        />

        <!-- Refresh Status -->
        <q-btn
          flat
          dense
          round
          icon="refresh"
          @click="refreshSystemStatus"
          :loading="systemStore.isRefreshing"
        />
      </q-toolbar>
    </q-header>

    <!-- Left Drawer -->
    <q-drawer
      v-model="leftDrawerOpen"
      show-if-above
      bordered
      class="bg-white"
      :width="260"
    >
      <q-list>
        <q-item-label header class="text-grey-8 text-weight-bold">
          메인 메뉴
        </q-item-label>

        <q-item
          v-for="item in menuItems"
          :key="item.path"
          clickable
          v-ripple
          :to="item.path"
          exact-active-class="bg-primary text-white"
          class="rounded-borders q-ma-xs"
        >
          <q-item-section avatar>
            <q-icon :name="item.icon" />
          </q-item-section>
          <q-item-section>
            <q-item-label>{{ item.label }}</q-item-label>
            <q-item-label caption>{{ item.caption }}</q-item-label>
          </q-item-section>
          <q-item-section side v-if="item.badge">
            <q-badge :color="item.badgeColor" :label="item.badge" />
          </q-item-section>
        </q-item>

        <q-separator class="q-my-md" />

        <q-item-label header class="text-grey-8 text-weight-bold">
          시스템
        </q-item-label>

        <q-item clickable v-ripple @click="showAboutDialog">
          <q-item-section avatar>
            <q-icon name="info" />
          </q-item-section>
          <q-item-section>
            <q-item-label>정보</q-item-label>
            <q-item-label caption>시스템 정보</q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <!-- Main Content -->
    <q-page-container>
      <router-view v-slot="{ Component }">
        <transition
          name="fade"
          mode="out-in"
          enter-active-class="animated fadeIn"
          leave-active-class="animated fadeOut"
        >
          <component :is="Component" />
        </transition>
      </router-view>
    </q-page-container>

    <!-- Footer -->
    <q-footer bordered class="bg-white text-primary">
      <q-toolbar class="q-py-sm">
        <div class="text-caption">
          © 2024 Manufacturing DataSheet RAG System v{{ appVersion }}
        </div>
        <q-space />
        <div class="text-caption text-grey-6">
          Powered by Vue 3 + Quasar + qwen2:0.5b
        </div>
      </q-toolbar>
    </q-footer>

    <!-- About Dialog -->
    <q-dialog v-model="showAbout">
      <q-card style="min-width: 350px">
        <q-card-section>
          <div class="text-h6">제조업 데이터시트 RAG 시스템</div>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <div class="text-body2 q-mb-md">
            지능형 문서 검색 및 질의응답 시스템
          </div>
          <q-list dense>
            <q-item>
              <q-item-section>
                <q-item-label caption>버전</q-item-label>
                <q-item-label>{{ appVersion }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section>
                <q-item-label caption>프론트엔드</q-item-label>
                <q-item-label>Vue 3 + Quasar Framework</q-item-label>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section>
                <q-item-label caption>백엔드</q-item-label>
                <q-item-label>FastAPI + Ollama</q-item-label>
              </q-item-section>
            </q-item>
            <q-item>
              <q-item-section>
                <q-item-label caption>모델</q-item-label>
                <q-item-label>{{ systemStore.currentModel || 'qwen2:0.5b' }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="닫기" color="primary" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useRouter } from 'vue-router'
import { useSystemStore } from '@/stores/system'
import { useUserStore } from '@/stores/user'
import { useDocumentsStore } from '@/stores/documents'

const $q = useQuasar()
const router = useRouter()
const systemStore = useSystemStore()
const userStore = useUserStore()
const documentsStore = useDocumentsStore()

// Layout state
const leftDrawerOpen = ref(false)
const showAbout = ref(false)

// App info
const appVersion = '1.0.0'

// Menu items
const menuItems = computed(() => [
  {
    path: '/',
    icon: 'dashboard',
    label: '대시보드',
    caption: '시스템 현황',
    badge: null,
    badgeColor: 'primary'
  },
  {
    path: '/chat',
    icon: 'chat',
    label: '질의응답',
    caption: 'AI 어시스턴트',
    badge: null,
    badgeColor: 'secondary'
  },
  {
    path: '/documents',
    icon: 'folder',
    label: '문서 관리',
    caption: 'PDF 업로드/관리',
    badge: documentsStore.totalDocuments > 0 ? documentsStore.totalDocuments.toString() : null,
    badgeColor: 'positive'
  },
  {
    path: '/analytics',
    icon: 'analytics',
    label: '분석',
    caption: '사용량 통계',
    badge: null,
    badgeColor: 'warning'
  },
  {
    path: '/settings',
    icon: 'settings',
    label: '설정',
    caption: '시스템 설정',
    badge: null,
    badgeColor: 'info'
  }
])

// Methods
const toggleLeftDrawer = () => {
  leftDrawerOpen.value = !leftDrawerOpen.value
}

const toggleTheme = () => {
  $q.dark.toggle()
  localStorage.setItem('theme', $q.dark.isActive ? 'dark' : 'light')
}

const refreshSystemStatus = async () => {
  await systemStore.checkSystemHealth()
  $q.notify({
    type: 'positive',
    message: '시스템 상태가 업데이트되었습니다.',
    timeout: 2000
  })
}

const onRoleChange = (newRole: string) => {
  $q.notify({
    type: 'info',
    message: `사용자 역할이 "${userStore.getRoleLabel(newRole)}"로 변경되었습니다.`,
    timeout: 2000
  })
}

const showAboutDialog = () => {
  showAbout.value = true
}

// Lifecycle
onMounted(async () => {
  // Load theme preference
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme === 'dark') {
    $q.dark.set(true)
  }

  // Initialize stores
  await Promise.all([
    systemStore.initialize(),
    userStore.initialize(),
    documentsStore.loadDocuments()
  ])

  // Setup periodic status checks
  setInterval(() => {
    systemStore.checkSystemHealth()
  }, 30000) // Check every 30 seconds
})
</script>

<style scoped>
.animated {
  animation-duration: 0.3s;
  animation-fill-mode: both;
}

.fadeIn {
  animation-name: fadeIn;
}

.fadeOut {
  animation-name: fadeOut;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes fadeOut {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
</style>