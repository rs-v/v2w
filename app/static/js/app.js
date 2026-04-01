// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const previewSection = document.getElementById('previewSection');
const preview = document.getElementById('preview');
const clearBtn = document.getElementById('clearBtn');
const convertBtn = document.getElementById('convertBtn');
const btnText = document.getElementById('btnText');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
const statusMessage = document.getElementById('statusMessage');

let selectedFile = null;

// Upload area click handler
uploadArea.addEventListener('click', () => {
    fileInput.click();
});

// File input change handler
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
});

// Drag and drop handlers
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');

    const file = e.dataTransfer.files[0];
    if (file) {
        handleFile(file);
    }
});

// Handle file selection
function handleFile(file) {
    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/bmp', 'image/tiff'];
    if (!allowedTypes.includes(file.type)) {
        showStatus('不支持的文件格式。请上传 PNG, JPEG, WebP, BMP 或 TIFF 图片。', 'error');
        return;
    }

    selectedFile = file;

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        preview.src = e.target.result;
        uploadArea.style.display = 'none';
        previewSection.style.display = 'block';
        convertBtn.disabled = false;
        showStatus('', '');
    };
    reader.readAsDataURL(file);
}

// Clear button handler
clearBtn.addEventListener('click', () => {
    selectedFile = null;
    fileInput.value = '';
    uploadArea.style.display = 'block';
    previewSection.style.display = 'none';
    convertBtn.disabled = true;
    progressBar.style.display = 'none';
    progressFill.style.width = '0%';
    showStatus('', '');
});

// Convert button handler
convertBtn.addEventListener('click', async () => {
    if (!selectedFile) {
        return;
    }

    // Prepare UI for conversion
    convertBtn.disabled = true;
    btnText.textContent = '转换中...';
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';
    showStatus('正在上传图片...', '');

    try {
        // Simulate progress for better UX
        progressFill.style.width = '30%';

        // Create form data
        const formData = new FormData();
        formData.append('file', selectedFile);

        showStatus('正在识别文字和公式...', '');
        progressFill.style.width = '60%';

        // Send request to API
        const response = await fetch('/api/v1/convert', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '转换失败' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        progressFill.style.width = '90%';
        showStatus('正在生成 Word 文档...', '');

        // Get the blob
        const blob = await response.blob();

        progressFill.style.width = '100%';

        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // Use original filename but change extension to .docx
        const originalName = selectedFile.name.split('.').slice(0, -1).join('.');
        a.download = originalName + '.docx';

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showStatus('✅ 转换成功！文档已下载。', 'success');

        // Reset after delay
        setTimeout(() => {
            btnText.textContent = '开始转换';
            convertBtn.disabled = false;
            progressBar.style.display = 'none';
            progressFill.style.width = '0%';
        }, 2000);

    } catch (error) {
        console.error('Conversion error:', error);
        showStatus(`❌ 转换失败：${error.message}`, 'error');
        btnText.textContent = '重试';
        convertBtn.disabled = false;
        progressBar.style.display = 'none';
        progressFill.style.width = '0%';
    }
});

// Show status message
function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = 'status-message';
    if (type) {
        statusMessage.classList.add(type);
    }
}
