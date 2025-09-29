import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/services/api'
import type { UserRole } from './user'

export interface ChatMessage {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  role?: UserRole
  metadata?: {
    confidence?: number
    sources?: Array<{
      document_id: string
      filename: string
      page_number: number
      score: number
    }>
    query_time_ms?: number
    model_used?: string
  }
  isLoading?: boolean
  error?: string
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  created_at: Date
  updated_at: Date
  role: UserRole
  message_count: number
}

export interface QueryRequest {
  question: string
  user_role: UserRole
  top_k?: number
  context_length?: number
}

export interface QueryResponse {
  answer: string
  confidence: number
  sources: Array<{
    document_id: string
    filename: string
    page_number: number
    score: number
    content: string
  }>
  query_time_ms: number
  model_used: string
}

export const useChatStore = defineStore('chat', () => {
  // State
  const currentSession = ref<ChatSession | null>(null)
  const sessions = ref<ChatSession[]>([])
  const isTyping = ref(false)
  const isLoading = ref(false)
  const streamingMessage = ref<string>('')

  // Current conversation state
  const messages = computed(() => currentSession.value?.messages || [])
  const messageCount = computed(() => messages.value.length)
  const hasMessages = computed(() => messageCount.value > 0)

  // Session statistics
  const totalSessions = computed(() => sessions.value.length)
  const totalMessages = computed(() =>
    sessions.value.reduce((sum, session) => sum + session.message_count, 0)
  )

  const recentSessions = computed(() =>
    sessions.value
      .sort((a, b) => b.updated_at.getTime() - a.updated_at.getTime())
      .slice(0, 10)
  )

  // Actions
  const createNewSession = (role: UserRole, title?: string) => {
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    const now = new Date()

    const newSession: ChatSession = {
      id: sessionId,
      title: title || `새 대화 (${new Date().toLocaleString()})`,
      messages: [],
      created_at: now,
      updated_at: now,
      role,
      message_count: 0
    }

    sessions.value.unshift(newSession)
    currentSession.value = newSession
    saveSessionsToStorage()

    return newSession
  }

  const switchToSession = (sessionId: string) => {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      currentSession.value = session
    }
  }

  const deleteSession = (sessionId: string) => {
    const index = sessions.value.findIndex(s => s.id === sessionId)
    if (index !== -1) {
      sessions.value.splice(index, 1)

      // If deleting current session, switch to most recent or create new
      if (currentSession.value?.id === sessionId) {
        if (sessions.value.length > 0) {
          currentSession.value = sessions.value[0]
        } else {
          currentSession.value = null
        }
      }

      saveSessionsToStorage()
    }
  }

  const addMessage = (message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    if (!currentSession.value) {
      throw new Error('No active session')
    }

    const newMessage: ChatMessage = {
      ...message,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date()
    }

    currentSession.value.messages.push(newMessage)
    currentSession.value.message_count = currentSession.value.messages.length
    currentSession.value.updated_at = new Date()

    // Auto-generate title from first user message
    if (currentSession.value.messages.length === 1 && message.type === 'user') {
      currentSession.value.title = message.content.slice(0, 50) + (message.content.length > 50 ? '...' : '')
    }

    saveSessionsToStorage()
    return newMessage
  }

  const updateMessage = (messageId: string, updates: Partial<ChatMessage>) => {
    if (!currentSession.value) return

    const messageIndex = currentSession.value.messages.findIndex(m => m.id === messageId)
    if (messageIndex !== -1) {
      currentSession.value.messages[messageIndex] = {
        ...currentSession.value.messages[messageIndex],
        ...updates
      }
      currentSession.value.updated_at = new Date()
      saveSessionsToStorage()
    }
  }

  const removeMessage = (messageId: string) => {
    if (!currentSession.value) return

    const messageIndex = currentSession.value.messages.findIndex(m => m.id === messageId)
    if (messageIndex !== -1) {
      currentSession.value.messages.splice(messageIndex, 1)
      currentSession.value.message_count = currentSession.value.messages.length
      currentSession.value.updated_at = new Date()
      saveSessionsToStorage()
    }
  }

  const sendQuestion = async (question: string, role: UserRole, options?: {
    top_k?: number
    context_length?: number
  }) => {
    if (!currentSession.value) {
      createNewSession(role)
    }

    // Add user message
    const userMessage = addMessage({
      type: 'user',
      content: question,
      role
    })

    // Add loading assistant message
    const loadingMessage = addMessage({
      type: 'assistant',
      content: '',
      isLoading: true
    })

    try {
      isTyping.value = true

      const request: QueryRequest = {
        question,
        user_role: role,
        top_k: options?.top_k || 5,
        context_length: options?.context_length
      }

      const response = await api.post<QueryResponse>('/query', request)
      const data = response.data

      // Update loading message with response
      updateMessage(loadingMessage.id, {
        content: data.answer,
        isLoading: false,
        metadata: {
          confidence: data.confidence,
          sources: data.sources,
          query_time_ms: data.query_time_ms,
          model_used: data.model_used
        }
      })

      return data

    } catch (error: any) {
      console.error('Query failed:', error)

      // Update loading message with error
      updateMessage(loadingMessage.id, {
        content: '죄송합니다. 답변을 생성하는 중 오류가 발생했습니다.',
        isLoading: false,
        error: error.message || '알 수 없는 오류'
      })

      throw error

    } finally {
      isTyping.value = false
    }
  }

  const regenerateResponse = async (messageId: string) => {
    if (!currentSession.value) return

    const messageIndex = currentSession.value.messages.findIndex(m => m.id === messageId)
    if (messageIndex === -1) return

    const assistantMessage = currentSession.value.messages[messageIndex]
    if (assistantMessage.type !== 'assistant') return

    // Find the previous user message
    let userMessage
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (currentSession.value.messages[i].type === 'user') {
        userMessage = currentSession.value.messages[i]
        break
      }
    }

    if (!userMessage) return

    // Update message to loading state
    updateMessage(messageId, {
      content: '',
      isLoading: true,
      error: undefined
    })

    try {
      isTyping.value = true

      const request: QueryRequest = {
        question: userMessage.content,
        user_role: userMessage.role || 'engineer'
      }

      const response = await api.post<QueryResponse>('/query', request)
      const data = response.data

      updateMessage(messageId, {
        content: data.answer,
        isLoading: false,
        metadata: {
          confidence: data.confidence,
          sources: data.sources,
          query_time_ms: data.query_time_ms,
          model_used: data.model_used
        }
      })

    } catch (error: any) {
      console.error('Regeneration failed:', error)

      updateMessage(messageId, {
        content: '답변 재생성 중 오류가 발생했습니다.',
        isLoading: false,
        error: error.message || '알 수 없는 오류'
      })
    } finally {
      isTyping.value = false
    }
  }

  const clearCurrentSession = () => {
    if (currentSession.value) {
      currentSession.value.messages = []
      currentSession.value.message_count = 0
      currentSession.value.updated_at = new Date()
      saveSessionsToStorage()
    }
  }

  const exportSession = (sessionId?: string) => {
    const session = sessionId
      ? sessions.value.find(s => s.id === sessionId)
      : currentSession.value

    if (!session) return null

    return {
      id: session.id,
      title: session.title,
      created_at: session.created_at.toISOString(),
      updated_at: session.updated_at.toISOString(),
      role: session.role,
      messages: session.messages.map(msg => ({
        type: msg.type,
        content: msg.content,
        timestamp: msg.timestamp.toISOString(),
        role: msg.role,
        metadata: msg.metadata
      }))
    }
  }

  const importSession = (sessionData: any) => {
    try {
      const session: ChatSession = {
        id: sessionData.id || `imported_${Date.now()}`,
        title: sessionData.title || '가져온 대화',
        created_at: sessionData.created_at ? new Date(sessionData.created_at) : new Date(),
        updated_at: sessionData.updated_at ? new Date(sessionData.updated_at) : new Date(),
        role: sessionData.role || 'engineer',
        message_count: sessionData.messages?.length || 0,
        messages: sessionData.messages?.map((msg: any) => ({
          id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: msg.type,
          content: msg.content,
          timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
          role: msg.role,
          metadata: msg.metadata
        })) || []
      }

      sessions.value.unshift(session)
      saveSessionsToStorage()
      return session

    } catch (error) {
      console.error('Failed to import session:', error)
      throw error
    }
  }

  const saveSessionsToStorage = () => {
    try {
      const data = {
        currentSessionId: currentSession.value?.id || null,
        sessions: sessions.value.map(session => ({
          ...session,
          created_at: session.created_at.toISOString(),
          updated_at: session.updated_at.toISOString(),
          messages: session.messages.map(msg => ({
            ...msg,
            timestamp: msg.timestamp.toISOString()
          }))
        }))
      }
      localStorage.setItem('chatSessions', JSON.stringify(data))
    } catch (error) {
      console.warn('Failed to save sessions:', error)
    }
  }

  const loadSessionsFromStorage = () => {
    try {
      const saved = localStorage.getItem('chatSessions')
      if (saved) {
        const data = JSON.parse(saved)

        sessions.value = data.sessions.map((session: any) => ({
          ...session,
          created_at: session.created_at ? new Date(session.created_at) : new Date(),
          updated_at: session.updated_at ? new Date(session.updated_at) : new Date(),
          messages: session.messages.map((msg: any) => ({
            ...msg,
            timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date()
          }))
        }))

        if (data.currentSessionId) {
          currentSession.value = sessions.value.find(s => s.id === data.currentSessionId) || null
        }
      }
    } catch (error) {
      console.warn('Failed to load sessions:', error)
    }
  }

  const initialize = () => {
    loadSessionsFromStorage()
  }

  return {
    // State
    currentSession,
    sessions,
    isTyping,
    isLoading,
    streamingMessage,

    // Computed
    messages,
    messageCount,
    hasMessages,
    totalSessions,
    totalMessages,
    recentSessions,

    // Actions
    createNewSession,
    switchToSession,
    deleteSession,
    addMessage,
    updateMessage,
    removeMessage,
    sendQuestion,
    regenerateResponse,
    clearCurrentSession,
    exportSession,
    importSession,
    initialize
  }
})