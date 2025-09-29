import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type UserRole = 'engineer' | 'quality' | 'sales' | 'support'

export interface UserPreferences {
  theme: 'auto' | 'light' | 'dark'
  language: 'ko' | 'en'
  notifications: boolean
  autoRefresh: boolean
  refreshInterval: number // seconds
  defaultTopK: number
  showConfidenceScore: boolean
  compactMode: boolean
}

export const useUserStore = defineStore('user', () => {
  // State
  const currentRole = ref<UserRole>('engineer')

  const preferences = ref<UserPreferences>({
    theme: 'auto',
    language: 'ko',
    notifications: true,
    autoRefresh: true,
    refreshInterval: 30,
    defaultTopK: 5,
    showConfidenceScore: true,
    compactMode: false
  })

  const isInitialized = ref(false)

  // Role definitions
  const roleDefinitions = {
    engineer: {
      label: '엔지니어',
      icon: 'engineering',
      color: 'primary',
      description: '기술적 세부사항과 사양에 중점을 둔 답변',
      prompts: [
        '이 제품의 기술 사양은?',
        '동작 전압과 주파수는?',
        '인터페이스 및 핀 구성은?',
        '전력 소모량은 얼마인가요?'
      ]
    },
    quality: {
      label: '품질관리',
      icon: 'verified',
      color: 'positive',
      description: '품질 기준과 한계치, 테스트 조건 중심 답변',
      prompts: [
        '품질 기준과 허용 오차는?',
        '테스트 조건과 방법은?',
        '내구성과 수명은?',
        '품질 인증 정보는?'
      ]
    },
    sales: {
      label: '영업',
      icon: 'business',
      color: 'secondary',
      description: '제품 특징과 장점, 경쟁 우위 중심 답변',
      prompts: [
        '제품의 주요 특징은?',
        '경쟁사 대비 장점은?',
        '적용 분야와 사례는?',
        '가격 경쟁력은?'
      ]
    },
    support: {
      label: '고객지원',
      icon: 'support_agent',
      color: 'warning',
      description: '문제해결과 호환성, 실용적 해결책 중심 답변',
      prompts: [
        '설치 및 설정 방법은?',
        '호환성 문제 해결법은?',
        '자주 발생하는 문제는?',
        'A/S 및 지원 정보는?'
      ]
    }
  }

  // Computed
  const roleOptions = computed(() =>
    Object.entries(roleDefinitions).map(([value, def]) => ({
      label: def.label,
      value,
      icon: def.icon,
      description: def.description
    }))
  )

  const currentRoleInfo = computed(() => roleDefinitions[currentRole.value])

  const currentRolePrompts = computed(() => currentRoleInfo.value.prompts)

  // Actions
  const setRole = (role: UserRole) => {
    currentRole.value = role
    saveToLocalStorage()
  }

  const updatePreferences = (newPreferences: Partial<UserPreferences>) => {
    preferences.value = { ...preferences.value, ...newPreferences }
    saveToLocalStorage()
  }

  const resetPreferences = () => {
    preferences.value = {
      theme: 'auto',
      language: 'ko',
      notifications: true,
      autoRefresh: true,
      refreshInterval: 30,
      defaultTopK: 5,
      showConfidenceScore: true,
      compactMode: false
    }
    saveToLocalStorage()
  }

  const getRoleLabel = (role: UserRole) => {
    return roleDefinitions[role]?.label || role
  }

  const getRoleIcon = (role: UserRole) => {
    return roleDefinitions[role]?.icon || 'person'
  }

  const getRoleColor = (role: UserRole) => {
    return roleDefinitions[role]?.color || 'primary'
  }

  const saveToLocalStorage = () => {
    const data = {
      currentRole: currentRole.value,
      preferences: preferences.value
    }
    localStorage.setItem('userStore', JSON.stringify(data))
  }

  const loadFromLocalStorage = () => {
    try {
      const saved = localStorage.getItem('userStore')
      if (saved) {
        const data = JSON.parse(saved)

        if (data.currentRole && roleDefinitions[data.currentRole as UserRole]) {
          currentRole.value = data.currentRole
        }

        if (data.preferences) {
          preferences.value = { ...preferences.value, ...data.preferences }
        }
      }
    } catch (error) {
      console.warn('Failed to load user preferences:', error)
    }
  }

  const initialize = async () => {
    if (isInitialized.value) return

    loadFromLocalStorage()
    isInitialized.value = true
  }

  const exportSettings = () => {
    return {
      role: currentRole.value,
      preferences: preferences.value,
      exportedAt: new Date().toISOString()
    }
  }

  const importSettings = (settings: any) => {
    try {
      if (settings.role && roleDefinitions[settings.role as UserRole]) {
        currentRole.value = settings.role
      }

      if (settings.preferences) {
        preferences.value = { ...preferences.value, ...settings.preferences }
      }

      saveToLocalStorage()
      return true
    } catch (error) {
      console.error('Failed to import settings:', error)
      return false
    }
  }

  return {
    // State
    currentRole,
    preferences,
    isInitialized,

    // Computed
    roleOptions,
    currentRoleInfo,
    currentRolePrompts,

    // Actions
    setRole,
    updatePreferences,
    resetPreferences,
    getRoleLabel,
    getRoleIcon,
    getRoleColor,
    initialize,
    exportSettings,
    importSettings
  }
})