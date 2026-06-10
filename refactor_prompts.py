import re

# 1. Update feishu_config.html
with open('feishu_config.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the prompt_env_selector block with prompt_category_selector
old_prompt_block = '''                    <div class="form-group">
                        <label>提示词环境预设 (Prompt Templates)</label>
                        <select id="prompt_env_selector" title="提示词模板选择" onchange="changePromptEnv()">
                            <option value="default" selected>默认常规考核</option>
                            <option value="strict">严格模式 (大促/双十一)</option>
                            <option value="encouraging">鼓励模式 (淡季/团建期)</option>
                            <option value="detailed">极度详细 (异常深挖版)</option>
                        </select>
                    </div>'''

new_prompt_block = '''                    <div class="form-group">
                        <label>选择生成报告的指标大分类</label>
                        <select id="prompt_category_selector" title="选择分类" onchange="changePromptCategory()">
                            <option value="" disabled selected>-- 请选择分类 --</option>
                        </select>
                    </div>'''
if old_prompt_block in content:
    content = content.replace(old_prompt_block, new_prompt_block)

# Add window.llmPromptsCache initialization inside get_config
old_prompt_init = '''                    document.getElementById('llm_custom_prompt').value = fs.llm_custom_prompt || defaultTemplate;'''
new_prompt_init = '''                    window.llmPromptsCache = fs.llm_custom_prompts || {};
                    populateCategorySelector();
                    if (document.getElementById('prompt_category_selector').options.length > 1) {
                        document.getElementById('prompt_category_selector').selectedIndex = 1;
                        changePromptCategory();
                    }'''
if old_prompt_init in content:
    content = content.replace(old_prompt_init, new_prompt_init)

# Replace changePromptEnv with changePromptCategory and populateCategorySelector
old_change_env = '''        function changePromptEnv() {
            const env = document.getElementById('prompt_env_selector').value;
            const promptBox = document.getElementById('llm_custom_prompt');
            
            const templates = {
                'default': '你是一个精通“美国接收国内电商尾程业务”的资深跨境物流调度专家。请根据提供的美国本地化时效数据和异常信息（如清关提货、干线Linehaul、尾程承运商注入、Hub集包），输出专业的定责考核报告，重点关注承运商截单时间和交件准点率。语言客观中立。',
                'strict': '你是一个极度严格的跨境大促期物流风控专家。当前处于黑五/网一/旺季大促期间，美国本地仓网任何轻微的延误（特别是错发、漏扫、未赶上尾程班车）都必须被严厉警告。请在报告中强调全员危机感，指出所有节点时效异常，并要求海外仓与车队在1小时内给出整改方案。',
                'encouraging': '你是一个充满活力的中美跨境物流协同“政委”。目前美国尾程派送压力较小，请在指出跨时区协作与末端集包问题的同时，多多鼓励海外华人及本地化团队，用词温和，强调持续降本增效，少用严厉的考核字眼。',
                'detailed': '你是一个专注中美跨境供应链的数据分析师。请极度详细地剖析美国尾程网络的每一个异常，推测可能的根因（如卡车资源短缺、仓库爆仓、天气因素、司机工时限制ELD等），给出多维度的改善行动建议。'
            };
            
            if (templates[env]) {
                promptBox.value = templates[env];
            }
        }'''

new_change_cat = '''        let lastSelectedCategory = null;
        
        function populateCategorySelector() {
            const sel = document.getElementById('prompt_category_selector');
            sel.innerHTML = '<option value="" disabled selected>-- 请选择分类 --</option>';
            const categories = currentRulesConfig.categories || {};
            Object.keys(categories).forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.innerText = cat;
                sel.appendChild(opt);
            });
        }

        function changePromptCategory() {
            const promptBox = document.getElementById('llm_custom_prompt');
            if (lastSelectedCategory) {
                window.llmPromptsCache[lastSelectedCategory] = promptBox.value;
            }
            
            const cat = document.getElementById('prompt_category_selector').value;
            lastSelectedCategory = cat;
            
            const defaultPrompt = '你是一个精通“美国接收国内电商尾程业务”的资深跨境物流调度专家。请根据提供的美国本地化时效数据和异常信息，输出专业的定责考核报告。';
            promptBox.value = window.llmPromptsCache[cat] || defaultPrompt;
        }'''
if old_change_env in content:
    content = content.replace(old_change_env, new_change_cat)

# Update saveConfiguration to save llm_custom_prompts instead of llm_custom_prompt
old_save_config_obj = '''                llm_model: llmModel,
                llm_custom_prompt: llmCustomPrompt
            };'''
new_save_config_obj = '''                llm_model: llmModel,
                llm_custom_prompts: window.llmPromptsCache
            };'''
if old_save_config_obj in content:
    content = content.replace(old_save_config_obj, new_save_config_obj)

old_save_config_var = '''            const llmCustomPrompt = document.getElementById('llm_custom_prompt').value;'''
new_save_config_var = '''            if (lastSelectedCategory) {
                window.llmPromptsCache[lastSelectedCategory] = document.getElementById('llm_custom_prompt').value;
            }'''
if old_save_config_var in content:
    content = content.replace(old_save_config_var, new_save_config_var)

# Update generateAndOpenEditor to send target_category
old_generate = '''            fetch('/api/generate_report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })'''
new_generate = '''            const cat = document.getElementById('prompt_category_selector') ? document.getElementById('prompt_category_selector').value : '';
            if (!cat) {
                alert("请先选择生成报告的分类！");
                notif.classList.remove('show');
                if (btn) { btn.disabled = false; btn.innerText = '一键生成今日诊断报告并推送'; }
                return;
            }
            fetch('/api/generate_report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_category: cat })
            })'''
if old_generate in content:
    content = content.replace(old_generate, new_generate)

with open('feishu_config.html', 'w', encoding='utf-8') as f:
    f.write(content)

# 2. Update server.py
with open('server.py', 'r', encoding='utf-8') as f:
    s_content = f.read()

s_old_feishu_prompt = '''    feishu_config["llm_custom_prompt"] = data.get("llm_custom_prompt", "")'''
s_new_feishu_prompt = '''    feishu_config["llm_custom_prompts"] = data.get("llm_custom_prompts", {})'''
if s_old_feishu_prompt in s_content:
    s_content = s_content.replace(s_old_feishu_prompt, s_new_feishu_prompt)

s_old_generate = '''@app.route("/api/generate_report", methods=["POST"])
def generate_report():
    try:
        from run_pipeline import run_pipeline
        logger.info("Executing real daily pipeline for manual review...")
        pipeline_results = run_pipeline()'''
s_new_generate = '''@app.route("/api/generate_report", methods=["POST"])
def generate_report():
    try:
        data = request.get_json(force=True, silent=True) or {}
        target_category = data.get("target_category", "")
        from run_pipeline import run_pipeline
        logger.info(f"Executing real daily pipeline for manual review... target_category: {target_category}")
        pipeline_results = run_pipeline(target_category)'''
if s_old_generate in s_content:
    s_content = s_content.replace(s_old_generate, s_new_generate)

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(s_content)

# 3. Update run_pipeline.py
with open('run_pipeline.py', 'r', encoding='utf-8') as f:
    rp_content = f.read()

rp_old_def = '''def run_pipeline() -> dict:'''
rp_new_def = '''def run_pipeline(target_category: str = "") -> dict:'''
if rp_old_def in rp_content:
    rp_content = rp_content.replace(rp_old_def, rp_new_def)

rp_old_cat = '''            categories = rules_config.get("categories", {})
            for cat_data in categories.values():
                if cat_data.get("data_source"):
                    feishu_url = cat_data.get("data_source")
                    break'''
rp_new_cat = '''            categories = rules_config.get("categories", {})
            if target_category and target_category in categories:
                feishu_url = categories[target_category].get("data_source", "")
            else:
                for cat_data in categories.values():
                    if cat_data.get("data_source"):
                        feishu_url = cat_data.get("data_source")
                        break'''
if rp_old_cat in rp_content:
    rp_content = rp_content.replace(rp_old_cat, rp_new_cat)

rp_old_analyzer = '''    analyzer = LLMAnalyzer()'''
rp_new_analyzer = '''    analyzer = LLMAnalyzer(target_category=target_category)'''
if rp_old_analyzer in rp_content:
    rp_content = rp_content.replace(rp_old_analyzer, rp_new_analyzer)

with open('run_pipeline.py', 'w', encoding='utf-8') as f:
    f.write(rp_content)

# 4. Update llm_analyzer.py
with open('llm_analyzer.py', 'r', encoding='utf-8') as f:
    llm_content = f.read()

llm_old_init = '''    def __init__(self, api_key: str = None, api_base: str = None, model: str = None):'''
llm_new_init = '''    def __init__(self, api_key: str = None, api_base: str = None, model: str = None, target_category: str = ""):'''
if llm_old_init in llm_content:
    llm_content = llm_content.replace(llm_old_init, llm_new_init)

llm_old_prompt = '''                    config_custom_prompt = config_data.get("llm_custom_prompt")'''
llm_new_prompt = '''                    config_custom_prompts = config_data.get("llm_custom_prompts", {})
                    config_custom_prompt = config_custom_prompts.get(target_category, "") if target_category else ""'''
if llm_old_prompt in llm_content:
    llm_content = llm_content.replace(llm_old_prompt, llm_new_prompt)

with open('llm_analyzer.py', 'w', encoding='utf-8') as f:
    f.write(llm_content)

print('All refactoring complete')
