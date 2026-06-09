from openai import OpenAI
import sys

# 强制输出编码为 utf-8，解决 Windows 终端下打印中文报错问题
sys.stdout.reconfigure(encoding='utf-8')


# 将 base_url 指向你本地部署的 web2api 服务
client = OpenAI(
    base_url="http://localhost:8082/v1", 
    api_key="sk-gemini"
)


try:
    response = client.chat.completions.create(
        model="gemini-3.5-flash-thinking",  # 体验深度思考模型
        messages=[{"role": "user", "content": "简单解释什么是量子计算。"}],
        stream=True  # 验证流式响应
    )

    print("--- 收到模型响应 ---")
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
    print("\n--------------------")

except Exception as e:
    print(f"验证失败，错误信息: {e}")