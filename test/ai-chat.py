import os
import json
import atexit
import shutil
import tempfile
import getpass
from pathlib import Path
from openai import BadRequestError, APITimeoutError, APIConnectionError
import requests
from openai import OpenAI

MODEL = "gpt-5"
from dotenv import load_dotenv
load_dotenv()

# 从 .env 文件加载 OPENAI_API_KEY 环境变量，确保你已经设置了这个环境变量。
api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")

client = OpenAI(api_key=api_key, base_url=base_url)


# =========================
# 会话级临时凭据文件
# =========================
class TempCredentialStore:
    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="agent_auth_"))
        self.file_path = self.temp_dir / "credentials.json"
        atexit.register(self.cleanup)

    def _read(self):
        if not self.file_path.exists():
            return {}
        return json.loads(self.file_path.read_text(encoding="utf-8"))

    def _write(self, data: dict):
        self.file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        try:
            os.chmod(self.file_path, 0o600)
        except Exception:
            pass

    def save(self, service: str, username: str, password: str):
        data = self._read()
        data[service] = {
            "username": username,
            "password": password
        }
        self._write(data)

    def load(self, service: str):
        return self._read().get(service)

    def has(self, service: str) -> bool:
        return self.load(service) is not None

    def delete(self, service: str):
        data = self._read()
        if service in data:
            del data[service]
            if data:
                self._write(data)
            else:
                self.cleanup()

    def cleanup(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)


TOOLS = [
    {
        "type": "function",
        "name": "request_auth",
        "description": "当访问某个受保护接口需要用户名和密码，但当前会话还没有该服务凭据时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "服务名，例如 crm、erp、order_api"
                },
                "reason": {
                    "type": "string",
                    "description": "为什么需要认证"
                }
            },
            "required": ["service"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "call_protected_api",
        "description": "调用受保护接口。支持 basic auth，或先登录换 token 再调用业务接口。",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "服务名"
                },
                "endpoint": {
                    "type": "string",
                    "description": "要调用的业务接口地址"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP 方法"
                },
                "auth_mode": {
                    "type": "string",
                    "enum": ["basic", "login_then_bearer"],
                    "description": "认证模式"
                },
                "login_url": {
                    "type": "string",
                    "description": "当 auth_mode=login_then_bearer 时使用的登录接口"
                },
                "token_field": {
                    "type": "string",
                    "description": "登录返回 JSON 中 token 字段名，默认 token"
                },
                "headers": {
                    "type": "object",
                    "description": "附加请求头",
                    "additionalProperties": True
                },
                "params": {
                    "type": "object",
                    "description": "查询参数",
                    "additionalProperties": True
                },
                "json_body": {
                    "type": "object",
                    "description": "JSON 请求体",
                    "additionalProperties": True
                }
            },
            "required": ["service", "endpoint"],
            "additionalProperties": False
        }
    }
]


INSTRUCTIONS = """
你是一个业务助手。

原则：
1. 如果用户要求访问需要认证的接口，而当前没有对应 service 的凭据，就调用 request_auth。
2. 不要在普通消息里直接要求用户把密码发给你。
3. 获取到认证后，再调用 call_protected_api。
4. 不要回显用户名和密码。
5. 用户如果只是问问题，不需要访问接口时，直接回答。
"""


def prompt_user_credentials(service: str):
    print(f"\n[需要认证] service = {service}")
    username = input("请输入用户名: ").strip()
    if not username:
        return None

    password = getpass.getpass("请输入密码: ").strip()
    if not password:
        return None

    return username, password


def request_auth(args: dict, cred_store: TempCredentialStore):
    service = args["service"]

    # 已有凭据，直接返回
    if cred_store.has(service):
        return {
            "ok": True,
            "service": service,
            "credential_state": "already_ready"
        }

    creds = prompt_user_credentials(service)
    if creds is None:
        return {
            "ok": False,
            "service": service,
            "error": "user_cancelled_auth"
        }

    username, password = creds
    cred_store.save(service, username, password)

    # 注意：只告诉模型“认证已准备好”，不把凭据回传给模型
    return {
        "ok": True,
        "service": service,
        "credential_state": "ready"
    }


