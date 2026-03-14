import asyncio; from services.lead_hunter.hunter import LeadHunter;
async def run():
    print('🏹 Запуск охоты с новым токеном...'); 
    h=LeadHunter(); 
    h.parser.vk_token='vk1.a.xjSVhe9KHAWSqXdIgUzJhMqJmhq54yjkQo28uhXXMRVVZ3S_iBjAsG-o0zMAZLexBRQNsMfs5SHwvn3F8CvQEmGx6dDFOMNfdrnwWie5mI6-IvZMToZcJIX5P9TcvQnSovmgceJe-mS4u537UE1uN8Z-zDKsrZXBbMT8CilNgT7JHwmT-F9yBGacNkP3hWj5-SbOGBpp6m-T9Sn6Y9_HYQ'; 
    h.business_hours_only=False; 
    await h.hunt()
asyncio.run(run())
