<template>
  <q-page class="q-pa-md">
    <div class="text-h4 q-mb-lg">설정</div>

    <div class="row ">
      <!-- User Preferences -->
      <div class="col-12 col-sm-6 q-pa-sm">
        <q-card>
          <q-card-section>
            <div class="text-h6 q-mb-md">사용자 설정</div>

            <q-form @submit="savePreferences">
              <q-select
                v-model="preferences.theme"
                :options="themeOptions"
                label="테마"
                outlined
                emit-value
                map-options
                class="q-mb-md"
              />

              <q-select
                v-model="preferences.language"
                :options="languageOptions"
                label="언어"
                outlined
                emit-value
                map-options
                class="q-mb-md"
              />

              <q-toggle
                v-model="preferences.notifications"
                label="알림 활성화"
                class="q-mb-md"
              />

              <q-toggle
                v-model="preferences.autoRefresh"
                label="자동 새로고침"
                class="q-mb-md"
              />

              <q-input
                v-model.number="preferences.refreshInterval"
                type="number"
                label="새로고침 간격 (초)"
                outlined
                class="q-mb-md"
                :min="5"
                :max="300"
                :disable="!preferences.autoRefresh"
              />

              <q-input
                v-model.number="preferences.defaultTopK"
                type="number"
                label="기본 검색 결과 수"
                outlined
                class="q-mb-md"
                :min="1"
                :max="20"
              />

              <q-toggle
                v-model="preferences.showConfidenceScore"
                label="신뢰도 점수 표시"
                class="q-mb-md"
              />

              <q-toggle
                v-model="preferences.compactMode"
                label="컴팩트 모드"
                class="q-mb-md"
              />

              <div class="q-gutter-sm">
                <q-btn type="submit" color="primary" label="저장" />
                <q-btn @click="resetPreferences" color="grey" label="초기화" />
              </div>
            </q-form>
          </q-card-section>
        </q-card>
      </div>

      <!-- System Information -->
      <div class="col-12 col-sm-6 q-pa-sm">
        <q-card>
          <q-card-section>
            <div class="text-h6 q-mb-md">시스템 정보</div>
            <q-list>
              <q-item>
                <q-item-section>
                  <q-item-label>애플리케이션 버전</q-item-label>
                  <q-item-label caption>v1.0.0</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label>모델</q-item-label>
                  <q-item-label caption>{{ systemStore.currentModel }}</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label>시스템 상태</q-item-label>
                  <q-item-label caption>{{ systemStore.statusText }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-chip
                    :color="systemStore.statusColor"
                    text-color="white"
                    size="sm"
                  >
                    {{ systemStore.statusText }}
                  </q-chip>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label>마지막 상태 확인</q-item-label>
                  <q-item-label caption>{{ formatDate(systemStore.lastHealthCheck) }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn
                    flat
                    round
                    icon="refresh"
                    @click="systemStore.checkSystemHealth()"
                    :loading="systemStore.isRefreshing"
                  />
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>

        <!-- Data Management -->
        <q-card class="q-mt-md">
          <q-card-section>
            <div class="text-h6 q-mb-md">데이터 관리</div>
            
            <div class="q-gutter-sm">
              <q-btn
                color="primary"
                label="설정 내보내기"
                icon="download"
                @click="exportSettings"
              />
              
              <q-btn
                color="secondary"
                label="설정 가져오기"
                icon="upload"
                @click="importSettingsDialog = true"
              />
              
              <q-btn
                color="orange"
                label="대화 내보내기"
                icon="chat"
                @click="exportAllChats"
              />
            </div>

            <q-separator class="q-my-md" />

            <div class="text-subtitle2 q-mb-sm">위험 영역</div>
            <div class="q-gutter-sm">
              <q-btn
                color="negative"
                label="모든 대화 삭제"
                icon="delete_forever"
                @click="clearAllChats"
              />
              
              <q-btn
                color="negative"
                label="시스템 초기화"
                icon="settings_backup_restore"
                @click="resetSystem"
              />
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Import Settings Dialog -->
    <q-dialog v-model="importSettingsDialog">
      <q-card style="min-width: 350px">
        <q-card-section>
          <div class="text-h6">설정 가져오기</div>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-file
            v-model="importFile"
            label="JSON 파일 선택"
            accept=".json"
            outlined
            @update:model-value="onImportFile"
          />
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="취소" color="primary" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useSystemStore } from '@/stores/system'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'
import { format } from 'date-fns'

const $q = useQuasar()
const systemStore = useSystemStore()
const userStore = useUserStore()
const chatStore = useChatStore()

// Local state
const preferences = reactive({ ...userStore.preferences })
const importSettingsDialog = ref(false)
const importFile = ref<File | null>(null)

// Options
const themeOptions = [
  { label: '자동', value: 'auto' },
  { label: '라이트', value: 'light' },
  { label: '다크', value: 'dark' }
]

const languageOptions = [
  { label: '한국어', value: 'ko' },
  { label: 'English', value: 'en' }
]

// Methods
const savePreferences = () => {
  userStore.updatePreferences(preferences)
  $q.notify({
    type: 'positive',
    message: '설정이 저장되었습니다.'
  })
}

const resetPreferences = () => {
  $q.dialog({
    title: '설정 초기화',
    message: '모든 설정을 초기화하시겠습니까?',
    cancel: true,
    persistent: true
  }).onOk(() => {
    userStore.resetPreferences()
    Object.assign(preferences, userStore.preferences)
    $q.notify({
      type: 'positive',
      message: '설정이 초기화되었습니다.'
    })
  })
}

const exportSettings = () => {
  const settings = userStore.exportSettings()
  const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'rag_system_settings.json'
  a.click()
  URL.revokeObjectURL(url)
  
  $q.notify({
    type: 'positive',
    message: '설정이 내보내기 완료되었습니다.'
  })
}

const onImportFile = (file: File | null) => {
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const settings = JSON.parse(e.target?.result as string)
      const success = userStore.importSettings(settings)
      
      if (success) {
        Object.assign(preferences, userStore.preferences)
        $q.notify({
          type: 'positive',
          message: '설정이 가져오기 완료되었습니다.'
        })
        importSettingsDialog.value = false
      } else {
        throw new Error('잘못된 설정 파일입니다.')
      }
    } catch (error: any) {
      $q.notify({
        type: 'negative',
        message: '설정 가져오기 실패',
        caption: error.message
      })
    }
  }
  reader.readAsText(file)
}

