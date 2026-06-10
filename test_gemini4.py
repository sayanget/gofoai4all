import google.generativeai as genai

genai.configure(
    api_key="sk-31d9d6efb7664d7eaa6ef50cf516e198",
    transport='rest',
    client_options={'api_endpoint': 'http://127.0.0.1:8045'}
)

try:
    model = genai.GenerativeModel('gemini-3.5-flash-extra-low')
    response = model.generate_content("【当前生效的大盘考核规则与红线】 发车准点率 异常 卸车及时率 异常 请分析以上物流数据并给出 JSON 报告")
    print("SUCCESS!")
    print(response.text)
except Exception as e:
    print("ERROR:", e)
