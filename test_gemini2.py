import google.generativeai as genai

genai.configure(
    api_key="dummy_key",
    transport='rest',
    client_options={'api_endpoint': 'http://127.0.0.1:8045'}
)

try:
    model = genai.GenerativeModel('gemini-3.5-flash-extra-low')
    response = model.generate_content("test")
    print("SUCCESS!")
    print(response.text)
except Exception as e:
    print("ERROR:", e)
