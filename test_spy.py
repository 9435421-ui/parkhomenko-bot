import asyncio
from vkbottle import API

async def test_vk():
    # Берем токен из вашего .env
    token = "vk1.a.ebdfO6zU8u-It6gN3bDijc6m3t_-73m6i2HUOyflE0vUuofxoQ5gYpJS6_N" # здесь я сократил для безопасности
    api = API(token)
    try:
        user = await api.users.get()
        print(f"✅ Токен работает! Авторизован пользователь: {user[0].first_name} {user[0].last_name}")
    except Exception as e:
        print(f"❌ Ошибка токена: {e}")

if __name__ == "__main__":
    asyncio.run(test_vk())