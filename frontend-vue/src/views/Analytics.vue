<template>
  <q-page class="q-pa-md">
    <div class="text-h4 q-mb-lg">분석</div>

    <div class="row  q-mb-lg">
      <!-- Overview Cards -->
      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-icon name="analytics" size="40px" color="primary" class="q-mb-sm" />
            <div class="text-h6">{{ chatStore.totalSessions }}</div>
            <div class="text-subtitle2 text-grey-6">총 세션</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-icon name="chat" size="40px" color="secondary" class="q-mb-sm" />
            <div class="text-h6">{{ chatStore.totalMessages }}</div>
            <div class="text-subtitle2 text-grey-6">총 메시지</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-icon name="folder" size="40px" color="positive" class="q-mb-sm" />
            <div class="text-h6">{{ documentsStore.totalDocuments }}</div>
            <div class="text-subtitle2 text-grey-6">업로드된 문서</div>
          </q-card-section>
        </q-card>
      </div>

      <div class="col-12 col-sm-3 q-pa-sm">
        <q-card class="text-center">
          <q-card-section>
            <q-icon name="storage" size="40px" color="warning" class="q-mb-sm" />
            <div class="text-h6">{{ documentsStore.formatFileSize(documentsStore.documentStats.totalSize) }}</div>
            <div class="text-subtitle2 text-grey-6">총 데이터 크기</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <div class="row ">
      <!-- Role Distribution -->
      <div class="col-12 col-sm-6 q-pa-sm">
        <q-card>
          <q-card-section>
            <div class="text-h6 q-mb-md">역할별 사용 현황</div>
            <div v-for="role in roleStats" :key="role.role" class="q-mb-md">
              <div class="row items-center">
                <div class="col-3">
                  <q-icon :name="userStore.getRoleIcon(role.role)" :color="userStore.getRoleColor(role.role)" />
                  {{ userStore.getRoleLabel(role.role) }}
                </div>
                <div class="col-7">
                  <q-linear-progress
                    :value="role.percentage / 100"
                    :color="userStore.getRoleColor(role.role)"
                    class="q-mt-xs"
                  />
                </div>
                <div class="col-2 text-right">
                  {{ role.count }}회
                </div>
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- Document Types -->
      <div class="col-12 col-sm-6 q-pa-sm">
        <q-card>
          <q-card-section>
            <div class="text-h6 q-mb-md">문서 유형별 분포</div>
            <div v-for="docType in documentTypeStats" :key="docType.type" class="q-mb-md">
              <div class="row items-center">
                <div class="col-4">
                  {{ documentsStore.getDocumentTypeLabel(docType.type) }}
                </div>
                <div class="col-6">
                  <q-linear-progress
                    :value="docType.percentage / 100"
                    color="primary"
                    class="q-mt-xs"
                  />
                </div>
                <div class="col-2 text-right">
                  {{ docType.count }}개
                </div>
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Recent Activity -->
    <q-card class="q-mt-md">
      <q-card-section>
        <div class="text-h6 q-mb-md">최근 활동</div>
        <q-timeline color="primary">
          <q-timeline-entry
            v-for="(activity, index) in recentActivities"
            :key="index"
            :title="activity.title"
            :subtitle="formatDate(activity.timestamp)"
            :icon="activity.icon"
            :color="activity.color"
          >
            <div>{{ activity.description }}</div>
          </q-timeline-entry>
        </q-timeline>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { useDocumentsStore } from '@/stores/documents'
import { useChatStore } from '@/stores/chat'
import { format } from 'date-fns'
import type { UserRole } from '@/stores/user'

const userStore = useUserStore()
const documentsStore = useDocumentsStore()
const chatStore = useChatStore()

// Computed stats
const roleStats = computed(() => {
  const roleCounts: Record<UserRole, number> = {
    engineer: 0,
    quality: 0,
    sales: 0,
    support: 0
  }

  // Count sessions by role
  chatStore.sessions.forEach(session => {
    roleCounts[session.role]++
  })

  const total = Object.values(roleCounts).reduce((sum, count) => sum + count, 0)

  return Object.entries(roleCounts).map(([role, count]) => ({
    role: role as UserRole,
    count,
    percentage: total > 0 ? (count / total) * 100 : 0
  })).sort((a, b) => b.count - a.count)
})

const documentTypeStats = computed(() => {
  const typeCounts: Record<string, number> = {}

  documentsStore.documents.forEach(doc => {
    typeCounts[doc.document_type] = (typeCounts[doc.document_type] || 0) + 1
  })

  const total = Object.values(typeCounts).reduce((sum, count) => sum + count, 0)

  return Object.entries(typeCounts).map(([type, count]) => ({
    type,
    count,
    percentage: total > 0 ? (count / total) * 100 : 0
  })).sort((a, b) => b.count - a.count)
})

const recentActivities = computed(() => {
  const activities: Array<{
    title: string
    description: string
    timestamp: Date
    icon: string
    color: string
  }> = []

  // Add recent chat sessions
  chatStore.recentSessions.slice(0, 3).forEach(session => {
    const timestamp = session.created_at instanceof Date ? session.created_at : new Date(session.created_at)
    if (!isNaN(timestamp.getTime())) {
      activities.push({
        title: '새 대화 세션',
        description: `${userStore.getRoleLabel(session.role)} 역할로 "${session.title}" 대화 시작`,
        timestamp,
        icon: 'chat',
        color: 'secondary'
      })
    }
  })

  // Add recent document uploads
  documentsStore.documents
    .filter(doc => doc.processing_status === 'completed')
    .slice(0, 3)
    .forEach(doc => {
      if (doc.upload_time) {
        const timestamp = new Date(doc.upload_time)
        if (!isNaN(timestamp.getTime())) {
          activities.push({
            title: '문서 업로드 완료',
            description: `"${doc.original_filename}" 처리 완료`,
            timestamp,
            icon: 'upload_file',
            color: 'positive'
          })
        }
      }
    })

  return activities
    .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
    .slice(0, 5)
})

const formatDate = (date: Date | string | null | undefined) => {
  if (!date) return '없음'

  const dateObj = typeof date === 'string' ? new Date(date) : date
  if (!dateObj || isNaN(dateObj.getTime())) {
    return '유효하지 않은 날짜'
  }

  return format(dateObj, 'yyyy-MM-dd HH:mm')
}

onMounted(async () => {
  // Load data if not already loaded
  if (documentsStore.documents.length === 0) {
    await documentsStore.loadDocuments()
  }
})
</script>