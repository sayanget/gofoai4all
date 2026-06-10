import re

with open('feishu_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add extractor_target_category selector
old_upload_zone = '''                    <!-- 文件上传/拖拽区域 -->'''
new_upload_zone = '''                    <!-- 选择目标大分类 -->
                    <div class="form-group" style="margin-bottom: 20px;">
                        <label>提取规则所属的大分类 (提取前必须选择)</label>
                        <select id="extractor_target_category" title="选择目标分类">
                            <option value="" disabled selected>-- 请选择分类 --</option>
                        </select>
                    </div>

                    <!-- 文件上传/拖拽区域 -->'''
if old_upload_zone in content and 'extractor_target_category' not in content:
    content = content.replace(old_upload_zone, new_upload_zone)

# 2. Update populateCategorySelector to also populate extractor_target_category
old_populate = '''        function populateCategorySelector() {
            const sel = document.getElementById('prompt_category_selector');
            sel.innerHTML = '<option value="" disabled selected>-- 请选择分类 --</option>';
            const categories = currentRulesConfig.categories || {};
            Object.keys(categories).forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.innerText = cat;
                sel.appendChild(opt);
            });
        }'''
new_populate = '''        function populateCategorySelector() {
            const sel1 = document.getElementById('prompt_category_selector');
            const sel2 = document.getElementById('extractor_target_category');
            if (sel1) sel1.innerHTML = '<option value="" disabled selected>-- 请选择分类 --</option>';
            if (sel2) sel2.innerHTML = '<option value="" disabled selected>-- 请选择分类 --</option>';
            
            const categories = currentRulesConfig.categories || {};
            Object.keys(categories).forEach(cat => {
                if (sel1) {
                    const opt1 = document.createElement('option');
                    opt1.value = cat;
                    opt1.innerText = cat;
                    sel1.appendChild(opt1);
                }
                if (sel2) {
                    const opt2 = document.createElement('option');
                    opt2.value = cat;
                    opt2.innerText = cat;
                    sel2.appendChild(opt2);
                }
            });
        }'''
if old_populate in content:
    content = content.replace(old_populate, new_populate)

# 3. Add validation in runRuleExtraction
old_run_extract = '''          function runRuleExtraction() {
              const notif = document.getElementById('notif');
              const btn = document.getElementById('btn_run_extractor');
              const textInput = document.getElementById('extractor_text_input').value.trim();

              if (!extractorSelectedFile && !textInput) {'''

new_run_extract = '''          function runRuleExtraction() {
              const notif = document.getElementById('notif');
              const btn = document.getElementById('btn_run_extractor');
              const textInput = document.getElementById('extractor_text_input').value.trim();
              const targetCat = document.getElementById('extractor_target_category');

              if (targetCat && !targetCat.value) {
                  notif.innerText = '请先选择指标大类后再进行 AI 智能解析。';
                  notif.style.background = 'rgba(239, 68, 68, 0.9)'; // Red
                  notif.classList.add('show');
                  setTimeout(() => notif.classList.remove('show'), 3000);
                  return;
              }

              if (!extractorSelectedFile && !textInput) {'''
if old_run_extract in content:
    content = content.replace(old_run_extract, new_run_extract)

# 4. Remove prompt in saveExtractedRulesToLibrary and use the selected category
old_save_extracted = '''        function saveExtractedRulesToLibrary() {
            const targetCat = prompt("请输入要将这些规则保存到的【大分类】名称（如果不存在将自动创建）：\\n(例如：TMS业务类, WMS业务类等)", "自动提取分类");
            if (!targetCat) return;'''
new_save_extracted = '''        function saveExtractedRulesToLibrary() {
            const targetCatEl = document.getElementById('extractor_target_category');
            const targetCat = targetCatEl ? targetCatEl.value : null;
            if (!targetCat) {
                alert("请先选择指标大类！");
                return;
            }'''
if old_save_extracted in content:
    content = content.replace(old_save_extracted, new_save_extracted)

with open('feishu_config.html', 'w', encoding='utf-8') as f:
    f.write(content)
