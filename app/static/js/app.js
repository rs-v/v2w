// DOM elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const previewSection = document.getElementById('previewSection');
const preview = document.getElementById('preview');
const clearBtn = document.getElementById('clearBtn');
const recognizeBtn = document.getElementById('recognizeBtn');
const btnText = document.getElementById('btnText');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
const statusMessage = document.getElementById('statusMessage');
const resultsSection = document.getElementById('resultsSection');
const resultsBlocks = document.getElementById('resultsBlocks');
const downloadBtn = document.getElementById('downloadBtn');
const downloadBtnText = document.getElementById('downloadBtnText');

let selectedFile = null;
// Recognised blocks from the /recognize endpoint
let recognisedBlocks = [];

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
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/bmp', 'image/tiff'];
    if (!allowedTypes.includes(file.type)) {
        showStatus('不支持的文件格式。请上传 PNG, JPEG, WebP, BMP 或 TIFF 图片。', 'error');
        return;
    }

    selectedFile = file;
    recognisedBlocks = [];

    const reader = new FileReader();
    reader.onload = (e) => {
        preview.src = e.target.result;
        uploadArea.style.display = 'none';
        previewSection.style.display = 'block';
        recognizeBtn.disabled = false;
        resultsSection.style.display = 'none';
        showStatus('', '');
    };
    reader.readAsDataURL(file);
}

// Clear button handler
clearBtn.addEventListener('click', () => {
    selectedFile = null;
    recognisedBlocks = [];
    fileInput.value = '';
    uploadArea.style.display = 'block';
    previewSection.style.display = 'none';
    recognizeBtn.disabled = true;
    progressBar.style.display = 'none';
    progressFill.style.width = '0%';
    resultsSection.style.display = 'none';
    resultsBlocks.innerHTML = '';
    showStatus('', '');
});

// ── Step 1: Recognise ──────────────────────────────────────────────────────────

recognizeBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    recognizeBtn.disabled = true;
    btnText.textContent = '识别中...';
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';
    resultsSection.style.display = 'none';
    showStatus('正在上传图片...', '');

    try {
        progressFill.style.width = '30%';

        const formData = new FormData();
        formData.append('file', selectedFile);

        showStatus('正在识别文字和公式...', '');
        progressFill.style.width = '60%';

        const response = await fetch('/api/v1/recognize', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '识别失败' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();
        recognisedBlocks = data.blocks || [];

        progressFill.style.width = '100%';
        showStatus(`✅ ${data.message}`, 'success');

        renderResults(recognisedBlocks);

        setTimeout(() => {
            btnText.textContent = '重新识别';
            recognizeBtn.disabled = false;
            progressBar.style.display = 'none';
            progressFill.style.width = '0%';
        }, 800);

    } catch (error) {
        console.error('Recognition error:', error);
        showStatus(`❌ 识别失败：${error.message}`, 'error');
        btnText.textContent = '重试';
        recognizeBtn.disabled = false;
        progressBar.style.display = 'none';
        progressFill.style.width = '0%';
    }
});

// Render recognised blocks with LaTeX rendered by MathJax
function renderResults(blocks) {
    resultsBlocks.innerHTML = '';

    if (blocks.length === 0) {
        resultsBlocks.innerHTML = '<p class="no-results">未能识别出任何内容。</p>';
        resultsSection.style.display = 'block';
        return;
    }

    blocks.forEach((block, idx) => {
        const div = document.createElement('div');
        div.className = `result-block result-block--${block.block_type}`;

        const label = document.createElement('span');
        label.className = 'result-block__label';
        label.textContent = block.block_type === 'formula' ? '公式' : '文字';
        div.appendChild(label);

        const content = document.createElement('div');
        content.className = 'result-block__content';

        if (block.block_type === 'formula') {
            // Render LaTeX using MathJax display math
            content.textContent = `$$${block.content}$$`;
        } else {
            content.textContent = block.content;
        }

        div.appendChild(content);
        resultsBlocks.appendChild(div);
    });

    resultsSection.style.display = 'block';

    // Ask MathJax to typeset the newly added content
    if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([resultsBlocks]).catch(console.error);
    }
}

// ── Step 2: Download Word ──────────────────────────────────────────────────────

downloadBtn.addEventListener('click', async () => {
    if (recognisedBlocks.length === 0) return;

    downloadBtn.disabled = true;
    downloadBtnText.textContent = '生成中...';

    try {
        const title = selectedFile ? selectedFile.name.split('.').slice(0, -1).join('.') : '识别文档';
        const payload = { blocks: recognisedBlocks, title };

        const response = await fetch('/api/v1/generate-word', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '生成失败' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = title + '.docx';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showStatus('✅ Word 文档已下载。', 'success');

    } catch (error) {
        console.error('Word generation error:', error);
        showStatus(`❌ 下载失败：${error.message}`, 'error');
    } finally {
        downloadBtnText.textContent = '⬇️ 下载 Word 文档';
        downloadBtn.disabled = false;
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
