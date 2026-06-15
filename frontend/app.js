document.addEventListener('DOMContentLoaded', () => {
    // ── DOM refs ──────────────────────────────────────────────────────────────
    const dropZone         = document.getElementById('dropZone');
    const fileInput        = document.getElementById('fileInput');
    const imagePreview     = document.getElementById('imagePreview');
    const previewImg       = document.getElementById('previewImg');
    const fileIconPreview  = document.getElementById('fileIconPreview');
    const fileNameDisplay  = document.getElementById('fileNameDisplay');
    const processBtn       = document.getElementById('processBtn');
    const loadingOverlay   = document.getElementById('loadingOverlay');
    const loadingText      = document.getElementById('loadingText');
    const resetFileBtn     = document.getElementById('resetFileBtn');

    const extractedTextEl  = document.getElementById('extractedText');
    const textPlaceholder  = document.getElementById('textPlaceholder');
    const saveTextBtn      = document.getElementById('saveTextBtn');
    const saveStatus       = document.getElementById('saveStatus');

    const chatInput        = document.getElementById('chatInput');
    const sendChatBtn      = document.getElementById('sendChatBtn');
    const chatMessages     = document.getElementById('chatMessages');

    const compareBtn       = document.getElementById('compareBtn');
    const compareTextInput = document.getElementById('compareTextInput');
    const compareStrategy  = document.getElementById('compareStrategy');
    const compareResults   = document.getElementById('compareResults');
    const simScoreValue    = document.getElementById('simScoreValue');
    const scoreArc         = document.getElementById('scoreArc');
    const scoreSubtext     = document.getElementById('scoreSubtext');
    const keywordsList     = document.getElementById('keywordsList');

    const API = 'http://127.0.0.1:8000';
    let currentFile    = null;

    // ── Backend health check on load ──────────────────────────────────────────
    fetch(`${API}/`)
        .then(r => r.json())
        .then(() => console.log('✅ Backend reachable'))
        .catch(() => {
            console.warn('⚠️ Backend not reachable at', API);
            showBanner(
                '⚠️ Cannot connect to backend. Make sure <code>run.py</code> is running and ' +
                'the backend started without errors on port 8000.',
                'warning'
            );
        });

    function showBanner(html, type = 'error') {
        let banner = document.getElementById('_statusBanner');
        if (!banner) {
            banner = document.createElement('div');
            banner.id = '_statusBanner';
            banner.style.cssText = [
                'position:fixed', 'top:1rem', 'left:50%', 'transform:translateX(-50%)',
                'z-index:9999', 'max-width:560px', 'width:90%',
                'padding:0.9rem 1.25rem', 'border-radius:0.6rem',
                'font-size:0.83rem', 'font-family:Space Mono,monospace',
                'line-height:1.5', 'box-shadow:0 8px 32px rgba(0,0,0,0.6)',
                'cursor:pointer'
            ].join(';');
            banner.title = 'Click to dismiss';
            banner.onclick = () => banner.remove();
            document.body.appendChild(banner);
        }
        banner.style.background  = type === 'warning' ? 'rgba(245,158,11,0.15)' : 'rgba(248,113,113,0.15)';
        banner.style.border      = type === 'warning' ? '1px solid rgba(245,158,11,0.5)' : '1px solid rgba(248,113,113,0.5)';
        banner.style.color       = type === 'warning' ? '#fbbf24' : '#f87171';
        banner.innerHTML         = html + ' <small style="opacity:0.5">(click to dismiss)</small>';
    }

    async function apiFetch(url, options = {}) {
        try {
            const res = await fetch(url, options);
            if (!res.ok) {
                let detail = `HTTP ${res.status}`;
                try { const j = await res.json(); detail = j.detail || j.message || detail; } catch (_) {}
                throw new Error(detail);
            }
            return await res.json();
        } catch (err) {
            if (err.message === 'Failed to fetch' || err instanceof TypeError) {
                throw new Error(
                    'Cannot reach the backend server.\n\n' +
                    '1. Make sure run.py is running.\n' +
                    '2. Check the terminal for Python errors.\n' +
                    '3. Visit http://127.0.0.1:8000 in your browser to verify.'
                );
            }
            throw err;
        }
    }

    // ── Drag & Drop ───────────────────────────────────────────────────────────
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', e => { if (e.target.files.length) handleFile(e.target.files[0]); });

    function handleFile(file) {
        currentFile = file;
        fileNameDisplay.textContent = file.name;
        dropZone.classList.add('hidden');
        imagePreview.classList.remove('hidden');

        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = e => {
                previewImg.src = e.target.result;
                previewImg.classList.remove('hidden');
                fileIconPreview.classList.add('hidden');
            };
            reader.readAsDataURL(file);
        } else {
            previewImg.classList.add('hidden');
            fileIconPreview.classList.remove('hidden');
            let icon = 'fa-file-lines';
            if (file.name.endsWith('.pdf'))                                       icon = 'fa-file-pdf';
            else if (file.name.endsWith('.doc') || file.name.endsWith('.docx'))   icon = 'fa-file-word';
            else if (file.name.endsWith('.xls') || file.name.endsWith('.xlsx'))   icon = 'fa-file-excel';
            fileIconPreview.innerHTML = `<i class="fa-solid ${icon}"></i>`;
        }
    }

    if (resetFileBtn) {
        resetFileBtn.addEventListener('click', () => {
            currentFile = null;
            fileNameDisplay.textContent = '';
            imagePreview.classList.add('hidden');
            dropZone.classList.remove('hidden');
            fileInput.value = '';
            
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('[data-target="text-result"]').classList.add('active');
            document.getElementById('text-result').classList.add('active');
            textPlaceholder.classList.remove('hidden');
            extractedTextEl.classList.add('hidden');
            saveTextBtn.classList.add('hidden');

            const compareExtText = document.getElementById('compareExtractedText');
            if (compareExtText) compareExtText.innerHTML = '<p style="color:var(--text-muted); font-size: 0.8rem;">Upload a document to extract text.</p>';
        });
    }

    // ── Process File ──────────────────────────────────────────────────────────
    processBtn.addEventListener('click', async () => {
        if (!currentFile) return;
        const formData = new FormData();
        formData.append('file', currentFile);

        showLoading('Extracting text & vectorizing document...');
        try {
            const data = await apiFetch(`${API}/api/process`, { method: 'POST', body: formData });
            if (data.status === 'error') throw new Error(data.message);
            displayResults(data);
        } catch (err) {
            alert('Error: ' + err.message);
        } finally {
            hideLoading();
        }
    });

    // ── Display Results ───────────────────────────────────────────────────────
    function displayResults(data) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector('[data-target="text-result"]').classList.add('active');
        document.getElementById('text-result').classList.add('active');

        // Unhide the query section below the upload area
        const querySection = document.getElementById('querySection');
        if (querySection) {
            querySection.style.display = 'block';
        }

        const text = data.text || data.extracted_text || '';
        if (text) {
            textPlaceholder.classList.add('hidden');
            extractedTextEl.classList.remove('hidden');
            extractedTextEl.value = text;
            saveTextBtn.classList.remove('hidden');
            
            const compareExtText = document.getElementById('compareExtractedText');
            if (compareExtText) compareExtText.textContent = text;
        } else {
            textPlaceholder.classList.remove('hidden');
            extractedTextEl.classList.add('hidden');
            textPlaceholder.querySelector('p').textContent = 'No text could be extracted.';
            
            const compareExtText = document.getElementById('compareExtractedText');
            if (compareExtText) compareExtText.innerHTML = '<p style="color:var(--text-muted); font-size: 0.8rem;">No text extracted.</p>';
        }
    }

    // ── Update Extracted Text ─────────────────────────────────────────────────
    saveTextBtn.addEventListener('click', async () => {
        const text = extractedTextEl.value;
        try {
            await apiFetch(`${API}/api/update_text`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_text: text, strategy: "word" }) // passing dummy strategy just to fit CompareRequest schema
            });
            const compareExtText = document.getElementById('compareExtractedText');
            if (compareExtText) compareExtText.textContent = text;
            
            saveStatus.style.opacity = 1;
            setTimeout(() => { saveStatus.style.opacity = 0; }, 2000);
        } catch(e) {
            alert('Failed to save updated text.');
        }
    });

    // ── Chat / Q&A ────────────────────────────────────────────────────────────
    function appendMessage(text, isUser=false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${isUser ? 'user' : 'system'}`;
        msgDiv.style.display = 'flex';
        msgDiv.style.gap = '0.75rem';
        msgDiv.style.justifyContent = isUser ? 'flex-end' : 'flex-start';
        
        let bubbleStyle = isUser ? 
            'background: var(--accent); color: #000; padding: 0.75rem 1rem; border-radius: 0.5rem; font-size: 0.85rem;' : 
            'background: rgba(56,189,248,0.1); padding: 0.75rem 1rem; border-radius: 0.5rem; border: 1px solid rgba(56,189,248,0.2); font-size: 0.85rem;';
        
        let avatarHTML = isUser ? '' : `<div class="msg-avatar" style="color: var(--accent); font-size: 1.5rem;"><i class="fa-solid fa-robot"></i></div>`;
        
        msgDiv.innerHTML = `
            ${avatarHTML}
            <div class="msg-bubble" style="${bubbleStyle} white-space: pre-wrap;">${text}</div>
        `;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    sendChatBtn.addEventListener('click', async () => {
        const q = chatInput.value.trim();
        if (!q) return;
        chatInput.value = '';
        appendMessage(q, true);
        
        showLoading('Asking document...');
        try {
            const data = await apiFetch(`${API}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: q })
            });
            const answer = data.status === 'success' ? data.response : (data.message || 'No response.');
            appendMessage(answer, false);
        } catch (err) {
            appendMessage('Error: ' + err.message, false);
        } finally {
            hideLoading();
        }
    });
    chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChatBtn.click(); });

    // ── Direct Query / Search ─────────────────────────────────────────────────
    const queryBtn = document.getElementById('queryBtn');
    const queryInput = document.getElementById('queryInput');
    const queryResult = document.getElementById('queryResult');

    if (queryBtn && queryInput && queryResult) {
        queryBtn.addEventListener('click', async () => {
            const q = queryInput.value.trim();
            if (!q) return;
            
            queryResult.innerHTML = '<p><i class="fa-solid fa-spinner fa-spin"></i> Searching...</p>';
            queryResult.classList.remove('hidden');

            try {
                let finalQuery = q;
                // If the user inputs a comma-separated list of fields, instruct the AI to extract all of them
                if (q.includes(',') && !q.includes('?')) {
                    finalQuery = `Please extract the following specific details from the document and present them as a bulleted list:\n${q}`;
                }

                const data = await apiFetch(`${API}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: finalQuery })
                });
                const answer = data.status === 'success' ? data.response : (data.message || 'No response.');
                
                queryResult.innerHTML = `<p style="white-space: pre-wrap;"><strong>Result:</strong><br/>${answer}</p>`;
                
                // Also append to the chat tab to keep history sync
                appendMessage(q, true);
                appendMessage(answer, false);
            } catch (err) {
                queryResult.innerHTML = `<p style="color:var(--danger)">Error: ${err.message}</p>`;
            }
        });

        queryInput.addEventListener('keydown', e => { if (e.key === 'Enter') queryBtn.click(); });
    }

    // ── Compare ───────────────────────────────────────────────────────────────
    compareBtn.addEventListener('click', async () => {
        const text = compareTextInput.value.trim();
        const strategy = compareStrategy ? compareStrategy.value : 'word';
        
        if (!text) { alert('Please paste text to compare.'); return; }
        showLoading(`Analyzing similarity using ${strategy} algorithm...`);
        try {
            const data = await apiFetch(`${API}/api/compare`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_text: text, strategy: strategy })
            });

            if (data.status === 'success') {
                compareResults.classList.remove('hidden');
                const placeholder = document.getElementById('compareResultsPlaceholder');
                if (placeholder) placeholder.classList.add('hidden');
                
                const accItem = document.getElementById('accHeaderResults');
                if (accItem && !accItem.parentElement.classList.contains('active')) {
                    accItem.parentElement.classList.add('active');
                }

                const score = data.similarity_score || 0;
                simScoreValue.textContent = score;
                const offset = 314 - (score / 100) * 314;
                scoreArc.style.strokeDashoffset = offset;
                scoreArc.style.stroke = score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#f87171';

                scoreSubtext.textContent = `Compared using ${strategy.toUpperCase()} matching strategy.`;

                keywordsList.innerHTML = (data.matching_keywords || []).length > 0
                    ? data.matching_keywords.sort()
                        .map(kw => `<span class="keyword-badge">${kw}</span>`).join('')
                    : '<p style="font-size:0.82rem;color:var(--text-muted)">None</p>';
                
                const missingList = document.getElementById('missingKeywordsList');
                if (missingList) {
                    missingList.innerHTML = (data.missing_keywords || []).length > 0
                        ? data.missing_keywords.sort()
                            .map(kw => `<span class="keyword-badge" style="color:var(--danger); border-color:var(--danger); background:rgba(248,113,113,0.1)">${kw}</span>`).join('')
                        : '<p style="font-size:0.82rem;color:var(--text-muted)">None</p>';
                }
            } else {
                alert(data.message || 'Error comparing text.');
            }
        } catch (err) {
            alert('Error: ' + err.message);
        } finally {
            hideLoading();
        }
    });

    // ── Tabs ──────────────────────────────────────────────────────────────────
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
        });
    });

    // ── Accordion ─────────────────────────────────────────────────────────────
    document.querySelectorAll('.accordion-header').forEach(header => {
        header.addEventListener('click', () => {
            const item = header.parentElement;
            item.classList.toggle('active');
        });
    });

    // ── Helpers ───────────────────────────────────────────────────────────────
    function showLoading(msg = 'Processing...') {
        loadingText.textContent = msg;
        loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        loadingOverlay.classList.add('hidden');
    }
});