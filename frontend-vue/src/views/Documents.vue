<template>
  <q-page class="q-pa-md">
    <div class="text-h4 q-mb-lg">문서 관리</div>

    <div class="row">
      <!-- Upload Section -->
      <div class="col-12 col-sm-4 q-pr-md">
        <q-card>
          <q-card-section>
            <div class="text-h6 q-mb-md">문서 업로드</div>

            <q-form @submit="handleUpload">
              <q-file
                v-model="uploadFile"
                label="PDF 파일 선택"
                accept=".pdf"
                outlined
                class="q-mb-md"
                :rules="[val => !!val || '파일을 선택해주세요']"
              >
                <template v-slot:prepend>
                  <q-icon name="attach_file" />
                </template>
              </q-file>

              <q-select
                v-model="uploadMetadata.document_type"
                :options="documentTypeOptions"
                label="문서 유형"
                outlined
                emit-value
                map-options
                class="q-mb-md"
                :rules="[val => !!val || '문서 유형을 선택해주세요']"
              />

              <q-input
                v-model="uploadMetadata.product_family"
                label="제품군"
                outlined
                class="q-mb-md"
                placeholder="예: DDR5, SSD, NAND Flash"
              />

              <q-input
                v-model="uploadMetadata.product_model"
                label="제품 모델"
                outlined
                class="q-mb-md"
                placeholder="예: RDIMM, eUFS"
              />

              <q-input
                v-model="uploadMetadata.version"
                label="버전"
                outlined
                class="q-mb-md"
                placeholder="예: v1.0, Rev.A"
              />

              <q-btn
                type="submit"
                color="primary"
                class="full-width"
                :loading="isUploading"
                :disable="!uploadFile"
              >
                <q-icon name="upload" class="q-mr-sm" />
                업로드
              </q-btn>
            </q-form>

            <!-- Upload Progress -->
            <div v-if="documentsStore.activeUploads.length > 0" class="q-mt-md">
              <div class="text-subtitle2 q-mb-sm">업로드 진행상황</div>
              <div v-for="upload in documentsStore.activeUploads" :key="upload.documentId" class="q-mb-sm">
                <div class="text-caption">{{ upload.message || '처리 중...' }}</div>
                <q-linear-progress
                  :value="upload.progress / 100"
                  color="primary"
                  class="q-mt-xs"
                />
              </div>
            </div>
          </q-card-section>
        </q-card>

        <!-- Statistics Card -->
        <q-card class="q-mt-md">
          <q-card-section>
            <div class="text-h6 q-mb-md">통계</div>
            <q-list dense>
              <q-item>
                <q-item-section>
                  <q-item-label>총 문서</q-item-label>
                  <q-item-label caption>{{ documentsStore.documentStats.total }}개</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label>처리 완료</q-item-label>
                  <q-item-label caption>{{ documentsStore.documentStats.completed }}개</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label>총 크기</q-item-label>
                  <q-item-label caption>{{ documentsStore.formatFileSize(documentsStore.documentStats.totalSize) }}</q-item-label>
                </q-item-section>
              </q-item>
              <q-item>
                <q-item-section>
                  <q-item-label>총 청크</q-item-label>
                  <q-item-label caption>{{ documentsStore.documentStats.totalChunks }}개</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
      </div>

      <!-- Documents List -->
      <div class="col-12 col-sm-8">
        <q-card>
          <q-card-section>
            <!-- Search and Filters -->
            <div class="row q-gutter-md q-mb-md">
              <div class="col-12 col-sm-6">
                <q-input
                  v-model="searchQuery"
                  placeholder="문서 검색..."
                  outlined
                  dense
                  debounce="500"
                  @update:model-value="onSearch"
                >
                  <template v-slot:prepend>
                    <q-icon name="search" />
                  </template>
                  <template v-slot:append>
                    <q-btn flat round dense icon="clear" @click="clearSearch" v-if="searchQuery" />
                  </template>
                </q-input>
              </div>

              <div class="col-12 col-sm-3">
                <q-select
                  v-model="selectedDocumentType"
                  :options="[{ label: '전체', value: '' }, ...documentsStore.documentTypes]"
                  label="문서 유형"
                  outlined
                  dense
                  emit-value
                  map-options
                  @update:model-value="onFilterChange"
                />
              </div>

              <div class="col-12 col-sm-3">
                <q-select
                  v-model="selectedProductFamily"
                  :options="[{ label: '전체', value: '' }, ...documentsStore.productFamilies]"
                  label="제품군"
                  outlined
                  dense
                  emit-value
                  map-options
                  @update:model-value="onFilterChange"
                />
              </div>
            </div>

            <!-- Documents Table -->
            <q-table
              :rows="documentsStore.filteredDocuments"
              :columns="tableColumns"
              row-key="id"
              :loading="documentsStore.isLoading"
              :pagination="tablePagination"
              @request="onTableRequest"
            >
              <template v-slot:body-cell-filename="props">
                <q-td :props="props">
                  <div class="flex items-center">
                    <q-icon name="picture_as_pdf" color="red" class="q-mr-sm" />
                    <div>
                      <div>{{ props.row.original_filename }}</div>
                      <div class="text-caption text-grey-6">
                        {{ documentsStore.formatFileSize(props.row.file_size) }}
                      </div>
                    </div>
                  </div>
                </q-td>
              </template>

              <template v-slot:body-cell-type="props">
                <q-td :props="props">
                  <q-chip
                    :label="documentsStore.getDocumentTypeLabel(props.row.document_type)"
                    size="sm"
                    color="primary"
                    text-color="white"
                  />
                </q-td>
              </template>

              <template v-slot:body-cell-status="props">
                <q-td :props="props">
                  <q-chip
                    :label="getStatusLabel(props.row.processing_status)"
                    size="sm"
                    :color="getStatusColor(props.row.processing_status)"
                    text-color="white"
                  />
                </q-td>
              </template>

              <template v-slot:body-cell-upload_time="props">
                <q-td :props="props">
                  {{ formatDate(props.row.upload_time) }}
                </q-td>
              </template>

              <template v-slot:body-cell-actions="props">
                <q-td :props="props">
                  <q-btn flat round dense icon="more_vert">
                    <q-menu>
                      <q-list style="min-width: 100px">
                        <q-item clickable @click="reprocessDocument(props.row.id)" v-if="props.row.processing_status === 'failed'">
                          <q-item-section>재처리</q-item-section>
                        </q-item>
                        <q-item clickable @click="deleteDocument(props.row.id)">
                          <q-item-section>삭제</q-item-section>
                        </q-item>
                      </q-list>
                    </q-menu>
                  </q-btn>
                </q-td>
              </template>
            </q-table>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useQuasar } from 'quasar'
