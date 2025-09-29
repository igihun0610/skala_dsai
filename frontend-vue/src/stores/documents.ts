import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/services/api'

export interface Document {
  id: string
  original_filename: string
  stored_filename: string
  file_size: number
  upload_time: string
  document_type: 'datasheet' | 'specification' | 'manual' | 'catalog'
  product_family?: string
  product_model?: string
  version?: string
  language: string
  processing_status: 'pending' | 'processing' | 'completed' | 'failed'
  chunk_count?: number
  metadata?: Record<string, any>
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
  page: number
  limit: number
  total_pages: number
}

export interface UploadProgress {
  documentId: string
  progress: number
  status: 'uploading' | 'processing' | 'completed' | 'failed'
  message?: string
}

export const useDocumentsStore = defineStore('documents', () => {
  // State
  const documents = ref<Document[]>([])
  const isLoading = ref(false)
  const uploadProgress = ref<Map<string, UploadProgress>>(new Map())
  const searchQuery = ref('')
  const currentPage = ref(1)
  const itemsPerPage = ref(10)
  const totalDocuments = ref(0)
  const totalPages = ref(0)

  // Filters
  const selectedDocumentType = ref<string>('')
  const selectedProductFamily = ref<string>('')
  const sortBy = ref<'upload_time' | 'filename' | 'file_size'>('upload_time')
  const sortOrder = ref<'asc' | 'desc'>('desc')

  // Computed
  const filteredDocuments = computed(() => {
    let filtered = [...documents.value]

    // Apply search filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      filtered = filtered.filter(doc =>
        doc.original_filename.toLowerCase().includes(query) ||
        doc.product_family?.toLowerCase().includes(query) ||
        doc.product_model?.toLowerCase().includes(query)
      )
    }

    // Apply type filter
    if (selectedDocumentType.value) {
      filtered = filtered.filter(doc => doc.document_type === selectedDocumentType.value)
    }

    // Apply product family filter
    if (selectedProductFamily.value) {
      filtered = filtered.filter(doc => doc.product_family === selectedProductFamily.value)
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let aValue: any, bValue: any

      switch (sortBy.value) {
        case 'filename':
          aValue = a.original_filename
          bValue = b.original_filename
          break
        case 'file_size':
          aValue = a.file_size
          bValue = b.file_size
          break
        case 'upload_time':
        default:
          aValue = a.upload_time ? new Date(a.upload_time) : new Date(0)
          bValue = b.upload_time ? new Date(b.upload_time) : new Date(0)
          if (isNaN(aValue.getTime())) aValue = new Date(0)
          if (isNaN(bValue.getTime())) bValue = new Date(0)
          break
      }

      if (aValue < bValue) return sortOrder.value === 'asc' ? -1 : 1
      if (aValue > bValue) return sortOrder.value === 'asc' ? 1 : -1
      return 0
    })

    return filtered
  })

  const documentTypes = computed(() => {
    const types = new Set(documents.value.map(doc => doc.document_type))
    return Array.from(types).map(type => ({
      label: getDocumentTypeLabel(type),
      value: type
    }))
  })

  const productFamilies = computed(() => {
    const families = new Set(documents.value
      .map(doc => doc.product_family)
      .filter(Boolean)
    )
    return Array.from(families).map(family => ({
      label: family,
      value: family
    }))
  })

  const documentStats = computed(() => ({
    total: totalDocuments.value,
    completed: documents.value.filter(doc => doc.processing_status === 'completed').length,
    processing: documents.value.filter(doc => doc.processing_status === 'processing').length,
    failed: documents.value.filter(doc => doc.processing_status === 'failed').length,
    totalSize: documents.value.reduce((sum, doc) => sum + doc.file_size, 0),
    totalChunks: documents.value.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0)
  }))

  const activeUploads = computed(() => {
    return Array.from(uploadProgress.value.values()).filter(
      upload => upload.status === 'uploading' || upload.status === 'processing'
    )
  })

  // Actions
  const loadDocuments = async (page = 1, limit = itemsPerPage.value) => {
    try {
      isLoading.value = true
      const response = await api.get<DocumentListResponse>('/documents', {
        params: {
          page,
          limit,
          document_type: selectedDocumentType.value || undefined,
          product_family: selectedProductFamily.value || undefined,
          search: searchQuery.value || undefined
        }
      })

      documents.value = response.data.documents
      totalDocuments.value = response.data.total
      totalPages.value = response.data.total_pages
      currentPage.value = response.data.page

    } catch (error) {
      console.error('Failed to load documents:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  const uploadDocument = async (
    file: File,
    metadata: {
      document_type: string
      product_family?: string
      product_model?: string
      version?: string
      language?: string
    }
  ) => {
    const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    try {
      // Initialize upload progress
      uploadProgress.value.set(uploadId, {
        documentId: uploadId,
        progress: 0,
        status: 'uploading'
      })

      const formData = new FormData()
      formData.append('file', file)
      formData.append('document_type', metadata.document_type)
      if (metadata.product_family) formData.append('product_family', metadata.product_family)
      if (metadata.product_model) formData.append('product_model', metadata.product_model)
      if (metadata.version) formData.append('version', metadata.version)
      if (metadata.language) formData.append('language', metadata.language)

      const response = await api.post('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            uploadProgress.value.set(uploadId, {
              documentId: uploadId,
              progress,
              status: progress < 100 ? 'uploading' : 'processing',
              message: progress < 100 ? '업로드 중...' : '처리 중...'
            })
          }
        }
      })

      // Mark as completed
      uploadProgress.value.set(uploadId, {
        documentId: uploadId,
        progress: 100,
        status: 'completed',
        message: '업로드 완료'
      })

      // Refresh document list
      await loadDocuments(1)

      // Clean up progress after delay
      setTimeout(() => {
        uploadProgress.value.delete(uploadId)
      }, 3000)

      return response.data

    } catch (error) {
      uploadProgress.value.set(uploadId, {
        documentId: uploadId,
        progress: 0,
        status: 'failed',
        message: '업로드 실패'
      })

      setTimeout(() => {
        uploadProgress.value.delete(uploadId)
      }, 5000)

      throw error
    }
  }

  const deleteDocument = async (documentId: string) => {
    try {
      await api.delete(`/upload/${documentId}`)
      await loadDocuments(currentPage.value)
      return true
    } catch (error) {
      console.error('Failed to delete document:', error)
      throw error
    }
  }

  const reprocessDocument = async (documentId: string) => {
    try {
      await api.post(`/upload/${documentId}/reprocess`)
      await loadDocuments(currentPage.value)
      return true
    } catch (error) {
      console.error('Failed to reprocess document:', error)
      throw error
    }
  }

  const searchDocuments = async (query: string) => {
    searchQuery.value = query
    currentPage.value = 1
    await loadDocuments(1)
  }

  const setFilters = async (filters: {
    documentType?: string
    productFamily?: string
    sortBy?: 'upload_time' | 'filename' | 'file_size'
    sortOrder?: 'asc' | 'desc'
  }) => {
    if (filters.documentType !== undefined) selectedDocumentType.value = filters.documentType
    if (filters.productFamily !== undefined) selectedProductFamily.value = filters.productFamily
    if (filters.sortBy) sortBy.value = filters.sortBy
    if (filters.sortOrder) sortOrder.value = filters.sortOrder

    currentPage.value = 1
    await loadDocuments(1)
  }

  const clearFilters = async () => {
    searchQuery.value = ''
    selectedDocumentType.value = ''
    selectedProductFamily.value = ''
    sortBy.value = 'upload_time'
    sortOrder.value = 'desc'
    currentPage.value = 1
    await loadDocuments(1)
  }

  const getDocumentTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      datasheet: '데이터시트',
      specification: '기술사양서',
      manual: '매뉴얼',
      catalog: '카탈로그'
    }
    return labels[type] || type
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const getDocumentById = (id: string) => {
    return documents.value.find(doc => doc.id === id)
  }

  return {
    // State
    documents,
    isLoading,
    uploadProgress,
    searchQuery,
    currentPage,
    itemsPerPage,
    totalDocuments,
    totalPages,
    selectedDocumentType,
    selectedProductFamily,
    sortBy,
    sortOrder,

    // Computed
    filteredDocuments,
    documentTypes,
    productFamilies,
    documentStats,
    activeUploads,

    // Actions
    loadDocuments,
    uploadDocument,
    deleteDocument,
    reprocessDocument,
    searchDocuments,
    setFilters,
    clearFilters,
    getDocumentTypeLabel,
    formatFileSize,
    getDocumentById
  }
})