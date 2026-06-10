import google.generativeai as genai
import json

genai.configure(
    api_key="sk-31d9d6efb7664d7eaa6ef50cf516e198",
    transport='rest',
    client_options={'api_endpoint': 'http://127.0.0.1:8045'}
)

try:
    model = genai.GenerativeModel(
        'gemini-3.5-flash-extra-low',
        generation_config=genai.GenerationConfig(
            temperature=0.2
        )
    )
    prompt = """你是一位资深的物流调度与运营管理专家。负责解读大盘当天的运行指标并定责。要求：必须且只能输出合法的 JSON，不要输出 Markdown 标记或其他多余内容。字段包括：status, title, date, summary, metrics_display, diagnosis_details, action_suggestions。"""
    response = model.generate_content(prompt)
    print("SUCCESS")
    print("Has text:", hasattr(response, "text"))
    try:
        print("Text:", repr(response.text))
    except Exception as e:
        print("Text Exception:", e)
    
    print("Candidates:", response.candidates)
    
    if response.candidates:
        part = response.candidates[0].content.parts[0]
        print("Part:", part)
        if part.function_call:
            print("Function Call name:", part.function_call.name)
            args_dict = type(part.function_call.args).to_dict(part.function_call.args) if hasattr(type(part.function_call.args), 'to_dict') else dict(part.function_call.args)
            print("Args dict:", args_dict)
            print("JSON:", json.dumps(args_dict))
            
except Exception as e:
    print("ERROR:", e)
