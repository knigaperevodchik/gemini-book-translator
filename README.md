# 📚 Gemini Book Translator

<!-- Языковой навигатор / Language Navigation -->
<p align="center">
  <a href="#-поддержать-проект-ru">Русский</a> • 
  <a href="#-support-the-project-en">English</a> • 
  <a href="#-支持此项目-zh">简体中文</a>
</p>

---

## 💰 Поддержать проект [RU]

[![TON](https://img.shields.io/badge/TON-USDT-0088cc?style=for-the-badge)](https://ton.org)
[![TRC20](https://img.shields.io/badge/TRC-USDT-26A17B?style=for-the-badge)]()

Если этот проект сэкономил ваше время или помог в работе, вы можете поддержать его развитие:

| Платформа / Сеть | Ссылка / Адрес кошелька |
| :--- | :--- |
| **Boosty** (Карты/Рубли) | [https://boosty.to/knigaperevodchik](https://boosty.to/knigaperevodchik) |
| **TON** (USDT) | `UQBWKwf2mgakNi4Ls2I6NNs1okcDyCxivdxxc22ypsMV4590` |
| **TRC20** (USDT) | `TDdok5FgB6fJSXZrPzxnn7hMk4qREUZPJe` |

---

## 💰 Support the Project [EN]

[![TON](https://img.shields.io/badge/TON-USDT-0088cc?style=for-the-badge)](https://ton.org)
[![TRC20](https://img.shields.io/badge/TRC-USDT-26A17B?style=for-the-badge)]()

If this project has saved your time or helped you, feel free to support its development:

| Platform / Network | Link / Wallet Address |
| :--- | :--- |
| **Boosty** (Fiat/Cards) | [https://boosty.to/knigaperevodchik](https://boosty.to/knigaperevodchik) |
| **TON** (USDT) | `UQBWKwf2mgakNi4Ls2I6NNs1okcDyCxivdxxc22ypsMV4590` |
| **TRC20** (USDT) | `TDdok5FgB6fJSXZrPzxnn7hMk4qREUZPJe` |

---

## 💰 支持此项目 [ZH]

https://img.shields.io/badge/TON-USDT-0088cc?style=for-the-badge
[![TRC20](https://img.shields.io/badge/TRC-USDT-26A17B?style=for-the-badge)]()

如果这个项目对您有所帮助，欢迎赞助以支持项目的持续 white-hat 维护与更新：

| 平台 / 网络 | 链接 / 钱包地址 |
| :--- | :--- |
| **TON** (USDT) | `UQBWKwf2mgakNi4Ls2I6NNs1okcDyCxivdxxc22ypsMV4590` |
| **TRC20** (USDT) | `TDdok5FgB6fJSXZrPzxnn7hMk4qREUZPJe` |

---

Автоматический перевод электронных книг (EPUB, FB2, TXT) через Google Gemini API с ротацией ключей и сохранением прогресса.

## ✨ Возможности

- 🔄 **Ротация API-ключей** — автоматическое переключение между ключами при исчерпании квоты
- 📖 **Поддержка форматов** — EPUB, FB2, TXT с полным сохранением структуры
- 🔁 **Повтор проблемных глав** — скрипт НЕ переходит к следующей главе, пока текущая не переведена полностью
- 💾 **Сохранение прогресса** — остановка через Ctrl+C, продолжение с того же места
- 🧪 **Параллельный перевод** — двумя моделями Gemini одновременно для сравнения качества
- 🎯 **Выборочный перевод** — только конкретные главы (EPUB) или секции (FB2)
- 🌍 **Универсальный поиск глав в TXT** — поддерживает 6 языков

## 📋 Требования

- Windows / Linux / macOS
- Python 3.8 или новее ([скачать](https://python.org))
- API-ключи Google Gemini ([получить бесплатно](https://aistudio.google.com/))

## 🚀 Установка и запуск

### 1. Скачать скрипт

**Способ A (через Git):**
```bash
git clone https://github.com/yourusername/gemini-book-translator.git
cd gemini-book-translator
```

**Способ B (без Git):**
- Нажмите `Code` → `Download ZIP`
- Распакуйте в любую папку

### 2. Открыть командную строку в папке со скриптом

**Windows:**
- Откройте папку → в адресной строке напишите `cmd` → Enter

**Linux/macOS:**
```bash
cd /путь/к/папке
```

### 3. Установить зависимости

```bash
pip install google-generativeai ebooklib beautifulsoup4 lxml
```

Если pip не найден:
```bash
python -m pip install google-generativeai ebooklib beautifulsoup4 lxml
```

### 4. Настроить API-ключи

Откройте `translate_gemini_new.py` в любом текстовом редакторе (Блокнот, Notepad++, VS Code).

Найдите массив `API_KEYS` и замените ключи на свои:

```python
API_KEYS = [
    "ВАШ_КЛЮЧ_1",
    "ВАШ_КЛЮЧ_2",
    "ВАШ_КЛЮЧ_3",
    # ... до 10 ключей
]
```

### 5. (Опционально) Сменить язык перевода

По умолчанию: **датский → русский**

Найдите функцию `make_prompt()` и замените слово `"датского"`:

```python
return f"""Переведи с испанского на русский. Сохраняй стиль автора...
```

### 6. Запустить

```bash
python translate_gemini_new.py
```

## 🎮 Использование

### При запуске

```
Путь к файлу (Enter = book_full.txt):
```

Укажите путь к книге или нажмите Enter для `book_full.txt`

### Меню для EPUB

```
Режим работы:
  1. Обычный перевод — вся книга (одна модель)
  2. Параллельный — вся книга (две модели → два файла)
  3. Перевод конкретных глав (одна модель)
  4. Параллельный — конкретные главы (две модели → два файла)
```

### Меню для FB2

```
Режим работы:
  1. Обычный перевод — вся книга (одна модель)
  2. Параллельный — вся книга (две модели → два файла)
  3. Перевод конкретных секций (одна модель)
  4. Параллельный — конкретные секции (две модели → два файла)
```

### Меню для TXT

```
Режим работы:
  1. Обычный перевод (одна модель)
  2. Параллельный — вся книга (две модели)
  3. Параллельный — конкретная часть/глава
```

При выборе режима 3 открывается подменю:

```
Выберите единицу:
  1. По номеру части
  2. По номеру главы
```

## 📁 Выходные файлы

### EPUB и FB2

| Режим | Имя выходного файла |
|-------|---------------------|
| 1. Обычный (вся книга) | `имя_файла_ru.epub` или `имя_файла_ru.fb2` |
| 2. Параллельный (вся книга) | `имя_файла_ru_название_модели.epub` (2 файла) |
| 3. Выборочные главы/секции | `имя_файла_ru_ch1_3.epub` или `имя_файла_ru_sec1_3.fb2` |
| 4. Параллельный + выборочные | `имя_файла_ru_ch1_3_название_модели.epub` (2 файла) |

### TXT

| Режим | Имя выходного файла |
|-------|---------------------|
| 1. Обычный (вся книга) | `имя_файла_ru.txt` |
| 2. Параллельный (вся книга) | `имя_файла_ru_название_модели1.txt` и `имя_файла_ru_название_модели2.txt` |
| 3. Параллельный — конкретная часть | `compare_partN_название_модели.txt` (2 файла) |
| 3. Параллельный — конкретная глава | `compare_glavaN_название_модели.txt` (2 файла) |

*Где N — номер части или главы*

## ⏸️ Остановка и продолжение

- Нажмите **Ctrl + C** — прогресс сохранится
- Запустите скрипт снова — он продолжит с того же места
- После завершения перевода файлы прогресса удаляются автоматически

## 📂 Файлы прогресса (автоматические)

| Файл | Для какого режима |
|------|-------------------|
| `translate_progress.txt` | TXT обычный (режим 1) |
| `translate_progress_chapter.txt` | EPUB |
| `translate_progress_fb2.txt` | FB2 |
| `translate_progress_parallel.txt` | FB2 параллельный |

## ⚠️ Частые проблемы и решения

| Проблема | Решение |
|----------|---------|
| `429 Too Many Requests` | Скрипт переключит ключ автоматически |
| `503 Service Unavailable` | Смените IP (перезагрузите роутер) или увеличьте задержки |
| `ModuleNotFoundError: No module named 'ebooklib'` | Установите библиотеку: `pip install ebooklib beautifulsoup4 lxml` |
| `Файл не найден` | Поместите книгу в ту же папку, что и скрипт |
| `Не определяется глава в TXT` | Универсальный поиск поддерживает 6 языков |

### Поддерживаемые языки для поиска глав в TXT

| Язык | Ключевое слово |
|------|----------------|
| Датский | KAPITEL |
| Английский | CHAPTER |
| Французский | CHAPITRE |
| Испанский | CAPÍTULO |
| Итальянский | CAPITOLO |
| Русский | ГЛАВА |

## 🛠️ Настройка задержек

Если часто вылетает ошибка 503, откройте скрипт и увеличьте значения:

```python
time.sleep(15)   # → time.sleep(30) или 45
time.sleep(5)    # → time.sleep(10)
```

## 📄 Лицензия

MIT — свободное использование, модификация и распространение.

## 🙏 Благодарности

- [Google Gemini API](https://ai.google.dev/) — модели перевода
- [ebooklib](https://github.com/aerkalov/ebooklib) — работа с EPUB
- [lxml](https://lxml.de/) — работа с FB2
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — обработка HTML

## ⭐ Если помогло

Поставьте звезду на GitHub — это помогает другим найти проект.
```

---

```markdown
# 📚 Gemini Book Translator

Automated translation of e-books (EPUB, FB2, TXT) using Google Gemini API with key rotation and progress saving.

## ✨ Features

- 🔄 **API Key Rotation** — automatically switches between keys when quota is exhausted
- 📖 **Format Support** — EPUB, FB2, TXT with full structure preservation
- 🔁 **Problem Chapter Retry** — script does NOT move to the next chapter until current one is fully translated
- 💾 **Progress Saving** — stop with Ctrl+C, resume from the same place
- 🧪 **Parallel Translation** — two Gemini models simultaneously for quality comparison
- 🎯 **Selective Translation** — only specific chapters (EPUB) or sections (FB2)
- 🌍 **Universal Chapter Search in TXT** — supports 6 languages

## 📋 Requirements

- Windows / Linux / macOS
- Python 3.8 or newer ([download](https://python.org))
- Google Gemini API keys ([get free](https://aistudio.google.com/))

## 🚀 Installation & Setup

### 1. Download the script

**Option A (via Git):**
```bash
git clone https://github.com/yourusername/gemini-book-translator.git
cd gemini-book-translator
```

**Option B (without Git):**
- Click `Code` → `Download ZIP`
- Extract to any folder

### 2. Open command line in the script folder

**Windows:**
- Open the folder → type `cmd` in the address bar → Enter

**Linux/macOS:**
```bash
cd /path/to/folder
```

### 3. Install dependencies

```bash
pip install google-generativeai ebooklib beautifulsoup4 lxml
```

If pip is not found:
```bash
python -m pip install google-generativeai ebooklib beautifulsoup4 lxml
```

### 4. Configure API keys

Open `translate_gemini_new.py` in any text editor (Notepad, Notepad++, VS Code).

Find the `API_KEYS` array and replace with your keys:

```python
API_KEYS = [
    "YOUR_KEY_1",
    "YOUR_KEY_2",
    "YOUR_KEY_3",
    # ... up to 10 keys
]
```

### 5. (Optional) Change source language

Default: **Danish → Russian**

Find the `make_prompt()` function and replace the word `"датского"` (Danish):

```python
return f"""Translate from Spanish to Russian. Preserve the author's style...
```

### 6. Run

```bash
python translate_gemini_new.py
```

## 🎮 Usage

### On startup

```
File path (Enter = book_full.txt):
```

Enter the book path or press Enter for `book_full.txt`

### EPUB Menu

```
Mode:
  1. Normal translation — entire book (one model)
  2. Parallel — entire book (two models → two files)
  3. Translate specific chapters (one model)
  4. Parallel — specific chapters (two models → two files)
```

### FB2 Menu

```
Mode:
  1. Normal translation — entire book (one model)
  2. Parallel — entire book (two models → two files)
  3. Translate specific sections (one model)
  4. Parallel — specific sections (two models → two files)
```

### TXT Menu

```
Mode:
  1. Normal translation (one model)
  2. Parallel — entire book (two models)
  3. Parallel — specific part/chapter
```

Selecting mode 3 opens submenu:

```
Choose unit:
  1. By part number
  2. By chapter number
```

## 📁 Output Files

### EPUB and FB2

| Mode | Output filename |
|------|-----------------|
| 1. Normal (entire book) | `filename_ru.epub` or `filename_ru.fb2` |
| 2. Parallel (entire book) | `filename_ru_modelname.epub` (2 files) |
| 3. Selected chapters/sections | `filename_ru_ch1_3.epub` or `filename_ru_sec1_3.fb2` |
| 4. Parallel + selected | `filename_ru_ch1_3_modelname.epub` (2 files) |

### TXT

| Mode | Output filename |
|------|-----------------|
| 1. Normal (entire book) | `filename_ru.txt` |
| 2. Parallel (entire book) | `filename_ru_modelname1.txt` and `filename_ru_modelname2.txt` |
| 3. Parallel — specific part | `compare_partN_modelname.txt` (2 files) |
| 3. Parallel — specific chapter | `compare_glavaN_modelname.txt` (2 files) |

*Where N is the part or chapter number*

## ⏸️ Stop and Resume

- Press **Ctrl + C** — progress is saved
- Run the script again — it continues from the same place
- Progress files are automatically deleted after completion

## 📂 Progress Files (automatic)

| File | For which mode |
|------|----------------|
| `translate_progress.txt` | TXT normal (mode 1) |
| `translate_progress_chapter.txt` | EPUB |
| `translate_progress_fb2.txt` | FB2 |
| `translate_progress_parallel.txt` | FB2 parallel |

## ⚠️ Common Issues & Solutions

| Problem | Solution |
|---------|----------|
| `429 Too Many Requests` | Script will switch keys automatically |
| `503 Service Unavailable` | Change IP (restart router) or increase delays |
| `ModuleNotFoundError: No module named 'ebooklib'` | Install: `pip install ebooklib beautifulsoup4 lxml` |
| `File not found` | Place the book in the same folder as the script |
| `Chapter not detected in TXT` | Universal search supports 6 languages |

### Supported languages for TXT chapter search

| Language | Keyword |
|----------|---------|
| Danish | KAPITEL |
| English | CHAPTER |
| French | CHAPITRE |
| Spanish | CAPÍTULO |
| Italian | CAPITOLO |
| Russian | ГЛАВА |

## 🛠️ Adjusting Delays

If you frequently get error 503, open the script and increase these values:

```python
time.sleep(15)   # → time.sleep(30) or 45
time.sleep(5)    # → time.sleep(10)
```

## 📄 License

MIT — free use, modification, and distribution.

## 🙏 Acknowledgments

- [Google Gemini API](https://ai.google.dev/) — translation models
- [ebooklib](https://github.com/aerkalov/ebooklib) — EPUB handling
- [lxml](https://lxml.de/) — FB2 handling
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML processing

## ⭐ If this helped

Give a star on GitHub — it helps others find the project.
```

---

```markdown
# 📚 Gemini 电子书翻译器

使用 Google Gemini API 自动翻译电子书（EPUB、FB2、TXT），支持密钥轮换和进度保存。

## ✨ 功能特点

- 🔄 **API 密钥轮换** — 配额用尽时自动切换密钥
- 📖 **格式支持** — EPUB、FB2、TXT，完整保留书籍结构
- 🔁 **问题章节重试** — 当前章节未完成翻译前，不会跳转到下一章
- 💾 **进度保存** — 按 Ctrl+C 停止，重新运行从断点继续
- 🧪 **并行翻译** — 同时使用两种 Gemini 模型，便于比较质量
- 🎯 **选择性翻译** — 仅翻译指定章节（EPUB）或区块（FB2）
- 🌍 **TXT 通用章节搜索** — 支持 6 种语言

## 📋 系统要求

- Windows / Linux / macOS
- Python 3.8 或更高版本（[下载](https://python.org)）
- Google Gemini API 密钥（[免费获取](https://aistudio.google.com/)）

## 🚀 安装与运行

### 1. 下载脚本

**方式 A（通过 Git）：**
```bash
git clone https://github.com/yourusername/gemini-book-translator.git
cd gemini-book-translator
```

**方式 B（不使用 Git）：**
- 点击 `Code` → `Download ZIP`
- 解压到任意文件夹

### 2. 在脚本所在文件夹打开命令行

**Windows：**
- 打开文件夹 → 在地址栏输入 `cmd` → 回车

**Linux/macOS：**
```bash
cd /路径/到/文件夹
```

### 3. 安装依赖

```bash
pip install google-generativeai ebooklib beautifulsoup4 lxml
```

如果找不到 pip：
```bash
python -m pip install google-generativeai ebooklib beautifulsoup4 lxml
```

### 4. 配置 API 密钥

用文本编辑器（记事本、Notepad++、VS Code）打开 `translate_gemini_new.py`。

找到 `API_KEYS` 数组，替换成你的密钥：

```python
API_KEYS = [
    "你的密钥_1",
    "你的密钥_2",
    "你的密钥_3",
    # ... 最多 10 个密钥
]
```

### 5. （可选）更改源语言

默认：**丹麦语 → 俄语**

找到 `make_prompt()` 函数，将 `"датского"`（丹麦语）替换为所需语言：

```python
return f"""从西班牙语翻译成俄语。保留作者风格...
```

### 6. 运行

```bash
python translate_gemini_new.py
```

## 🎮 使用方法

### 启动时

```
文件路径 (回车 = book_full.txt):
```

输入书籍路径，或直接回车使用 `book_full.txt`

### EPUB 菜单

```
工作模式：
  1. 普通翻译 — 整本书（单一模型）
  2. 并行翻译 — 整本书（双模型 → 两个文件）
  3. 翻译指定章节（单一模型）
  4. 并行翻译 + 指定章节（双模型 → 两个文件）
```

### FB2 菜单

```
工作模式：
  1. 普通翻译 — 整本书（单一模型）
  2. 并行翻译 — 整本书（双模型 → 两个文件）
  3. 翻译指定区块（单一模型）
  4. 并行翻译 + 指定区块（双模型 → 两个文件）
```

### TXT 菜单

```
工作模式：
  1. 普通翻译（单一模型）
  2. 并行翻译 — 整本书（双模型）
  3. 并行翻译 — 指定段落/章节
```

选择模式 3 后出现子菜单：

```
请选择：
  1. 按段落编号
  2. 按章节编号
```

## 📁 输出文件

### EPUB 和 FB2

| 模式 | 输出文件名 |
|------|-----------|
| 1. 普通翻译（整本书） | `文件名_ru.epub` 或 `文件名_ru.fb2` |
| 2. 并行翻译（整本书） | `文件名_ru_模型名.epub`（2 个文件）|
| 3. 指定章节/区块 | `文件名_ru_ch1_3.epub` 或 `文件名_ru_sec1_3.fb2` |
| 4. 并行 + 指定 | `文件名_ru_ch1_3_模型名.epub`（2 个文件）|

### TXT

| 模式 | 输出文件名 |
|------|-----------|
| 1. 普通翻译（整本书） | `文件名_ru.txt` |
| 2. 并行翻译（整本书） | `文件名_ru_模型名1.txt` 和 `文件名_ru_模型名2.txt` |
| 3. 并行 — 指定段落 | `compare_partN_模型名.txt`（2 个文件）|
| 3. 并行 — 指定章节 | `compare_glavaN_模型名.txt`（2 个文件）|

*其中 N 为段落或章节编号*

## ⏸️ 停止与继续

- 按 **Ctrl + C** — 进度自动保存
- 重新运行脚本 — 从断点继续翻译
- 翻译完成后，进度文件自动删除

## 📂 进度文件（自动生成）

| 文件 | 对应模式 |
|------|---------|
| `translate_progress.txt` | TXT 普通模式（模式 1）|
| `translate_progress_chapter.txt` | EPUB |
| `translate_progress_fb2.txt` | FB2 |
| `translate_progress_parallel.txt` | FB2 并行模式 |

## ⚠️ 常见问题与解决方案

| 问题 | 解决方案 |
|------|---------|
| `429 Too Many Requests` | 脚本会自动切换密钥 |
| `503 Service Unavailable` | 更换 IP（重启路由器）或增加延迟 |
| `ModuleNotFoundError: No module named 'ebooklib'` | 安装依赖：`pip install ebooklib beautifulsoup4 lxml` |
| `文件未找到` | 将书籍文件放在脚本同一文件夹下 |
| `TXT 中无法识别章节` | 通用搜索支持 6 种语言 |

### TXT 章节搜索支持的语言

| 语言 | 关键词 |
|------|--------|
| 丹麦语 | KAPITEL |
| 英语 | CHAPTER |
| 法语 | CHAPITRE |
| 西班牙语 | CAPÍTULO |
| 意大利语 | CAPITOLO |
| 俄语 | ГЛАВА |

## 🛠️ 调整延迟

如果频繁遇到 503 错误，打开脚本并增大以下值：

```python
time.sleep(15)   # → 改为 time.sleep(30) 或 45
time.sleep(5)    # → 改为 time.sleep(10)
```

## 📄 许可证

MIT — 可自由使用、修改和分发。

## 🙏 致谢

- [Google Gemini API](https://ai.google.dev/) — 翻译模型
- [ebooklib](https://github.com/aerkalov/ebooklib) — EPUB 处理
- [lxml](https://lxml.de/) — FB2 处理
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML 处理

## ⭐ 如果这个项目对你有帮助

请在 GitHub 上点亮 Star — 帮助更多人发现这个项目。
```
