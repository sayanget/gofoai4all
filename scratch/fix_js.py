with open('card_editor.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
'''        const metricsList = document.getElementById("card_metrics_list");
        if (report.metrics_display) {
          let metricsHtml = `''',
'''        const metricsList = document.getElementById("card_metrics_list");
        const previewMetricsList = document.getElementById("preview_card_metrics_list");
        if (report.metrics_display) {
          let metricsHtml = `'''
)

content = content.replace(
'''          if (metricsList) metricsList.innerHTML = metricsHtml;
        }
      }

      function sendFinalCard() {''',
'''          if (metricsList) metricsList.innerHTML = metricsHtml;
          if (previewMetricsList) previewMetricsList.innerHTML = metricsHtml;
        }
        
        syncToPreview();
      }

      function sendFinalCard() {'''
)

with open('card_editor.html', 'w', encoding='utf-8') as f:
    f.write(content)
