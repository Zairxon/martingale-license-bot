//+------------------------------------------------------------------+
//|                       MartingaleVPS_Enhanced_LICENSED.mq5      |
//|                            VPS Optimized Version + LICENSE     |
//|                       Защищенная лицензионная версия           |
//+------------------------------------------------------------------+
#property copyright "TradingBot 2025 - VPS Enhanced + LICENSE PROTECTION"
#property version   "1.61"
#property description "VPS Optimized Auto Martingale Robot - LICENSED VERSION"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>

//--- Trading objects
CTrade trade;
CPositionInfo position;
COrderInfo order;

//+------------------------------------------------------------------+
//| СИСТЕМА ЛИЦЕНЗИРОВАНИЯ - НЕ УДАЛЯТЬ!                           |
//+------------------------------------------------------------------+
input group "=== 🔐 ЛИЦЕНЗИЯ ==="
input string LicenseKey = "";                   // Лицензионный ключ (обязательно!)

//--- Лицензионные переменные
bool licenseValid = false;
datetime lastLicenseCheck = 0;
datetime licenseCheckInterval = 24 * 60 * 60;   // Проверка каждые 24 часа
string botURL = "https://martingale-license-bot-production.up.railway.app"; // URL вашего бота
bool tradingBlocked = true;                     // Блокировка торговли по умолчанию

//--- Input parameters (ОРИГИНАЛЬНЫЕ НАСТРОЙКИ)
input group "=== ОСНОВНЫЕ ПАРАМЕТРЫ ==="
input double InitialLot = 0.01;              // Начальный размер лота
input int TakeProfitPips = 10000;            // Take Profit в пунктах
input int BuyStopPips = 3000;                // Расстояние Buy Stop в пунктах

input group "=== УПРАВЛЕНИЕ РИСКАМИ ==="
input int MaxDoubling = 15;                  // Максимальное количество удвоений
input double MaxLotSize = 50.0;              // Максимальный размер лота

input group "=== VPS ОПТИМИЗАЦИЯ ==="
input int MaxRetries = 3;                    // Макс попыток для неудачных операций
input int RetryDelay = 500;                  // Задержка между попытками (мс)
input int MinTicksForStart = 1;              // Мин тиков перед запуском
input bool WaitForMarketOpen = false;        // Ждать открытия рынка - ОТКЛЮЧЕНО
input int MarketCheckInterval = 1;           // Интервал проверки рынка (сек)

input group "=== НАСТРОЙКИ АВТО ТРЕНДА ==="
input int TrendPeriod = 20;                  // Период для определения тренда
input double TrendThreshold = 50.0;          // Порог тренда в пунктах
input bool UseMA = true;                     // Использовать скользящую среднюю
input int DelayBetweenSessions = 5;          // Задержка между сессиями (секунды)

input group "=== НАСТРОЙКИ СЕССИИ ==="
input bool ResetAfterTP = true;              // Сброс после Take Profit
input int MagicNumber = 123456;              // Магический номер
input string CommentPrefix = "VPS_Mart";     // Префикс комментария

//--- Рабочие переменные (ОРИГИНАЛЬНЫЕ)
bool WorkingUseMA = true;
double currentLot = 0.01;
int doublingCount = 0;
bool sessionActive = false;
bool robotStarted = false;
bool marketReady = false;
double sessionStartPrice = 0;
datetime lastTradeTime = 0;
datetime lastSessionEnd = 0;
datetime lastMarketCheck = 0;
double pipValue = 0;
string tradingSymbol = "";
int tickCounter = 0;
int startupDelay = 1;
datetime robotStartTime = 0;

//--- Уровни сессии (ОРИГИНАЛЬНЫЕ)
double sessionSellLevel = 0;
double sessionBuyLevel = 0;
double sessionTP = 0;
double sessionSL = 0;

//--- Определение тренда (ОРИГИНАЛЬНЫЕ)
int maHandle = INVALID_HANDLE;

//--- Мониторинг VPS соединения (ОРИГИНАЛЬНЫЕ)
datetime lastTickTime = 0;
int connectionErrors = 0;

//--- Отслеживание позиций (ОРИГИНАЛЬНЫЕ)
struct PositionData {
    ulong ticket;
    int type;
    double lots;
    double openPrice;
    double takeProfit;
    double stopLoss;
    datetime openTime;
};

PositionData positions[];

//+------------------------------------------------------------------+
//| 🔐 ПРОВЕРКА ЛИЦЕНЗИИ - КРИТИЧЕСКАЯ ФУНКЦИЯ                    |
//+------------------------------------------------------------------+
bool CheckLicense() {
    Print("🔐 === ПРОВЕРКА ЛИЦЕНЗИИ ===");
    
    // Проверяем что ключ введен
    if(StringLen(LicenseKey) == 0) {
        Alert("❌ ОШИБКА: Лицензионный ключ не введен!");
        Print("❌ КРИТИЧЕСКАЯ ОШИБКА: Пустой лицензионный ключ!");
        Print("❌ Введите лицензионный ключ в настройках советника!");
        return false;
    }
    
    Print("🔐 Лицензионный ключ: ", StringSubstr(LicenseKey, 0, 8), "...");
    Print("🔐 Проверяем лицензию на сервере...");
    
    // Формируем URL для проверки
    string checkURL = botURL + "/check_license?key=" + LicenseKey;
    Print("🔐 URL проверки: ", checkURL);
    
    // Выполняем HTTP запрос
    string headers = "";
    char post[], result[];
    int timeout = 5000; // 5 секунд
    
    Print("🔐 Отправляем запрос на сервер...");
    int httpResult = WebRequest("GET", checkURL, headers, timeout, post, result, headers);
    
    if(httpResult == -1) {
        int error = GetLastError();
        Print("❌ ОШИБКА HTTP запроса: ", error);
        
        if(error == 4060) {
            Alert("❌ ОШИБКА: URL не разрешен! Добавьте в настройки:\n" + botURL);
            Print("❌ Добавьте в MT5: Сервис -> Настройки -> Советники -> Разрешить WebRequest для URL:");
            Print("❌ ", botURL);
        }
        
        return false;
    }
    
    string response = CharArrayToString(result);
    Print("🔐 Ответ сервера (", httpResult, "): ", response);
    
    // Проверяем HTTP статус
    if(httpResult != 200) {
        Print("❌ Ошибка сервера. HTTP код: ", httpResult);
        Alert("❌ ОШИБКА: Сервер лицензий недоступен (код " + IntegerToString(httpResult) + ")");
        return false;
    }
    
    // Простая проверка ответа
    if(StringFind(response, "\"valid\":true") >= 0 || StringFind(response, "active") >= 0) {
        Print("✅ ЛИЦЕНЗИЯ ДЕЙСТВИТЕЛЬНА!");
        lastLicenseCheck = TimeCurrent();
        return true;
    } else if(StringFind(response, "expired") >= 0) {
        Alert("❌ ЛИЦЕНЗИЯ ИСТЕКЛА! Обновите лицензию в боте.");
        Print("❌ Лицензия истекла");
        return false;
    } else if(StringFind(response, "invalid") >= 0) {
        Alert("❌ НЕВЕРНЫЙ ЛИЦЕНЗИОННЫЙ КЛЮЧ!");
        Print("❌ Неверный ключ");
        return false;
    } else {
        Print("❌ Неизвестный ответ сервера: ", response);
        Alert("❌ ОШИБКА: Неожиданный ответ сервера лицензий");
        return false;
    }
}