def call_protected_api(args: dict, cred_store: TempCredentialStore):
    service = args["service"]
    endpoint = args["endpoint"]
    method = args.get("method", "GET").upper()
    auth_mode = args.get("auth_mode", "basic")

    headers = args.get("headers", {}) or {}
    params = args.get("params", {}) or {}
    json_body = args.get("json_body", {}) or {}

    creds = cred_store.load(service)
    if not creds:
        return {
            "ok": False,
            "service": service,
            "error": "missing_credentials"
        }

    username = creds["username"]
    password = creds["password"]

    try:
        if auth_mode == "basic":
            resp = requests.request(
                method=method,
                url=endpoint,
                headers=headers,
                params=params,
                json=json_body if method in ("POST", "PUT", "DELETE") else None,
                auth=(username, password),
                timeout=30,
            )

        elif auth_mode == "login_then_bearer":
            login_url = args.get("login_url")
            token_field = args.get("token_field", "token")

            if not login_url:
                return {
                    "ok": False,
                    "service": service,
                    "error": "login_url_required_for_login_then_bearer"
                }

            # 这里假设登录接口接收 JSON: {"username": "...", "password": "..."}
            login_resp = requests.post(
                login_url,
                json={"username": username, "password": password},
                timeout=30,
            )

            if login_resp.status_code >= 400:
                return {
                    "ok": False,
                    "service": service,
                    "error": "login_failed",
                    "status_code": login_resp.status_code,
                    "response_text": login_resp.text[:500]
                }

            login_data = {}
            try:
                login_data = login_resp.json()
            except Exception:
                return {
                    "ok": False,
                    "service": service,
                    "error": "login_response_not_json"
                }

            token = login_data.get(token_field)
            if not token:
                return {
                    "ok": False,
                    "service": service,
                    "error": f"token_field_not_found: {token_field}"
                }

            headers = dict(headers)
            headers["Authorization"] = f"Bearer {token}"

            resp = requests.request(
                method=method,
                url=endpoint,
                headers=headers,
                params=params,
                json=json_body if method in ("POST", "PUT", "DELETE") else None,
                timeout=30,
            )

        else:
            return {
                "ok": False,
                "service": service,
                "error": f"unsupported_auth_mode: {auth_mode}"
            }

        result = {
            "ok": True,
            "service": service,
            "status_code": resp.status_code,
        }

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                result["data"] = resp.json()
            except Exception:
                result["data"] = {"raw_text": resp.text[:2000]}
        else:
            result["data"] = {"raw_text": resp.text[:2000]}

        return result

    except requests.RequestException as e:
        return {
            "ok": False,
            "service": service,
            "error": "request_exception",
            "detail": str(e)
        }
        
def execute_tool_call(tool_call, cred_store: TempCredentialStore):
    """
    tool_call 一般会有:
    - tool_call.name
    - tool_call.arguments (JSON 字符串)
    - tool_call.call_id
    """
    name = tool_call.name
    args = json.loads(tool_call.arguments or "{}")

    if name == "request_auth":
        return request_auth(args, cred_store)

    if name == "call_protected_api":
        return call_protected_api(args, cred_store)

    return {
        "ok": False,
        "error": f"unknown_tool: {name}"
    }


def run_agent(user_text: str, cred_store: TempCredentialStore):
    try:
        response = client.responses.create(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=user_text,
            tools=TOOLS,
            tool_choice="auto",
            store=True,
        )

        while True:
            tool_calls = [item for item in response.output if item.type == "function_call"]

            if not tool_calls:
                return response.output_text

            tool_outputs = []
            for tool_call in tool_calls:
                print(f"正在执行工具调用: {tool_call.name}")
                result = execute_tool_call(tool_call, cred_store)
                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": json.dumps(result, ensure_ascii=False)
                })

            response = client.responses.create(
                model=MODEL,
                instructions=INSTRUCTIONS,
                previous_response_id=response.id,
                input=tool_outputs,
                tools=TOOLS,
                tool_choice="auto",
                store=True,
            )

    except BadRequestError as e:
        return f"请求参数错误: {e}"
    except APITimeoutError:
        return "OpenAI 请求超时，请稍后重试。"
    except APIConnectionError:
        return "无法连接 OpenAI，请检查网络。"
    except Exception as e:
        return f"运行失败: {type(e).__name__}: {e}"


def main():
    cred_store = TempCredentialStore()

    print("输入 /exit 退出；退出时会删除临时凭据文件。")
    print(f"{cred_store.file_path} 是当前会话的临时凭据文件，模型调用 request_auth 后会把认证信息保存在这里。\n")
    print("示例：帮我调用 ERP 接口查询订单 10086\n")

    try:
        while True:
            user_text = input("你> ").strip()
            if not user_text:
                continue
            if user_text == "/exit":
                break

            answer = run_agent(user_text, cred_store)
            
            print(f"助手> {answer}\n")

    finally:
        cred_store.cleanup()
        print("临时凭据文件已删除。")


if __name__ == "__main__":
    main()