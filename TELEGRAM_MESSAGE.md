# Выдача Voice Input в Telegram

Пользователь открывает бота по ссылке `https://t.me/present_ai_dima_bot?start=voice_input` и выбирает свою систему. Готовые установщики лежат в GitHub Releases; бот передаёт их прямыми кнопками. ZIP со скриптами предназначен для Windows; DOCX содержит инструкции для Windows и macOS.

## Текст после `/start voice_input`

**Бесплатный голосовой ввод для Windows и Mac**

Удерживай сочетание клавиш, говори и отпусти его. Текст появится в активном поле. На Windows зажимай `Ctrl` + `Alt`; на Mac — `Control` + `Option`. Распознавание выполняется на компьютере.

1. Выбери установщик для своей системы и процессора.
2. Для первой диктовки нужен интернет: модель Whisper `base` скачивается один раз (около 150 МБ).
3. На Mac разреши Voice Input доступ к микрофону, Input Monitoring и Accessibility. Инструкция по установке есть в DOCX.

Аудио не отправляется на сервер и не сохраняется. Нужны микрофон и Windows 10/11 x64 либо Mac с Apple silicon или Intel.

## Кнопки и файлы

- **Windows — установщик x64** → `VoiceInput-Setup-0.3.0-x64.exe`
- **MacBook — Apple silicon** → `VoiceInput-0.3.0-macos-arm64.dmg`
- **MacBook — Intel** → `VoiceInput-0.3.0-macos-x86_64.dmg`
- **Скрипты для Windows (ZIP)** → `VoiceInput-Source-0.3.0.zip`, отправляется ботом как документ.
- **Инструкция Word** → `VoiceInput-Guide-RU.docx`, отправляется ботом как документ.
- **Все файлы на GitHub** → https://github.com/divolax/voice-input-windows/releases/latest

Сборки macOS пока не подписаны сертификатом Apple Developer ID и не нотарифицированы. При первом запуске macOS может потребовать подтвердить открытие в **System Settings → Privacy & Security**.

## Обновление

Создай и отправь тег `vX.Y.Z`. GitHub Actions соберёт EXE, DMG для arm64 и DMG для Intel. После этого обнови имена файлов в кнопках бота и повторно выложи DOCX/скриптовый ZIP в новый Release.
