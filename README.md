# Yandex Music Discord Rich Presence

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

Простое фоновое приложение для отображения текущего трека из Яндекс.Музыки в статусе Discord Rich Presence

## Скриншот
*Здесь можно добавить скриншот готового статуса в Discord*

## Установка собранной программы

### Установка

1. **Скачайте последний релиз**
   Перейдите в раздел [Releases](https://github.com/JustATRIK/YandexMusixDiscordRichPresence/releases) и скачайте нужную версию
   Распакуйте архив в удобную вам папку
2. **Скопируйте куки Яндекс.Музыки**
   - Откройте [Яндекс.Музыку](https://music.yandex.ru) в браузере и войдите в свой аккаунт
   - Откройте инструменты разработчика (`F12`)
   - Перейдите на вкладку **Application** (или **Хранилище**)
   - В левом меню найдите **Cookies** → `https://music.yandex.ru`
   - Скопируйте занчение и вставте в файл `.env` в строку `COOKIES=""` между кавычками, находящийся по пути `/data/.env` относительно папки, куда вы распаковали скачанный архив
     Должно получится нечто такое: `COOKIES="receive-cookie-deprecation=1; yandexuid=...; _ym_uid=...;..."`
2. **Скопируйте ID пользователя Яндекс.Музыки**
   - Откройте [Яндекс.Музыку](https://music.yandex.ru) в браузере и войдите в свой аккаунт
   - Откройте инструменты разработчика (`F12`)
   - Перейдите на вкладку **Network** (или **Сеть**)
   - В фильтрак выберите тип `Socket`
   - Выбрите любой из запросов ниже, в поле `sec-websocket-protocol` найдите `X-Yandex-Music-Multi-Auth-User-Id%22%3A%22`, после нее, до знака `%` будет написан ваш ID
   - Скопируйте этот ID d файл `.env` в строку `USER_ID=` (как в прошлом шаге, но без кавычек)
     Должно получится нечто такое: `USER_ID=000000000`
3. **Проверьте работоспособность программы**
   - Откройте приложение Яндекс Музыки и Discord
   - Запустите `main.exe` из папки, в которую вы распаковали архив
   - ⚠️ Если программа не работает и статус не обновляется - попробуйте еще раз скопировать куки и ID пользователя.
     ⚠️ Если ничего не помогает - можете либо открыть тикет, либо написать мне в Телеграмм: `@atrikits`/ Дискорд: `shortatrik`
     ⚠️ Обязательно приложите логи (файл `/data/yamusic.log`, относительно папки, куда вы распаковали скачанный архив)

## Настройка
После того, как вы успешно установили программу - вы можете ее настроить!
Вся конфигурация происходит через файл `/data/config.json`
"details": "[font.small_capital:[song.title]]",
        "details_url": "[song.song_url]",
        "state": "\ud83c\udfa7[song.album_title] ([song.like_count]\u2665) \u043e\u0442 [song.artists]",
        "status_url": "[main_artist.artist_url]",
        "large_image": "[song.cover_url]",
        "large_text_first": "\ud83d\udcfb[song.genre] | [statistics.listened_tracks_count], [statistics.listened_time]",
        "large_text_second": "\ud83d\ude3bT\u00d8P [statistics.listened_by_artist:twenty one pilots] | [statistics.most_listened_genre_name] [statistics.most_listened_genre_count]",
        "small_image": "[main_artist.cover_url]",
        "small_text": "[main_artist.name]"
# Структура файла конфигурации
`rpc_config`:
  - `details` - 1-я строка текста
  - `details_url` - Ссылка, которая будет открыта при нажатии на 1-ю строку текста
  - `state` - 2-я строка текста
  - `status_url` - Ссылка, которая будет открыта при нажатии на 2-ю строку текста
  - `large_image` - Ссылка на большое изображение
  - `large_text_first` - 3-я строка текста. Меняется каждые `n>=10` секунд с `large_text_second`
  - `large_text_second` - 3-я строка текста
  - `small_image` - Ссылка на маленькое изображение
  - `small_text` - Текст, отображаемый при навдении на маленькое изображение
`large_text_switch_seconds` - раз во сколько секунд менятся `large_text`. Должно быть больше 10 и кратно ему
`app_id` - ID приложения ЯндексМузыки (скорее всего, вам это менять не нужно)
`presence_id` - ID клиента Rich Presence (скорее всего, вам это менять не нужно)
# Плейсхолдеры
Для настройки программы используется система с плейсхолдорами (при обновлении RPC, ключевые слова будут заменены на необходимые данные)
Примеры использования: `[font.small_capital:[song.title]]`, `[main_artist.artist_url]`, `Жанр: [song.genre]`
**Список всех провайдеров:**
1. **statistics**:
   - `listened_tracks_count` -> Количество прослушанных треков
   - `most_listened_genre_name` -> Имя наиболее прослушанного жанра
   - `most_listened_genre_count` -> Количество треков наиболее прослушанного жанра
   - `most_listened_artist_name` -> Имя наиболее прослушанного исполнителя
   - `most_listened_artist_count` -> Количество треков наиболее прослушанного жанра
   - `listened_time` -> Время прослушивания музыки
   - `listened_by_genre:id жанра` -> Количество прослушанных треков определенного жанра (например, `[statistcis.listened_by_genre:indie]` вернет количество прослушанных инди треков)
   - `listened_by_artist:twenty one pilots` -> Количество прослушанных треков определенного исполниеля (например, `[statistics.listened_by_genre:indie]` вернет количество прослушанных треков **twenty one pilots**)
2. **album** - альбом трека
   - `id` -> ID альбома
   - `title` -> Название альбома
   - `year` -> Год выхода альбома
   - `cover_url` -> Ссылка на обложну альбома размером 1000x1000
   - `likes_count` -> Количество лайков у альбома
   - `genre` -> Жанр альбома
3. **song** - трек
   - `id` -> ID трека
   - `title` -> Название трека
   - `artists` -> Исполнители, перечисленные через запятую
   - `song_url` -> Ссылка на трек (если трек был загружен пользователем и является приватным, то это будет ссылка на поисковой запрос на YouTube)
4. **main_artist** - 'главный' исполнитель трека
   - `id` -> ID исполнителя
   - `name` -> Имя исполнителя
   - `cover_url` -> Ссылка на обложну исполнителя размером 200x200
   - `artist_url` -> Ссылка на исполнителя (если трек был загружен пользователем и является приватным, то это будет ссылка на поисковой запрос на YouTube)

