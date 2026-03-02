import vk_api

def test_vk():
    token = "ВАШ_ТОКЕН_ИЗ_ENV"
    vk_session = vk_api.VkApi(token=token)
    try:
        vk = vk_session.get_api()
        user = vk.users.get()
        print(f"✅ Успех! Пользователь: {user[0]['first_name']} {user[0]['last_name']}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    test_vk()