"""
Kimi飞书机器人 - 简化版
"""
from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

# 从环境变量读取密钥
LARK_APP_ID = os.environ.get('LARK_APP_ID')
LARK_APP_SECRET = os.environ.get('LARK_APP_SECRET')
LARK_VERIFY_TOKEN = os.environ.get('LARK_VERIFY_TOKEN')
KIMI_API_KEY = os.environ.get('KIMI_API_KEY')

access_token_cache = {}

def get_tenant_access_token():
    """获取飞书tenant_access_token"""
    if 'token' in access_token_cache:
        return access_token_cache['token']
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": LARK_APP_ID,
        "app_secret": LARK_APP_SECRET
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        result = response.json()
        if result.get("code") == 0:
            token = result["tenant_access_token"]
            access_token_cache['token'] = token
            return token
    except Exception as e:
        print(f"获取token失败: {e}")
    
    return None

def call_kimi_api(message):
    """调用Kimi API获取回复"""
    url = "https://api.moonshot.cn/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIMI_API_KEY}"
    }
    data = {
        "model": "moonshot-v1-8k",
        "messages": [
            {"role": "system", "content": "你是一个友好的AI助手"},
            {"role": "user", "content": message}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"调用Kimi API失败: {e}")
    
    return "抱歉，我暂时无法回复，请稍后再试"

def send_lark_message(chat_id, message):
    """发送消息到飞书"""
    token = get_tenant_access_token()
    if not token:
        return False
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {"receive_id_type": "chat_id"}
    data = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": message})
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
        result = response.json()
        return result.get("code") == 0
    except Exception as e:
        print(f"发送消息失败: {e}")
    
    return False

@app.route('/webhook/feishu', methods=['POST'])
def webhook():
    """处理飞书Webhook请求"""
    try:
        data = request.json
        print(f"收到请求: {data}")
        
        # 验证token
        if LARK_VERIFY_TOKEN:
            header_token = request.headers.get('X-Lark-Token')
            if header_token != LARK_VERIFY_TOKEN:
                print("Token验证失败")
                return jsonify({"code": 403, "msg": "Forbidden"})
        
        # 处理URL验证
        if data.get('type') == 'url_verification':
            challenge = data.get('challenge')
            return jsonify({"challenge": challenge})
        
        # 处理消息事件
        event = data.get('event', {})
        if event.get('type') == 'im.message.receive_v1':
            message = event.get('message', {})
            chat_type = message.get('chat_type')
            
            # 只处理群聊消息
            if chat_type == 'group':
                chat_id = message.get('chat_id')
                content = json.loads(message.get('content', '{}'))
                text = content.get('text', '')
                
                print(f"收到群聊消息: {text}")
                
                # 调用Kimi获取回复
                reply = call_kimi_api(text)
                
                # 发送回复
                if send_lark_message(chat_id, reply):
                    print("回复成功")
                else:
                    print("回复失败")
        
        return jsonify({"code": 0, "msg": "success"})
    
    except Exception as e:
        print(f"处理请求出错: {e}")
        return jsonify({"code": 500, "msg": "Internal Server Error"})

@app.route('/')
def index():
    """首页"""
    return "Kimi飞书机器人运行中！"

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
