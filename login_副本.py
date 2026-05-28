import json
import time
from datetime import datetime

import pandas as pd
import requests
from playwright.sync_api import sync_playwright


def login_and_get_session(username: str, password: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = context.new_page()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                page.goto("https://cdn.xiavier.com/login", wait_until="domcontentloaded", timeout=60000)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"页面加载失败(第{attempt+1}次)，重试中...")
                    page.wait_for_timeout(3000)
                else:
                    raise e
        print("正在加载登录页面...")
        page.wait_for_timeout(3000)

        # 填写用户名和密码（表单两个字段都填完再提交）
        print(f"正在填写账号: {username}")
        page.fill('#username', username)
        print("正在填写密码...")
        page.fill('#password', password)

        # 等待 Turnstile 自动完成验证
        print("正在等待 Turnstile 验证...")
        for i in range(120):
            page.wait_for_timeout(1000)
            token = page.evaluate("""() => {
                var input = document.querySelector('input[name="cf-turnstile-response"]');
                var textarea = document.querySelector('textarea[name="cf-turnstile-response"]');
                return (input && input.value) ? input.value : (textarea && textarea.value ? textarea.value : null);
            }""")
            if token:
                print("验证完成！")
                break
            if i % 10 == 0 and i > 0:
                print(f"已等待 {i} 秒...")

        if not token:
            browser.close()
            raise Exception("Turnstile 验证超时")

        # 点击"继续"按钮提交表单（该按钮 type=submit，是登录表单的提交按钮）
        print("正在点击继续按钮...")
        submit_button = page.query_selector('button[type="submit"]')
        if not submit_button:
            submit_button = page.query_selector('button:has-text("继续")')
        if submit_button:
            print(f"找到提交按钮: {submit_button.text_content()}")
            submit_button.click()
        else:
            print("未找到提交按钮，尝试回车提交...")
            page.press('#password', 'Enter')

        # 轮询等待：检查页面跳转（成功）或错误提示（失败）
        print("等待登录响应...")
        user_id = None
        error_msg = None
        success_detected = False
        for i in range(20):
            page.wait_for_timeout(1000)
            current_url = page.url

            if '/console' in current_url or '/dashboard' in current_url:
                print(f"当前 URL: {current_url}")
                print("检测到已进入控制台，登录成功！")
                user_info = page.evaluate("""() => {
                    try {
                        return window.localStorage.getItem('user');
                    } catch(e) {
                        return null;
                    }
                }""")
                if user_info:
                    try:
                        user_data = json.loads(user_info)
                        user_id = user_data.get('id')
                        print(f"用户ID: {user_id}")
                    except:
                        pass
                break

            error_msg = page.evaluate("""() => {
                var selectors = [
                    '.semi-notification-description',
                    '.semi-toast-content',
                    '.semi-toast',
                    '.error-message',
                    '[class*="error"]',
                    '[class*="toast"]',
                    '[class*="notification"]',
                    '[class*="alert"]',
                    '[class*="message"]'
                ];
                for (var i = 0; i < selectors.length; i++) {
                    var el = document.querySelector(selectors[i]);
                    if (el && el.textContent && el.textContent.trim().length > 0) {
                        return el.textContent.trim();
                    }
                }
                return null;
            }""")
            if error_msg:
                if any(kw in error_msg for kw in ['成功', 'success']):
                    print(f"当前 URL: {current_url}")
                    print(f"检测到成功消息: {error_msg}")
                    success_detected = True
                    error_msg = None
                    continue
                if not success_detected:
                    print(f"当前 URL: {current_url}")
                    print(f"检测到错误信息: {error_msg}")
                    break

        # 判断最终结果
        if user_id:
            pass
        elif success_detected:
            print("检测到登录成功但未获取到用户信息，尝试获取 session cookie")
        elif error_msg:
            browser.close()
            return {'success': False, 'message': error_msg}
        else:
            print(f"当前 URL: {current_url}")
            # 最终兜底：再全面捞一次页面可见文本中的错误关键词
            page_text = page.evaluate("""() => document.body.innerText""")
            for keyword in ['错误', '失败', '禁止', '封禁', '锁定']:
                for line in page_text.split('\n'):
                    if keyword in line and len(line.strip()) > 2:
                        error_msg = line.strip()
                        break
                if error_msg:
                    break
            if error_msg:
                print(f"检测到错误信息: {error_msg}")
            else:
                error_msg = '登录失败，请检查账号密码'
            browser.close()
            return {'success': False, 'message': error_msg}

        # 登录成功，获取 cookies
        cookies = context.cookies()
        session_cookie = None
        for cookie in cookies:
            if cookie["name"] == "session":
                session_cookie = cookie["value"]
                break

        browser.close()

        if session_cookie and user_id:
            print(f"获取到 session cookie: {session_cookie[:50]}...")
            return {
                'success': True,
                'session_cookie': session_cookie,
                'user_id': user_id,
            }
        elif session_cookie:
            print(f"获取到 session cookie: {session_cookie[:50]}...")
            return {
                'success': True,
                'session_cookie': session_cookie,
            }
        else:
            return {'success': False, 'message': '未能获取 session cookie'}


