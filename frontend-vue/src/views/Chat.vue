<template>
  <q-page class="q-pa-md">
    <div class="text-h4 q-mb-lg">질의응답</div>

    <div class="row" style="height: calc(100vh - 150px)">
      <!-- Chat Messages Area -->
      <div class="col-12 col-sm-9 q-pr-md">
        <q-card class="full-height">
          <q-card-section class="q-pa-none full-height">
            <!-- Messages Container -->
            <div class="q-pa-md" style="height: calc(100% - 120px); overflow-y: auto;">
              <div v-if="!chatStore.hasMessages" class="text-center q-mt-xl">
                <q-icon name="chat" size="60px" color="grey-5" />
                <div class="text-h6 q-mt-md text-grey-6">대화를 시작해보세요!</div>
                <div class="text-body2 text-grey-5 q-mt-sm">
                  {{ userStore.currentRoleInfo.label }} 역할로 질문하실 수 있습니다.
                </div>
              </div>

              <!-- Messages -->
              <div v-for="message in chatStore.messages" :key="message.id" class="q-mb-md">
                <div v-if="message.type === 'user'" class="row justify-end">
                  <div class="col-8">
                    <q-card class="bg-primary text-white">
                      <q-card-section class="q-pa-sm">
                        <div class="text-caption">
                          <q-icon :name="userStore.getRoleIcon(message.role || 'engineer')" />
                          {{ userStore.getRoleLabel(message.role || 'engineer') }}
                        </div>
                        <div class="q-mt-xs">{{ message.content }}</div>
                      </q-card-section>
                    </q-card>
                    <div class="text-caption text-grey-6 q-mt-xs text-right">
                      {{ formatTime(message.timestamp) }}
                    </div>
                  </div>
                </div>

                <div v-else class="row">
                  <div class="col-8">
                    <q-card>
                      <q-card-section class="q-pa-sm">
                        <div class="text-caption text-grey-6">
                          <q-icon name="smart_toy" />
                          AI 어시스턴트
                        </div>
                        <div class="q-mt-xs">
                          <div v-if="message.isLoading" class="flex items-center">
                            <q-spinner color="primary" size="20px" class="q-mr-sm" />
                            답변 생성 중...
                          </div>
                          <div v-else>{{ message.content }}</div>
                        </div>

                        <!-- Metadata -->
                        <div v-if="message.metadata && !message.isLoading" class="q-mt-sm">
                          <div class="text-caption text-grey-6">
                            신뢰도: {{ (message.metadata.confidence * 100).toFixed(1) }}% |
                            처리시간: {{ message.metadata.query_time_ms }}ms |
                            모델: {{ message.metadata.model_used }}
                          </div>

                          <!-- Sources -->
                          <div v-if="message.metadata.sources && message.metadata.sources.length > 0" class="q-mt-sm">
                            <div class="text-caption text-grey-7 q-mb-xs">참조 문서:</div>
                            <div v-for="source in message.metadata.sources" :key="source.document_id" class="text-caption">
                              📄 {{ source.filename }} (페이지 {{ source.page_number }})
                            </div>
                          </div>
                        </div>

                        <!-- Error -->
                        <div v-if="message.error" class="text-negative q-mt-sm">
                          <q-icon name="error" /> {{ message.error }}
                        </div>
                      </q-card-section>

                      <!-- Actions -->
                      <q-card-actions v-if="!message.isLoading" align="right">
                        <q-btn flat dense icon="refresh" @click="regenerateMessage(message.id)" />
                      </q-card-actions>
                    </q-card>
                    <div class="text-caption text-grey-6 q-mt-xs">
                      {{ formatTime(message.timestamp) }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Input Area -->
            <div class="q-pa-md bg-grey-1">
              <!-- Role Selector -->
              <div class="q-mb-sm">
                <q-btn-toggle
                  v-model="userStore.currentRole"
                  :options="userStore.roleOptions"
                  color="primary"
                  dense
                  @update:model-value="onRoleChange"
                />
              </div>

              <!-- Quick Prompts -->
              <div class="q-mb-sm">
                <q-btn
                  v-for="prompt in userStore.currentRolePrompts"
                  :key="prompt"
                  @click="setQuestion(prompt)"
                  flat
                  dense
                  size="sm"
                  class="q-mr-xs q-mb-xs"
                  color="grey-7"
                >
                  {{ prompt }}
                </q-btn>
              </div>

              <!-- Input Field -->
              <div class="row q-gutter-sm">
                <div class="col">
                  <q-input
                    v-model="questionInput"
                    placeholder="질문을 입력하세요..."
                    outlined
                    dense
                    @keyup.enter="sendQuestion"
                    :loading="chatStore.isTyping"
                  />
                </div>
                <div>
                  <q-btn
                    color="primary"
                    icon="send"
                    @click="sendQuestion"
                    :loading="chatStore.isTyping"
                    :disable="!questionInput.trim()"
                  />
                </div>
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- Session History Sidebar -->
      <div class="col-12 col-sm-3">
        <q-card class="full-height">
          <q-card-section>
            <div class="row items-center q-mb-md">
              <div class="col">
                <div class="text-h6">대화 목록</div>
              </div>
              <div>
                <q-btn
                  color="primary"
                  icon="add"
                  dense
                  round
                  @click="createNewSession"
                />
              </div>
            </div>

            <q-list>
              <q-item
                v-for="session in chatStore.sessions"
                :key="session.id"
                clickable
                v-ripple
                :active="chatStore.currentSession?.id === session.id"
                @click="chatStore.switchToSession(session.id)"
              >
                <q-item-section avatar>
                  <q-icon :name="userStore.getRoleIcon(session.role)" :color="userStore.getRoleColor(session.role)" />
                </q-item-section>
                <q-item-section>
                  <q-item-label lines="1">{{ session.title }}</q-item-label>
                  <q-item-label caption>
                    {{ formatTime(session.updated_at) }} • {{ session.message_count }}개 메시지
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn flat round dense icon="more_vert">
                    <q-menu>
                      <q-list style="min-width: 100px">
                        <q-item clickable @click="exportSession(session.id)">
                          <q-item-section>내보내기</q-item-section>
                        </q-item>
                        <q-item clickable @click="deleteSession(session.id)">
                          <q-item-section>삭제</q-item-section>
                        </q-item>
                      </q-list>
                    </q-menu>
                  </q-btn>
                </q-item-section>
              </q-item>

              <q-item v-if="chatStore.sessions.length === 0">
                <q-item-section>
                  <div class="text-grey-6 text-center">아직 대화가 없습니다.</div>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'
import { format } from 'date-fns'

const $q = useQuasar()
const userStore = useUserStore()
const chatStore = useChatStore()

const questionInput = ref('')

const formatTime = (date: Date | null | undefined) => {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return '--:--'
  }
  return format(date, 'HH:mm')
}