//+------------------------------------------------------------------+
//| 🔐 ПЕРИОДИЧЕСКАЯ ПРОВЕРКА ЛИЦЕНЗИИ                             |
//+------------------------------------------------------------------+
void CheckLicensePeriodically() {
    // Проверяем раз в 24 часа
    if(TimeCurrent() - lastLicenseCheck > licenseCheckInterval) {
        Print("🔐 Время периодической проверки лицензии...");
        
        bool newStatus = CheckLicense();
        
        if(newStatus != licenseValid) {
            licenseValid = newStatus;
            tradingBlocked = !licenseValid;
            
            if(!licenseValid) {
                Print("❌ ЛИЦЕНЗИЯ СТАЛА НЕДЕЙСТВИТЕЛЬНОЙ! БЛОКИРУЕМ ТОРГОВЛЮ!");
                Comment("❌ СОВЕТНИК ЗАБЛОКИРОВАН\n" +
                        "🔐 ПРИЧИНА: Недействительная лицензия\n" +
                        "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                        "🔑 КЛЮЧ: " + StringSubstr(LicenseKey, 0, 8) + "...\n" +
                        "📞 Обратитесь к администратору!");
                
                // Закрываем все позиции
                CloseAllPositionsAndOrders();
            } else {
                Print("✅ Лицензия снова действительна!");
                Comment("✅ ЛИЦЕНЗИЯ ВОССТАНОВЛЕНА\n" +
                        "📊 СТАТУС: Готов к торговле\n" +
                        "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()));
            }
        }
    }
}

//+------------------------------------------------------------------+
//| 🔐 БЛОКИРОВКА ТОРГОВЛИ ПРИ НЕВЕРНОЙ ЛИЦЕНЗИИ                  |
//+------------------------------------------------------------------+
bool IsLicenseValid() {
    if(tradingBlocked) {
        static datetime lastWarning = 0;
        
        // Показываем предупреждение раз в минуту
        if(TimeCurrent() - lastWarning > 60) {
            Print("🚫 ТОРГОВЛЯ ЗАБЛОКИРОВАНА: Недействительная лицензия");
            lastWarning = TimeCurrent();
            
            Comment("🚫 ТОРГОВЛЯ ЗАБЛОКИРОВАНА\n" +
                    "🔐 ПРИЧИНА: Неверная/истекшая лицензия\n" +
                    "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                    "🔑 КЛЮЧ: " + (StringLen(LicenseKey) > 0 ? StringSubstr(LicenseKey, 0, 8) + "..." : "НЕ УКАЗАН") + "\n" +
                    "💡 РЕШЕНИЕ:\n" +
                    "   1. Проверьте лицензионный ключ\n" +
                    "   2. Обновите лицензию в Telegram боте\n" +
                    "   3. Убедитесь что интернет работает\n" +
                    "📞 Поддержка: @YourSupportBot");
        }
        
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Инициализация эксперта - МОДИФИЦИРОВАННАЯ                      |
//+------------------------------------------------------------------+
int OnInit() {
    Print("🚀🚀🚀 НАЧАЛО ИНИЦИАЛИЗАЦИИ РОБОТА 🚀🚀🚀");
    Print("📋 НАЗВАНИЕ СОВЕТНИКА: MartingaleVPS_Enhanced v1.61 [LICENSED]");
    Print("📋 АВТОР: TradingBot 2025 - VPS Enhanced + LICENSE");
    Print("📋 ОПИСАНИЕ: VPS Optimized Auto Martingale Robot - LICENSED VERSION");
    
    //+------------------------------------------------------------------+
    //| 🔐 ПЕРВООЧЕРЕДНАЯ ПРОВЕРКА ЛИЦЕНЗИИ                           |
    //+------------------------------------------------------------------+
    Print("🔐 === ЗАПУСК ПРОВЕРКИ ЛИЦЕНЗИИ ===");
    
    // Проверяем лицензию ДО всего остального
    licenseValid = CheckLicense();
    tradingBlocked = !licenseValid;
    
    if(!licenseValid) {
        Print("❌❌❌ КРИТИЧЕСКАЯ ОШИБКА: НЕДЕЙСТВИТЕЛЬНАЯ ЛИЦЕНЗИЯ! ❌❌❌");
        
        Comment("❌ СОВЕТНИК ЗАБЛОКИРОВАН\n" +
                "🔐 ПРИЧИНА: Недействительная лицензия\n" +
                "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                "🔑 ВВЕДЕННЫЙ КЛЮЧ: " + (StringLen(LicenseKey) > 0 ? StringSubstr(LicenseKey, 0, 8) + "..." : "НЕ УКАЗАН") + "\n\n" +
                "💡 КАК ИСПРАВИТЬ:\n" +
                "   1. Получите лицензию в Telegram боте\n" +
                "   2. Скопируйте лицензионный ключ\n" +
                "   3. Вставьте ключ в настройки советника\n" +
                "   4. Перезапустите советника\n\n" +
                "📞 Поддержка: @YourSupportBot\n" +
                "🌐 Бот: " + botURL);
        
        Alert("❌ ДОСТУП ЗАПРЕЩЕН!\n\nНеверная лицензия!\nПолучите лицензию в Telegram боте!");
        
        // СОВЕТНИК НЕ БУДЕТ ТОРГОВАТЬ, НО ОСТАНЕТСЯ ЗАПУЩЕННЫМ для показа предупреждений
        Print("🔐 Советник запущен в режиме ТОЛЬКО ПРОСМОТР (торговля заблокирована)");
    } else {
        Print("✅✅✅ ЛИЦЕНЗИЯ ДЕЙСТВИТЕЛЬНА! ✅✅✅");
        Print("🔐 Ключ: ", StringSubstr(LicenseKey, 0, 8), "...");
        Print("🔐 Торговля РАЗРЕШЕНА!");
        
        Comment("✅ ЛИЦЕНЗИЯ ПОДТВЕРЖДЕНА\n" +
                "📊 СТАТУС: Инициализация...\n" +
                "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                "🔑 КЛЮЧ: " + StringSubstr(LicenseKey, 0, 8) + "...\n" +
                "🤖 РЕЖИМ: VPS Оптимизированный");
    }
    
    //+------------------------------------------------------------------+
    //| ОРИГИНАЛЬНАЯ ЛОГИКА ИНИЦИАЛИЗАЦИИ (БЕЗ ИЗМЕНЕНИЙ)            |
    //+------------------------------------------------------------------+
    
    // Отображение на графике
    tradingSymbol = Symbol();
    robotStartTime = TimeCurrent();
    
    Print("=== VPS УЛУЧШЕННЫЙ МАРТИНГЕЙЛ РОБОТ ЗАПУЩЕН ===");
    Print("🔧 Терминал подключен: ", (TerminalInfoInteger(TERMINAL_CONNECTED) ? "ДА" : "НЕТ"));
    Print("🔧 Автоторговля разрешена: ", (TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "ДА" : "НЕТ"));
    Print("🔧 Счет торговый: ", AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) ? "ДА" : "НЕТ");
    Print("🔧 Баланс: $", DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2));
    Print("🔧 Символ: ", tradingSymbol);
    Print("🔧 Начальный лот: ", DoubleToString(InitialLot, 3));
    Print("🔧 Дистанция стопов: ", BuyStopPips, " пунктов");
    Print("🔧 Take Profit: ", TakeProfitPips, " пунктов");
    
    // Инициализация рабочих переменных
    WorkingUseMA = UseMA;
    
    // Сброс VPS-специфичных переменных
    marketReady = false;
    tickCounter = 0;
    connectionErrors = 0;
    lastTickTime = TimeCurrent();
    
    // Настройка торговых объектов с VPS оптимизацией
    trade.SetExpertMagicNumber(MagicNumber);
    trade.SetMarginMode();
    trade.SetTypeFillingBySymbol(tradingSymbol);
    trade.SetDeviationInPoints(50);
    
    // Расчет стоимости пункта
    CalculatePipValue();
    
    // Показать полную информацию о символе
    ShowSymbolInfo();
    
    // Инициализация определения тренда с обработкой ошибок
    if(WorkingUseMA) {
        Print("📈 Создание MA индикатора...");
        maHandle = iMA(tradingSymbol, PERIOD_CURRENT, TrendPeriod, 0, MODE_SMA, PRICE_CLOSE);
        if(maHandle == INVALID_HANDLE) {
            Print("❌ Ошибка создания MA индикатора - будет использован резервный метод");
            WorkingUseMA = false;
        } else {
            Print("✅ MA индикатор создан успешно");
        }
    } else {
        Print("📊 Используется анализ цен без MA индикатора");
    }
    
    // Инициализация переменных
    currentLot = InitialLot;
    doublingCount = 0;
    sessionActive = false;
    robotStarted = false;
    
    Print("=== VPS НАСТРОЙКИ ===");
    Print("Макс попыток: ", MaxRetries);
    Print("Задержка повтора: ", RetryDelay, " мс");
    Print("Мин тиков: ", MinTicksForStart);
    Print("Задержка запуска: ", startupDelay, " секунд");
    Print("Задержка сессии: ", DelayBetweenSessions, " секунд");
    
    // Проверка существующих позиций
    CheckExistingPositions();
    
    // Запуск VPS-оптимизированной последовательности инициализации
    if(!sessionActive && licenseValid) {
        Print("🔄 VPS Инициализация: УСКОРЕННЫЙ РЕЖИМ!");
        Print("🔄 Ожидание всего ", MinTicksForStart, " тик для запуска!");
        Print("🔄 Максимальная задержка: ", startupDelay, " секунд");
        Print("🔄 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК через 5 секунд если не запустится!");
        lastMarketCheck = TimeCurrent();
    }
    
    Print("✅✅✅ СОВЕТНИК 'MartingaleVPS_Enhanced v1.61 [LICENSED]' УСПЕШНО ЗАПУЩЕН! ✅✅✅");
    
    if(licenseValid) {
        Print("🤖 Робот готов к работе на VPS!");
        
        // Финальное уведомление на график
        Comment("✅ СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
                "📊 СТАТУС: ЗАПУЩЕН И ГОТОВ!\n" +
                "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                "💰 СИМВОЛ: " + tradingSymbol + "\n" +
                "🔧 БАЛАНС: $" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n" +
                "🚀 VPS РЕЖИМ: АКТИВЕН\n" +
                "🔐 ЛИЦЕНЗИЯ: ДЕЙСТВИТЕЛЬНА");
    } else {
        Print("🚫 Робот в режиме ПРОСМОТРА (торговля заблокирована)!");
    }
    
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Деинициализация эксперта - МОДИФИЦИРОВАННАЯ                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
    if(maHandle != INVALID_HANDLE) {
        IndicatorRelease(maHandle);
    }
    
    Print("=== VPS РОБОТ ОСТАНОВЛЕН ===");
    Print("Причина: ", reason);
    Print("Всего ошибок соединения: ", connectionErrors);
    Print("🔐 Последняя проверка лицензии: ", TimeToString(lastLicenseCheck));
    
    // Финальное сообщение на график
    Comment("❌ СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
            "📊 СТАТУС: ОСТАНОВЛЕН\n" +
            "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
            "🛑 ПРИЧИНА: " + IntegerToString(reason) + "\n" +
            "📊 ОШИБОК: " + IntegerToString(connectionErrors) + "\n" +
            "🔐 ЛИЦЕНЗИЯ: " + (licenseValid ? "БЫЛА ДЕЙСТВИТЕЛЬНА" : "НЕДЕЙСТВИТЕЛЬНА"));
}

//+------------------------------------------------------------------+
//| Функция тика эксперта - МОДИФИЦИРОВАННАЯ                       |
//+------------------------------------------------------------------+
void OnTick() {
    //+------------------------------------------------------------------+
    //| 🔐 ПЕРВАЯ ПРОВЕРКА: ЛИЦЕНЗИЯ                                  |
    //+------------------------------------------------------------------+
    
    // Проверяем лицензию каждый тик (быстрая проверка локального статуса)
    if(!IsLicenseValid()) {
        return; // Блокируем весь OnTick если лицензия недействительна
    }
    
    // Периодическая проверка лицензии на сервере
    CheckLicensePeriodically();
    
    // Если лицензия стала недействительной - выходим
    if(tradingBlocked) {
        return;
    }
    
    //+------------------------------------------------------------------+
    //| ОРИГИНАЛЬНАЯ ЛОГИКА OnTick (БЕЗ ИЗМЕНЕНИЙ)                   |
    //+------------------------------------------------------------------+
    
    // БАЗОВАЯ ДИАГНОСТИКА КАЖДОГО ТИКА
    tickCounter++;
    lastTickTime = TimeCurrent();
    
    // Каждые 10 тиков показываем статус
    if(tickCounter % 10 == 0 || tickCounter <= 5) {
        Print("📊 ТИК #", tickCounter, " | Время: ", TimeToString(TimeCurrent()), " | Сессия: ", (sessionActive ? "АКТИВНА" : "НЕТ"));
    }
    
    // ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ЧЕРЕЗ 5 СЕКУНД!
    int secondsFromStart = (int)(TimeCurrent() - robotStartTime);
    if(secondsFromStart >= 5 && !sessionActive && !marketReady) {
        Print("🚨 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК! Прошло ", secondsFromStart, " секунд - запускаем принудительно!");
        ForceStartTrading();
        return;
    }
    
    // Показываем прогресс каждую секунду первые 10 секунд
    if(secondsFromStart <= 10 && secondsFromStart != 0) {
        static int lastSecond = 0;
        if(secondsFromStart != lastSecond) {
            Print("⏰ Прошло ", secondsFromStart, " сек | Готовность: ", (marketReady ? "ДА" : "НЕТ"), " | Сессия: ", (sessionActive ? "ДА" : "НЕТ"));
            lastSecond = secondsFromStart;
        }
    }
    
    // Проверка соединения терминала
    if(!TerminalInfoInteger(TERMINAL_CONNECTED)) {
        connectionErrors++;
        Print("⚠️ Терминал не подключен (Ошибка #", connectionErrors, ")");
        return;
    }
    
    // Проверка готовности рынка для VPS
    if(!CheckMarketReadiness()) {
        return;
    }
    
    // Печать когда рынок становится готов
    static bool wasReady = false;
    if(marketReady && !wasReady) {
        Print("🎉 Рынок готов! Переход к торговой логике...");
        Comment("✅ СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
                "📊 СТАТУС: РЫНОК ГОТОВ!\n" +
                "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                "💰 СИМВОЛ: " + tradingSymbol + "\n" +
                "🎯 СЕССИЯ: " + (sessionActive ? "АКТИВНА" : "ОЖИДАНИЕ") + "\n" +
                "🔢 ТИКОВ: " + IntegerToString(tickCounter) + "\n" +
                "🔐 ЛИЦЕНЗИЯ: ДЕЙСТВИТЕЛЬНА");
        wasReady = true;
    }
    
    // Обновление информации о позициях
    UpdatePositionsInfo();
    
    // Проверка торговых условий
    CheckTradingConditions();
    
    // Проверка глобального Take Profit
    CheckGlobalTakeProfit();
    
    // VPS-оптимизированный автозапуск
    CheckVPSAutoStart();
    
    // Обновление статуса на графике каждые 50 тиков + ДИАГНОСТИКА
    if(tickCounter % 50 == 0) {
        string status = sessionActive ? "ТОРГУЕТ" : (marketReady ? "ОЖИДАНИЕ" : "ПОДГОТОВКА");
        
        // Подсчет позиций и ордеров
        int ourPositions = 0;
        int ourOrders = 0;
        int buyStops = 0;
        int sellStops = 0;
        
        for(int i = 0; i < PositionsTotal(); i++) {
            if(position.SelectByIndex(i)) {
                if(position.Symbol() == tradingSymbol && position.Magic() == MagicNumber) {
                    ourPositions++;
                }
            }
        }
        
        for(int i = 0; i < OrdersTotal(); i++) {
            if(order.SelectByIndex(i)) {
                if(order.Symbol() == tradingSymbol && order.Magic() == MagicNumber) {
                    ourOrders++;
                    if(order.OrderType() == ORDER_TYPE_BUY_STOP) buyStops++;
                    if(order.OrderType() == ORDER_TYPE_SELL_STOP) sellStops++;
                }
            }
        }
        
        Comment("🤖 СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
                "📊 СТАТУС: " + status + "\n" +
                "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                "💰 СИМВОЛ: " + tradingSymbol + "\n" +
                "🔢 ТИКОВ: " + IntegerToString(tickCounter) + "\n" +
                "💵 БАЛАНС: $" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n" +
                "📊 ПОЗИЦИИ: " + IntegerToString(ourPositions) + " | ОРДЕРА: " + IntegerToString(ourOrders) + "\n" +
                "🔥 УДВОЕНИЙ: " + IntegerToString(doublingCount) + "/" + IntegerToString(MaxDoubling) + "\n" +
                "🎯 BUY_STOP: " + IntegerToString(buyStops) + " | SELL_STOP: " + IntegerToString(sellStops) + "\n" +
                "📦 В МАССИВЕ: " + IntegerToString(ArraySize(positions)) + "\n" +
                "🔐 ЛИЦЕНЗИЯ: АКТИВНА | ✅ ПРОВЕРЕНА");
        
        // Периодическая детальная диагностика
        if(tickCounter % 200 == 0 && sessionActive) {
            Print("🔍 === ПЕРИОДИЧЕСКАЯ ДИАГНОСТИКА (ТИК ", tickCounter, ") ===");
            Print("🔍 sessionActive=", sessionActive);
            Print("🔍 doublingCount=", doublingCount);
            Print("🔍 currentLot=", DoubleToString(currentLot, 3));
            Print("🔍 Позиций в терминале=", ourPositions);
            Print("🔍 Ордеров в терминале=", ourOrders);
            Print("🔍 Позиций в массиве=", ArraySize(positions));
            Print("🔍 Buy Stops=", buyStops, " | Sell Stops=", sellStops);
            Print("🔐 Лицензия действительна=", licenseValid);
            Print("🔐 Торговля заблокирована=", tradingBlocked);
            
            if(ourPositions > 1 && ourOrders == 0) {
                Print("🚨 ПРОБЛЕМА: Много позиций но нет ордеров!");
                Print("🚨 Это может быть причиной отсутствия следующих позиций!");
            }
        }
    }
}

//+------------------------------------------------------------------+
//| ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ                   |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Принудительный запуск торговли - АВАРИЙНАЯ ФУНКЦИЯ             |
//+------------------------------------------------------------------+
void ForceStartTrading() {
    Print("🚨🚨🚨 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ТОРГОВЛИ! 🚨🚨🚨");
    
    // Обновление статуса на графике
    Comment("🚨 СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
            "📊 СТАТУС: ПРИНУДИТЕЛЬНЫЙ ЗАПУСК!\n" +
            "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
            "💰 СИМВОЛ: " + tradingSymbol + "\n" +
            "🚨 РЕЖИМ: ЭКСТРЕННЫЙ СТАРТ\n" +
            "🔐 ЛИЦЕНЗИЯ: ПРОВЕРЕНА");
    
    // Принудительно готовим рынок
    marketReady = true;
    robotStarted = true;
    
    // Базовая проверка котировок
    double bid = SymbolInfoDouble(tradingSymbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(tradingSymbol, SYMBOL_ASK);
    
    Print("💰 ПРИНУДИТЕЛЬНЫЕ котировки: Bid=", DoubleToString(bid, Digits()), " Ask=", DoubleToString(ask, Digits()));
    
    if(bid <= 0 || ask <= 0) {
        Print("❌ КРИТИЧЕСКАЯ ОШИБКА: Нет котировок! Bid=", bid, " Ask=", ask);
        Print("🔧 Проверьте:");
        Print("   1. Подключение к интернету");
        Print("   2. Настройки символа BTCUSD");
        Print("   3. Работу торгового сервера");
        return;
    }
    
    // Быстрое определение тренда
    long bidLong = (long)bid;
    ENUM_POSITION_TYPE direction = (bidLong % 2 == 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
    
    Print("🎯 ПРИНУДИТЕЛЬНОЕ направление: ", (direction == POSITION_TYPE_BUY ? "ПОКУПКА" : "ПРОДАЖА"));
    
    // Принудительный запуск сессии
    StartNewSessionFast(direction);
}

//+------------------------------------------------------------------+
//| Быстрый анализ тренда для быстрого старта                      |
//+------------------------------------------------------------------+
ENUM_POSITION_TYPE GetQuickTrend() {
    Print("⚡ БЫСТРЫЙ анализ тренда...");
    
    double currentPrice = SymbolInfoDouble(tradingSymbol, SYMBOL_BID);
    
    // Простейший метод - по последней цифре цены
    long priceLong = (long)currentPrice;
    long lastDigit = priceLong % 10;
    
    if(lastDigit >= 5) {
        Print("📈 БЫСТРЫЙ ТРЕНД: ПОКУПКА (цифра ", lastDigit, ")");
        return POSITION_TYPE_BUY;
    } else {
        Print("📉 БЫСТРЫЙ ТРЕНД: ПРОДАЖА (цифра ", lastDigit, ")");
        return POSITION_TYPE_SELL;
    }
}

//+------------------------------------------------------------------+
//| Быстрый старт сессии - МИНИМАЛЬНЫЕ ПРОВЕРКИ                    |
//+------------------------------------------------------------------+
void StartNewSessionFast(ENUM_POSITION_TYPE startDirection) {
    Print("🚀🚀🚀 БЫСТРЫЙ СТАРТ СЕССИИ! 🚀🚀🚀");
    Print("Направление: ", (startDirection == POSITION_TYPE_BUY ? "ПОКУПКА" : "ПРОДАЖА"));
    
    // Минимальная инициализация
    currentLot = InitialLot;
    doublingCount = 0;
    sessionStartPrice = SymbolInfoDouble(tradingSymbol, SYMBOL_BID);
    sessionActive = true;
    
    Print("💰 Цена старта: ", DoubleToString(sessionStartPrice, Digits()));
    
    // Быстрый расчет уровней
    if(startDirection == POSITION_TYPE_BUY) {
        sessionBuyLevel = sessionStartPrice;
        sessionSellLevel = sessionBuyLevel - BuyStopPips * Point();
    } else {
        sessionSellLevel = sessionStartPrice;
        sessionBuyLevel = sessionSellLevel + BuyStopPips * Point();
    }
    
    sessionTP = sessionBuyLevel + TakeProfitPips * Point();
    sessionSL = sessionSellLevel - TakeProfitPips * Point();
    
    Print("📍 БЫСТРЫЕ уровни:");
    Print("   SELL: ", DoubleToString(sessionSellLevel, Digits()));
    Print("   BUY: ", DoubleToString(sessionBuyLevel, Digits()));
    Print("   TP: ", DoubleToString(sessionTP, Digits()));
    Print("   SL: ", DoubleToString(sessionSL, Digits()));
    
    ArrayResize(positions, 0);
    
    // НЕМЕДЛЕННОЕ открытие позиции
    bool success = false;
    if(startDirection == POSITION_TYPE_BUY) {
        success = OpenBuyPositionFast();
    } else {
        success = OpenSellPositionFast();
    }
    
    if(success) {
        Print("✅✅✅ СЕССИЯ ЗАПУЩЕНА УСПЕШНО! ✅✅✅");
        Comment("🚀 СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
                "📊 СТАТУС: СЕССИЯ АКТИВНА!\n" +
                "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                "💰 СИМВОЛ: " + tradingSymbol + "\n" +
                "🎯 НАПРАВЛЕНИЕ: " + (startDirection == POSITION_TYPE_BUY ? "ПОКУПКА" : "ПРОДАЖА") + "\n" +
                "💵 ЛОТ: " + DoubleToString(currentLot, 3) + "\n" +
                "🔐 ЛИЦЕНЗИЯ: АКТИВНА");
    } else {
        Print("❌❌❌ ОШИБКА ЗАПУСКА СЕССИИ! ❌❌❌");
        Comment("❌ СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
                "📊 СТАТУС: ОШИБКА ЗАПУСКА!\n" +
                "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
                "💰 СИМВОЛ: " + tradingSymbol + "\n" +
                "🚨 ПРОБЛЕМА: Не удалось открыть позицию\n" +
                "🔐 ЛИЦЕНЗИЯ: АКТИВНА");
        sessionActive = false;
    }
}

//+------------------------------------------------------------------+
//| Быстрое открытие BUY позиции                                   |
//+------------------------------------------------------------------+
bool OpenBuyPositionFast() {
    Print("💰 БЫСТРОЕ открытие BUY позиции...");
    
    double ask = SymbolInfoDouble(tradingSymbol, SYMBOL_ASK);
    
    Print("💱 ASK цена: ", DoubleToString(ask, Digits()));
    Print("💱 Лот: ", DoubleToString(currentLot, 3));
    Print("💱 SL: ", DoubleToString(sessionSL, Digits()));
    Print("💱 TP: ", DoubleToString(sessionTP, Digits()));
    
    if(trade.Buy(currentLot, tradingSymbol, ask, sessionSL, sessionTP, CommentPrefix + "_FASTBUY_0")) {
        Print("✅ БЫСТРАЯ BUY позиция открыта!");
        
        // Быстрая установка Sell Stop
        double nextLot = currentLot * 2;
        if(trade.SellStop(nextLot, sessionSellLevel, tradingSymbol, sessionTP, sessionSL, ORDER_TIME_GTC, 0, CommentPrefix + "_SELLSTOP_1")) {
            Print("✅ Sell Stop установлен: ", DoubleToString(nextLot, 3), " лот");
        } else {
            Print("⚠️ Sell Stop не установлен: ", trade.ResultRetcode());
        }
        
        return true;
    } else {
        Print("❌ Ошибка открытия BUY: ", trade.ResultRetcode());
        return false;
    }
}

//+------------------------------------------------------------------+
//| Быстрое открытие SELL позиции                                  |
//+------------------------------------------------------------------+
bool OpenSellPositionFast() {
    Print("💰 БЫСТРОЕ открытие SELL позиции...");
    
    double bid = SymbolInfoDouble(tradingSymbol, SYMBOL_BID);
    
    Print("💱 BID цена: ", DoubleToString(bid, Digits()));
    Print("💱 Лот: ", DoubleToString(currentLot, 3));
    Print("💱 SL: ", DoubleToString(sessionTP, Digits()));
    Print("💱 TP: ", DoubleToString(sessionSL, Digits()));
    
    if(trade.Sell(currentLot, tradingSymbol, bid, sessionTP, sessionSL, CommentPrefix + "_FASTSELL_0")) {
        Print("✅ БЫСТРАЯ SELL позиция открыта!");
        
        // Быстрая установка Buy Stop
        double nextLot = currentLot * 2;
        if(trade.BuyStop(nextLot, sessionBuyLevel, tradingSymbol, sessionSL, sessionTP, ORDER_TIME_GTC, 0, CommentPrefix + "_BUYSTOP_1")) {
            Print("✅ Buy Stop установлен: ", DoubleToString(nextLot, 3), " лот");
        } else {
            Print("⚠️ Buy Stop не установлен: ", trade.ResultRetcode());
        }
        
        return true;
    } else {
        Print("❌ Ошибка открытия SELL: ", trade.ResultRetcode());
        return false;
    }
}

//+------------------------------------------------------------------+
//| Проверка готовности рынка для VPS операций - БЫСТРАЯ ВЕРСИЯ    |
//+------------------------------------------------------------------+
bool CheckMarketReadiness() {
    // ПРИНУДИТЕЛЬНЫЙ ЗАПУСК ЧЕРЕЗ 5 СЕКУНД!
    if(TimeCurrent() - robotStartTime >= 5) {
        if(!marketReady) {
            Print("🚀 ПРИНУДИТЕЛЬНЫЙ ЗАПУСК! 5 секунд прошло - запускаем торговлю!");
            marketReady = true;
        }
        return true;
    }
    
    // Минимальные проверки для быстрого старта
    if(tickCounter < MinTicksForStart) {
        return false;
    }
    
    // Только базовая проверка котировок
    double bid = SymbolInfoDouble(tradingSymbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(tradingSymbol, SYMBOL_ASK);
    
    if(bid > 0 && ask > 0 && ask > bid) {
        if(!marketReady) {
            double spread = (ask - bid) / Point();
            Print("✅ БЫСТРЫЙ СТАРТ! Bid=", DoubleToString(bid, Digits()), " Ask=", DoubleToString(ask, Digits()), " Спред=", DoubleToString(spread, 1));
            marketReady = true;
        }
        return true;
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| VPS-оптимизированная проверка автозапуска - БЫСТРАЯ ВЕРСИЯ     |
//+------------------------------------------------------------------+
void CheckVPSAutoStart() {
    // БЫСТРАЯ ПРОВЕРКА - минимум условий
    if(!marketReady || sessionActive) return;
    
    // Быстрая активация робота
    if(!robotStarted) {
        robotStarted = true;
        lastSessionEnd = TimeCurrent() - DelayBetweenSessions;
        Print("🚀 БЫСТРАЯ АКТИВАЦИЯ! Робот готов к торговле!");
    }
    
    // Минимальная задержка между сессиями
    if(TimeCurrent() - lastSessionEnd < DelayBetweenSessions) return;
    
    Print("🎯 БЫСТРЫЙ АНАЛИЗ ТРЕНДА...");
    
    // Простой и быстрый анализ тренда
    ENUM_POSITION_TYPE trendDirection = GetQuickTrend();
    
    Print("🚀 НЕМЕДЛЕННЫЙ СТАРТ! Направление: ", (trendDirection == POSITION_TYPE_BUY ? "ПОКУПКА" : "ПРОДАЖА"));
    
    // Немедленный запуск сессии
    StartNewSessionFast(trendDirection);
}

//+------------------------------------------------------------------+
//| Проверка торговых условий                                       |
//+------------------------------------------------------------------+
void CheckTradingConditions() {
    if(!sessionActive || !marketReady) return;
    
    CheckExecutedOrders();
}

//+------------------------------------------------------------------+
//| Проверка исполненных ордеров                                   |
//+------------------------------------------------------------------+
void CheckExecutedOrders() {
    static int lastPositionCount = -1;
    static int lastOrderCount = -1;
    int currentPositionCount = 0;
    int currentOrderCount = 0;
    
    // Подсчитываем наши позиции и ордера
    for(int i = 0; i < PositionsTotal(); i++) {
        if(position.SelectByIndex(i)) {
            if(position.Symbol() == tradingSymbol && position.Magic() == MagicNumber) {
                currentPositionCount++;
            }
        }
    }
    
    for(int i = 0; i < OrdersTotal(); i++) {
        if(order.SelectByIndex(i)) {
            if(order.Symbol() == tradingSymbol && order.Magic() == MagicNumber) {
                currentOrderCount++;
            }
        }
    }
    
    // Если количество изменилось - показываем детали
    if(lastPositionCount != -1 && (currentPositionCount != lastPositionCount || currentOrderCount != lastOrderCount)) {
        Print("🔄 === ИЗМЕНЕНИЕ В ТЕРМИНАЛЕ ===");
        Print("🔄 Позиции: Было=", lastPositionCount, " Стало=", currentPositionCount);
        Print("🔄 Ордера: Было=", lastOrderCount, " Стало=", currentOrderCount);
        Print("🔄 Позиций в нашем массиве: ", ArraySize(positions));
        
        // Показываем все наши позиции
        Print("🔄 === ВСЕ НАШИ ПОЗИЦИИ В ТЕРМИНАЛЕ ===");
        for(int i = 0; i < PositionsTotal(); i++) {
            if(position.SelectByIndex(i)) {
                if(position.Symbol() == tradingSymbol && position.Magic() == MagicNumber) {
                    Print("🔄 Позиция: ", position.Ticket(), 
                          " | ", (position.PositionType() == POSITION_TYPE_BUY ? "BUY" : "SELL"),
                          " | ", DoubleToString(position.Volume(), 3),
                          " | ", DoubleToString(position.PriceOpen(), Digits()));
                }
            }
        }
        
        // Показываем все наши ордера
        Print("🔄 === ВСЕ НАШИ ОРДЕРА В ТЕРМИНАЛЕ ===");
        for(int i = 0; i < OrdersTotal(); i++) {
            if(order.SelectByIndex(i)) {
                if(order.Symbol() == tradingSymbol && order.Magic() == MagicNumber) {
                    Print("🔄 Ордер: ", order.Ticket(), 
                          " | ", (order.OrderType() == ORDER_TYPE_BUY_STOP ? "BUY_STOP" : 
                                 order.OrderType() == ORDER_TYPE_SELL_STOP ? "SELL_STOP" : "ДРУГОЙ"),
                          " | ", DoubleToString(order.VolumeCurrent(), 3),
                          " | ", DoubleToString(order.PriceOpen(), Digits()));
                }
            }
        }
    }
    
    lastPositionCount = currentPositionCount;
    lastOrderCount = currentOrderCount;
    
    // Проверяем новые позиции (основная логика)
    for(int i = 0; i < PositionsTotal(); i++) {
        if(position.SelectByIndex(i)) {
            if(position.Symbol() == tradingSymbol && position.Magic() == MagicNumber) {
                bool found = false;
                for(int j = 0; j < ArraySize(positions); j++) {
                    if(positions[j].ticket == position.Ticket()) {
                        found = true;
                        break;
                    }
                }
                
                if(!found) {
                    Print("🆕 === ОБНАРУЖЕНА НОВАЯ ПОЗИЦИЯ! ===");
                    Print("🆕 Ticket: ", position.Ticket());
                    Print("🆕 Тип: ", (position.PositionType() == POSITION_TYPE_BUY ? "BUY" : "SELL"));
                    Print("🆕 Лот: ", DoubleToString(position.Volume(), 3));
                    Print("🆕 Цена: ", DoubleToString(position.PriceOpen(), Digits()));
                    Print("🆕 Время: ", TimeToString(position.Time()));
                    Print("🆕 Размер массива ДО обработки: ", ArraySize(positions));
                    
                    ProcessNewPositionSafe();
                    
                    Print("🆕 Размер массива ПОСЛЕ обработки: ", ArraySize(positions));
                    Print("🆕 === КОНЕЦ ОБРАБОТКИ НОВОЙ ПОЗИЦИИ ===");
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Обработка новой позиции с VPS безопасностью                    |
//+------------------------------------------------------------------+
void ProcessNewPositionSafe() {
    Print("🆕 ============ ОБРАБОТКА НОВОЙ ПОЗИЦИИ ============");
    Print("🆕 Тип: ", (position.PositionType() == POSITION_TYPE_BUY ? "ПОКУПКА" : "ПРОДАЖА"));
    Print("🆕 Лот: ", DoubleToString(position.Volume(), 3));
    Print("🆕 Цена: ", DoubleToString(position.PriceOpen(), Digits()));
    Print("🆕 Ticket: ", position.Ticket());
    Print("🆕 Время: ", TimeToString(position.Time()));
    
    // КРИТИЧЕСКАЯ ДИАГНОСТИКА МАССИВА ПОЗИЦИЙ
    Print("🔍 === СОСТОЯНИЕ МАССИВА ПОЗИЦИЙ ДО ===");
    Print("🔍 Размер массива: ", ArraySize(positions));
    for(int k = 0; k < ArraySize(positions); k++) {
        Print("🔍 Позиция #", k, ": Ticket=", positions[k].ticket, " | Тип=", positions[k].type, " | Лот=", DoubleToString(positions[k].lots, 3));
    }
    
    bool isFirstPosition = (ArraySize(positions) == 0);
    
    Print("🔍 === ЛОГИКА ОПРЕДЕЛЕНИЯ ===");
    Print("🔍 isFirstPosition=", isFirstPosition);
    Print("🔍 doublingCount ДО=", doublingCount);
    Print("🔍 currentLot ДО=", DoubleToString(currentLot, 3));
    Print("🔍 sessionActive=", sessionActive);
    
    // ЛОГИКА ДЛЯ BUY ПОЗИЦИЙ
    if(position.PositionType() == POSITION_TYPE_BUY) {
        Print("📈 === ОБРАБОТКА BUY ПОЗИЦИИ ===");
        
        if(!isFirstPosition) {
            Print("🔥 ЭТО НЕ ПЕРВАЯ ПОЗИЦИЯ! Увеличиваем счетчики...");
            doublingCount++;
            currentLot = InitialLot * MathPow(2, doublingCount);
            Print("🔥 НОВЫЕ ЗНАЧЕНИЯ: doublingCount=", doublingCount, " | currentLot=", DoubleToString(currentLot, 3));
            
            // КРИТИЧЕСКАЯ ПРОВЕРКА ЛИМИТОВ
            Print("🔍 Проверка лимитов: doublingCount=", doublingCount, " | MaxDoubling=", MaxDoubling);
            Print("🔍 Проверка лота: currentLot=", DoubleToString(currentLot, 3), " | MaxLotSize=", DoubleToString(MaxLotSize, 3));
            
        } else {
            Print("📝 ЭТО ПЕРВАЯ BUY ПОЗИЦИЯ В СЕССИИ");
        }
        
        // Установка TP/SL с повторами
        Print("🎯 Установка TP/SL для BUY...");
        bool tpslResult = ModifyPositionSafe(position.Ticket(), sessionSL, sessionTP);
        Print("🎯 Результат TP/SL: ", (tpslResult ? "УСПЕХ" : "ОШИБКА"));
        
        if(!isFirstPosition) {
            Print("🚀 === ПОПЫТКА УСТАНОВКИ СЛЕДУЮЩЕГО SELL STOP ===");
            Print("🚀 Текущие уровни сессии:");
            Print("🚀 sessionSellLevel=", DoubleToString(sessionSellLevel, Digits()));
            Print("🚀 sessionBuyLevel=", DoubleToString(sessionBuyLevel, Digits()));
            Print("🚀 sessionTP=", DoubleToString(sessionTP, Digits()));
            Print("🚀 sessionSL=", DoubleToString(sessionSL, Digits()));
            
            SetupNextSellStopSafe();
        } else {
            Print("ℹ️ Первая позиция - стоп уже должен быть установлен при открытии");
        }
        
    // ЛОГИКА ДЛЯ SELL ПОЗИЦИЙ  
    } else if(position.PositionType() == POSITION_TYPE_SELL) {
        Print("📉 === ОБРАБОТКА SELL ПОЗИЦИИ ===");
        
        if(!isFirstPosition) {
            Print("🔥 ЭТО НЕ ПЕРВАЯ ПОЗИЦИЯ! Увеличиваем счетчики...");
            doublingCount++;
            currentLot = InitialLot * MathPow(2, doublingCount);
            Print("🔥 НОВЫЕ ЗНАЧЕНИЯ: doublingCount=", doublingCount, " | currentLot=", DoubleToString(currentLot, 3));
            
            // КРИТИЧЕСКАЯ ПРОВЕРКА ЛИМИТОВ
            Print("🔍 Проверка лимитов: doublingCount=", doublingCount, " | MaxDoubling=", MaxDoubling);
            Print("🔍 Проверка лота: currentLot=", DoubleToString(currentLot, 3), " | MaxLotSize=", DoubleToString(MaxLotSize, 3));
            
        } else {
            Print("📝 ЭТО ПЕРВАЯ SELL ПОЗИЦИЯ В СЕССИИ");
        }
        
        // Установка TP/SL с повторами
        Print("🎯 Установка TP/SL для SELL...");
        bool tpslResult = ModifyPositionSafe(position.Ticket(), sessionTP, sessionSL);
        Print("🎯 Результат TP/SL: ", (tpslResult ? "УСПЕХ" : "ОШИБКА"));
        
        if(!isFirstPosition) {
            Print("🚀 === ПОПЫТКА УСТАНОВКИ СЛЕДУЮЩЕГО BUY STOP ===");
            Print("🚀 Текущие уровни сессии:");
            Print("🚀 sessionSellLevel=", DoubleToString(sessionSellLevel, Digits()));
            Print("🚀 sessionBuyLevel=", DoubleToString(sessionBuyLevel, Digits()));
            Print("🚀 sessionTP=", DoubleToString(sessionTP, Digits()));
            Print("🚀 sessionSL=", DoubleToString(sessionSL, Digits()));
            
            SetupNextBuyStopSafe();
        } else {
            Print("ℹ️ Первая позиция - стоп уже должен быть установлен при открытии");
        }
    }
    
    // ДОБАВЛЕНИЕ В МАССИВ (КРИТИЧЕСКИЙ МОМЕНТ!)
    Print("📊 === ДОБАВЛЕНИЕ В МАССИВ ===");
    Print("📊 Размер массива ДО добавления: ", ArraySize(positions));
    AddPositionToArray();
    Print("📊 Размер массива ПОСЛЕ добавления: ", ArraySize(positions));
    
    // ФИНАЛЬНАЯ ДИАГНОСТИКА
    Print("🔍 === СОСТОЯНИЕ ПОСЛЕ ОБРАБОТКИ ===");
    Print("🔍 doublingCount=", doublingCount);
    Print("🔍 currentLot=", DoubleToString(currentLot, 3));
    Print("🔍 Позиций в массиве=", ArraySize(positions));
    
    // ПРОВЕРКА ВСЕХ ОРДЕРОВ В ТЕРМИНАЛЕ
    Print("📋 === ТЕКУЩИЕ ОРДЕРА В ТЕРМИНАЛЕ ===");
    int totalOrders = OrdersTotal();
    int ourOrders = 0;
    
    for(int i = 0; i < totalOrders; i++) {
        if(order.SelectByIndex(i)) {
            if(order.Symbol() == tradingSymbol && order.Magic() == MagicNumber) {
                ourOrders++;
                Print("📋 Ордер #", ourOrders, ": ", 
                      (order.OrderType() == ORDER_TYPE_BUY_STOP ? "BUY_STOP" : 
                       order.OrderType() == ORDER_TYPE_SELL_STOP ? "SELL_STOP" : "ДРУГОЙ"),
                      " | Лот: ", DoubleToString(order.VolumeCurrent(), 3),
                      " | Цена: ", DoubleToString(order.PriceOpen(), Digits()),
                      " | Ticket: ", order.Ticket());
            }
        }
    }
    
    Print("📋 Всего наших ордеров: ", ourOrders, " из ", totalOrders);
    Print("🆕 ============ КОНЕЦ ОБРАБОТКИ ПОЗИЦИИ ============");
}

//+------------------------------------------------------------------+
//| Безопасное изменение позиции                                   |
//+------------------------------------------------------------------+
bool ModifyPositionSafe(ulong ticket, double sl, double tp) {
    for(int retry = 0; retry < MaxRetries; retry++) {
        if(trade.PositionModify(ticket, sl, tp)) {
            Print("✅ VPS Позиция изменена: TP=", DoubleToString(tp, Digits()), " SL=", DoubleToString(sl, Digits()));
            return true;
        } else {
            Print("❌ Изменение позиции попытка ", retry + 1, " неудачна: ", trade.ResultRetcode());
            if(retry < MaxRetries - 1) Sleep(RetryDelay);
        }
    }
    return false;
}

//+------------------------------------------------------------------+
//| Безопасная установка следующего Buy Stop                       |
//+------------------------------------------------------------------+
void SetupNextBuyStopSafe() {
    Print("🔍 ==================== УСТАНОВКА BUY STOP ====================");
    Print("🔍 ВХОДНЫЕ ПАРАМЕТРЫ:");
    Print("🔍   doublingCount=", doublingCount);
    Print("🔍   MaxDoubling=", MaxDoubling);
    Print("🔍   currentLot=", DoubleToString(currentLot, 3));
    Print("🔍   sessionActive=", sessionActive);
    
    // ПРОВЕРКА 1: Лимит удвоений
    if(doublingCount >= MaxDoubling) {
        Print("❌ СТОП: Достигнут максимум удвоений (", doublingCount, "/", MaxDoubling, ")");
        return;
    }
    
    // ПРОВЕРКА 2: Существующие ордера
    Print("🔍 Проверка существующих Buy Stop ордеров...");
    bool orderExists = CheckOrderExists(ORDER_TYPE_BUY_STOP);
    Print("🔍 Buy Stop уже существует: ", (orderExists ? "ДА" : "НЕТ"));
    
    if(orderExists) {
        Print("⚠️ СТОП: Buy Stop уже установлен");
        return;
    }
    
    // ПРОВЕРКА 3: Валидность уровней сессии
    Print("🔍 ПРОВЕРКА УРОВНЕЙ СЕССИИ:");
    Print("🔍   sessionBuyLevel=", DoubleToString(sessionBuyLevel, Digits()));
    Print("🔍   sessionSellLevel=", DoubleToString(sessionSellLevel, Digits()));
    Print("🔍   sessionTP=", DoubleToString(sessionTP, Digits()));
    Print("🔍   sessionSL=", DoubleToString(sessionSL, Digits()));
    
    if(sessionBuyLevel <= 0 || sessionSL <= 0 || sessionTP <= 0) {
        Print("❌ КРИТИЧЕСКАЯ ОШИБКА: Неверные уровни сессии!");
        Print("❌   sessionBuyLevel=", sessionBuyLevel);
        Print("❌   sessionSL=", sessionSL);
        Print("❌   sessionTP=", sessionTP);
        return;
    }
    
    // ПРОВЕРКА 4: Расчет следующего лота
    double nextLot = currentLot * 2;
    double limitedLot = MathMin(nextLot, MaxLotSize);
    
    Print("🔍 РАСЧЕТ ЛОТА:");
    Print("🔍   currentLot * 2 = ", DoubleToString(nextLot, 3));
    Print("🔍   MaxLotSize = ", DoubleToString(MaxLotSize, 3));
    Print("🔍   Финальный лот = ", DoubleToString(limitedLot, 3));
    
    if(limitedLot != nextLot) {
        Print("⚠️ ВНИМАНИЕ: Лот ограничен максимумом (", DoubleToString(nextLot, 3), " → ", DoubleToString(limitedLot, 3), ")");
    }
    
    // ПРОВЕРКА 5: Минимальные требования брокера
    double minLot = SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_MAX);
    double stepLot = SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_STEP);
    
    Print("🔍 ТРЕБОВАНИЯ БРОКЕРА:");
    Print("🔍   Min Lot: ", DoubleToString(minLot, 3));
    Print("🔍   Max Lot: ", DoubleToString(maxLot, 3));
    Print("🔍   Step Lot: ", DoubleToString(stepLot, 3));
    
    if(limitedLot < minLot || limitedLot > maxLot) {
        Print("❌ ОШИБКА: Лот вне допустимого диапазона!");
        return;
    }
    
    // ФИНАЛЬНАЯ ПОПЫТКА УСТАНОВКИ
    Print("🚀 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Запуск установки Buy Stop...");
    Print("🚀 Параметры:");
    Print("🚀   Лот: ", DoubleToString(limitedLot, 3));
    Print("🚀   Цена: ", DoubleToString(sessionBuyLevel, Digits()));
    Print("🚀   SL: ", DoubleToString(sessionSL, Digits()));
    Print("🚀   TP: ", DoubleToString(sessionTP, Digits()));
    
    bool result = SetBuyStopSafe(limitedLot);
    
    Print("🚀 РЕЗУЛЬТАТ УСТАНОВКИ BUY STOP: ", (result ? "✅ УСПЕХ" : "❌ НЕУДАЧА"));
    Print("🔍 ==================== КОНЕЦ УСТАНОВКИ BUY STOP ====================");
}

//+------------------------------------------------------------------+
//| Безопасная установка следующего Sell Stop                      |
//+------------------------------------------------------------------+
void SetupNextSellStopSafe() {
    Print("🔍 ==================== УСТАНОВКА SELL STOP ====================");
    Print("🔍 ВХОДНЫЕ ПАРАМЕТРЫ:");
    Print("🔍   doublingCount=", doublingCount);
    Print("🔍   MaxDoubling=", MaxDoubling);
    Print("🔍   currentLot=", DoubleToString(currentLot, 3));
    Print("🔍   sessionActive=", sessionActive);
    
    // ПРОВЕРКА 1: Лимит удвоений
    if(doublingCount >= MaxDoubling) {
        Print("❌ СТОП: Достигнут максимум удвоений (", doublingCount, "/", MaxDoubling, ")");
        return;
    }
    
    // ПРОВЕРКА 2: Существующие ордера
    Print("🔍 Проверка существующих Sell Stop ордеров...");
    bool orderExists = CheckOrderExists(ORDER_TYPE_SELL_STOP);
    Print("🔍 Sell Stop уже существует: ", (orderExists ? "ДА" : "НЕТ"));
    
    if(orderExists) {
        Print("⚠️ СТОП: Sell Stop уже установлен");
        return;
    }
    
    // ПРОВЕРКА 3: Валидность уровней сессии
    Print("🔍 ПРОВЕРКА УРОВНЕЙ СЕССИИ:");
    Print("🔍   sessionSellLevel=", DoubleToString(sessionSellLevel, Digits()));
    Print("🔍   sessionBuyLevel=", DoubleToString(sessionBuyLevel, Digits()));
    Print("🔍   sessionTP=", DoubleToString(sessionTP, Digits()));
    Print("🔍   sessionSL=", DoubleToString(sessionSL, Digits()));
    
    if(sessionSellLevel <= 0 || sessionSL <= 0 || sessionTP <= 0) {
        Print("❌ КРИТИЧЕСКАЯ ОШИБКА: Неверные уровни сессии!");
        Print("❌   sessionSellLevel=", sessionSellLevel);
        Print("❌   sessionSL=", sessionSL);
        Print("❌   sessionTP=", sessionTP);
        return;
    }
    
    // ПРОВЕРКА 4: Расчет следующего лота
    double nextLot = currentLot * 2;
    double limitedLot = MathMin(nextLot, MaxLotSize);
    
    Print("🔍 РАСЧЕТ ЛОТА:");
    Print("🔍   currentLot * 2 = ", DoubleToString(nextLot, 3));
    Print("🔍   MaxLotSize = ", DoubleToString(MaxLotSize, 3));
    Print("🔍   Финальный лот = ", DoubleToString(limitedLot, 3));
    
    if(limitedLot != nextLot) {
        Print("⚠️ ВНИМАНИЕ: Лот ограничен максимумом (", DoubleToString(nextLot, 3), " → ", DoubleToString(limitedLot, 3), ")");
    }
    
    // ПРОВЕРКА 5: Минимальные требования брокера
    double minLot = SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_MAX);
    double stepLot = SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_STEP);
    
    Print("🔍 ТРЕБОВАНИЯ БРОКЕРА:");
    Print("🔍   Min Lot: ", DoubleToString(minLot, 3));
    Print("🔍   Max Lot: ", DoubleToString(maxLot, 3));
    Print("🔍   Step Lot: ", DoubleToString(stepLot, 3));
    
    if(limitedLot < minLot || limitedLot > maxLot) {
        Print("❌ ОШИБКА: Лот вне допустимого диапазона!");
        return;
    }
    
    // ФИНАЛЬНАЯ ПОПЫТКА УСТАНОВКИ
    Print("🚀 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Запуск установки Sell Stop...");
    Print("🚀 Параметры:");
    Print("🚀   Лот: ", DoubleToString(limitedLot, 3));
    Print("🚀   Цена: ", DoubleToString(sessionSellLevel, Digits()));
    Print("🚀   SL: ", DoubleToString(sessionTP, Digits()));
    Print("🚀   TP: ", DoubleToString(sessionSL, Digits()));
    
    bool result = SetSellStopSafe(limitedLot);
    
    Print("🚀 РЕЗУЛЬТАТ УСТАНОВКИ SELL STOP: ", (result ? "✅ УСПЕХ" : "❌ НЕУДАЧА"));
    Print("🔍 ==================== КОНЕЦ УСТАНОВКИ SELL STOP ====================");
}

//+------------------------------------------------------------------+
//| Безопасная установка Buy Stop                                  |
//+------------------------------------------------------------------+
bool SetBuyStopSafe(double lotSize) {
    Print("💰 === УСТАНОВКА BUY STOP ===");
    Print("💰 Лот: ", DoubleToString(lotSize, 3));
    Print("💰 Цена: ", DoubleToString(sessionBuyLevel, Digits()));
    Print("💰 SL: ", DoubleToString(sessionSL, Digits()));
    Print("💰 TP: ", DoubleToString(sessionTP, Digits()));
    
    // Проверки перед установкой
    double currentPrice = SymbolInfoDouble(tradingSymbol, SYMBOL_BID);
    Print("💰 Текущая цена: ", DoubleToString(currentPrice, Digits()));
    
    if(sessionBuyLevel <= currentPrice) {
        Print("❌ ОШИБКА: Buy Stop цена (", DoubleToString(sessionBuyLevel, Digits()), 
              ") должна быть выше текущей цены (", DoubleToString(currentPrice, Digits()), ")");
        return false;
    }
    
    // Проверка минимального расстояния
    double minStopsLevel = SymbolInfoInteger(tradingSymbol, SYMBOL_TRADE_STOPS_LEVEL) * Point();
    double distance = sessionBuyLevel - currentPrice;
    
    Print("💰 Минимальное расстояние: ", DoubleToString(minStopsLevel, Digits()));
    Print("💰 Наше расстояние: ", DoubleToString(distance, Digits()));
    
    if(distance < minStopsLevel && minStopsLevel > 0) {
        Print("❌ ОШИБКА: Слишком близко к цене. Требуется: ", DoubleToString(minStopsLevel, Digits()));
        return false;
    }
    
    for(int retry = 0; retry < MaxRetries; retry++) {
        Print("💰 Попытка установки Buy Stop #", retry + 1);
        
        if(trade.BuyStop(lotSize, sessionBuyLevel, tradingSymbol, sessionSL, sessionTP, ORDER_TIME_GTC, 0, CommentPrefix + "_BUYSTOP_" + IntegerToString(doublingCount + 1))) {
            Print("✅ VPS Buy Stop установлен УСПЕШНО! Лот: ", DoubleToString(lotSize, 3));
            Print("✅ Ticket: ", trade.ResultOrder());
            return true;
        } else {
            Print("❌ Buy Stop попытка ", retry + 1, " неудачна. Код ошибки: ", trade.ResultRetcode());
            Print("❌ Описание ошибки: ", trade.ResultRetcodeDescription());
            
            // Дополнительная диагностика
            if(trade.ResultRetcode() == TRADE_RETCODE_INVALID_STOPS) {
                Print("❌ Неверные стопы! Проверьте расчеты TP/SL");
            } else if(trade.ResultRetcode() == TRADE_RETCODE_INVALID_PRICE) {
                Print("❌ Неверная цена! Цена Buy Stop: ", DoubleToString(sessionBuyLevel, Digits()));
            } else if(trade.ResultRetcode() == TRADE_RETCODE_INVALID_VOLUME) {
                Print("❌ Неверный объем! Лот: ", DoubleToString(lotSize, 3));
            }
            
            if(retry < MaxRetries - 1) {
                Print("⏳ Ожидание ", RetryDelay, " мс перед повтором...");
                Sleep(RetryDelay);
                // Обновляем цены
                currentPrice = SymbolInfoDouble(tradingSymbol, SYMBOL_BID);
            }
        }
    }
    
    Print("❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось установить Buy Stop после ", MaxRetries, " попыток!");
    return false;
}

//+------------------------------------------------------------------+
//| Безопасная установка Sell Stop                                 |
//+------------------------------------------------------------------+
bool SetSellStopSafe(double lotSize) {
    Print("💰 === УСТАНОВКА SELL STOP ===");
    Print("💰 Лот: ", DoubleToString(lotSize, 3));
    Print("💰 Цена: ", DoubleToString(sessionSellLevel, Digits()));
    Print("💰 SL: ", DoubleToString(sessionTP, Digits()));
    Print("💰 TP: ", DoubleToString(sessionSL, Digits()));
    
    // Проверки перед установкой
    double currentPrice = SymbolInfoDouble(tradingSymbol, SYMBOL_ASK);
    Print("💰 Текущая цена: ", DoubleToString(currentPrice, Digits()));
    
    if(sessionSellLevel >= currentPrice) {
        Print("❌ ОШИБКА: Sell Stop цена (", DoubleToString(sessionSellLevel, Digits()), 
              ") должна быть ниже текущей цены (", DoubleToString(currentPrice, Digits()), ")");
        return false;
    }
    
    // Проверка минимального расстояния
    double minStopsLevel = SymbolInfoInteger(tradingSymbol, SYMBOL_TRADE_STOPS_LEVEL) * Point();
    double distance = currentPrice - sessionSellLevel;
    
    Print("💰 Минимальное расстояние: ", DoubleToString(minStopsLevel, Digits()));
    Print("💰 Наше расстояние: ", DoubleToString(distance, Digits()));
    
    if(distance < minStopsLevel && minStopsLevel > 0) {
        Print("❌ ОШИБКА: Слишком близко к цене. Требуется: ", DoubleToString(minStopsLevel, Digits()));
        return false;
    }
    
    for(int retry = 0; retry < MaxRetries; retry++) {
        Print("💰 Попытка установки Sell Stop #", retry + 1);
        
        if(trade.SellStop(lotSize, sessionSellLevel, tradingSymbol, sessionTP, sessionSL, ORDER_TIME_GTC, 0, CommentPrefix + "_SELLSTOP_" + IntegerToString(doublingCount + 1))) {
            Print("✅ VPS Sell Stop установлен УСПЕШНО! Лот: ", DoubleToString(lotSize, 3));
            Print("✅ Ticket: ", trade.ResultOrder());
            return true;
        } else {
            Print("❌ Sell Stop попытка ", retry + 1, " неудачна. Код ошибки: ", trade.ResultRetcode());
            Print("❌ Описание ошибки: ", trade.ResultRetcodeDescription());
            
            // Дополнительная диагностика
            if(trade.ResultRetcode() == TRADE_RETCODE_INVALID_STOPS) {
                Print("❌ Неверные стопы! Проверьте расчеты TP/SL");
            } else if(trade.ResultRetcode() == TRADE_RETCODE_INVALID_PRICE) {
                Print("❌ Неверная цена! Цена Sell Stop: ", DoubleToString(sessionSellLevel, Digits()));
            } else if(trade.ResultRetcode() == TRADE_RETCODE_INVALID_VOLUME) {
                Print("❌ Неверный объем! Лот: ", DoubleToString(lotSize, 3));
            }
            
            if(retry < MaxRetries - 1) {
                Print("⏳ Ожидание ", RetryDelay, " мс перед повтором...");
                Sleep(RetryDelay);
                // Обновляем цены
                currentPrice = SymbolInfoDouble(tradingSymbol, SYMBOL_ASK);
            }
        }
    }
    
    Print("❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось установить Sell Stop после ", MaxRetries, " попыток!");
    return false;
}

//+------------------------------------------------------------------+
//| Проверка глобального Take Profit                               |
//+------------------------------------------------------------------+
void CheckGlobalTakeProfit() {
    if(!sessionActive) return;
    
    double totalProfit = 0;
    int activePositions = 0;
    
    for(int i = 0; i < PositionsTotal(); i++) {
        if(position.SelectByIndex(i)) {
            if(position.Symbol() == tradingSymbol && position.Magic() == MagicNumber) {
                totalProfit += position.Profit() + position.Swap() + position.Commission();
                activePositions++;
            }
        }
    }
    
    if(activePositions > 1) {
        double targetProfit = TakeProfitPips * pipValue * InitialLot;
        
        if(totalProfit >= targetProfit && ResetAfterTP) {
            Print("🎉 VPS ГЛОБАЛЬНЫЙ TP! Прибыль: $", DoubleToString(totalProfit, 2));
            CloseAllPositionsAndOrders();
        }
    }
}

//+------------------------------------------------------------------+
//| Обновление информации о позициях                               |
//+------------------------------------------------------------------+
void UpdatePositionsInfo() {
    for(int i = ArraySize(positions) - 1; i >= 0; i--) {
        if(!position.SelectByTicket(positions[i].ticket)) {
            Print("📈 VPS Позиция закрыта: ", positions[i].ticket, " - СЕССИЯ ЗАВЕРШЕНА");
            CloseAllPositionsAndOrders();
            return;
        }
    }
}

//+------------------------------------------------------------------+
//| Закрытие всех позиций и ордеров                                |
//+------------------------------------------------------------------+
void CloseAllPositionsAndOrders() {
    Print("🔄 VPS Закрытие всех позиций и ордеров...");
    
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(position.SelectByIndex(i)) {
            if(position.Symbol() == tradingSymbol && position.Magic() == MagicNumber) {
                trade.PositionClose(position.Ticket());
            }
        }
    }
    
    for(int i = OrdersTotal() - 1; i >= 0; i--) {
        if(order.SelectByIndex(i)) {
            if(order.Symbol() == tradingSymbol && order.Magic() == MagicNumber) {
                trade.OrderDelete(order.Ticket());
            }
        }
    }
    
    sessionActive = false;
    lastSessionEnd = TimeCurrent();
    ArrayResize(positions, 0);
    
    Comment("✅ СОВЕТНИК: MartingaleVPS_Enhanced v1.61\n" +
            "📊 СТАТУС: СЕССИЯ ЗАКРЫТА\n" +
            "⏰ ВРЕМЯ: " + TimeToString(TimeCurrent()) + "\n" +
            "💰 СИМВОЛ: " + tradingSymbol + "\n" +
            "🔄 ПЕРЕЗАПУСК ЧЕРЕЗ: " + IntegerToString(DelayBetweenSessions) + " сек\n" +
            "🤖 РЕЖИМ: AUTO\n" +
            "🔐 ЛИЦЕНЗИЯ: АКТИВНА");
    
    Print("✅ VPS Сессия закрыта. Авто-перезапуск через ", DelayBetweenSessions, " секунд");
}

//+------------------------------------------------------------------+
//| Добавление позиции в массив                                    |
//+------------------------------------------------------------------+
void AddPositionToArray() {
    Print("📊 === ДОБАВЛЕНИЕ ПОЗИЦИИ В МАССИВ ===");
    
    int size = ArraySize(positions);
    Print("📊 Текущий размер массива: ", size);
    
    // Проверяем, не добавлена ли уже эта позиция
    for(int i = 0; i < size; i++) {
        if(positions[i].ticket == position.Ticket()) {
            Print("⚠️ ПОЗИЦИЯ УЖЕ В МАССИВЕ! Ticket: ", position.Ticket(), " на индексе ", i);
            return;
        }
    }
    
    ArrayResize(positions, size + 1);
    Print("📊 Массив увеличен до размера: ", ArraySize(positions));
    
    positions[size].ticket = position.Ticket();
    positions[size].type = position.PositionType();
    positions[size].lots = position.Volume();
    positions[size].openPrice = position.PriceOpen();
    positions[size].takeProfit = position.TakeProfit();
    positions[size].stopLoss = position.StopLoss();
    positions[size].openTime = position.Time();
    
    Print("📊 ПОЗИЦИЯ ДОБАВЛЕНА:");
    Print("📊   Индекс: ", size);
    Print("📊   Ticket: ", positions[size].ticket);
    Print("📊   Тип: ", (positions[size].type == POSITION_TYPE_BUY ? "BUY" : "SELL"));
    Print("📊   Лот: ", DoubleToString(positions[size].lots, 3));
    Print("📊   Цена: ", DoubleToString(positions[size].openPrice, Digits()));
    Print("📊   TP: ", DoubleToString(positions[size].takeProfit, Digits()));
    Print("📊   SL: ", DoubleToString(positions[size].stopLoss, Digits()));
    Print("📊   Время: ", TimeToString(positions[size].openTime));
    
    Print("📊 === ВЕСЬ МАССИВ ПОСЛЕ ДОБАВЛЕНИЯ ===");
    for(int j = 0; j < ArraySize(positions); j++) {
        Print("📊 [", j, "] Ticket: ", positions[j].ticket, 
              " | Тип: ", (positions[j].type == POSITION_TYPE_BUY ? "BUY" : "SELL"),
              " | Лот: ", DoubleToString(positions[j].lots, 3));
    }
    Print("📊 === КОНЕЦ МАССИВА ===");
}

//+------------------------------------------------------------------+
//| Проверка существующих позиций при запуске                      |
//+------------------------------------------------------------------+
void CheckExistingPositions() {
    int posCount = 0;
    
    for(int i = 0; i < PositionsTotal(); i++) {
        if(position.SelectByIndex(i)) {
            if(position.Symbol() == tradingSymbol && position.Magic() == MagicNumber) {
                posCount++;
                sessionActive = true;
                robotStarted = true;
                marketReady = true;
                AddPositionToArray();
            }
        }
    }
    
    if(posCount > 0) {
        Print("📊 VPS Найдены существующие позиции: ", posCount, " | Сессия возобновлена");
    }
}

//+------------------------------------------------------------------+
//| Проверка существования ордера                                  |
//+------------------------------------------------------------------+
bool CheckOrderExists(ENUM_ORDER_TYPE orderType) {
    Print("🔍 === ПРОВЕРКА СУЩЕСТВУЮЩИХ ОРДЕРОВ ===");
    Print("🔍 Ищем тип ордера: ", orderType, " (", 
          (orderType == ORDER_TYPE_BUY_STOP ? "BUY_STOP" : 
           orderType == ORDER_TYPE_SELL_STOP ? "SELL_STOP" : "ДРУГОЙ"), ")");
    Print("🔍 Всего ордеров в терминале: ", OrdersTotal());
    
    int ourOrders = 0;
    int targetOrders = 0;
    
    for(int i = 0; i < OrdersTotal(); i++) {
        if(order.SelectByIndex(i)) {
            bool isOurSymbol = (order.Symbol() == tradingSymbol);
            bool isOurMagic = (order.Magic() == MagicNumber);
            bool isTargetType = (order.OrderType() == orderType);
            
            if(isOurSymbol && isOurMagic) {
                ourOrders++;
                Print("🔍 Найден наш ордер #", i, ": ", 
                      order.OrderType(), " | Ticket: ", order.Ticket(), 
                      " | Лот: ", DoubleToString(order.VolumeCurrent(), 3),
                      " | Цена: ", DoubleToString(order.PriceOpen(), Digits()));
                      
                if(isTargetType) {
                    targetOrders++;
                    Print("✅ НАЙДЕН целевой ордер! Ticket: ", order.Ticket());
                }
            }
        }
    }
    
    Print("🔍 Наших ордеров всего: ", ourOrders);
    Print("🔍 Целевых ордеров: ", targetOrders);
    Print("🔍 === КОНЕЦ ПРОВЕРКИ ОРДЕРОВ ===");
    
    return (targetOrders > 0);
}

//+------------------------------------------------------------------+
//| Расчет стоимости пункта                                        |
//+------------------------------------------------------------------+
void CalculatePipValue() {
    pipValue = SymbolInfoDouble(tradingSymbol, SYMBOL_TRADE_TICK_VALUE);
    Print("💱 VPS Стоимость пункта: ", DoubleToString(pipValue, 5));
}

//+------------------------------------------------------------------+
//| Диагностическая функция - показывает все параметры символа     |
//+------------------------------------------------------------------+
void ShowSymbolInfo() {
    Print("📊 === ИНФОРМАЦИЯ О СИМВОЛЕ ", tradingSymbol, " ===");
    Print("💰 Bid: ", DoubleToString(SymbolInfoDouble(tradingSymbol, SYMBOL_BID), Digits()));
    Print("💰 Ask: ", DoubleToString(SymbolInfoDouble(tradingSymbol, SYMBOL_ASK), Digits()));
    Print("📏 Point: ", DoubleToString(Point(), _Digits));
    Print("📏 Digits: ", Digits());
    Print("💱 Tick Value: ", DoubleToString(SymbolInfoDouble(tradingSymbol, SYMBOL_TRADE_TICK_VALUE), 5));
    Print("📊 Min Lot: ", DoubleToString(SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_MIN), 3));
    Print("📊 Max Lot: ", DoubleToString(SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_MAX), 3));
    Print("📊 Lot Step: ", DoubleToString(SymbolInfoDouble(tradingSymbol, SYMBOL_VOLUME_STEP), 3));
    Print("🔓 Trade Mode: ", SymbolInfoInteger(tradingSymbol, SYMBOL_TRADE_MODE));
    Print("📊 Contract Size: ", DoubleToString(SymbolInfoDouble(tradingSymbol, SYMBOL_TRADE_CONTRACT_SIZE), 2));
    Print("📊 === КОНЕЦ ИНФОРМАЦИИ О СИМВОЛЕ ===");
}
