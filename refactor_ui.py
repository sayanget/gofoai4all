import re

with open('frontend/feishu_config.html' if not __import__('os').path.exists('feishu_config.html') else 'feishu_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace #rules_metrics_list with #rules_categories_list
content = content.replace('<div id="rules_metrics_list">', '<div id="rules_categories_list">')
content = content.replace('addNewMetricRow()', 'addNewCategoryCard()')
content = content.replace('新增考核/通晒指标', '新增指标分类')

# 2. Update renderRulesManager
old_render = '''        function renderRulesManager() {
            const metricsContainer = document.getElementById('rules_metrics_list');
            metricsContainer.innerHTML = '';
            
            const metrics = currentRulesConfig.metrics || {};
            Object.entries(metrics).forEach(([name, meta]) => {
                addNewMetricRow(name, meta.control_level, meta.data_source, meta.red_line, meta.description);
            });'''

new_render = '''        function renderRulesManager() {
            const categoriesContainer = document.getElementById('rules_categories_list');
            if (categoriesContainer) categoriesContainer.innerHTML = '';
            
            const categories = currentRulesConfig.categories || {};
            Object.entries(categories).forEach(([catName, catData]) => {
                addNewCategoryCard(catName, catData.data_source || '', catData.metrics || {});
            });'''
content = content.replace(old_render, new_render)

# 3. Add createMetricRowHtml, addNewCategoryCard, addNewMetricToCat
new_js = '''
        function createMetricRowHtml(name, meta) {
            const controlLevel = meta.control_level || '考核';
            const redLine = meta.red_line !== undefined && meta.red_line !== null ? meta.red_line : '';
            const desc = meta.description || '';
            return `
                <div class="rule-card-item metric-row" style="border-left: 3px solid var(--accent-blue); background:rgba(255,255,255,0.02); padding:10px; margin-bottom:10px;">
                    <div style="display:flex; gap:10px; align-items:flex-end;">
                        <div class="form-group" style="flex:2; margin-bottom:0;">
                            <label style="font-size:0.8rem;">指标名称</label>
                            <input type="text" class="metric-name" value="${name}" placeholder="如：班次发货及时率">
                        </div>
                        <div class="form-group" style="flex:1; margin-bottom:0;">
                            <label style="font-size:0.8rem;">管控级别</label>
                            <select class="metric-level">
                                <option value="考核" ${controlLevel === '考核' ? 'selected' : ''}>考核</option>
                                <option value="通晒" ${controlLevel === '通晒' ? 'selected' : ''}>通晒</option>
                            </select>
                        </div>
                        <div class="form-group" style="flex:1; margin-bottom:0;">
                            <label style="font-size:0.8rem;">红线值</label>
                            <input type="number" step="0.01" class="metric-redline" value="${redLine}" placeholder="如 0.95">
                        </div>
                        <div class="form-group" style="flex:4; margin-bottom:0;">
                            <label style="font-size:0.8rem;">说明</label>
                            <input type="text" class="metric-desc" value="${desc}" placeholder="规则业务说明">
                        </div>
                        <button class="btn delete-btn" style="padding:8px; margin-bottom:0;" onclick="this.closest('.metric-row').remove()">删除</button>
                    </div>
                </div>
            `;
        }

        function addNewCategoryCard(catName='', dataSource='', metrics={}) {
            const container = document.getElementById('rules_categories_list');
            const catId = 'cat_' + Date.now() + Math.floor(Math.random() * 1000);
            const div = document.createElement('div');
            div.className = 'category-card';
            div.style.border = '1px solid rgba(255,255,255,0.1)';
            div.style.padding = '16px';
            div.style.marginBottom = '20px';
            div.style.borderRadius = '8px';
            div.style.background = 'rgba(0,0,0,0.2)';
            
            let metricsHtml = '';
            Object.entries(metrics).forEach(([mName, meta]) => {
                metricsHtml += createMetricRowHtml(mName, meta);
            });

            div.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                    <div style="display:flex; gap:12px; align-items:center; flex:1;">
                        <input type="text" class="cat-name-input" value="${catName}" placeholder="输入大分类名称 (如：TMS类指标)" style="font-size:1.1em; font-weight:bold; width:220px;">
                        <input type="text" class="cat-source-input" value="${dataSource}" placeholder="填写该分类通用的数据源链接 (飞书URL)..." style="flex:1;" oninput="triggerUrlValidation(this)">
                        <div class="validation-status"></div>
                    </div>
                    <button class="btn delete-btn" style="margin-left:12px; padding:6px 12px;" onclick="this.closest('.category-card').remove()">删除分类</button>
                </div>
                <div class="cat-metrics-list" id="${catId}_metrics">
                    ${metricsHtml}
                </div>
                <button class="btn btn-secondary" style="padding:6px 12px; font-size:0.85rem;" onclick="addNewMetricToCat('${catId}')">+ 增加一条指标</button>
            `;
            container.appendChild(div);
            
            if (dataSource) {
                const sourceInput = div.querySelector('.cat-source-input');
                if (sourceInput) triggerUrlValidation(sourceInput);
            }
        }

        function addNewMetricToCat(catId) {
            const metricsContainer = document.getElementById(catId + '_metrics');
            if (metricsContainer) {
                metricsContainer.insertAdjacentHTML('beforeend', createMetricRowHtml('', {}));
            }
        }
'''
content = content.replace('function addNewMetricRow', new_js + '\n        function old_addNewMetricRow_removed')

# 4. saveAllRulesToServer update
old_save = '''        // 保存全部规则
        function saveAllRulesToServer() {
            const metrics = {};
            const vehicle_capacity = {};
            
            const metricCards = document.querySelectorAll('#rules_metrics_list .rule-card-item');
            metricCards.forEach(card => {
                const nameInput = card.querySelector('.metric-name');
                const levelSelect = card.querySelector('.metric-level');
                const sourceInput = card.querySelector('.metric-source');
                const redlineInput = card.querySelector('.metric-redline');
                const descTextarea = card.querySelector('.metric-desc');
                
                const name = nameInput.value.trim();
                if (!name) return;
                
                const meta = {
                    control_level: levelSelect.value,
                    data_source: sourceInput.value.trim(),
                    description: descTextarea.value.trim()
                };
                
                if (redlineInput.value.trim() !== '') {
                    meta.red_line = parseFloat(redlineInput.value);
                }
                
                metrics[name] = meta;
            });'''
new_save = '''        // 保存全部规则
        function saveAllRulesToServer() {
            const categories = {};
            const vehicle_capacity = {};
            
            const catCards = document.querySelectorAll('#rules_categories_list .category-card');
            catCards.forEach(card => {
                const catName = card.querySelector('.cat-name-input').value.trim();
                const catSource = card.querySelector('.cat-source-input').value.trim();
                if (!catName) return;
                
                const metrics = {};
                const metricRows = card.querySelectorAll('.metric-row');
                metricRows.forEach(row => {
                    const name = row.querySelector('.metric-name').value.trim();
                    if (!name) return;
                    
                    const level = row.querySelector('.metric-level').value;
                    const redlineInput = row.querySelector('.metric-redline').value.trim();
                    const desc = row.querySelector('.metric-desc').value.trim();
                    
                    const meta = {
                        control_level: level,
                        description: desc
                    };
                    if (redlineInput !== '') {
                        meta.red_line = parseFloat(redlineInput);
                    }
                    metrics[name] = meta;
                });
                
                categories[catName] = {
                    data_source: catSource,
                    metrics: metrics
                };
            });'''
content = content.replace(old_save, new_save)

old_payload = '''            const payload = {
                metrics,
                vehicle_capacity
            };'''
new_payload = '''            const payload = {
                categories,
                vehicle_capacity
            };'''
content = content.replace(old_payload, new_payload)

# 5. For the AI rule extractor "提取" logic
# Find "function saveExtractedRulesToLibrary()" and change it to ask for a Category name
old_extract_save = '''        function saveExtractedRulesToLibrary() {
            // Read extracted metrics inputs
            const metricRows = document.querySelectorAll('#extracted_metrics_list .rule-card-item');
            const newMetrics = {};
            metricRows.forEach(row => {
                const name = row.querySelector('.ext-metric-name').value.trim();
                if (!name) return;
                
                const level = row.querySelector('.ext-metric-level').value;
                const source = row.querySelector('.ext-metric-source').value.trim();
                const redlineInput = row.querySelector('.ext-metric-redline').value.trim();
                const redline = redlineInput !== '' ? parseFloat(redlineInput) : null;
                const desc = row.querySelector('.ext-metric-desc').value.trim();
                
                newMetrics[name] = {
                    control_level: level,
                    data_source: source,
                    description: desc,
                    red_line: redline
                };
            });'''

new_extract_save = '''        function saveExtractedRulesToLibrary() {
            const targetCat = prompt("请输入要将这些规则保存到的【大分类】名称（如果不存在将自动创建）：\\n(例如：TMS业务类, WMS业务类等)", "自动提取分类");
            if (!targetCat) return;
            
            // Read extracted metrics inputs
            const metricRows = document.querySelectorAll('#extracted_metrics_list .rule-card-item');
            const newMetrics = {};
            metricRows.forEach(row => {
                const name = row.querySelector('.ext-metric-name').value.trim();
                if (!name) return;
                
                const level = row.querySelector('.ext-metric-level').value;
                const redlineInput = row.querySelector('.ext-metric-redline').value.trim();
                const redline = redlineInput !== '' ? parseFloat(redlineInput) : null;
                const desc = row.querySelector('.ext-metric-desc').value.trim();
                
                newMetrics[name] = {
                    control_level: level,
                    description: desc,
                    red_line: redline
                };
            });'''
content = content.replace(old_extract_save, new_extract_save)

# Also update the part that merges into currentRulesConfig inside saveExtractedRulesToLibrary
old_merge = '''            // Merge into currentRulesConfig
            if (!currentRulesConfig.metrics) currentRulesConfig.metrics = {};
            if (!currentRulesConfig.vehicle_capacity) currentRulesConfig.vehicle_capacity = {};

            Object.assign(currentRulesConfig.metrics, newMetrics);
            Object.assign(currentRulesConfig.vehicle_capacity, newCapacity);'''

new_merge = '''            // Merge into currentRulesConfig
            if (!currentRulesConfig.categories) currentRulesConfig.categories = {};
            if (!currentRulesConfig.categories[targetCat]) {
                currentRulesConfig.categories[targetCat] = { data_source: '', metrics: {} };
            }
            if (!currentRulesConfig.vehicle_capacity) currentRulesConfig.vehicle_capacity = {};

            Object.assign(currentRulesConfig.categories[targetCat].metrics, newMetrics);
            Object.assign(currentRulesConfig.vehicle_capacity, newCapacity);'''
content = content.replace(old_merge, new_merge)

with open('feishu_config.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('feishu_config.html refactoring done')
