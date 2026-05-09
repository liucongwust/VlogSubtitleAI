import asyncio
from bilibili_api import login_v2

async def main():
    try:
        login = login_v2.QrCodeLogin()
        print("Generating QR code...")
        await login.generate_qrcode()
        # In version 17, the link is private but accessible via name mangling or there's a getter
        # Let's try to see if there's a public way
        link = getattr(login, "_QrCodeLogin__qr_link", None)
        print(f"Link: {link}")
        
        # Check status
        state = await login.check_state()
        print(f"State: {state}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
