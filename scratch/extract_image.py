import base64
import json
import requests
import os

image_path = r"d:\project\gofoai\发货及时率.png"
api_base = "http://localhost:8082/v1"
api_key = "sk-gemini"
model = "gemini-auto" # Fallback to gemini-auto which is supported

with open(image_path, "rb") as f:
    img_data = f.read()

image_base64 = base64.b64encode(img_data).decode("utf-8")

system_prompt = (
    "你是一个物流时效与调度指标规则提取专家。请从用户输入的图片中，提取出所有的指标考核规则和车型财务容量配置，并以标准的 JSON 格式输出。\n"
    "输出的 JSON 结构必须严格符合如下格式，且不要包含任何 markdown 代码块包裹（如 ```json），也不要有任何其他文字：\n"
    "{\n"
    "  \"metrics\": {\n"
    "    \"指标名称\": {\n"
    "      \"control_level\": \"考核\" 或 \"通晒\",\n"
    "      \"data_source\": \"数据来源(如TMS-出发到达管理、班次监控等)\",\n"
    "      \"description\": \"详细的指标计算公式和判定规则说明\",\n"
    "      \"red_line\": 浮点数值 (例如 0.95 代表 95%，若没有特定红线则设为 null)\n"
    "    }\n"
    "  },\n"
    "  \"vehicle_capacity\": {\n"
    "    \"车型名称\": 额定装载量数值 (整数)\n"
    "  }\n"
    "}"
)

messages = [
    {"role": "system", "content": system_prompt},
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "请分析图片，提取其中的物流考核指标规则与车型容积配置。请直接返回标准的 JSON，不要用 markdown 格式包裹。"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
        ]
    }
]

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
payload = {
    "model": model,
    "messages": messages,
    "temperature": 0.1
}

url_endpoint = f"{api_base.rstrip('/')}/chat/completions"
print("Calling LLM endpoint...")
resp = requests.post(url_endpoint, headers=headers, json=payload, timeout=40)
print(f"Status code: {resp.status_code}")
if resp.status_code == 200:
    res_json = resp.json()
    raw_content = res_json["choices"][0]["message"]["content"].strip()
    with open("scratch/raw_response.txt", "w", encoding="utf-8") as rf:
        rf.write(raw_content)
    
    # Try parsing
    if raw_content.startswith("```"):
        lines = raw_content.splitlines()
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            raw_content = "\n".join(lines[1:-1])
    raw_content = raw_content.strip()
    data = json.loads(raw_content)
    with open("scratch/extracted_rules.json", "w", encoding="utf-8") as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
    print("Successfully saved to scratch/extracted_rules.json")
else:
    print(resp.text)
