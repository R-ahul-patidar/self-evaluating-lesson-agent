/**
 * app.js — Vanilla JavaScript for the Self-Evaluating Lesson Agent UI.
 *
 * Flow:
 *   1. User submits form → POST /generate → gets run_id
 *   2. setInterval polls GET /runs/{run_id} every 2s
 *   3. Each poll: update workflow steps, evaluation panel
 *   4. On terminal status (PASS/FAIL): stop polling, show final results
 *
 * No framework. No build step. Plain DOM manipulation.
 */

'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let currentRunId = null;
let pollInterval = null;
let currentTopic = '';
let currentContent = '';
let lastStepsCount = 0;

// ── DOM References ────────────────────────────────────────────────────────────
const form          = document.getElementById('generate-form');
const submitBtn     = document.getElementById('submit-btn');
const workflowSec   = document.getElementById('workflow-section');
const evalSec       = document.getElementById('evaluation-section');
const logSec        = document.getElementById('rejection-log-section');
const lessonSec     = document.getElementById('lesson-section');
const errorToast    = document.getElementById('error-toast');
const toastMsg      = document.getElementById('toast-message');
const attemptBadge  = document.getElementById('attempt-badge');
const evalBadge     = document.getElementById('eval-overall-badge');
const evalTable     = document.getElementById('eval-checks-table');
const logContent    = document.getElementById('rejection-log-content');
const lessonContent = document.getElementById('lesson-content');
const lessonMeta    = document.getElementById('lesson-meta');
const copyBtn       = document.getElementById('copy-btn');
const downloadBtn   = document.getElementById('download-btn');

// ── Form submission ───────────────────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await startGeneration();
});

async function startGeneration() {
    const topic = document.getElementById('topic').value.trim();
    if (!topic) { showError('Please enter a topic.'); return; }

    currentTopic = topic;
    currentContent = '';
    lastStepsCount = 0;

    // Reset UI
    resetUI();
    setButtonLoading(true);
    workflowSec.classList.remove('hidden');

    const payload = {
        topic:           topic,
        content_type:    document.getElementById('content_type').value,
        education_level: document.getElementById('education_level').value,
        english_level:   document.getElementById('english_level').value,
        prior_knowledge: document.getElementById('prior_knowledge').value,
        learning_goal:   document.getElementById('learning_goal').value,
        demo_mode:       document.getElementById('demo_mode').checked,
    };

    try {
        const res = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Generation failed.');
        }

        const data = await res.json();
        currentRunId = data.run_id;

        // Mark first step done
        markStepDone('step-request_received', 'pass', '✓');

        // Start polling
        pollInterval = setInterval(pollRunStatus, 2000);

    } catch (err) {
        setButtonLoading(false);
        showError(err.message || 'Failed to start generation.');
        workflowSec.classList.add('hidden');
    }
}

// ── Polling ───────────────────────────────────────────────────────────────────
async function pollRunStatus() {
    if (!currentRunId) return;

    try {
        const res = await fetch(`/runs/${currentRunId}`);
        if (!res.ok) return;
        const data = await res.json();
        updateUI(data);

        // Stop polling on terminal state
        if (data.status === 'PASS' || data.status === 'FAIL' || data.status === 'error') {
            clearInterval(pollInterval);
            pollInterval = null;
            setButtonLoading(false);
        }

    } catch (err) {
        console.warn('Poll error:', err);
    }
}

// ── UI Update from Poll ───────────────────────────────────────────────────────
function updateUI(data) {
    const steps = data.steps_completed || [];
    const status = data.status;
    const attempt = data.attempt || 1;
    const maxAttempts = data.max_attempts || 3;

    // Update attempt badge
    attemptBadge.textContent = `Attempt ${attempt} / ${maxAttempts}`;

    // Update workflow steps based on completed steps list
    updateWorkflowSteps(steps, status);

    // Update evaluation panel
    if (data.evaluation) {
        updateEvaluationPanel(data.evaluation);
    }

    // Update rejection log
    if (data.rejection_log && data.rejection_log.length > 0) {
        updateRejectionLog(data.rejection_log);
    }

    // Handle terminal states
    if (status === 'PASS') {
        markWorkflowFinal('pass');
        if (data.final_content) {
            currentContent = data.final_content;
            showFinalLesson(data);
        }
    } else if (status === 'FAIL') {
        markWorkflowFinal('fail');
        if (data.final_content) {
            currentContent = data.final_content;
            showFinalLesson(data);
        }
    } else if (status === 'error') {
        showError(data.error || 'Workflow encountered an error.');
    }
}