const exportAllChats = () => {
  const allChats = chatStore.sessions.map(session => chatStore.exportSession(session.id))
  const blob = new Blob([JSON.stringify(allChats, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'rag_system_chats.json'
  a.click()
  URL.revokeObjectURL(url)
  
  $q.notify({
    type: 'positive',
    message: '대화 내보내기가 완료되었습니다.'
  })
}

const clearAllChats = () => {
  $q.dialog({
    title: '대화 전체 삭제',
    message: '모든 대화를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.',
    cancel: true,
    persistent: true
  }).onOk(() => {
    chatStore.sessions.forEach(session => {
      chatStore.deleteSession(session.id)
    })
    $q.notify({
      type: 'positive',
      message: '모든 대화가 삭제되었습니다.'
    })
  })
}

const resetSystem = () => {
  $q.dialog({
    title: '시스템 초기화',
    message: '시스템을 초기화하시겠습니까? 모든 데이터가 삭제됩니다.',
    cancel: true,
    persistent: true
  }).onOk(async () => {
    try {
      await systemStore.resetSystem()
      $q.notify({
        type: 'positive',
        message: '시스템이 초기화되었습니다.'
      })
    } catch (error: any) {
      $q.notify({
        type: 'negative',
        message: '시스템 초기화 실패',
        caption: error.message
      })
    }
  })
}

const formatDate = (date: Date | string | null | undefined) => {
  if (!date) return '없음'

  const dateObj = typeof date === 'string' ? new Date(date) : date
  if (!dateObj || isNaN(dateObj.getTime())) {
    return '유효하지 않은 날짜'
  }

  return format(dateObj, 'yyyy-MM-dd HH:mm')
}

onMounted(() => {
  // Sync local preferences with store
  Object.assign(preferences, userStore.preferences)
})
</script>