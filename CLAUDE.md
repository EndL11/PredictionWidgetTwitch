# CLAUDE.md: контекст проєкту для Claude Code

## Що це
OBS Browser Source віджет для прогнозів Twitch за бали каналу. Два файли без збірки і без залежностей:
- `widget.html`: сам віджет (вся логіка, стилі й розмітка в одному файлі; так і має лишатися, щоб OBS міг відкрити його як локальний файл або через URL).
- `setup.html`: допоміжна сторінка, яка отримує OAuth-токен (implicit grant) і генерує URL з параметрами для OBS.

Мова інтерфейсу і коментарів у коді українська. Користувач спілкується українською.

## Архітектура `widget.html`

Скрипт поділено на секції з коментарями `/* ===== ... ===== */`:

1. **CONFIG**: параметри читаються з `location.search` в обʼєкт `CFG` (повний список у README).
2. **ЗВУК**: `playStartSound()`. Якщо задано `CFG.sound`, грає `Audio`, інакше синтезований арпеджіо-«дзвіночок» через Web Audio.
3. **UI**:
   - `state`: поточний прогноз `{id, title, status: active|locked|resolved|canceled, locks_at, outcomes[], winning_outcome_id}`.
   - **Плавні оновлення.** `render()` перебудовує DOM (`build()`) **лише коли змінюється ключ** `id|outcomes.length|status|winner`. В інших випадках він тільки виставляє цілі значення:
     - числа через `tweenTo(key, target)` і RAF-цикл `twLoop`; елементи з `data-tw="<key>" data-f="<formatter>"` перемальовує `paintTweens()`. Ключі: `p{i}` бали, `u{i}` люди, `r{i}` коефіцієнт, `c{i}` відсоток;
     - ширина смуг через CSS transition на `flex-basis` (2 варіанти) або `width` (3+), елементи `[data-seg=i]`.
     - `lastPc` зберігає попередні відсотки, щоб після перебудови (зміна статусу) смуга не стрибала.
   - Компонування для 2 варіантів: `.duo-head` (назви, чипи з `ratio`/`pts`/`Winner!`, таймер посередині) і `.bar`. Для 3+ варіантів використовуються `.multi-row`.
4. **РЕЗУЛЬТАТИ**: `showResults()` будує `#results`. Для 2 варіантів кожен список стоїть над своєю стороною, для 3+ зліва переможці, справа всі, хто програв. Блок абсолютно позиціонований над `.duo-head` (CSS-змінна `--rb` рахується в JS). Прокрутка зроблена через Web Animations API (`translateY` від низу до верху), функція повертає тривалість у мс. Поки йде прокрутка, `#card.rolling` приглушує заголовок.
5. **Показ і приховування**: `show()`, `hideNow()`, `scheduleHide(extraMs)` (після результатів: `extraMs + hide`), `scheduleLockHide()` (один раз на прогноз, прапорець `lockHideArmed`; викликається з `onLock` і з `tickTimer`, коли таймер дійшов до 0 раніше за подію від Twitch).
6. **Обробники подій**: `onBegin(ev, silent)`, `onProgress`, `onLock`, `onEnd`. Якщо подія прийшла для невідомого `id`, викликається тихий `onBegin`. `mergeOutcomes()` зберігає порядок і кольори з початкових даних.
7. **TWITCH**:
   - `validateToken()`: `GET id.twitch.tv/oauth2/validate`, дає `user_id`, перевіряє scope.
   - `loadCurrent()`: `GET helix/predictions?broadcaster_id=…&first=1`. Підхоплює ACTIVE-прогноз після перезапуску OBS. LOCKED-прогноз не показується, віджет чекає на результат.
   - `connect()`: EventSub WebSocket `wss://eventsub.wss.twitch.tv/ws`. На `session_welcome` віджет створює підписки через `POST helix/eventsub/subscriptions` на `channel.prediction.begin|progress|lock|end` (v1, transport websocket). Також обробляються `session_keepalive` (watchdog), `session_reconnect` (нове зʼєднання, старе закривається, повторні підписки не потрібні) і `revocation`. При обриві зʼєднання віджет перепідключається через 3 с.
8. **ДЕМО** (`?demo=1`): `runDemo()` циклічно генерує прогноз: закриття ставок на 30-й с, результат на 40-й, фейкові `top_predictors`.

Публічні функції `onBegin/onProgress/onLock/onEnd` викликаються напряму з тестів (`page.evaluate`), тому їхні сигнатури треба зберігати.

## Дані Twitch (EventSub v1), які використовуються
- `begin`: `id, title, outcomes[{id,title,color}], started_at, locks_at`
- `progress` / `lock`: `outcomes[{id,title,color,users,channel_points,top_predictors[]}]`. У цих подіях `channel_points_won` завжди `null`.
- `end`: `status: resolved|canceled`, `winning_outcome_id`, `outcomes[].top_predictors[{user_name,user_login,channel_points_used,channel_points_won}]`. У `top_predictors` максимум 10 записів на варіант.
- `color`: `blue`/`pink` для 2 варіантів. Для 3+ варіантів Twitch віддає однаковий колір, тому використовується палітра `DEFAULT_COLORS`.

## Підводні камені
- **CORS**: `id.twitch.tv/oauth2/validate` і `api.twitch.tv/helix` дозволяють запити з браузера, сервер не потрібен. Токен отримується через implicit grant (`id.twitch.tv/oauth2/authorize?response_type=token`) (redirect на `http://localhost`, токен користувач копіює з адресного рядка), бо `file://` не може бути redirect URI.
- **Implicit-токен** не оновлюється, живе близько 60 днів. Віджет показує помилку в `#status`.
- **Автовідтворення звуку**: OBS CEF дозволяє звук без взаємодії користувача. У звичайному Chrome звук на демо може не грати, поки не було кліку.
- Висоту джерела в OBS має задати користувач. Картка стоїть по центру джерела (`body` flex `justify-content:center; align-items:center`), а списки займають місце над нею. У 660×360 (2 варіанти) і 660×460 (3 варіанти) над карткою лишається лише кілька пікселів запасу, тест це перевіряє.
- Токен потрапляє в URL. **Не можна** логувати його, відправляти кудись, крім Twitch, або комітити згенеровані URL.

## Тестування
```bash
pip install playwright && playwright install chromium
python tests/test_lifecycle.py [--chrome /path/to/chrome]   # 12 перевірок: показ/приховування, плавність, скасування, центрування, JS-помилки
python tests/screenshots.py   [--chrome /path/to/chrome]    # оновлює docs/*.png (~45 с)
```
Ручна перевірка: відкрити `widget.html?demo=1`. Перевірка з реальними даними: створити тестовий прогноз на своєму каналі в Twitch (панель «Прогнози» в чаті або в Stream Manager).

## Правила роботи
- Зберігати віджет одним файлом без зовнішніх залежностей і CDN.
- Новий параметр додавати в 4 місця: коментар CONFIG у `widget.html`, обʼєкт `CFG`, поле в `setup.html` (і в генерацію URL), таблицю в README.
- Після змін запускати `tests/test_lifecycle.py`. Якщо змінюється поведінка, додати перевірку.
- Оновлювати `PROGRESS.md` (історія + беклог).