function updateWorkflowSteps(steps, status) {
    // Map completed step identifiers to DOM step elements
    const hasStep = (prefix) => steps.some(s => s.startsWith(prefix));

    if (hasStep('reference_context_retrieved')) {
        markStepDone('step-context', 'pass', '✓');
    } else if (status === 'running') {
        setStepRunning('step-context');
    }

    if (hasStep('content_generated')) {
        markStepDone('step-generate', 'pass', '✓');
    } else if (hasStep('reference_context_retrieved') && status === 'running') {
        setStepRunning('step-generate');
    }

    const evalPassed = steps.some(s => s.startsWith('evaluation_passed'));
    const evalFailed = steps.some(s => s.startsWith('evaluation_failed'));

    if (evalPassed || evalFailed) {
        const cls = evalPassed ? 'pass' : 'fail';
        const icon = evalPassed ? '✓' : '✗';
        markStepDone('step-evaluate', cls, icon);
    } else if (hasStep('content_generated') && status === 'running') {
        setStepRunning('step-evaluate');
    }

    // Show regenerate step if a retry happened
    if (hasStep('regenerated_attempt')) {
        const regenStep = document.getElementById('step-regenerate');
        regenStep.classList.remove('hidden');
        const isRegenerating = status === 'running' && !hasStep('finalized');
        markStepDone('step-regenerate', isRegenerating ? 'running' : 'pass',
                      isRegenerating ? '↻' : '✓');
    }

    if (hasStep('finalized')) {
        const finalCls = status === 'PASS' ? 'pass' : 'fail';
        const finalIcon = status === 'PASS' ? '✓' : '✗';
        markStepDone('step-finalize', finalCls, finalIcon);
    } else if ((evalPassed || evalFailed) && status === 'running') {
        setStepRunning('step-finalize');
    }
}

function markStepDone(elementId, cls, icon) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.classList.remove('pending', 'running', 'pass', 'fail');
    el.classList.add(cls);
    el.querySelector('.step-icon').textContent = icon;
}

function setStepRunning(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (!el.classList.contains('running')) {
        el.classList.remove('pending', 'pass', 'fail');
        el.classList.add('running');
        el.querySelector('.step-icon').textContent = '↻';
    }
}

function markWorkflowFinal(cls) {
    markStepDone('step-finalize', cls, cls === 'pass' ? '✓' : '✗');
}

// ── Evaluation Panel ─────────────────────────────────────────────────────────
function updateEvaluationPanel(evaluation) {
    evalSec.classList.remove('hidden');

    // Overall badge
    evalBadge.textContent = evaluation.passed ? '✓ PASS' : '✗ FAIL';
    evalBadge.className = 'status-badge ' + (evaluation.passed ? 'pass' : 'fail');

    // Checks table
    evalTable.innerHTML = '';
    (evaluation.checks || []).forEach(check => {
        const row = document.createElement('div');
        row.className = 'eval-row ' + (check.passed ? 'pass' : 'fail');
        row.innerHTML = `
            <span class="eval-check-name">${formatCheckName(check.name)}</span>
            <span class="eval-check-status ${check.passed ? 'pass' : 'fail'}">${check.passed ? '✓ PASS' : '✗ FAIL'}</span>
            <span class="eval-check-reason">${renderInlineMarkdown(check.reason || '')}</span>
        `;
        evalTable.appendChild(row);
    });
}

// ── Rejection Log ─────────────────────────────────────────────────────────────
function updateRejectionLog(rejectionLog) {
    logSec.classList.remove('hidden');
    logContent.innerHTML = '';

    rejectionLog.forEach(entry => {
        const div = document.createElement('div');
        div.className = 'rejection-entry';
        div.innerHTML = `
            <div class="rejection-header">
                <span class="rejection-attempt">✗ Attempt ${entry.attempt} — ${entry.status}</span>
                <span style="font-size:12px;color:var(--text-muted)">${formatTimestamp(entry.timestamp)}</span>
            </div>
            <div class="rejection-body">
                <div class="rejection-section">
                    <div class="rejection-section-title">Failed Checks</div>
                    <ul>
                        ${entry.failed_checks.map(c => `<li>${formatCheckName(c)}</li>`).join('')}
                    </ul>
                </div>
                <div class="rejection-section">
                    <div class="rejection-section-title">Failure Reasons</div>
                    <ul>
                        ${entry.failure_reasons.map(r => `<li>${renderInlineMarkdown(r)}</li>`).join('')}
                    </ul>
                </div>
                ${entry.changes_made ? `
                <div class="rejection-section">
                    <div class="rejection-section-title">Changes Applied</div>
                    <p class="rejection-changes">${renderInlineMarkdown(entry.changes_made)}</p>
                </div>` : ''}
            </div>
        `;
        logContent.appendChild(div);
    });
}