const setQuestion = (question: string) => {
  questionInput.value = question
}

const sendQuestion = async () => {
  if (!questionInput.value.trim()) return

  try {
    await chatStore.sendQuestion(questionInput.value, userStore.currentRole)
    questionInput.value = ''
  } catch (error: any) {
    $q.notify({
      type: 'negative',
      message: '질문 처리 중 오류가 발생했습니다.',
      caption: error.message
    })
  }
}

const regenerateMessage = async (messageId: string) => {
  try {
    await chatStore.regenerateResponse(messageId)
  } catch (error: any) {
    $q.notify({
      type: 'negative',
      message: '답변 재생성 중 오류가 발생했습니다.',
      caption: error.message
    })
  }
}

const createNewSession = () => {
  chatStore.createNewSession(userStore.currentRole)
}

const deleteSession = (sessionId: string) => {
  $q.dialog({
    title: '대화 삭제',
    message: '이 대화를 삭제하시겠습니까?',
    cancel: true,
    persistent: true
  }).onOk(() => {
    chatStore.deleteSession(sessionId)
    $q.notify({
      type: 'positive',
      message: '대화가 삭제되었습니다.'
    })
  })
}

const exportSession = (sessionId: string) => {
  const sessionData = chatStore.exportSession(sessionId)
  if (sessionData) {
    const blob = new Blob([JSON.stringify(sessionData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `chat_session_${sessionId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }
}

const onRoleChange = (newRole: string) => {
  $q.notify({
    type: 'info',
    message: `역할이 "${userStore.getRoleLabel(newRole)}"로 변경되었습니다.`
  })
}

onMounted(() => {
  // Create initial session if none exists
  if (!chatStore.currentSession && chatStore.sessions.length === 0) {
    chatStore.createNewSession(userStore.currentRole)
  }
})
</script>