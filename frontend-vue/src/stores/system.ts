import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/services/api'

export interface SystemHealth {
  status: 'healthy' | 'unhealthy' | 'unknown'
  timestamp: string
  components: {
    api: boolean
    ollama: boolean
    vector_db: boolean
    database: boolean
  }
}

export interface SystemStatus {
  ollama_status: 'healthy' | 'unhealthy'
  vector_db_status: 'healthy' | 'empty' | 'unhealthy'
  documents_count: number
  total_chunks: number
  last_activity: string | null
}

export const useSystemStore = defineStore('system', () => {
  // State
  const health = ref<SystemHealth>({
    status: 'unknown',
    timestamp: new Date().toISOString(),
    components: {
      api: false,
      ollama: false,
      vector_db: false,
      database: false
    }
  })

  const status = ref<SystemStatus>({
    ollama_status: 'unhealthy',
    vector_db_status: 'empty',
    documents_count: 0,
    total_chunks: 0,
    last_activity: null
  })

  const isRefreshing = ref(false)
  const lastHealthCheck = ref<Date | null>(null)
  const currentModel = ref<string>('qwen2:0.5b')

  // Computed
  const statusColor = computed(() => {
    switch (health.value.status) {
      case 'healthy':
        return 'positive'
      case 'unhealthy':
        return 'negative'
      default:
        return 'warning'
    }
  })

  const statusIcon = computed(() => {
    switch (health.value.status) {
      case 'healthy':
        return 'check_circle'
      case 'unhealthy':
        return 'error'
      default:
        return 'help'
    }
  })

  const statusText = computed(() => {
    switch (health.value.status) {
      case 'healthy':
        return '정상'
      case 'unhealthy':
        return '오류'
      default:
        return '확인중'
    }
  })

  const isHealthy = computed(() => health.value.status === 'healthy')

  const systemMetrics = computed(() => ({
    documentsCount: status.value.documents_count,
    chunksCount: status.value.total_chunks,
    ollamaStatus: status.value.ollama_status,
    vectorDbStatus: status.value.vector_db_status,
    lastActivity: status.value.last_activity
  }))

  // Actions
  const checkSystemHealth = async () => {
    try {
      isRefreshing.value = true

      // Check health endpoint
      const healthResponse = await api.get('/health')
      health.value = {
        status: healthResponse.data.status === 'healthy' ? 'healthy' : 'unhealthy',
        timestamp: new Date().toISOString(),
        components: {
          api: true,
          ollama: healthResponse.data.ollama_available || false,
          vector_db: healthResponse.data.vector_db_available || false,
          database: healthResponse.data.database_available || false
        }
      }

      // Check detailed status
      const statusResponse = await api.get('/status')
      status.value = statusResponse.data

      lastHealthCheck.value = new Date()

    } catch (error) {
      console.error('Health check failed:', error)
      health.value = {
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        components: {
          api: false,
          ollama: false,
          vector_db: false,
          database: false
        }
      }
    } finally {
      isRefreshing.value = false
    }
  }

  const initialize = async () => {
    await checkSystemHealth()

    // Set current model (from environment or default)
    currentModel.value = 'qwen2:0.5b'
  }

  const resetSystem = async () => {
    try {
      // Reset local state
      health.value = {
        status: 'unknown',
        timestamp: new Date().toISOString(),
        components: {
          api: false,
          ollama: false,
          vector_db: false,
          database: false
        }
      }

      // Re-check system health
      await checkSystemHealth()
      return true
    } catch (error) {
      console.error('System reset failed:', error)
      return false
    }
  }

  const runSelfTest = async () => {
    try {
      const response = await api.post('/selftest/run')
      await checkSystemHealth()
      return response.data
    } catch (error) {
      console.error('Self test failed:', error)
      throw error
    }
  }

  return {
    // State
    health,
    status,
    isRefreshing,
    lastHealthCheck,
    currentModel,

    // Computed
    statusColor,
    statusIcon,
    statusText,
    isHealthy,
    systemMetrics,

    // Actions
    checkSystemHealth,
    initialize,
    resetSystem,
    runSelfTest
  }
})