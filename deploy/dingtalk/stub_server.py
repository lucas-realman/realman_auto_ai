"""
Sirus AI-CRM 钉钉 Bot — Web 聊天测试 & DingTalk Stream 桥接
=========================================================
用法:
    python stub_server.py          # 启动 Web 测试页面 (端口 9001)

功能:
    1. 浏览器打开 http://<host>:9001/ 即可直接与 Bot 对话
    2. 后端复用 bot_server.py 的意图解析 + CRM 调用逻辑
    3. 未来接入钉钉 Stream 长连接只需填 APP_KEY / APP_SECRET
"""

import json
import logging
from typing import Dict, Any

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import settings
from message_parser import parse_intent, Intent
from card_templates import (
    lead_list_card,
    customer_detail_card,
    opportunity_card,
    help_card,
    error_card,
    success_card,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Sirus CRM Bot — Web 测试", version="0.1.0")

CRM_BASE = settings.crm_api_base.rstrip("/")

# ──────────────────── CRM helpers ────────────────────

async def crm_get(path: str, params=None) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        resp = await c.get(f"{CRM_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

async def crm_post(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        resp = await c.post(f"{CRM_BASE}{path}", json=data)
        resp.raise_for_status()
        return resp.json()

async def crm_put(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        resp = await c.put(f"{CRM_BASE}{path}", json=data)
        resp.raise_for_status()
        return resp.json()

# ──────────────────── Intent handlers ────────────────────

async def handle_list_leads(params: Dict) -> str:
    try:
        result = await crm_get("/api/v1/leads", params={"page": 1, "size": 10})
        items = result.get("items", [])
        total = result.get("total", 0)
        if not items:
            return "📭 暂无线索数据"
        lines = [f"📋 **线索列表** (共 {total} 条)\n"]
        for i, lead in enumerate(items, 1):
            lines.append(
                f"{i}. **{lead.get('companyName', '未知')}** — "
                f"{lead.get('contactName', '')} "
                f"{lead.get('phone', '')} "
                f"[{lead.get('status', '')}]"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 获取线索失败: {e}"

async def handle_search_customer(params: Dict) -> str:
    try:
        keyword = params.get("keyword", "")
        result = await crm_get("/api/v1/customers", params={"page": 1, "size": 5})
        items = result.get("items", [])
        if keyword:
            items = [c for c in items if keyword.lower() in (c.get("companyName", "") or "").lower()]
        if not items:
            return f"🔍 未找到匹配「{keyword}」的客户"
        c = items[0]
        return (
            f"👤 **客户详情**\n"
            f"- 公司: {c.get('companyName', '')}\n"
            f"- 联系人: {c.get('contactPerson', '')}\n"
            f"- 行业: {c.get('industry', '未知')}\n"
            f"- 级别: {c.get('level', '未知')}\n"
            f"- ID: `{c.get('id', '')}`"
        )
    except Exception as e:
        return f"❌ 搜索客户失败: {e}"

async def handle_create_lead(params: Dict) -> str:
    try:
        data = {
            "companyName": params.get("company_name", params.get("company", "未命名公司")),
            "contactName": params.get("contact_name", params.get("contact", "未知联系人")),
            "phone": params.get("phone"),
            "source": "dingtalk",
        }
        result = await crm_post("/api/v1/leads", data)
        return (
            f"✅ **线索创建成功！**\n"
            f"- 公司: {result.get('companyName')}\n"
            f"- 联系人: {result.get('contactName')}\n"
            f"- ID: `{result.get('id')}`"
        )
    except Exception as e:
        return f"❌ 创建线索失败: {e}"

async def handle_opportunity_info(params: Dict) -> str:
    try:
        result = await crm_get("/api/v1/opportunities", params={"page": 1, "size": 5})
        items = result.get("items", [])
        if not items:
            return "📭 暂无商机数据"
        total = result.get("total", 0)
        lines = [f"💼 **商机列表** (共 {total} 条)\n"]
        for i, opp in enumerate(items, 1):
            lines.append(
                f"{i}. **{opp.get('name', '未命名')}** — "
                f"阶段: {opp.get('stage', '')} "
                f"金额: ¥{opp.get('amount', 0):,.0f}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 获取商机失败: {e}"

async def handle_help(params: Dict) -> str:
    return (
        "🤖 **Sirus AI-CRM 机器人指令帮助**\n\n"
        "| 指令 | 示例 | 说明 |\n"
        "|---|---|---|\n"
        "| `查线索` | 查线索 Test | 搜索线索列表 |\n"
        "| `新建线索` | 新建线索 公司 联系人 手机号 | 创建新线索 |\n"
        "| `客户详情` | 客户详情 XX公司 | 查看客户信息 |\n"
        "| `推进商机` | 推进商机 XX | 查看商机信息 |\n"
        "| `最近活动` | 最近活动 | 查看最近活动 |\n"
        "| `帮助` | 帮助 | 显示本帮助 |"
    )

INTENT_HANDLERS = {
    Intent.LIST_LEADS: handle_list_leads,
    Intent.SEARCH_CUSTOMER: handle_search_customer,
    Intent.CREATE_LEAD: handle_create_lead,
    Intent.OPPORTUNITY_INFO: handle_opportunity_info,
    Intent.HELP: handle_help,
}

# ──────────────────── Chat API ────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """处理用户消息并返回回复"""
    text = req.message.strip()
    if not text:
        return ChatResponse(reply=await handle_help({}))
    
    intent, params = parse_intent(text)
    logger.info(f"消息: {text} → 意图: {intent}, 参数: {params}")
    
    handler = INTENT_HANDLERS.get(intent)
    if handler:
        reply = await handler(params)
    else:
        reply = f"🤔 不太理解你的意思: 「{text}」\n\n发送 **帮助** 查看可用指令"
    
    return ChatResponse(reply=reply)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "crm-bot-web-test"}

# ──────────────────── Web Chat UI ────────────────────

CHAT_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sirus AI-CRM 机器人</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f0f2f5; height: 100vh; display: flex; flex-direction: column; }
.header { background: #1677ff; color: white; padding: 16px 24px;
           display: flex; align-items: center; gap: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.15); }
.header h1 { font-size: 18px; font-weight: 600; }
.header .dot { width: 10px; height: 10px; background: #52c41a; border-radius: 50%; }
.chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.msg { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; word-break: break-word; font-size: 14px; }
.msg.bot { background: white; align-self: flex-start; box-shadow: 0 1px 2px rgba(0,0,0,.1); border-bottom-left-radius: 4px; }
.msg.user { background: #1677ff; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
.msg pre { background: #f5f5f5; padding: 8px; border-radius: 6px; overflow-x: auto; margin: 4px 0; font-size: 13px; }
.msg table { border-collapse: collapse; margin: 8px 0; font-size: 13px; }
.msg th, .msg td { border: 1px solid #e8e8e8; padding: 4px 10px; text-align: left; }
.msg th { background: #fafafa; }
.input-area { background: white; padding: 16px 20px; display: flex; gap: 12px; box-shadow: 0 -2px 8px rgba(0,0,0,.06); }
.input-area input { flex: 1; padding: 10px 16px; border: 1px solid #d9d9d9; border-radius: 8px; font-size: 14px; outline: none; transition: border .2s; }
.input-area input:focus { border-color: #1677ff; }
.input-area button { padding: 10px 24px; background: #1677ff; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; transition: background .2s; }
.input-area button:hover { background: #0958d9; }
.input-area button:disabled { background: #d9d9d9; cursor: not-allowed; }
.quick-btns { display: flex; gap: 8px; padding: 0 20px 8px; flex-wrap: wrap; }
.quick-btns button { padding: 6px 14px; background: #e6f4ff; color: #1677ff; border: 1px solid #91caff; border-radius: 16px; cursor: pointer; font-size: 13px; transition: all .2s; }
.quick-btns button:hover { background: #1677ff; color: white; }
.typing { color: #999; font-size: 13px; padding: 4px 16px; }
</style>
</head>
<body>
<div class="header">
  <div class="dot"></div>
  <h1>🤖 Sirus AI-CRM 机器人</h1>
</div>
<div class="chat-container" id="chat"></div>
<div class="quick-btns">
  <button onclick="sendMsg('帮助')">📖 帮助</button>
  <button onclick="sendMsg('查线索')">🔍 查线索</button>
  <button onclick="sendMsg('最近活动')">📅 最近活动</button>
  <button onclick="sendMsg('推进商机')">💼 推进商机</button>
  <button onclick="sendMsg('新建线索 测试公司 张三 13800000001')">➕ 新建线索(示例)</button>
</div>
<div class="input-area">
  <input id="input" type="text" placeholder="输入指令，如: 查线索 Test ..." autocomplete="off">
  <button id="sendBtn" onclick="sendInput()">发送</button>
</div>
<script>
const chatEl = document.getElementById('chat');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');

// Simple markdown → HTML
function md(t) {
  return t
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/^\\|(.+)$/gm, r => {
      const cells = r.split('|').filter(Boolean).map(c => c.trim());
      if (cells.every(c => /^-+$/.test(c))) return '';
      const tag = chatEl.querySelector('table:last-child thead') ? 'td' : 'th';
      const wrap = tag === 'th' ? 'thead' : 'tbody';
      return `<table><${wrap}><tr>${cells.map(c=>`<${tag}>${c}</${tag}>`).join('')}</tr></${wrap}></table>`;
    })
    .replace(/<\\/table>\\s*<table>/g, '')
    .replace(/\\n/g,'<br>');
}

function addMsg(text, cls) {
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.innerHTML = cls === 'bot' ? md(text) : text.replace(/</g,'&lt;');
  chatEl.appendChild(d);
  chatEl.scrollTop = chatEl.scrollHeight;
  return d;
}

async function sendMsg(text) {
  if (!text.trim()) return;
  addMsg(text, 'user');
  inputEl.value = '';
  sendBtn.disabled = true;
  const typing = document.createElement('div');
  typing.className = 'typing';
  typing.textContent = '🤖 正在思考...';
  chatEl.appendChild(typing);
  chatEl.scrollTop = chatEl.scrollHeight;
  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await resp.json();
    typing.remove();
    addMsg(data.reply || '(空回复)', 'bot');
  } catch(e) {
    typing.remove();
    addMsg('⚠️ 请求失败: ' + e.message, 'bot');
  }
  sendBtn.disabled = false;
  inputEl.focus();
}

function sendInput() { sendMsg(inputEl.value); }
inputEl.addEventListener('keydown', e => { if(e.key==='Enter') sendInput(); });

// Welcome
addMsg('👋 你好！我是 Sirus AI-CRM 机器人。\\n\\n发送 **帮助** 查看可用指令，或点击下方快捷按钮。', 'bot');
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return CHAT_HTML


# ──────────────────── Startup ────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Web 聊天测试页: http://0.0.0.0:9001/")
    print(f"📡 CRM API 后端: {CRM_BASE}")
    uvicorn.run("stub_server:app", host="0.0.0.0", port=9001, reload=True)
