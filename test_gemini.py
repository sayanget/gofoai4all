import google.generativeai as genai

genai.configure(
    api_key="sk-31d9d6efb7664d7eaa6ef50cf516e198",
    transport='rest',
    client_options={'api_endpoint': 'http://127.0.0.1:8045'}
)

try:
    model = genai.GenerativeModel('gemini-3.5-flash-extra-low')
    response = model.generate_content("Hello")
    print("SUCCESS!")
    print(response.text)
except Exception as e:
    print("ERROR:", e)
