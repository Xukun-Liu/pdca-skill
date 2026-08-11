/* 日积面板 - 原生 JS + fetch + 契约校验 */
let API_CONTRACTS = {};
let memoryData = { entries: [], projects: [] };
let currentProject = null;
let currentDocType = 'summary';

document.addEventListener('DOMContentLoaded', async () => {
    await loadContracts();
    await checkHealth();
    await loadDashboard();
});

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function escapeAttr(text) {
    if (text === null || text === undefined) return '';
    return String(text).replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-fadeout');
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

function openModal(title, contentHtml) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = contentHtml;
    document.getElementById('modal').style.display = 'flex';
}

function closeModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('modal').style.display = 'none';
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

async function syncAllData() {
    const btn = document.querySelector('.btn-sync');
    const originalText = btn.textContent;
    btn.textContent = '🔄 同步中...';
    btn.disabled = true;
    try {
        await loadContracts();
        await checkHealth();
        await loadDashboard();
        const activePage = document.querySelector('.page.active');
        if (activePage.id === 'page-docs') {
            await loadProjects();
            if (currentProject) {
                await loadProjectDoc(currentProject, currentDocType);
            }
        } else if (activePage.id === 'page-skills') {
            await loadSkills();
            await loadAgents();
        } else if (activePage.id === 'page-knowledge') {
            await loadMemories();
        } else if (activePage.id === 'page-settings') {
            await loadSettingsPage();
        }
        showToast('数据同步完成', 'success');
    } catch (err) {
        showToast('同步失败: ' + err.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function apiFetch(url, options = {}) {
    const res = await fetch(url, options);
    let data = null;
    const contentType = res.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        data = await res.json();
    }

    const contractName = guessContractName(url);
    if (contractName && API_CONTRACTS[contractName]) {
        const isValid = validateResponse(contractName, data);
        if (!isValid) {
            console.warn(`[Contract Warn] ${url} response does not match ${contractName} contract`, data);
        }
    }
    return { res, data };
}

function guessContractName(url) {
    if (url.includes('/contracts.json')) return null;
    if (url.includes('/health')) return null;
    if (url === '/api/projects' || url.includes('/projects')) return 'ProjectInfo';
    if (url === '/api/skills' || url.includes('/skill/') && url.endsWith('/content')) return 'SkillInfo';
    if (url === '/api/agents') return 'AgentInfo';
    if (url.includes('/knowledge')) return null;
    return null;
}

async function loadContracts() {
    try {
        const { data } = await apiFetch('/api/contracts.json');
        API_CONTRACTS = data || {};
        console.log('API contracts loaded:', Object.keys(API_CONTRACTS));
    } catch (err) {
        console.warn('契约加载失败，前端不校验', err);
    }
}

function validateResponse(contractName, data) {
    const contract = API_CONTRACTS[contractName];
    if (!contract) return true;
    if (Array.isArray(data)) return data.every(item => validateSingle(contract, item));
    return validateSingle(contract, data);
}

function validateSingle(contract, item) {
    if (!item || typeof item !== 'object') return false;
    return contract.fields.every(f => f.name in item);
}

async function checkHealth() {
    try {
        const { data } = await apiFetch('/api/health');
        const el = document.getElementById('healthStatus');
        if (data.status === 'ok') {
            el.textContent = '● 运行中 ' + data.version;
            el.classList.add('ok');
        }
        document.getElementById('version').textContent = data.version;
    } catch (err) {
        document.getElementById('healthStatus').textContent = '● 异常';
    }
}

function switchPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + pageId).classList.add('active');
    document.querySelector(`[data-page="${pageId}"]`).classList.add('active');

    if (pageId === 'intro') { /* intro 页面不需要加载数据 */ }
    if (pageId === 'docs') loadProjects();
    if (pageId === 'skills') { loadSkills(); loadAgents(); }
    if (pageId === 'knowledge') { loadMemories(); loadSourceFiles(); loadLessons(); }
    if (pageId === 'settings') loadSettingsPage();
}

