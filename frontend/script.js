// API 기본 URL
const API_BASE_URL = 'http://localhost:8000/api';

// 전역 변수
let uploadedDocuments = [];

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    checkSystemStatus();
    loadDocuments();
    setupEventListeners();
});

// 이벤트 리스너 설정
function setupEventListeners() {
    // 파일 업로드 폼
    document.getElementById('uploadForm').addEventListener('submit', handleFileUpload);

    // 질문 입력 엔터키 처리
    document.getElementById('questionInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendQuestion();
        }
    });
}

// 시스템 상태 확인
async function checkSystemStatus() {
    try {
        // 헬스체크
        const healthResponse = await fetch(`${API_BASE_URL}/health`);
        const healthData = await healthResponse.json();

        // 상태 체크
        const statusResponse = await fetch(`${API_BASE_URL}/status`);
        const statusData = await statusResponse.json();

        updateSystemStatus(healthData, statusData);

    } catch (error) {
        console.error('시스템 상태 확인 실패:', error);
        updateSystemStatusError();
    }
}

// 시스템 상태 UI 업데이트
function updateSystemStatus(health, status) {
    const statusBadge = document.getElementById('systemStatus');
    const statusCards = document.getElementById('statusCards');

    // 전체 상태
    if (health.status === 'healthy') {
        statusBadge.className = 'badge bg-success me-2';
        statusBadge.textContent = '정상 운영';
    } else {
        statusBadge.className = 'badge bg-danger me-2';
        statusBadge.textContent = '오류 발생';
    }

    // 상세 상태 카드
    statusCards.innerHTML = `
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card status-card text-center">
                <div class="card-body">
                    <div class="status-icon ${health.status === 'healthy' ? 'status-healthy' : 'status-error'}">
                        <i class="fas fa-server"></i>
                    </div>
                    <h6 class="card-title">API 서버</h6>
                    <p class="card-text">${health.status === 'healthy' ? '정상' : '오류'}</p>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card status-card text-center">
                <div class="card-body">
                    <div class="status-icon ${status.ollama_status === 'healthy' ? 'status-healthy' : 'status-error'}">
                        <i class="fas fa-robot"></i>
                    </div>
                    <h6 class="card-title">Ollama LLM</h6>
                    <p class="card-text">${status.ollama_status === 'healthy' ? '정상' : '연결 오류'}</p>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card status-card text-center">
                <div class="card-body">
                    <div class="status-icon ${status.vector_db_status === 'healthy' ? 'status-healthy' : 'status-warning'}">
                        <i class="fas fa-database"></i>
                    </div>
                    <h6 class="card-title">벡터 DB</h6>
                    <p class="card-text">${status.vector_db_status === 'healthy' ? '정상' : '비어있음'}</p>
                </div>
            </div>
        </div>
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="card status-card text-center">
                <div class="card-body">
                    <div class="status-icon status-healthy">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <h6 class="card-title">문서</h6>
                    <p class="card-text">${status.documents_count || 0}개</p>
                </div>
            </div>
        </div>
    `;
}

// 시스템 상태 오류 UI
function updateSystemStatusError() {
    const statusBadge = document.getElementById('systemStatus');
    statusBadge.className = 'badge bg-danger me-2';
    statusBadge.textContent = '연결 실패';

    document.getElementById('statusCards').innerHTML = `
        <div class="col-12">
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.
            </div>
        </div>
    `;
}

// 파일 업로드 처리
async function handleFileUpload(event) {
    event.preventDefault();

    const formData = new FormData();
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];

    if (!file) {
        showToast('파일을 선택해주세요.', 'error');
        return;
    }

    // FormData 준비
    formData.append('file', file);
    formData.append('document_type', document.getElementById('documentType').value);
    formData.append('product_family', document.getElementById('productFamily').value);
    formData.append('product_model', document.getElementById('productModel').value);

    // 업로드 진행상황 표시
    showUploadProgress();

    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            showToast('파일 업로드가 성공했습니다!', 'success');
            document.getElementById('uploadForm').reset();
            loadDocuments(); // 문서 목록 새로고침
            checkSystemStatus(); // 상태 새로고침
        } else {
            throw new Error(result.detail || '업로드 실패');
        }

    } catch (error) {
        console.error('업로드 오류:', error);
        showToast(`업로드 실패: ${error.message}`, 'error');
    } finally {
        hideUploadProgress();
    }
}

// 업로드된 문서 목록 로드
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        const documents = await response.json();

        uploadedDocuments = documents;
        updateDocumentsList(documents);

    } catch (error) {
        console.error('문서 목록 로드 실패:', error);
    }
}

