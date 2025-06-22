async def handle_download_ea(query):
    """Обработчик скачивания EA"""
    user_id = query.from_user.id
    license_data = get_user_license(user_id)
    
    if not license_data or license_data[1] == 'inactive':
        await query.message.reply_text(
            "❌ **Нет активной лицензии!**\n\n"
            "Для скачивания EA нужна активная лицензия.\n"
            "Получите пробную или купите полную лицензию.",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        return
    
    license_key = license_data[0]
    
    # Отправляем инструкцию
    await query.message.reply_text(
        f"📁 **Скачивание EA**\n\n"
        f"🔑 **Ваш лицензионный ключ:** `{license_key}`\n\n"
        f"📋 **Инструкция:**\n"
        f"1. Скачайте файл который придет следующим сообщением\n"
        f"2. Поместите EA в папку: MQL5/Experts/\n"
        f"3. Перезапустите MetaTrader 5\n"
        f"4. При запуске EA введите ваш ключ: `{license_key}`\n\n"
        f"⏳ Отправляю файл...",
        parse_mode='Markdown'
    )
    
    # Отправляем файл EA
    try:
        ea_file_data = get_ea_file()
        if ea_file_data:
            await query.message.reply_document(
                document=ea_file_data,
                filename="Simple_VPS_Optimized_Version.ex5",
                caption=f"🤖 **Торговый советник**\n\n🔑 **Лицензионный ключ:** `{license_key}`\n\n❗ Сохраните ключ - он понадобится при запуске EA!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            await query.message.reply_text(
                "❌ **Ошибка!**\n\nФайл EA временно недоступен. Обратитесь к администратору.",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        print(f"Ошибка отправки файла: {e}")
        await query.message.reply_text(
            "❌ **Ошибка отправки файла!**\n\nПопробуйте позже или обратитесь к администратору.",
            reply_markup=get_main_keyboard()
        )
