import google.generativeai as genai

genai.configure(
    api_key="sk-31d9d6efb7664d7eaa6ef50cf516e198",
    transport='rest',
    client_options={'api_endpoint': 'http://127.0.0.1:8045'}
)

try:
    model = genai.GenerativeModel(
        'gemini-3.5-flash-extra-low',
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json"
        )
    )
    response = model.generate_content("输出一个包含 status 字段的 JSON")
    print("SUCCESS!")
    try:
        print(response.text)
    except Exception as e:
        print("TEXT ERROR:", e)
        print("CANDIDATES:", response.candidates)
except Exception as e:
    print("ERROR:", e)