// 문서 목록 UI 업데이트
function updateDocumentsList(documents) {
    const fileList = document.getElementById('fileList');

    if (documents.length === 0) {
        fileList.innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="fas fa-inbox fa-2x mb-2"></i>
                <p>업로드된 문서가 없습니다.</p>
            </div>
        `;
        return;
    }

    fileList.innerHTML = documents.map(doc => `
        <div class="file-item">
            <div class="file-info">
                <i class="fas fa-file-pdf file-icon"></i>
                <div>
                    <div class="file-name">${doc.original_filename}</div>
                    <div class="file-meta">${doc.document_type} | ${doc.product_family} | ${formatFileSize(doc.file_size)}</div>
                </div>
            </div>
            <div class="file-actions">
                <button class="btn btn-sm btn-outline-danger" onclick="deleteDocument('${doc.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

// 문서 삭제
async function deleteDocument(documentId) {
    if (!confirm('정말로 이 문서를 삭제하시겠습니까?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/upload/${documentId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('문서가 삭제되었습니다.', 'success');
            loadDocuments();
            checkSystemStatus();
        } else {
            throw new Error('삭제 실패');
        }

    } catch (error) {
        console.error('문서 삭제 실패:', error);
        showToast('문서 삭제에 실패했습니다.', 'error');
    }
}

// 질문 전송
async function sendQuestion() {
    const questionInput = document.getElementById('questionInput');
    const question = questionInput.value.trim();

    if (!question) {
        showToast('질문을 입력해주세요.', 'error');
        return;
    }

    const userRole = document.querySelector('input[name="userRole"]:checked').value;

    // 사용자 메시지 추가
    addChatMessage('user', question, userRole);

    // 입력창 비우기
    questionInput.value = '';

    // 로딩 메시지 추가
    const loadingMessageId = addChatMessage('assistant', '답변을 생성중입니다...', 'AI 어시스턴트', true);

    try {
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                user_role: userRole,
                top_k: 5
            })
        });

        const result = await response.json();

        // 로딩 메시지 제거
        removeChatMessage(loadingMessageId);

        if (response.ok) {
            // 답변 메시지 추가
            addChatMessage('assistant', result.answer, 'AI 어시스턴트', false, {
                confidence: result.confidence,
                sources: result.sources,
                queryTime: result.query_time_ms,
                model: result.model_used
            });
        } else {
            throw new Error(result.detail || '질문 처리 실패');
        }

    } catch (error) {
        console.error('질문 처리 오류:', error);
        removeChatMessage(loadingMessageId);

        // IMPROVED: 더 구체적인 오류 메시지 제공
        let errorMessage = '죄송합니다. ';
        if (error.message.includes('validation') || error.message.includes('데이터 형식')) {
            errorMessage += '데이터 처리 중 형식 오류가 발생했습니다. 관리자에게 문의해주세요.';
        } else if (error.message.includes('timeout') || error.message.includes('초과')) {
            errorMessage += '응답 시간이 초과되었습니다. 더 간단한 질문으로 시도해보세요.';
        } else if (error.message.includes('connection') || error.message.includes('연결')) {
            errorMessage += '서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.';
        } else if (error.message.includes('model') || error.message.includes('모델')) {
            errorMessage += 'AI 모델을 로드 중입니다. 잠시 후 다시 시도해주세요.';
        } else if (error.message.includes('initialization') || error.message.includes('초기화')) {
            errorMessage += '서비스가 초기화 중입니다. 잠시 후 다시 시도해주세요.';
        } else {
            errorMessage += `오류가 발생했습니다: ${error.message}`;
        }

        addChatMessage('assistant', errorMessage, 'AI 어시스턴트');
    }
}

// 채팅 메시지 추가
function addChatMessage(type, content, role, isLoading = false, metadata = null) {
    const chatMessages = document.getElementById('chatMessages');
    const messageId = 'msg-' + Date.now();

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;
    messageDiv.id = messageId;

    let roleIcon = type === 'user' ? getRoleIcon(role) : '<i class="fas fa-robot"></i>';

    let metaInfo = '';
    if (metadata) {
        metaInfo = `
            <div class="message-meta">
                <span>신뢰도: ${(metadata.confidence * 100).toFixed(1)}%</span> |
                <span>처리시간: ${metadata.queryTime}ms</span> |
                <span>모델: ${metadata.model}</span>
            </div>
        `;
    }

    let sourcesInfo = '';
    if (metadata && metadata.sources && metadata.sources.length > 0) {
        sourcesInfo = `
            <div class="message-sources">
                <strong>참조 문서:</strong>
                ${metadata.sources.map(source => `
                    <div>📄 ${source.filename} (페이지 ${source.page_number})</div>
                `).join('')}
            </div>
        `;
    }

    messageDiv.innerHTML = `
        <div class="message-role">${roleIcon} ${role}</div>
        <div class="message-content">
            ${isLoading ? '<span class="spinner"></span> ' : ''}${content}
        </div>
        ${sourcesInfo}
        ${metaInfo}
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageId;
}

// 채팅 메시지 제거
function removeChatMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

// 역할 아이콘 가져오기
function getRoleIcon(role) {
    const icons = {
        engineer: '<i class="fas fa-cogs"></i>',
        quality: '<i class="fas fa-check-circle"></i>',
        sales: '<i class="fas fa-handshake"></i>',
        support: '<i class="fas fa-life-ring"></i>'
    };
    return icons[role] || '<i class="fas fa-user"></i>';
}

// 예시 질문 설정
function setQuestion(question) {
    document.getElementById('questionInput').value = question;
}

// 키 입력 처리
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendQuestion();
    }
}

// 업로드 진행상황 표시/숨김
function showUploadProgress() {
    document.getElementById('uploadProgress').style.display = 'block';
}

function hideUploadProgress() {
    document.getElementById('uploadProgress').style.display = 'none';
}

// 파일 크기 포맷팅
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 토스트 메시지 표시
function showToast(message, type = 'info') {
    const toastContainer = getOrCreateToastContainer();

    const toastId = 'toast-' + Date.now();
    const bgClass = type === 'success' ? 'bg-success' :
                   type === 'error' ? 'bg-danger' : 'bg-info';

    const toastHTML = `
        <div id="${toastId}" class="toast ${bgClass} text-white" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement);
    toast.show();

    // 자동 제거
    setTimeout(() => {
        toastElement.remove();
    }, 5000);
}

// 토스트 컨테이너 생성/반환
function getOrCreateToastContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    return container;
}