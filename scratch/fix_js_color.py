with open('card_editor.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
'''      function updateCardColor() {
        const status = document.getElementById("card_status_select").value;
        const header = document.getElementById("card_header");
        const metricsBox = document.getElementById("card_metrics_box");

        header.className = "feishu-header";
        if (status === "danger") {
          header.classList.add("red");
          if (metricsBox)
            metricsBox.className = "feishu-fields-box error-border";
        } else if (status === "warning") {
          header.classList.add("orange");
          if (metricsBox) metricsBox.className = "feishu-fields-box";
        } else {
          header.classList.add("blue");
          if (metricsBox) metricsBox.className = "feishu-fields-box";
        }
      }''',
'''      function updateCardColor() {
        const status = document.getElementById("card_status_select").value;
        const header = document.getElementById("card_header");
        const metricsBox = document.getElementById("card_metrics_box");
        
        const previewHeader = document.getElementById("preview_card_header");
        const previewMetricsBox = document.getElementById("preview_card_metrics_box");

        header.className = "feishu-header";
        if (previewHeader) previewHeader.className = "feishu-header";
        
        if (status === "danger") {
          header.classList.add("red");
          if (metricsBox) metricsBox.className = "feishu-fields-box error-border";
          if (previewHeader) previewHeader.classList.add("red");
          if (previewMetricsBox) previewMetricsBox.className = "feishu-fields-box error-border";
        } else if (status === "warning") {
          header.classList.add("orange");
          if (metricsBox) metricsBox.className = "feishu-fields-box";
          if (previewHeader) previewHeader.classList.add("orange");
          if (previewMetricsBox) previewMetricsBox.className = "feishu-fields-box";
        } else {
          header.classList.add("blue");
          if (metricsBox) metricsBox.className = "feishu-fields-box";
          if (previewHeader) previewHeader.classList.add("blue");
          if (previewMetricsBox) previewMetricsBox.className = "feishu-fields-box";
        }
      }'''
)

with open('card_editor.html', 'w', encoding='utf-8') as f:
    f.write(content)