def checkin(session_cookie: str, user_id: int) -> dict:
    """发送签到请求"""
    url = "https://cdn.xiavier.com/api/user/checkin"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-HK;q=0.6",
        "cache-control": "no-store",
        "content-length": "0",
        "new-api-user": str(user_id),
        "origin": "https://cdn.xiavier.com",
        "priority": "u=1, i",
        "referer": "https://cdn.xiavier.com/console/personal",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    }
    cookies = {"session": session_cookie}

    session = requests.Session()
    session.cookies.set("session", session_cookie)

    resp = session.post(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_user_id_from_session(session_cookie: str) -> int:
    """通过 API 获取用户 ID"""
    url = "https://cdn.xiavier.com/api/user/self"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-HK;q=0.6",
        "cache-control": "no-store",
        "new-api-user": "0",
        "origin": "https://cdn.xiavier.com",
        "priority": "u=1, i",
        "referer": "https://cdn.xiavier.com/console/personal",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    }
    session = requests.Session()
    session.cookies.set("session", session_cookie)

    resp = session.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if data.get("success"):
        return data["data"]["id"]
    else:
        raise Exception(f"获取用户信息失败: {data.get('message')}")


def process_accounts(excel_path: str):
    """批量处理账号登录和签到"""
    # 读取 Excel 文件
    df = pd.read_excel(excel_path)
    accounts = df[['账号', '密码']].dropna(subset=['账号', '密码'])

    print(f"共读取到 {len(accounts)} 个账号")

    # 记录失败的账号
    failed_accounts = []

    # 遍历每个账号进行登录和签到
    for index, row in accounts.iterrows():
        username = str(row['账号']).strip()
        password = str(row['密码']).strip()

        print(f"\n{'='*50}")
        print(f"处理账号 [{index+1}/{len(accounts)}]: {username}")
        print("="*50)

        try:
            # 通过浏览器登录
            print("正在通过浏览器登录...")
            login_result = login_and_get_session(username, password)

            if login_result.get("success"):
                session_cookie = login_result["session_cookie"]
                user_id = login_result.get("user_id")
                print(f"✅ 登录成功")
                if user_id:
                    print(f"用户ID: {user_id}")

                # 签到（登录时已获取 user_id 则直接使用，否则回退 API）
                if not user_id:
                    try:
                        user_id = get_user_id_from_session(session_cookie)
                        print(f"用户ID: {user_id}")
                    except Exception as e:
                        error_msg = f"获取用户信息失败: {str(e)}"
                        print(f"❌ {error_msg}")
                        failed_accounts.append({
                            '账号': username,
                            '密码': password,
                            '失败类型': '登录失败',
                            '失败原因': error_msg
                        })
                        continue

                # 签到
                try:
                    checkin_result = checkin(session_cookie, user_id)

                    if checkin_result.get("success"):
                        print(f"✅ 签到成功: {checkin_result.get('message', '')}")
                    else:
                        checkin_msg = checkin_result.get("message", "签到失败")
                        print(f"⚠️ 签到结果: {checkin_msg}")

                        if "已签到" not in checkin_msg:
                            failed_accounts.append({
                                '账号': username,
                                '密码': password,
                                '失败类型': '签到失败',
                                '失败原因': checkin_msg
                            })

                except requests.exceptions.HTTPError as e:
                    error_msg = f"签到请求失败: {e}"
                    print(f"❌ {error_msg}")
                    failed_accounts.append({
                        '账号': username,
                        '密码': password,
                        '失败类型': '签到失败',
                        '失败原因': error_msg
                    })
                except Exception as e:
                    error_msg = f"签到异常: {str(e)}"
                    print(f"❌ {error_msg}")
                    failed_accounts.append({
                        '账号': username,
                        '密码': password,
                        '失败类型': '签到失败',
                        '失败原因': error_msg
                    })

            else:
                # 登录失败
                login_msg = login_result.get("message", "登录失败")
                error_msg = f"登录失败: {login_msg}"
                print(f"❌ {error_msg}")
                failed_accounts.append({
                    '账号': username,
                    '密码': password,
                    '失败类型': '登录失败',
                    '失败原因': login_msg
                })

        except Exception as e:
            error_msg = f"处理异常: {str(e)}"
            print(f"❌ {error_msg}")
            failed_accounts.append({
                '账号': username,
                '密码': password,
                '失败类型': '登录失败',
                '失败原因': error_msg
            })

        # 每个账号处理完后等待一段时间，避免请求过于频繁
        if index < len(accounts) - 1:
            wait_seconds = 10
            print(f"等待 {wait_seconds} 秒后处理下一个账号...")
            time.sleep(wait_seconds)

    # 保存失败记录到 Excel
    if failed_accounts:
        failed_df = pd.DataFrame(failed_accounts)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failed_excel_path = f"/Users/zhaoguangshuai/py/login-sign/failed_accounts_{timestamp}.xlsx"
        failed_df.to_excel(failed_excel_path, index=False)
        print(f"\n{'='*50}")
        print(f"处理完成！失败账号已保存到: {failed_excel_path}")
        print(f"共 {len(failed_accounts)} 个账号失败")
        print("="*50)
    else:
        print(f"\n{'='*50}")
        print("处理完成！所有账号均登录并签到成功")
        print("="*50)


if __name__ == "__main__":
    EXCEL_PATH = "/Users/zhaoguangshuai/py/login-sign/login-info.xlsx"
    process_accounts(EXCEL_PATH)
