import asyncio
from bilibili_api import login_v2, video, sync
import qrcode_terminal
import json
import os

async def main():
    print("Please scan the QR code to login to Bilibili:")
    
    # 使用 login_v2 获取登录状态
    login_obj = await login_v2.login_with_qrcode()
    
    # 打印二维码到终端
    url = login_obj.get_url()
    qrcode_terminal.draw(url)
    
    print("\nWaiting for scan... Please scan the code with your Bilibili App.")
    
    try:
        # 等待扫码结果
        res = await login_obj.wait_for_scan()
        print("\nLogin Successful!")
        
        # 获取 Credential 并在本地保存凭证
        cred = login_obj.get_credential()
        auth_data = {
            "sessdata": cred.sessdata,
            "bili_jct": cred.bili_jct,
            "buvid3": cred.buvid3,
            "dedeuserid": cred.dedeuserid
        }
        with open("bili_auth.json", "w") as f:
            json.dump(auth_data, f)
        print("Credentials saved to 'bili_auth.json'.")
        
    except Exception as e:
        print(f"\nLogin Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