function formatTime(isoStr) {
    if (!isoStr) return '-';
    try {
        const d = new Date(isoStr);
        const pad = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch {
        return isoStr.substring(0, 16);
    }
}

async function loadDashboard() {
    try {
        const [{ data: projects }, { data: skills }, { data: agents }] = await Promise.all([
            apiFetch('/api/projects'), apiFetch('/api/skills'), apiFetch('/api/agents')
        ]);

        document.getElementById('statProjects').textContent = (projects || []).length;
        document.getElementById('statSkills').textContent = (skills || []).length;
        document.getElementById('statAgents').textContent = (agents || []).length;
        document.getElementById('statZeroCall').textContent = (skills || []).filter(s => s.frequency_level === 'zero').length;
    } catch (err) {
        console.error('Dashboard load failed', err);
    }
}

async function loadProjects() {
    try {
        const { data: projects } = await apiFetch('/api/projects');
        const list = document.getElementById('docsProjectList');
        if (!projects || projects.length === 0) {
            list.innerHTML = '<p class="empty-state">无项目</p>';
            return;
        }
        list.innerHTML = projects.map(p => `
            <div class="project-item" data-name="${escapeAttr(p.name)}" onclick="loadProjectDoc('${escapeAttr(p.name)}', 'summary')">
                <div class="project-name">${escapeHtml(p.name)}</div>
                <div class="project-meta">
                    ${p.has_summary ? '<span class="badge badge-ok">SUMMARY</span>' : '<span class="badge badge-miss">无SUMMARY</span>'}
                    ${p.has_spec_main ? '<span class="badge badge-ok">SPEC</span>' : '<span class="badge badge-miss">无SPEC</span>'}
                    ${escapeHtml(p.last_active || '')}
                </div>
                <div class="project-path" title="${escapeAttr(p.path || '')}">${escapeHtml(p.path || '')}</div>
            </div>
        `).join('');
        if (projects.length === 1 && !currentProject) {
            const content = document.getElementById('docsContent');
            content.innerHTML = `
                <div class="single-project-hint">
                    <p>当前只有一个项目 <strong>${escapeHtml(projects[0].name)}</strong></p>
                    <p class="hint">在 SCAN_ROOT 下新增其他含 docs_rj/ 的项目后，可在此切换。</p>
                </div>`;
        }
    } catch (err) {
        console.error('Projects load failed', err);
    }
    loadScanRoots();
}

async function loadProjectDoc(name, docType) {
    currentProject = name;
    currentDocType = docType;
    document.querySelectorAll('.project-item').forEach(el => el.classList.remove('active'));
    const target = document.querySelector(`.project-item[data-name="${CSS.escape(name)}"]`);
    if (target) target.classList.add('active');

    loadProjectFiles(name);
    const content = document.getElementById('docsContent');
    content.innerHTML = '<p class="loading">加载中...</p>';

    try {
        const endpoint = docType === 'spec_main' ? 'spec_main' : 'summary';
        const label = docType === 'spec_main' ? 'SPEC MAIN' : 'SUMMARY';
        const { data, res } = await apiFetch(`/api/project/${encodeURIComponent(name)}/${endpoint}`);

        let toggleHtml = '';
        if (res.status === 200) {
            const otherType = docType === 'summary' ? 'spec_main' : 'summary';
            const otherLabel = docType === 'summary' ? '查看 SPEC MAIN' : '查看 SUMMARY';
            toggleHtml = `<div class="doc-toggle" style="margin-bottom:12px;">
                <button class="btn-primary" style="font-size:12px;padding:4px 12px;opacity:0.8;" onclick="loadProjectDoc('${escapeAttr(name)}', '${otherType}')">${otherLabel}</button>
            </div>`;
        }

        if (res.ok && data && data.content) {
            content.innerHTML = toggleHtml +
                `<h3>${escapeHtml(name)} - ${label}</h3><pre style="white-space:pre-wrap;font-family:inherit;max-height:500px;overflow-y:auto;">${escapeHtml(data.content)}</pre>`;
        } else {
            content.innerHTML = toggleHtml + `<p class="empty-state">无 ${label} 文件</p>`;
        }
    } catch (err) {
        content.innerHTML = '<p class="empty-state">加载失败</p>';
    }
}

async function loadSkills() {
    try {
        const { data: skills } = await apiFetch('/api/skills');
        const tbody = document.getElementById('skillTableBody');
        if (!skills || skills.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">无参考模块</td></tr>';
            return;
        }
        tbody.innerHTML = skills.map(s => {
            const agents = (s.related_agents || []).join(', ') || '-';
            return `
            <tr>
                <td><a href="#" onclick="viewSkillContent('${escapeAttr(s.name)}');return false;" style="color:var(--blue)">${escapeHtml(s.name)}</a></td>
                <td>${escapeHtml(s.pdca_tag || '-')}</td>
                <td style="max-width:250px;word-wrap:break-word;white-space:normal;line-height:1.4;">${escapeHtml(s.description || '')}</td>
                <td>${s.call_count}</td>
                <td class="freq-${s.frequency_level}">${freqLabel(s.frequency_level)}</td>
                <td style="font-size:12px;color:var(--text-muted);white-space:nowrap;">${escapeHtml(formatTime(s.last_called))}</td>
                <td style="font-size:12px;color:var(--text-secondary);max-width:150px;word-wrap:break-word;">${escapeHtml(agents)}</td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Skills load failed', err);
    }
}

async function loadAgents() {
    try {
        const { data: agents } = await apiFetch('/api/agents');
        const grid = document.getElementById('agentGrid');
        if (!agents || agents.length === 0) {
            grid.innerHTML = '<p class="empty-state">无子机器人</p>';
            return;
        }
        document.getElementById('statAgents').textContent = agents.length;
        grid.innerHTML = agents.map(a => {
            const shortName = a.name.replace('_agent_pdca', '').replace(/_pdca$/, '');
            const knowledgeHtml = (a.knowledge || []).map(k => {
                const base = k.replace('references/', '').replace('.md', '');
                return `<span class="tag tag-skill">${escapeHtml(base)}</span>`;
            }).join('') || '<span class="text-muted">-</span>';
            const triggersHtml = (a.triggers || []).slice(0, 8).map(t =>
                `<span class="tag tag-trigger">${escapeHtml(t)}</span>`
            ).join('');
            const outputHtml = (a.output_format || []).map(o =>
                `<span class="tag tag-output">${escapeHtml(o)}</span>`
            ).join('') || '-';
            return `
            <div class="agent-card">
                <div class="agent-card-header">
                    <span class="agent-icon">🤖</span>
                    <div>
                        <div class="agent-name">${escapeHtml(shortName)}</div>
                        <div class="agent-role">${escapeHtml(a.role || '')}</div>
                    </div>
                </div>
                <div class="agent-desc">${escapeHtml(a.description || '')}</div>
                <div class="agent-section">
                    <div class="agent-section-title">知识库</div>
                    <div class="tag-list">${knowledgeHtml}</div>
                </div>
                <div class="agent-section">
                    <div class="agent-section-title">触发词</div>
                    <div class="tag-list">${triggersHtml}</div>
                </div>
                <div class="agent-section">
                    <div class="agent-section-title">输出格式</div>
                    <div class="tag-list">${outputHtml}</div>
                </div>
            </div>`;
        }).join('');
    } catch (err) {
        console.error('Agents load failed', err);
    }
}

async function viewSkillContent(name) {
    try {
        const { data, res } = await apiFetch(`/api/skill/${encodeURIComponent(name)}/content`);
        if (res.ok && data && data.content) {
            openModal(`📖 ${escapeHtml(name)}`, 
                `<pre style="white-space:pre-wrap;font-family:inherit;max-height:400px;overflow-y:auto;background:var(--bg-primary);padding:12px;border-radius:6px;">${escapeHtml(data.content)}</pre>`
            );
        } else {
            showToast('技能内容加载失败', 'error');
        }
    } catch (err) {
        showToast('加载失败: ' + err.message, 'error');
    }
}

function switchSkillTab(tabId) {
    document.querySelectorAll('#page-skills .tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#page-skills .tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    event.target.classList.add('active');
}

/* ========== 记忆中心 ========== */

async function loadMemories() {
    try {
        const { data } = await apiFetch('/api/knowledge/memories');
        memoryData = data || { entries: [], projects: [], total: 0 };
        renderMemories();
    } catch (err) {
        console.error('Memories load failed', err);
        const grid = document.getElementById('memoryGrid');
        if (grid) grid.innerHTML = '<p class="empty-state">加载失败，请刷新重试</p>';
    }
}

function renderMemories() {
    const entries = memoryData.entries || [];
    const statsEl = document.getElementById('memoryStats');
    if (!statsEl) return;

    const successCount = entries.filter(e => e.outcome === 'success').length;
    const failCount = entries.filter(e => e.outcome === 'fail').length;
    const projectCount = (memoryData.projects || []).length;

    statsEl.innerHTML = `<div class="knowledge-stats-inner">
        <span>总计: <strong>${entries.length}</strong></span>
        <span>📁 项目: <strong style="color:var(--blue)">${projectCount}</strong></span>
        <span>✅ 成功: <strong style="color:#3fb950">${successCount}</strong></span>
        <span>❌ 失败: <strong style="color:#db6165">${failCount}</strong></span>
    </div>`;

    populateProjectFilter();
    filterMemories();
}

function populateProjectFilter() {
    const select = document.getElementById('memoryProjectFilter');
    if (!select) return;
    const currentVal = select.value;
    const projects = memoryData.projects || [];
    select.innerHTML = '<option value="">全部项目</option>' +
        projects.map(p => `<option value="${escapeAttr(p)}">${escapeHtml(p)}</option>`).join('');
    select.value = currentVal;
}

function filterMemories() {
    const grid = document.getElementById('memoryGrid');
    if (!grid) return;

    const searchTerm = (document.getElementById('memorySearch')?.value || '').toLowerCase();
    const projectFilter = document.getElementById('memoryProjectFilter')?.value || '';
    const outcomeFilter = document.getElementById('memoryOutcomeFilter')?.value || '';
    let entries = memoryData.entries || [];

    if (projectFilter) entries = entries.filter(e => e.project === projectFilter);
    if (outcomeFilter) entries = entries.filter(e => e.outcome === outcomeFilter);
    if (searchTerm) entries = entries.filter(e =>
        (e.task_name || '').toLowerCase().includes(searchTerm) ||
        (e.intent || '').toLowerCase().includes(searchTerm) ||
        (e.tags || []).some(t => t.toLowerCase().includes(searchTerm))
    );

    if (entries.length === 0) {
        grid.innerHTML = '<p class="empty-state">无匹配记忆条目</p>';
        return;
    }

    const outcomeLabels = { success: '✅ 成功', fail: '❌ 失败', mixed: '~ 混合', unknown: '? 未知' };

    grid.innerHTML = entries.map(e => {
        const tagsHtml = (e.tags || []).map(t => `<span class="memory-tag">${escapeHtml(t)}</span>`).join('');
        const toolsHtml = (e.tools || []).join(', ');
        return `
        <div class="memory-card" id="mem-${escapeAttr(e.id)}">
            <div class="memory-card-header">
                <span class="memory-task-name">${escapeHtml(e.task_name || '未命名')}</span>
                <span class="memory-time">${escapeHtml(e.timestamp || '')}</span>
                <span class="memory-outcome ${e.outcome || 'unknown'}">${outcomeLabels[e.outcome] || '? 未知'}</span>
            </div>
            ${e.intent ? `<div class="memory-intent">🎯 ${escapeHtml(e.intent)}</div>` : ''}
            <div class="memory-meta">
                ${e.project ? `<span class="memory-meta-item">📁 ${escapeHtml(e.project)}</span>` : ''}
                ${toolsHtml ? `<span class="memory-meta-item">🔧 ${escapeHtml(toolsHtml)}</span>` : ''}
                ${e.feedback ? `<span class="memory-meta-item">💬 ${escapeHtml(e.feedback)}</span>` : ''}
            </div>
            ${tagsHtml ? `<div class="memory-tags">${tagsHtml}</div>` : ''}
            <button class="memory-expand-btn" onclick="toggleMemoryBody('${escapeAttr(e.id)}')">展开详情</button>
            <div class="memory-body">${escapeHtml(e.body || '(无正文)')}</div>
            ${e.source_file ? `<div class="memory-source">📄 ${escapeHtml(e.source_file)}</div>` : ''}
        </div>`;
    }).join('');
}

function toggleMemoryBody(id) {
    const card = document.getElementById('mem-' + id);
    if (!card) return;
    card.classList.toggle('expanded');
    const btn = card.querySelector('.memory-expand-btn');
    if (btn) btn.textContent = card.classList.contains('expanded') ? '收起详情' : '展开详情';
}

async function openPromoteModal() {
    const modal = document.getElementById('promoteModal');
    const list = document.getElementById('promoteList');
    modal.style.display = 'flex';
    list.innerHTML = '<p class="loading">加载项目记忆...</p>';

    try {
        const { data } = await apiFetch('/api/knowledge/project-memories');
        const entries = data?.entries || [];
        if (entries.length === 0) {
            list.innerHTML = '<p class="empty-state">暂无可提炼的项目记忆</p>';
            return;
        }
        list.innerHTML = entries.map(e => `
            <div class="promote-item">
                <input type="checkbox" value="${escapeAttr(e.source_file)}" class="promote-checkbox">
                <div class="promote-item-info">
                    <div class="promote-item-name">${escapeHtml(e.task_name || '未命名')}</div>
                    <div class="promote-item-meta">
                        ${escapeHtml(e.timestamp || '')} · ${escapeHtml(e.outcome || 'unknown')}
                        ${e.intent ? ' · ' + escapeHtml(e.intent.substring(0, 60)) : ''}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (err) {
        list.innerHTML = '<p class="empty-state">加载失败</p>';
    }
}

function closePromoteModal() {
    document.getElementById('promoteModal').style.display = 'none';
}

async function confirmPromote() {
    const checkboxes = document.querySelectorAll('.promote-checkbox:checked');
    if (checkboxes.length === 0) {
        showToast('请至少选择一条记忆', 'error');
        return;
    }

    const files = Array.from(checkboxes).map(cb => cb.value.split('/').pop());

    try {
        const { data, res } = await apiFetch('/api/knowledge/promote', {
            method: 'POST',
            body: JSON.stringify({ files })
        });
        if (res.ok && data) {
            showToast(`提炼完成：提升 ${data.promoted} 条，跳过 ${data.skipped} 条`, 'success');
            closePromoteModal();
            await loadMemories();
        } else {
            showToast('提炼失败: ' + ((data && data.error) || `HTTP ${res.status}`), 'error');
        }
    } catch (err) {
        showToast('提炼失败: ' + err.message, 'error');
    }
}

async function loadSourceFiles() {
    try {
        const { data } = await apiFetch('/api/knowledge/sources');
        const list = document.getElementById('sourceFileList');
        if (!data || data.length === 0) {
            list.innerHTML = '<p class="empty-state">无记忆文件</p>';
            return;
        }
        list.innerHTML = data.map(f => `
            <div class="project-item" onclick="loadSourceContent('${escapeAttr(f.path)}')">
                <div class="project-name">${escapeHtml(f.name)}</div>
                <div class="project-meta">${(f.size / 1024).toFixed(1)}KB</div>
                <div class="project-path" style="font-size:10px;">${escapeHtml(f.path)}</div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Source files load failed', err);
    }
}

async function loadSourceContent(filePath) {
    const content = document.getElementById('sourceFileContent');
    content.innerHTML = '<p class="loading">加载中...</p>';
    try {
        const { data, res } = await apiFetch(`/api/knowledge/source/${encodeURIComponent(filePath)}`);
        if (res.ok && data) {
            content.innerHTML = `<h3>${escapeHtml(data.path)}</h3><pre style="white-space:pre-wrap;font-family:inherit;max-height:500px;overflow-y:auto;">${escapeHtml(data.content)}</pre>`;
        } else {
            content.innerHTML = '<p class="empty-state">文件不存在或为空</p>';
        }
    } catch (err) {
        content.innerHTML = '<p class="empty-state">加载失败</p>';
    }
}

function switchKnowledgeTab(tabId) {
    document.querySelectorAll('#page-knowledge .tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#page-knowledge .tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    event.target.classList.add('active');
    // 联动加载：切到 lessons tab 时重新加载经验库
    if (tabId === 'lessons') loadLessons();
}

function freqLabel(level) {
    return { high: '高', medium: '中', low: '低', zero: '零' }[level] || level;
}

async function loadScanRoots() {
    try {
        const { data } = await apiFetch('/api/scan-roots');
        const list = document.getElementById('scanRootsList');
        if (!data || !data.roots) return;
        list.innerHTML = data.roots.map(r => `
            <span class="scan-root-tag">
                ${escapeHtml(r)}
                ${r !== data.default_root ? `<span class="scan-root-remove" onclick="removeScanRoot('${escapeAttr(r)}')" title="移除">&times;</span>` : ''}
            </span>
        `).join('');
    } catch (err) {
        console.error('Scan roots load failed', err);
    }
}

function showAddScanRoot() {
    const path = prompt('请输入要扫描的文件夹路径:');
    if (!path || !path.trim()) return;
    addScanRoot(path.trim());
}

async function addScanRoot(path) {
    try {
        const { data, res } = await apiFetch('/api/scan-roots', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        if (res.ok) {
            showToast('路径已添加', 'success');
            await loadScanRoots();
            await loadProjects();
        } else {
            const errMsg = (data && data.error) ? data.error : `HTTP ${res.status}`;
            showToast('添加失败: ' + errMsg, 'error');
        }
    } catch (err) {
        showToast('添加失败: ' + err.message, 'error');
    }
}

async function removeScanRoot(path) {
    try {
        const { data, res } = await apiFetch('/api/scan-roots', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        if (res.ok) {
            showToast('路径已移除', 'success');
            await loadScanRoots();
            await loadProjects();
        } else {
            const errMsg = (data && data.error) ? data.error : `HTTP ${res.status}`;
            showToast('移除失败: ' + errMsg, 'error');
        }
    } catch (err) {
        showToast('移除失败: ' + err.message, 'error');
    }
}

async function loadProjectFiles(name) {
    const tree = document.getElementById('docsFileTree');
    tree.innerHTML = '<p class="loading">加载中...</p>';
    try {
        const { data, res } = await apiFetch(`/api/project/${encodeURIComponent(name)}/files`);
        if (res.ok && data && data.files && data.files.length > 0) {
            const files = data.files;
            const coreFiles = [];
            const otherFiles = [];

            files.forEach(f => {
                const upperName = f.name.toUpperCase();
                if (upperName.startsWith('SUMMARY') || upperName.startsWith('SPEC_MAIN')) {
                    coreFiles.push(f);
                } else {
                    otherFiles.push(f);
                }
            });

            otherFiles.sort((a, b) => {
                if (!a.modified) return 1;
                if (!b.modified) return -1;
                return new Date(b.modified) - new Date(a.modified);
            });

            const recentFiles = otherFiles.slice(0, 5);
            const displayFiles = [...coreFiles, ...recentFiles];

            tree.innerHTML = displayFiles.map(f => {
                const isCore = f.name.toUpperCase().startsWith('SUMMARY') || f.name.toUpperCase().startsWith('SPEC_MAIN');
                return `
                <div class="file-item ${isCore ? 'file-item-core' : ''}" onclick="loadFileContent('${escapeAttr(name)}', '${escapeAttr(f.relative_path)}')" title="${escapeAttr(f.relative_path)}">
                    <span class="file-icon">${isCore ? (f.name.toUpperCase().startsWith('SUMMARY') ? '📋' : '📐') : '📄'}</span>
                    <span class="file-name">${escapeHtml(f.name)}</span>
                    <span class="file-path">${escapeHtml(f.relative_path.replace(f.name, ''))}</span>
                    ${f.modified ? `<span class="file-modified">${escapeHtml(f.modified)}</span>` : ''}
                </div>
                `;
            }).join('');

            if (otherFiles.length > 5) {
                tree.innerHTML += `<div class="file-more">还有 ${otherFiles.length - 5} 个文件未显示</div>`;
            }
        } else {
            tree.innerHTML = '<p class="empty-state">无文档文件</p>';
        }
    } catch (err) {
        tree.innerHTML = '<p class="empty-state">加载失败</p>';
    }
}

async function loadFileContent(projectName, relativePath) {
    const content = document.getElementById('docsContent');
    content.innerHTML = '<p class="loading">加载中...</p>';
    try {
        const { data, res } = await apiFetch(`/api/project/${encodeURIComponent(projectName)}/file?path=${encodeURIComponent(relativePath)}`);
        if (res.ok && data && data.content) {
            content.innerHTML = `<h3>${escapeHtml(relativePath)}</h3><pre style="white-space:pre-wrap;font-family:inherit;max-height:600px;overflow-y:auto;">${escapeHtml(data.content)}</pre>`;
        } else {
            content.innerHTML = '<p class="empty-state">文件不存在或为空</p>';
        }
    } catch (err) {
        content.innerHTML = '<p class="empty-state">加载失败</p>';
    }
}

/* ============ T011 数据管理页 ============ */
async function loadSettingsPage() {
    try {
        const { res, data } = await apiFetch('/api/settings/data-path');
        if (res.ok && data) {
            document.getElementById('settingsCurrentPath').textContent = data.path || '(未知)';
            const stats = `大小: ${data.size_mb ?? '-'} MB | 文件数: ${data.file_count ?? '-'} | 最后修改: ${formatTime(data.last_modified)}`;
            document.getElementById('settingsStats').textContent = stats;
        } else {
            document.getElementById('settingsCurrentPath').textContent = '加载失败';
            document.getElementById('settingsStats').textContent = '';
        }
    } catch (err) {
        document.getElementById('settingsCurrentPath').textContent = '加载失败: ' + err.message;
        document.getElementById('settingsStats').textContent = '';
    }
}

async function saveDataPath() {
    const newPath = document.getElementById('settingsNewPath').value.trim();
    if (!newPath) { showToast('路径不能为空', 'error'); return; }
    try {
        const { res, data } = await apiFetch('/api/settings/data-path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: newPath })
        });
        if (res.ok) {
            showToast('路径已保存，新位置: ' + (data.new_path || newPath), 'success');
            await loadSettingsPage();
        } else {
            showToast('保存失败: ' + (data.error || res.status), 'error');
        }
    } catch (err) {
        showToast('保存失败: ' + err.message, 'error');
    }
}

async function migrateData() {
    const target = document.getElementById('settingsMigrateTarget').value.trim();
    if (!target) { showToast('迁移目标路径不能为空', 'error'); return; }
    if (!confirm(`确认把数据迁移到 ${target} ?`)) return;
    try {
        const { res, data } = await apiFetch('/api/settings/migrate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_path: target })
        });
        if (res.ok) {
            showToast('迁移成功: ' + (data.status || 'ok') + ' | 文件数: ' + (data.file_count ?? '-'), 'success');
            await loadSettingsPage();
        } else {
            showToast('迁移失败: ' + (data.error || res.status), 'error');
        }
    } catch (err) {
        showToast('迁移失败: ' + err.message, 'error');
    }
}

/* ========== 精华经验库（T005） ========== */

// importance_level 白名单（防异常值污染 className）
const VALID_IMPORTANCE_LEVELS = ['high', 'medium', 'low'];

async function loadLessons() {
    const listEl = document.getElementById('lessonsList');
    const statsEl = document.getElementById('lessonsStats');
    if (!listEl) return;
    try {
        const { data, res } = await apiFetch('/api/knowledge/lessons');
        // 清空加载提示（用 textContent 不用 innerHTML，防 XSS）
        listEl.textContent = '';
        if (!res.ok) {
            const errEl = document.createElement('p');
            errEl.className = 'empty-state';
            errEl.textContent = '加载失败: ' + (data && data.error ? data.error : 'HTTP ' + res.status);
            listEl.appendChild(errEl);
            return;
        }
        const lessons = (data && data.lessons) || [];
        const total = (data && data.total_lessons) || 0;

        // 统计条
        if (statsEl) {
            const highCount = lessons.filter(l => l.importance_level === 'high').length;
            const mediumCount = lessons.filter(l => l.importance_level === 'medium').length;
            const lowCount = lessons.filter(l => l.importance_level === 'low').length;
            const adoptedCount = lessons.filter(l => l.adopted).length;
            statsEl.innerHTML = `<div class="knowledge-stats-inner">
                <span>总计: <strong>${total}</strong></span>
                <span>🔴 高: <strong style="color:#db6165">${highCount}</strong></span>
                <span>🟡 中: <strong style="color:#d29922">${mediumCount}</strong></span>
                <span>🟢 低: <strong style="color:#3fb950">${lowCount}</strong></span>
                <span>✅ 已采纳: <strong style="color:var(--blue)">${adoptedCount}</strong></span>
            </div>`;
        }

        if (lessons.length === 0) {
            const hint = document.createElement('p');
            hint.className = 'empty-state';
            hint.textContent = (data && data.message) ? data.message : '暂无经验（运行 distill 后产出）';
            listEl.appendChild(hint);
            return;
        }

        for (const lesson of lessons) {
            // 用 DOM API 构建卡片，所有用户内容用 textContent 赋值（防 XSS）
            const card = document.createElement('div');
            card.className = 'lesson-card memory-card';
            card.setAttribute('data-id', lesson.lesson_id || '');

            const header = document.createElement('div');
            header.className = 'lesson-header';
            const titleEl = document.createElement('span');
            titleEl.className = 'lesson-title';
            titleEl.textContent = lesson.title || '';  // textContent 防 XSS
            const impEl = document.createElement('span');
            // importance_level 用白名单校验后拼 className，防异常值污染样式
            const safeLevel = VALID_IMPORTANCE_LEVELS.includes(lesson.importance_level) ? lesson.importance_level : 'medium';
            impEl.className = 'lesson-importance importance-' + safeLevel;
            impEl.textContent = safeLevel;
            header.appendChild(titleEl);
            header.appendChild(impEl);

            const contentEl = document.createElement('p');
            contentEl.className = 'lesson-content';
            contentEl.textContent = lesson.content || '';  // textContent 防 XSS

            const tagsEl = document.createElement('div');
            tagsEl.className = 'lesson-tags';
            for (const tag of (lesson.experience_tags || [])) {
                const tagSpan = document.createElement('span');
                tagSpan.className = 'tag';
                tagSpan.textContent = tag;  // textContent 防 XSS
                tagsEl.appendChild(tagSpan);
            }

            // H3-B 修复：移除采纳按钮，采纳统一走 /act AskUserQuestion 流程
            // 卡片改为纯展示 + 采纳状态徽章（已采纳的经验显示徽章，未采纳的不显示按钮）
            if (lesson.adopted) {
                const adoptedBadge = document.createElement('span');
                adoptedBadge.className = 'adopted-badge';
                adoptedBadge.textContent = '✅ 已采纳';
                tagsEl.appendChild(adoptedBadge);
            }

            card.appendChild(header);
            card.appendChild(contentEl);
            card.appendChild(tagsEl);
            listEl.appendChild(card);
        }
    } catch (err) {
        console.error('Lessons load failed', err);
        listEl.textContent = '';
        const errEl = document.createElement('p');
        errEl.className = 'empty-state';
        errEl.textContent = '加载失败，请刷新重试';
        listEl.appendChild(errEl);
    }
}

