// DOM Elements
const urlInput = document.getElementById('url-input');
const previewBtn = document.getElementById('preview-btn');
const convertBtn = document.getElementById('convert-btn');
const previewSection = document.getElementById('preview-section');
const progressSection = document.getElementById('progress-section');
const downloadSection = document.getElementById('download-section');
const errorSection = document.getElementById('error-section');
const downloadBtn = document.getElementById('download-btn');
const newConversionBtn = document.getElementById('new-conversion-btn');
const retryBtn = document.getElementById('retry-btn');

// Preview elements
const previewThumbnail = document.getElementById('preview-thumbnail');
const previewTitle = document.getElementById('preview-title');
const previewChannel = document.getElementById('preview-channel');
const previewDuration = document.getElementById('preview-duration');
const previewChapters = document.getElementById('preview-chapters');

// Progress elements
const progressFill = document.getElementById('progress-fill');
const progressMessage = document.getElementById('progress-message');
const progressPercent = document.getElementById('progress-percent');

// Error elements
const errorText = document.getElementById('error-text');

// State
let currentJobId = null;
let currentUrl = null;
let eventSource = null;

// Event Listeners
urlInput.addEventListener('input', handleUrlInput);
urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        previewBtn.click();
    }
});
previewBtn.addEventListener('click', handlePreview);
convertBtn.addEventListener('click', handleConvert);
downloadBtn.addEventListener('click', handleDownload);
newConversionBtn.addEventListener('click', resetUI);
retryBtn.addEventListener('click', resetUI);

// Handlers
function handleUrlInput() {
    const url = urlInput.value.trim();
    const isValid = isValidYouTubeUrl(url);
    previewBtn.disabled = !isValid;

    if (!isValid) {
        hideAllSections();
        convertBtn.disabled = true;
    }
}

async function handlePreview() {
    const url = urlInput.value.trim();
    if (!isValidYouTubeUrl(url)) return;

    currentUrl = url;
    previewBtn.disabled = true;
    previewBtn.textContent = 'Loading...';

    try {
        const response = await fetch(`/api/v1/preview?url=${encodeURIComponent(url)}`);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to fetch video info');
        }

        const data = await response.json();
        showPreview(data);
        convertBtn.disabled = false;
    } catch (error) {
        showError(error.message);
    } finally {
        previewBtn.disabled = false;
        previewBtn.textContent = 'Preview';
    }
}

async function handleConvert() {
    if (!currentUrl) return;

    hideAllSections();
    showProgress();
    convertBtn.disabled = true;
    previewBtn.disabled = true;
    urlInput.disabled = true;

    try {
        const response = await fetch('/api/v1/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: currentUrl }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start conversion');
        }

        const data = await response.json();
        currentJobId = data.job_id;

        // Start SSE connection for progress updates
        startProgressStream(currentJobId);
    } catch (error) {
        showError(error.message);
        enableInputs();
    }
}

function startProgressStream(jobId) {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource(`/api/v1/convert/${jobId}/progress`);

    eventSource.addEventListener('progress', (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);

        if (data.status === 'completed') {
            eventSource.close();
            showDownload();
        } else if (data.status === 'failed') {
            eventSource.close();
            showError(data.error || 'Conversion failed');
            enableInputs();
        }
    });

    eventSource.addEventListener('error', () => {
        eventSource.close();
        showError('Connection lost. Please try again.');
        enableInputs();
    });
}

function handleDownload() {
    if (!currentJobId) return;

    // Trigger download
    window.location.href = `/api/v1/convert/${currentJobId}/download`;
}

// UI Functions
function showPreview(data) {
    previewThumbnail.src = data.thumbnail_url || '';
    previewTitle.textContent = data.title;
    previewChannel.textContent = data.channel;
    previewDuration.textContent = `Duration: ${data.duration_formatted}`;
    previewChapters.textContent = data.has_chapters
        ? `${data.chapter_count} chapters`
        : 'No chapters';

    hideAllSections();
    previewSection.classList.remove('hidden');
}

function showProgress() {
    hideAllSections();
    progressSection.classList.remove('hidden');
    updateProgress({ progress: 0, message: 'Starting conversion...' });
}

function updateProgress(data) {
    const percent = data.progress || 0;
    progressFill.style.width = `${percent}%`;
    progressPercent.textContent = `${percent}%`;
    progressMessage.textContent = data.message || 'Processing...';
}

function showDownload() {
    hideAllSections();
    downloadSection.classList.remove('hidden');
}

function showError(message) {
    hideAllSections();
    errorText.textContent = message;
    errorSection.classList.remove('hidden');
}

function hideAllSections() {
    previewSection.classList.add('hidden');
    progressSection.classList.add('hidden');
    downloadSection.classList.add('hidden');
    errorSection.classList.add('hidden');
}

function resetUI() {
    hideAllSections();
    urlInput.value = '';
    urlInput.disabled = false;
    previewBtn.disabled = true;
    convertBtn.disabled = true;
    currentJobId = null;
    currentUrl = null;

    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    enableInputs();
    urlInput.focus();
}

function enableInputs() {
    urlInput.disabled = false;
    previewBtn.disabled = !isValidYouTubeUrl(urlInput.value.trim());
    convertBtn.disabled = true;
}

// Utility Functions
function isValidYouTubeUrl(url) {
    const patterns = [
        /(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=[a-zA-Z0-9_-]{11}/,
        /(?:https?:\/\/)?(?:www\.)?youtu\.be\/[a-zA-Z0-9_-]{11}/,
        /(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/[a-zA-Z0-9_-]{11}/,
    ];
    return patterns.some(pattern => pattern.test(url));
}

// Initialize
urlInput.focus();
