import asyncio
from bilibili_api import login_v2

async def main():
    try:
        print("尝试生成 B站 二维码...")
        login_obj = await login_v2.login_with_qrcode()
        url = login_obj.get_url()
        print(f"成功! URL: {url[:30]}...")
    except Exception as e:
        print(f"❌ 失败! 错误类型: {type(e).__name__}, 错误内容: {str(e)}")

if __name__ == '__main__':
    asyncio.run(main())
