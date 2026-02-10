# -*- coding: utf-8 -*-
import requests
import time
import random

# ================= 🔧 配置区 (填这里) =================
accounts = [
    # 账号 1
    ("jintian03030411@gmail.com", "liunuoyan106303"), 
    
    # 账号 2
    ("ssong4329@gmail.com", "liunuoyan106303"),
    
    # 账号 3
    ("873245372@qq.com", "liunuoyan106303"),
]

# ================= ⚙️ 核心逻辑区 =================

def login_and_get_token(email, password, index):
    """
    第一步：登录接口
    解释：直接请求乐淘商城的登录口，它支持用乐一番账号直接认证
    """
    print(f"🔐 [账号 {index}] 正在尝试自动登录...")
    
    # 这是乐淘商城的专用登录接口
    login_url = "https://api.mall.leyifan.cn/api/front/login/leyifan"
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        # 伪装成从乐淘一番网页发起的请求
        "Origin": "https://letaoyifan.com",
        "Referer": "https://letaoyifan.com/",
        "Clientid": "cbdb7a7d-d6d8-4c2e-a398-534de34b449a6", # 这是一个通用的浏览器客户端ID
        "Appplatform": "other",
        "platform": "web"
    }
    
    payload = {
        "account": email,
        "password": password
    }
    
    try:
        resp = requests.post(login_url, json=payload, headers=headers)
        
        if resp.status_code == 200:
            data = resp.json()
            # 只要这里拿到 Token，就说明不需要去“乐一番”母站跳转，因为后台已经帮我们验证了
            if data.get("code") == 200 and "data" in data and "token" in data["data"]:
                token = data["data"]["token"]
                print(f"✅ [账号 {index}] 登录成功！获取到商城 Token: {token[:10]}...")
                return token
            else:
                print(f"❌ [账号 {index}] 登录失败: {data.get('message')}")
                return None
        else:
            print(f"❌ [账号 {index}] 网络错误: {resp.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ [账号 {index}] 登录报错: {e}")
        return None

def sign_in(token, index):
    """
    第二步：签到接口
    """
    print(f"🚀 [账号 {index}] 正在执行签到...")
    
    # 🔴 关键修复：这里的域名必须是 api.mall...，之前报错404就是因为这里错了
    sign_url = "https://api.mall.leyifan.cn/api/front/user/sign/integral"
    
    headers = {
        # 把拿到的 Token 塞进 Header
        "Authori-zation": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Origin": "https://letaoyifan.com",
        "Referer": "https://letaoyifan.com/",
        "App-Version": "30361",
        "platform": "web"
    }
    
    try:
        # GET 请求
        resp = requests.get(sign_url, headers=headers)
        
        if resp.status_code == 200:
            if "成功" in resp.text:
                print(f"✅ [账号 {index}] 签到成功！积分已到手。")
            else:
                print(f"ℹ️ [账号 {index}] 接口返回: {resp.text}")
                
        elif resp.status_code == 500:
            # 乐淘一番把“重复签到”算作500错误，这是正常的
            if "已签到" in resp.text:
                print(f"⚠️ [账号 {index}] 今天已经签过了 (不用担心，这代表成功)。")
            else:
                print(f"❌ [账号 {index}] 服务器内部错误: {resp.text}")
        else:
            print(f"❌ [账号 {index}] 签到失败: {resp.status_code} (如果还是404请告诉我)")
            
    except Exception as e:
        print(f"❌ [账号 {index}] 签到报错: {e}")

# ================= ▶️ 主程序 =================
if __name__ == "__main__":
    print(f"🤖 乐淘一番自动签到 V2.2 (纠正域名版)")
    print(f"📋 共加载了 {len(accounts)} 个账号\n")
    
    for i, (email, pwd) in enumerate(accounts, 1):
        if "填在这里" in pwd:
            print(f"⚠️ 跳过账号 {i}：请填写密码")
            continue
            
        # 1. 直接攻击商城登录口
        new_token = login_and_get_token(email, pwd, i)
        
        # 2. 如果拿到票，就进场
        if new_token:
            time.sleep(1)
            sign_in(new_token, i)
        
        print("-" * 30)
        
        if i < len(accounts):
            time.sleep(3)

    #input("\n所有任务完成，按回车退出...")