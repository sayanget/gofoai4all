import re

with open('card_editor.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix CSS
content = content.replace(
'''      .container {
        display: flex;
        justify-content: center;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
        gap: 40px;
      }''',
'''      .container {
        display: flex;
        justify-content: center;
        max-width: 1600px;
        width: 95%;
        margin: 0 auto;
        padding: 20px;
        gap: 40px;
      }'''
)

content = content.replace(
'''      .editor-column,
      .preview-column {
        display: flex;
        flex-direction: column;
        gap: 20px;
      }''',
'''      .editor-column,
      .preview-column {
        display: flex;
        flex-direction: column;
        gap: 20px;
        flex: 1;
        width: 50%;
      }'''
)

# 2. Fix IDs in the right column
right_col_start = content.find('<!-- 右侧：飞书卡片动态效果预览 (Live Preview) -->')
if right_col_start != -1:
    left_part = content[:right_col_start]
    right_part = content[right_col_start:]
    
    # Rename IDs
    right_part = right_part.replace('id="feishu_card_element"', 'id="preview_feishu_card_element"')
    right_part = right_part.replace('id="card_header"', 'id="preview_card_header"')
    right_part = right_part.replace('id="card_summary"', 'id="preview_card_summary"')
    right_part = right_part.replace('id="card_metrics_box"', 'id="preview_card_metrics_box"')
    right_part = right_part.replace('id="card_metrics_list"', 'id="preview_card_metrics_list"')
    right_part = right_part.replace('id="card_note"', 'id="preview_card_note"')
    
    content = left_part + right_part

# 3. Add Sync logic
js_sync = """
      function syncToPreview() {
        if(document.getElementById("preview_card_header") && document.getElementById("card_header")) {
            document.getElementById("preview_card_header").innerText = document.getElementById("card_header").innerText;
        }
        if(document.getElementById("preview_card_summary") && document.getElementById("card_summary")) {
            document.getElementById("preview_card_summary").innerHTML = document.getElementById("card_summary").innerHTML;
        }
        
        // Find the AI note part
        let leftNote = document.getElementById("card_note");
        let rightNote = document.getElementById("preview_card_note");
        if(leftNote && rightNote) {
            rightNote.innerHTML = leftNote.innerHTML;
        }
      }

      // Add event listeners to contenteditable elements
      window.addEventListener("DOMContentLoaded", () => {
        const editables = ["card_header", "card_summary", "card_note"];
        editables.forEach(id => {
          const el = document.getElementById(id);
          if (el) {
            el.addEventListener('input', syncToPreview);
          }
        });
      });
"""

script_end = content.rfind('</script>')
if script_end != -1:
    content = content[:script_end] + js_sync + "\n    </script>" + content[script_end+9:]

with open('card_editor.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("HTML structure updated successfully!")