// ── Final Lesson ──────────────────────────────────────────────────────────────
function showFinalLesson(data) {
    lessonSec.classList.remove('hidden');

    const statusText = data.status === 'PASS' ? '✓ PASSED' : '✗ FAILED (retry limit reached)';
    const statusCls = data.status === 'PASS' ? 'pass' : 'fail';

    lessonMeta.innerHTML = `
        <span class="status-badge ${statusCls}">${statusText}</span>
        <span>Attempts: ${data.attempt}</span>
    `;

    // Render formatted markdown with highlighted terms
    lessonContent.innerHTML = renderMarkdown(data.final_content || '');

    // Scroll into view
    lessonSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Copy / Download ───────────────────────────────────────────────────────────
function copyLesson() {
    if (!currentContent) return;
    navigator.clipboard.writeText(currentContent).then(() => {
        const orig = copyBtn.innerHTML;
        copyBtn.innerHTML = '<span>✓</span> Copied!';
        setTimeout(() => { copyBtn.innerHTML = orig; }, 2000);
    });
}

function downloadLesson() {
    if (!currentContent) return;
    const blob = new Blob([currentContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentTopic.replace(/\s+/g, '_').toLowerCase()}_lesson.md`;
    a.click();
    URL.revokeObjectURL(url);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function resetUI() {
    evalSec.classList.add('hidden');
    logSec.classList.add('hidden');
    lessonSec.classList.add('hidden');
    evalTable.innerHTML = '';
    logContent.innerHTML = '';
    lessonContent.textContent = '';
    evalBadge.textContent = '';
    evalBadge.className = 'status-badge';
    errorToast.classList.add('hidden');

    // Reset all workflow steps to pending
    document.querySelectorAll('.workflow-step').forEach(step => {
        step.classList.remove('running', 'pass', 'fail');
        step.classList.add('pending');
        step.querySelector('.step-icon').textContent = '○';
    });
    document.getElementById('step-regenerate').classList.add('hidden');
    attemptBadge.textContent = 'Attempt 1 / 3';
}

function setButtonLoading(loading) {
    submitBtn.disabled = loading;
    if (loading) {
        submitBtn.innerHTML = '<span class="btn-spinner"></span><span class="btn-text">Generating…</span>';
    } else {
        submitBtn.innerHTML = '<span class="btn-icon">⚡</span><span class="btn-text">Generate Lesson</span>';
    }
}

function showError(message) {
    toastMsg.textContent = message;
    errorToast.classList.remove('hidden');
    setTimeout(() => errorToast.classList.add('hidden'), 6000);
}

function formatCheckName(name) {
    return (name || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatTimestamp(ts) {
    if (!ts) return '';
    try { return new Date(ts).toLocaleTimeString(); }
    catch { return ts; }
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function renderMarkdown(md) {
    if (!md) return '';
    if (window.marked && typeof window.marked.parse === 'function') {
        try {
            return window.marked.parse(md, { gfm: true, breaks: true });
        } catch (e) {
            console.warn('Marked parse error, using fallback:', e);
        }
    }
    return fallbackMarkdown(md);
}

function renderInlineMarkdown(text) {
    if (!text) return '';
    let escaped = escapeHtml(text);
    // Bold: **text** -> <strong class="highlight-term">text</strong>
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong class="highlight-term">$1</strong>');
    escaped = escaped.replace(/__(.*?)__/g, '<strong class="highlight-term">$1</strong>');
    // Italic: *text* -> <em>text</em>
    escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');
    escaped = escaped.replace(/_(.*?)_/g, '<em>$1</em>');
    // Inline code: `code` -> <code>code</code>
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
    return escaped;
}

function fallbackMarkdown(md) {
    let html = escapeHtml(md);
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="highlight-term">$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/```([\s\S]*?)```/gm, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\n\n+/g, '</p><p>');
    return '<p>' + html + '</p>';
}

// Expose for inline onclick
window.copyLesson = copyLesson;
window.downloadLesson = downloadLesson;