import { useDocumentsStore } from '@/stores/documents'
import { format } from 'date-fns'

const $q = useQuasar()
const documentsStore = useDocumentsStore()

// Upload state
const uploadFile = ref<File | null>(null)
const isUploading = ref(false)
const uploadMetadata = reactive({
  document_type: '',
  product_family: '',
  product_model: '',
  version: '',
  language: 'ko'
})

// Search and filter state
const searchQuery = ref('')
const selectedDocumentType = ref('')
const selectedProductFamily = ref('')

// Table configuration
const tableColumns = [
  {
    name: 'filename',
    required: true,
    label: '파일명',
    align: 'left',
    field: 'original_filename',
    sortable: true
  },
  {
    name: 'type',
    label: '유형',
    align: 'center',
    field: 'document_type',
    sortable: true
  },
  {
    name: 'product_family',
    label: '제품군',
    align: 'left',
    field: 'product_family',
    sortable: true
  },
  {
    name: 'status',
    label: '상태',
    align: 'center',
    field: 'processing_status',
    sortable: true
  },
  {
    name: 'upload_time',
    label: '업로드 시간',
    align: 'center',
    field: 'upload_time',
    sortable: true
  },
  {
    name: 'actions',
    label: '작업',
    align: 'center'
  }
]

const tablePagination = ref({
  page: 1,
  rowsPerPage: 10,
  rowsNumber: 0
})

// Options
const documentTypeOptions = [
  { label: '데이터시트', value: 'datasheet' },
  { label: '기술사양서', value: 'specification' },
  { label: '매뉴얼', value: 'manual' },
  { label: '카탈로그', value: 'catalog' }
]

// Methods
const handleUpload = async () => {
  if (!uploadFile.value) return

  try {
    isUploading.value = true

    await documentsStore.uploadDocument(uploadFile.value, uploadMetadata)

    $q.notify({
      type: 'positive',
      message: '파일 업로드가 시작되었습니다.',
      caption: '처리 완료 시 목록에 표시됩니다.'
    })

    // Reset form
    uploadFile.value = null
    Object.assign(uploadMetadata, {
      document_type: '',
      product_family: '',
      product_model: '',
      version: '',
      language: 'ko'
    })

  } catch (error: any) {
    $q.notify({
      type: 'negative',
      message: '업로드 실패',
      caption: error.message
    })
  } finally {
    isUploading.value = false
  }
}

const onSearch = async (query: string) => {
  await documentsStore.searchDocuments(query)
  updateTablePagination()
}

const clearSearch = async () => {
  searchQuery.value = ''
  await documentsStore.searchDocuments('')
  updateTablePagination()
}

const onFilterChange = async () => {
  await documentsStore.setFilters({
    documentType: selectedDocumentType.value,
    productFamily: selectedProductFamily.value
  })
  updateTablePagination()
}

const onTableRequest = async (props: any) => {
  const { page, rowsPerPage } = props.pagination

  await documentsStore.loadDocuments(page, rowsPerPage)

  tablePagination.value = {
    page: documentsStore.currentPage,
    rowsPerPage: documentsStore.itemsPerPage,
    rowsNumber: documentsStore.totalDocuments
  }
}

const updateTablePagination = () => {
  tablePagination.value.rowsNumber = documentsStore.totalDocuments
}

const deleteDocument = async (documentId: string) => {
  $q.dialog({
    title: '문서 삭제',
    message: '이 문서를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.',
    cancel: true,
    persistent: true
  }).onOk(async () => {
    try {
      await documentsStore.deleteDocument(documentId)
      $q.notify({
        type: 'positive',
        message: '문서가 삭제되었습니다.'
      })
      updateTablePagination()
    } catch (error: any) {
      $q.notify({
        type: 'negative',
        message: '삭제 실패',
        caption: error.message
      })
    }
  })
}

const reprocessDocument = async (documentId: string) => {
  try {
    await documentsStore.reprocessDocument(documentId)
    $q.notify({
      type: 'positive',
      message: '문서 재처리가 시작되었습니다.'
    })
  } catch (error: any) {
    $q.notify({
      type: 'negative',
      message: '재처리 실패',
      caption: error.message
    })
  }
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: '대기중',
    processing: '처리중',
    completed: '완료',
    failed: '실패'
  }
  return labels[status] || status
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'orange',
    processing: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colors[status] || 'grey'
}

const formatDate = (dateString: string | null | undefined) => {
  if (!dateString) {
    return '없음'
  }

  const date = new Date(dateString)
  if (isNaN(date.getTime())) {
    return '유효하지 않은 날짜'
  }

  return format(date, 'yyyy-MM-dd HH:mm')
}

onMounted(async () => {
  await documentsStore.loadDocuments()
  updateTablePagination()
})
</script>