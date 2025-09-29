<template>
  <q-page class="q-pa-md">
    <div class="text-h4 q-mb-lg">대시보드</div>

    <!-- System Status Overview -->
    <div class="row  q-mb-lg">
      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-circular-progress
              :value="systemStore.isHealthy ? 100 : 0"
              size="60px"
              :color="systemStore.statusColor"
              track-color="grey-3"
              class="q-mb-sm"
            />
            <div class="text-h6">시스템 상태</div>
            <div class="text-subtitle2 text-grey-6">{{ systemStore.statusText }}</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-icon name="folder" size="40px" color="primary" class="q-mb-sm" />
            <div class="text-h6">{{ documentsStore.totalDocuments }}</div>
            <div class="text-subtitle2 text-grey-6">업로드된 문서</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-icon name="chat" size="40px" color="secondary" class="q-mb-sm" />
            <div class="text-h6">{{ chatStore.totalMessages }}</div>
            <div class="text-subtitle2 text-grey-6">총 대화 수</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-icon name="person" size="40px" color="orange" class="q-mb-sm" />
            <div class="text-h6">{{ userStore.getRoleLabel(userStore.currentRole) }}</div>
            <div class="text-subtitle2 text-grey-6">현재 역할</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="row  q-mb-lg">
      <div class="col-12 col-sm-6 q-pa-sm">
        <q-card>
          <q-card-section>
            <div class="text-h6 q-mb-md">빠른 실행</div>
            <div class="row q-gutter-sm">
              <q-btn color="primary" label="문서 업로드" icon="upload" to="/documents" />
              <q-btn color="secondary" label="질의응답" icon="chat" to="/chat" />
              <q-btn color="positive" label="분석 보기" icon="analytics" to="/analytics" />
            </div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-sm-6 q-pa-sm">
        <q-card>
          <q-card-section>
            <div class="text-h6 q-mb-md">시스템 정보</div>
            <q-list dense>
              <q-item>
                <q-item-section>
                  <q-item-label>모델</q-item-label>
                  <q-item-label caption>{{ systemStore.currentModel }}</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label>마지막 상태 확인</q-item-label>
                  <q-item-label caption>{{ formatDate(systemStore.lastHealthCheck) }}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Recent Activity -->
    <q-card>
      <q-card-section>
        <div class="text-h6 q-mb-md">최근 활동</div>
        <q-list separator>
          <q-item v-for="session in chatStore.recentSessions.slice(0, 5)" :key="session.id">
            <q-item-section avatar>
              <q-icon :name="userStore.getRoleIcon(session.role)" :color="userStore.getRoleColor(session.role)" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ session.title }}</q-item-label>
              <q-item-label caption>{{ formatDate(session.updated_at) }} • {{ session.message_count }}개 메시지</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-btn flat round icon="open_in_new" @click="$router.push('/chat')" />
            </q-item-section>
          </q-item>
          <q-item v-if="chatStore.recentSessions.length === 0">
            <q-item-section>
              <q-item-label class="text-grey-6">아직 대화 기록이 없습니다.</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import { useUserStore } from '@/stores/user'
import { useDocumentsStore } from '@/stores/documents'
import { useChatStore } from '@/stores/chat'
import { format } from 'date-fns'

const systemStore = useSystemStore()
const userStore = useUserStore()
const documentsStore = useDocumentsStore()
const chatStore = useChatStore()

const formatDate = (date: Date | string | null | undefined) => {
  if (!date) return '없음'

  const dateObj = typeof date === 'string' ? new Date(date) : date
  if (!dateObj || isNaN(dateObj.getTime())) {
    return '유효하지 않은 날짜'
  }

  return format(dateObj, 'yyyy-MM-dd HH:mm')
}

onMounted(async () => {
  // Load initial data
  await systemStore.checkSystemHealth()
  await documentsStore.loadDocuments()
})
</script>