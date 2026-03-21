import os
from dotenv import load_dotenv
import httpx
from openai import OpenAI, APITimeoutError, APIConnectionError
load_dotenv()
# 检查是否设置了环境变量
if "OPENAI_API_KEY" not in os.environ:
    print("请设置环境变量 OPENAI_API_KEY")
    exit(1)

if "OPENAI_BASE_URL" not in os.environ:
    print("请设置环境变量 OPENAI_BASE_URL")
    exit(1)

print("环境变量已设置，正在创建 OpenAI 客户端...")
base_url = os.environ.get("OPENAI_BASE_URL")
print(f"使用的 OpenAI Base URL: {base_url}")

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=base_url,
    timeout=httpx.Timeout(60.0, connect=20.0, read=60.0, write=60.0),
)

try:
    resp = client.responses.create(
        model="gpt-5",
        input="你好，回复一个 ok",
        store=False,
    )
    print(resp.output_text)
except APITimeoutError as e:
    print("OpenAI 请求超时:", e)
except APIConnectionError as e:
    print("OpenAI 连接失败:", e)
except Exception as e:
    print("其他错误:", type(e).__name__, e)