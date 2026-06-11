with open('card_editor.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix right card HTML
content = content.replace(
'''              <!-- AI 诊断 -->
              <div class="feishu-note-box" id="preview_card_note">
                🔍 <b>AI 专家诊断方案：</b><br />
                <span style="color: var(--text-secondary); font-style: italic"
                  >(生成诊断后在此处显示详细定责与追溯信息)</span
                >
              </div>''',
'''              <!-- AI 诊断 -->
              <div class="feishu-note-box">
                🔍 <b>AI 专家诊断方案：</b><br />
                <div
                  id="preview_card_diagnosis"
                  style="margin-top: 5px; min-height: 40px"
                >
                  <span style="color: var(--text-secondary); font-style: italic">(生成诊断后在此处显示详细定责与追溯信息)</span>
                </div>
                <div style="margin-top: 10px">✅ <b>行动建议：</b><br /></div>
                <div
                  id="preview_card_suggestions"
                  style="margin-top: 5px; min-height: 40px"
                ></div>
              </div>'''
)

# Fix renderLivePreview to update both sides
content = content.replace(
'''        document.getElementById("card_diagnosis").innerText = diagText;

        const sugText = (report.action_suggestions || []).join("\\n");
        document.getElementById("card_suggestions").innerText = sugText;''',
'''        document.getElementById("card_diagnosis").innerText = diagText;
        const previewDiag = document.getElementById("preview_card_diagnosis");
        if(previewDiag) previewDiag.innerText = diagText;

        const sugText = (report.action_suggestions || []).join("\\n");
        document.getElementById("card_suggestions").innerText = sugText;
        const previewSug = document.getElementById("preview_card_suggestions");
        if(previewSug) previewSug.innerText = sugText;'''
)

# Fix syncToPreview
content = content.replace(
'''        // Find the AI note part
        let leftNote = document.getElementById("card_note");
        let rightNote = document.getElementById("preview_card_note");
        if(leftNote && rightNote) {
            rightNote.innerHTML = leftNote.innerHTML;
        }''',
'''        if(document.getElementById("preview_card_diagnosis") && document.getElementById("card_diagnosis")) {
            document.getElementById("preview_card_diagnosis").innerHTML = document.getElementById("card_diagnosis").innerHTML;
        }
        if(document.getElementById("preview_card_suggestions") && document.getElementById("card_suggestions")) {
            document.getElementById("preview_card_suggestions").innerHTML = document.getElementById("card_suggestions").innerHTML;
        }'''
)

# Fix editables array in DOMContentLoaded
content = content.replace(
'''const editables = ["card_header", "card_summary", "card_note"];''',
'''const editables = ["card_header", "card_summary", "card_diagnosis", "card_suggestions"];'''
)

with open('card_editor.html', 'w', encoding='utf-8') as f:
    f.write(content)
