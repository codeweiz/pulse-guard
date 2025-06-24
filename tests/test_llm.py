from langchain.chat_models import init_chat_model


# 测试 Ollama 模型
def test_ollama():
    ollama_deepseek = init_chat_model(
        model="deepseek-r1:32b",
        model_provider="ollama",
        base_url="http://192.168.220.15:11434",
        api_key="21321323423432"
    )

    prompt = "请介绍一下你自己。"
    response = ollama_deepseek.invoke(prompt)
    print(response.content)
