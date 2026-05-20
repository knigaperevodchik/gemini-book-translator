import google.generativeai as genai
import time
import os
import threading
import sys
import re

# Все API ключи
API_KEYS = [
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
    "ВАШ КЛЮЧ API",
]

PROGRESS_FILE = "translate_progress.txt"
PROGRESS_FILE_CHAPTER = "translate_progress_chapter.txt"
PROGRESS_FILE_FB2 = "translate_progress_fb2.txt"
PROGRESS_FILE_PARALLEL = "translate_progress_parallel.txt"
CHUNK_SIZE = 3000

MODELS = {
    "1": "gemini-2.0-flash",
    "2": "gemini-1.5-flash",
    "3": "gemini-1.5-pro",
    "4": "gemini-flash-latest",
    "5": "gemini-3.5-flash",
}

# Глобальные переменные для текущего состояния
current_key_index = 0
current_model_name = "gemini-2.0-flash"


# ══════════════════════════════════════════════
#  РАБОТА С ФОРМАТАМИ
# ══════════════════════════════════════════════

def detect_format(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".epub":
        return "epub"
    elif ext == ".fb2":
        return "fb2"
    elif ext == ".txt":
        return "txt"
    else:
        return "unknown"


# ── TXT ──────────────────────────────────────

def read_txt(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_txt(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


# ── FB2 ──────────────────────────────────────

def read_fb2(path):
    """
    Возвращает список секций: [{"id": str, "title": str|None, "paragraphs": [str]}]
    Сохраняет структуру (sections/titles/p) для последующей сборки.
    """
    try:
        from lxml import etree
    except ImportError:
        import xml.etree.ElementTree as etree

    tree = etree.parse(path)
    root = tree.getroot()

    # FB2 использует namespace
    ns = ""
    tag = root.tag
    if tag.startswith("{"):
        ns = tag.split("}")[0] + "}"

    sections = []

    def parse_section(el, depth=0):
        sec = {"title": None, "paragraphs": [], "subsections": []}
        for child in el:
            local = child.tag.replace(ns, "")
            if local == "title":
                parts = []
                for p in child.iter(ns + "p"):
                    parts.append("".join(p.itertext()))
                sec["title"] = " ".join(parts).strip()
            elif local == "p":
                text = "".join(child.itertext()).strip()
                if text:
                    sec["paragraphs"].append(text)
            elif local == "section":
                sec["subsections"].append(parse_section(child, depth + 1))
            elif local in ("epigraph", "poem", "cite", "subtitle", "empty-line"):
                text = "".join(child.itertext()).strip()
                if text:
                    sec["paragraphs"].append(text)
        return sec

    bodies = root.findall(f"{ns}body")
    result = []
    for body in bodies:
        for section_el in body.findall(f"{ns}section"):
            result.append(parse_section(section_el))
    return result, tree, ns


def flatten_fb2_sections(sections):
    """
    Преобразует список секций в плоский список (title, text) для перевода.
    Возвращает list of dict: {"type": "title"|"paragraph", "text": str, "path": tuple}
    """
    flat = []

    def walk(sec, path=()):
        if sec["title"]:
            flat.append({"type": "title", "text": sec["title"], "path": path + ("title",)})
        for i, p in enumerate(sec["paragraphs"]):
            flat.append({"type": "paragraph", "text": p, "path": path + ("p", i)})
        for j, sub in enumerate(sec["subsections"]):
            walk(sub, path + ("sub", j))

    for i, s in enumerate(sections):
        walk(s, (i,))
    return flat


def rebuild_fb2(original_path, output_path, translations):
    """
    Берёт оригинальный FB2, заменяет текстовые узлы переводами, сохраняет структуру.
    translations — dict: индекс_элемента_flat -> переведённый текст
    """
    try:
        from lxml import etree
        USE_LXML = True
    except ImportError:
        import xml.etree.ElementTree as etree
        USE_LXML = False

    # Читаем оригинал как текст для сохранения XML-пролога
    with open(original_path, 'rb') as f:
        raw = f.read()

    tree = etree.parse(original_path)
    root = tree.getroot()
    ns_uri = ""
    tag = root.tag
    if tag.startswith("{"):
        ns_uri = tag.split("}")[0][1:]  # без фигурных скобок

    ns = f"{{{ns_uri}}}" if ns_uri else ""

    # Собираем все <p> и <title><p> в порядке обхода
    all_text_nodes = []

    def collect(el):
        local = el.tag.replace(ns, "")
        if local in ("p", "subtitle"):
            all_text_nodes.append(el)
        for child in el:
            collect(child)

    for body in root.findall(f"{ns}body"):
        collect(body)

    # Заменяем тексты переводами по порядку
    for idx, (el, translated) in enumerate(zip(all_text_nodes, translations)):
        if translated:
            # Очищаем дочерние элементы, оставляем только текст
            for child in list(el):
                el.remove(child)
            el.text = translated

    # Обновляем метаданные: язык
    title_info = root.find(f".//{ns}title-info")
    if title_info is not None:
        lang_el = title_info.find(f"{ns}lang")
        if lang_el is not None:
            lang_el.text = "ru"
        src_lang_el = title_info.find(f"{ns}src-lang")
        if src_lang_el is None:
            # добавляем src-lang если его нет
            src_lang = etree.SubElement(title_info, f"{ns}src-lang")
            src_lang.text = "da"

    if USE_LXML:
        tree.write(output_path, encoding='utf-8', xml_declaration=True,
                   pretty_print=True)
    else:
        tree.write(output_path, encoding='unicode', xml_declaration=False)

    print(f"FB2 сохранён: {output_path}")


# ── EPUB ─────────────────────────────────────

def check_ebooklib():
    try:
        import ebooklib
        from ebooklib import epub
        return True
    except ImportError:
        print("\n[!] ebooklib не установлен. Установите: pip install ebooklib")
        print("    Или: pip install ebooklib beautifulsoup4")
        return False


def read_epub(path):
    """
    Возвращает список глав: [{"id": str, "title": str, "html": str, "paragraphs": [str]}]
    """
    import ebooklib
    from ebooklib import epub
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.texts = []
            self.current = []
            self.in_block = False
            self.BLOCK_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                               'li', 'td', 'th', 'div', 'blockquote'}

        def handle_starttag(self, tag, attrs):
            if tag in self.BLOCK_TAGS:
                self.in_block = True
                self.current = []

        def handle_endtag(self, tag):
            if tag in self.BLOCK_TAGS and self.in_block:
                text = ''.join(self.current).strip()
                if text:
                    self.texts.append(text)
                self.current = []
                self.in_block = False

        def handle_data(self, data):
            if self.in_block:
                self.current.append(data)

    book = epub.read_epub(path)
    chapters = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html_content = item.get_content().decode('utf-8', errors='replace')
        extractor = TextExtractor()
        extractor.feed(html_content)
        if extractor.texts:
            # Пытаемся получить название главы
            title = item.get_id()
            if hasattr(item, 'get_name') and item.get_name():
                title = item.get_name()
            chapters.append({
                "id": item.get_id(),
                "name": item.get_name(),
                "title": title,
                "html": html_content,
                "paragraphs": extractor.texts
            })

    return book, chapters


def rebuild_epub(book, chapters, translations_map, output_path):
    """
    translations_map: {chapter_id: [translated_paragraph, ...]}
    """
    import ebooklib
    from ebooklib import epub
    try:
        from bs4 import BeautifulSoup
        USE_BS4 = True
    except ImportError:
        USE_BS4 = False
        print("[!] beautifulsoup4 не установлен, HTML структура может упроститься")

    BLOCK_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'li', 'td', 'th', 'blockquote']

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        ch_id = item.get_id()
        if ch_id not in translations_map:
            continue

        translated_paras = translations_map[ch_id]
        html = item.get_content().decode('utf-8', errors='replace')

        if USE_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            block_els = []
            for tag in BLOCK_TAGS:
                block_els.extend(soup.find_all(tag))
            # Сортируем по порядку в документе
            all_tags = soup.find_all(BLOCK_TAGS)
            para_idx = 0
            for el in all_tags:
                text = el.get_text(strip=True)
                if text and para_idx < len(translated_paras):
                    el.string = translated_paras[para_idx]
                    para_idx += 1
            new_html = str(soup).encode('utf-8')
        else:
            # Простая замена: просто соединяем переводы в базовый HTML
            body = "\n".join(f"<p>{p}</p>" for p in translated_paras)
            new_html = f"<html><body>{body}</body></html>".encode('utf-8')

        item.set_content(new_html)

    # Обновляем метаданные языка
    book.set_language("ru")

    epub.write_epub(output_path, book)
    print(f"EPUB сохранён: {output_path}")


# ══════════════════════════════════════════════
#  ПЕРЕВОДЧИК (общая логика)
# ══════════════════════════════════════════════

def make_prompt(text, mode=0):
    if mode == 0:
        return f"""Переведи с датского на русский. Сохраняй стиль автора.
Правила:
- Первая буква абзаца заглавная, остальные слова строчными (кроме имён собственных)
- Слова написанные ЗАГЛАВНЫМИ БУКВАМИ переводи как обычные слова без капслока
- Верни только перевод без пояснений

Текст:
{text}"""
    elif mode == 1:
        return f"""Ты опытный переводчик художественной литературы.
Передай этот фрагмент на русском языке, сохраняя живой разговорный стиль и эмоции автора.
Первая буква абзаца заглавная, остальные слова строчными (кроме имён собственных).
Слова написанные ЗАГЛАВНЫМИ БУКВАМИ переводи как обычные слова без капслока.
Верни только перевод без пояснений.

Текст:
{text}"""
    else:
        return f"""Ты опытный переводчик художественной прозы с датского языка.
Выполни литературный перевод — передай характеры персонажей, атмосферу и интонацию автора, сохраняя живость и естественность речи.
Первая буква абзаца заглавная, остальные слова строчными (кроме имён собственных).
Слова написанные ЗАГЛАВНЫМИ БУКВАМИ переводи как обычные слова без капслока.
Верни только текст перевода без пояснений.

Фрагмент:
{text}"""


def choose_model(label="", current_model=None):
    print(f"\nВыберите модель Gemini{' (' + label + ')' if label else ''}:")
    for k, v in MODELS.items():
        print(f"  {k}. {v}")
    print("  6. Ввести вручную")
    if current_model:
        print(f"  [Enter] — оставить текущую ({current_model})")
    try:
        choice = input("\nВаш выбор: ").strip()
    except:
        choice = ""
    if choice == "" and current_model:
        return current_model
    elif choice in MODELS:
        return MODELS[choice]
    elif choice == "6":
        return input("Введите название модели: ").strip()
    elif current_model:
        return current_model
    else:
        return "gemini-2.0-flash"


def make_model(api_key, model_name):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def switch_key(current_key_index, current_model_name, auto=False):
    """
    Быстрое переключение API ключа.
    Если auto=True — сразу берёт следующий без вопросов.
    Иначе даёт 3 секунды ввести номер ключа вручную, потом переключает сам.
    Возвращает (new_key_index, new_model_name).
    """
    next_index = current_key_index + 1
    if next_index >= len(API_KEYS):
        print("Все API ключи исчерпаны!")
        return None, current_model_name

    if auto:
        print(f"[Авто] Переключаюсь на ключ #{next_index + 1}/{len(API_KEYS)}")
        return next_index, current_model_name

    print(f"\n{'─'*40}")
    print(f"Доступны ключи: #1–#{len(API_KEYS)}")
    print(f"Текущий: #{current_key_index + 1}  →  Авто: #{next_index + 1}")
    print("Введите номер ключа (1–{}) или Enter = авто через 3 сек".format(len(API_KEYS)))

    result = [None]

    def ask():
        try:
            val = input("Номер ключа: ").strip()
            result[0] = val
        except Exception:
            pass

    t = threading.Thread(target=ask)
    t.daemon = True
    t.start()
    t.join(timeout=3)

    chosen = result[0]
    if chosen and chosen.isdigit():
        idx = int(chosen) - 1
        if 0 <= idx < len(API_KEYS):
            print(f"Выбран ключ #{idx + 1}")
            return idx, current_model_name
        else:
            print(f"Номер вне диапазона, беру ключ #{next_index + 1}")

    print(f"[Авто] Переключаюсь на ключ #{next_index + 1}/{len(API_KEYS)}")
    return next_index, current_model_name


def translate_chunk_with_retry(text, chunk_num, total, start_key_index=0, model_name=None):
    """
    Переводит один чанк текста, переключая ключи при ошибке.
    Возвращает (translated_text, success, final_key_index)
    """
    if model_name is None:
        model_name = current_model_name
    
    key_idx = start_key_index
    
    for mode in [0, 1, 2]:
        prompt = make_prompt(text, mode)
        
        while key_idx < len(API_KEYS):
            try:
                model = make_model(API_KEYS[key_idx], model_name)
                response = model.generate_content(prompt)
                print(f"Часть {chunk_num}/{total} переведена ✓ (ключ #{key_idx+1}, промпт {mode+1})")
                return response.text, True, key_idx
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower() or "location" in err.lower():
                    print(f"Ошибка квоты/региона в части {chunk_num} на ключе #{key_idx+1}")
                    key_idx += 1
                    if key_idx < len(API_KEYS):
                        print(f"Переключаюсь на ключ #{key_idx+1}")
                        time.sleep(1)
                        continue
                    else:
                        print(f"Все ключи исчерпаны для части {chunk_num}")
                        return None, False, key_idx
                if "PROHIBITED_CONTENT" in err or "block_reason" in err:
                    if mode < 2:
                        print(f"Часть {chunk_num} заблокирована, пробую промпт {mode+2}...")
                        time.sleep(5)
                        break  # break out of key loop, try next mode
                    else:
                        print(f"Часть {chunk_num} заблокирована всеми промптами.")
                        return None, False, key_idx
                print(f"Ошибка в части {chunk_num} на ключе #{key_idx+1}: {err}")
                if mode < 2:
                    print("Жду 30 секунд и пробую другой промпт...")
                    time.sleep(30)
                    break
                return None, False, key_idx
        
        # Если вышли из цикла по ключам, пробуем следующий промпт с того же ключа
        if key_idx >= len(API_KEYS):
            return None, False, key_idx
    
    return None, False, key_idx


def translate_paragraphs(paragraphs, model_name, start_key_index=0):
    """
    Переводит список абзацев пачками по CHUNK_SIZE символов.
    Возвращает список переведённых абзацев того же размера.
    НЕ ПРОПУСКАЕТ — повторяет неудачные батчи с новыми ключами.
    """
    # Группируем абзацы в чанки
    batches = []          # list of list of (idx, text)
    current_batch = []
    current_len = 0

    for i, p in enumerate(paragraphs):
        if not p or not p.strip():
            current_batch.append((i, ""))
            continue
        if current_len + len(p) > CHUNK_SIZE and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_len = 0
        current_batch.append((i, p))
        current_len += len(p) if p else 0
    if current_batch:
        batches.append(current_batch)

    total_batches = len(batches)
    results = [""] * len(paragraphs)
    current_key_idx = start_key_index

    batch_num = 0
    while batch_num < total_batches:
        batch = batches[batch_num]
        combined = "\n\n".join(p for _, p in batch if p)
        
        if not combined.strip():
            # Пустой батч — просто пропускаем
            for orig_idx, _ in batch:
                results[orig_idx] = ""
            batch_num += 1
            continue
        
        print(f"  Батч {batch_num + 1}/{total_batches} ({len(batch)} абзацев, {len(combined)} символов)")
        
        translated, success, new_key_idx = translate_chunk_with_retry(
            combined, batch_num + 1, total_batches, current_key_idx, model_name
        )
        
        if success and translated:
            # Разбиваем перевод обратно по абзацам (по двойному переносу)
            translated_parts = [p.strip() for p in translated.split("\n\n") if p.strip()]
            if len(translated_parts) == len(batch):
                for (orig_idx, _), t_text in zip(batch, translated_parts):
                    results[orig_idx] = t_text
            else:
                # Не совпало — кладём перевод целиком в первый абзац
                results[batch[0][0]] = translated
                print(f"    Предупреждение: несовпадение числа абзацев ({len(translated_parts)} vs {len(batch)})")
            batch_num += 1
            current_key_idx = new_key_idx
        else:
            print(f"  Батч {batch_num + 1} не удался. Повторяем попытку...")
            # Не увеличиваем batch_num — повторяем этот же батч
            if new_key_idx >= len(API_KEYS):
                print(f"  Все ключи исчерпаны. Невозможно продолжить.")
                break
            current_key_idx = new_key_idx
            time.sleep(3)
    
    return results


def translate_single_text(text, model_name, start_key_index=0):
    """Переводит один текст (заголовок или абзац) с переключением ключей."""
    if not text or not text.strip():
        return text
    
    translated, success, _ = translate_chunk_with_retry(
        text, 1, 1, start_key_index, model_name
    )
    return translated if success else text


def split_text(text, chunk_size):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            while end > start and text[end] != '\n':
                end -= 1
        chunks.append(text[start:end])
        start = end + 1
    return chunks


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return int(f.read().strip())
    return 0


def save_progress(chunk_num):
    with open(PROGRESS_FILE, 'w') as f:
        f.write(str(chunk_num))


# ══════════════════════════════════════════════
#  РЕЖИМЫ ПЕРЕВОДА (С ИСПРАВЛЕНИЯМИ)
# ══════════════════════════════════════════════

def run_normal_txt(chunks, start_from, output_file, key_index, model_name):
    """Обычный режим для TXT — одна модель"""
    total = len(chunks)
    current_key_index = key_index
    current_model_name = model_name

    mode = 'a' if start_from > 0 else 'w'
    with open(output_file, mode, encoding='utf-8') as out:
        i = start_from
        while i < total:
            translated, success, current_key_index = translate_chunk_with_retry(
                chunks[i], i + 1, total, current_key_index, current_model_name
            )
            if success and translated:
                out.write(translated + "\n")
                out.flush()
                save_progress(i + 1)
                i += 1
            else:
                print(f"Часть {i+1} не удалось перевести после всех ключей.")
                break
            time.sleep(15)

    print(f"\nПеревод сохранён: {output_file}")
    if load_progress() >= total:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
        print("Перевод завершён полностью!")


def run_epub(input_path, output_path, model_name, only_chapters=None):
    """
    only_chapters — список индексов глав (0-based) для частичного перевода.
    Если None — переводятся все главы.
    ГЛАВЫ НЕ ПЕРЕКЛЮЧАЮТСЯ, ПОКА ТЕКУЩАЯ НЕ ПЕРЕВЕДЕНА ПОЛНОСТЬЮ.
    """
    if not check_ebooklib():
        return
    print(f"\nЧитаем EPUB: {input_path}")
    book, chapters = read_epub(input_path)
    total_ch = len(chapters)
    print(f"Глав/разделов с текстом: {total_ch}")

    to_translate = only_chapters if only_chapters is not None else list(range(total_ch))
    translations_map = {}

    # Загружаем последнюю обрабатываемую главу
    last_chapter = 0
    if os.path.exists(PROGRESS_FILE_CHAPTER):
        try:
            with open(PROGRESS_FILE_CHAPTER, 'r') as f:
                last_chapter = int(f.read().strip())
        except:
            pass

    # Начинаем с сохранённой главы
    start_pos = 0
    for i, ch_idx in enumerate(to_translate):
        if ch_idx >= last_chapter:
            start_pos = i
            break

    i = start_pos
    current_key_idx = 0
    
    while i < len(to_translate):
        ch_idx = to_translate[i]
        if ch_idx >= total_ch:
            i += 1
            continue
        
        chapter = chapters[ch_idx]
        print(f"\n{'='*50}")
        print(f"=== Глава {ch_idx+1}/{total_ch}: {chapter['title']} "
              f"({len(chapter['paragraphs'])} абзацев) ===")
        print(f"{'='*50}")
        
        # Пытаемся перевести главу, пока не получится
        success = False
        max_attempts = len(API_KEYS) * 3
        attempt = 0
        
        while not success and attempt < max_attempts:
            translated_paras = translate_paragraphs(
                chapter["paragraphs"], model_name, current_key_idx
            )
            
            # Проверяем, успешно ли переведена глава (больше половины абзацев не пустые)
            non_empty = sum(1 for p in translated_paras if p and p.strip())
            if non_empty > len(chapter["paragraphs"]) * 0.5:
                translations_map[chapter["id"]] = translated_paras
                success = True
                # Сохраняем прогресс — какая глава завершена
                with open(PROGRESS_FILE_CHAPTER, 'w') as f:
                    f.write(str(ch_idx + 1))
            else:
                attempt += 1
                print(f"\n[!] Глава {ch_idx+1} переведена не полностью ({non_empty}/{len(chapter['paragraphs'])} абзацев).")
                print(f"    Повторная попытка {attempt}/{max_attempts}...")
                time.sleep(5)
        
        if success:
            i += 1
        else:
            print(f"\n[ОШИБКА] Глава {ch_idx+1} не переведена после {max_attempts} попыток.")
            print("Остановка. Запустите скрипт снова для продолжения.")
            break

    # Удаляем файл прогресса, если всё переведено
    if i >= len(to_translate) and os.path.exists(PROGRESS_FILE_CHAPTER):
        os.remove(PROGRESS_FILE_CHAPTER)

    print(f"\nСобираем EPUB...")
    rebuild_epub(book, chapters, translations_map, output_path)


def run_epub_parallel(input_path, output_path1, output_path2, model_name1, model_name2, only_chapters=None):
    """Параллельный перевод EPUB двумя моделями → два файла.
    ГЛАВЫ НЕ ПЕРЕКЛЮЧАЮТСЯ, ПОКА ТЕКУЩАЯ НЕ ПЕРЕВЕДЕНА.
    """
    if not check_ebooklib():
        return
    print(f"\nЧитаем EPUB: {input_path}")
    book1, chapters = read_epub(input_path)
    total_ch = len(chapters)
    print(f"Глав/разделов с текстом: {total_ch}")

    to_translate = only_chapters if only_chapters is not None else list(range(total_ch))

    map1 = {}
    map2 = {}

    for ch_idx in to_translate:
        if ch_idx >= total_ch:
            print(f"[!] Глава #{ch_idx+1} не существует, пропускаю")
            continue
        
        chapter = chapters[ch_idx]
        print(f"\n{'='*50}")
        print(f"=== Глава {ch_idx+1}/{total_ch}: {chapter['title']} "
              f"({len(chapter['paragraphs'])} абзацев) ===")
        print(f"{'='*50}")
        
        # Переводим главу моделью 1
        print(f"[{model_name1}] переводит...")
        success1 = False
        attempt1 = 0
        t1 = None
        while not success1 and attempt1 < len(API_KEYS) * 3:
            t1 = translate_paragraphs(chapter["paragraphs"], model_name1, 0)
            non_empty = sum(1 for p in t1 if p and p.strip())
            if non_empty > len(chapter["paragraphs"]) * 0.5:
                success1 = True
            else:
                attempt1 += 1
                print(f"  Повторная попытка {attempt1} для модели {model_name1}...")
                time.sleep(5)
        
        # Переводим главу моделью 2
        print(f"[{model_name2}] переводит...")
        success2 = False
        attempt2 = 0
        t2 = None
        while not success2 and attempt2 < len(API_KEYS) * 3:
            t2 = translate_paragraphs(chapter["paragraphs"], model_name2, 1)
            non_empty = sum(1 for p in t2 if p and p.strip())
            if non_empty > len(chapter["paragraphs"]) * 0.5:
                success2 = True
            else:
                attempt2 += 1
                print(f"  Повторная попытка {attempt2} для модели {model_name2}...")
                time.sleep(5)
        
        if success1 and t1:
            map1[chapter["id"]] = t1
        if success2 and t2:
            map2[chapter["id"]] = t2
        
        if not success1 or not success2:
            print(f"\n[ОШИБКА] Глава {ch_idx+1} не переведена полностью одной из моделей.")
            print("Остановка.")
            break

    book2, _ = read_epub(input_path)

    if map1:
        print(f"\nСобираем EPUB #1 ({model_name1})...")
        rebuild_epub(book1, chapters, map1, output_path1)
    if map2:
        print(f"\nСобираем EPUB #2 ({model_name2})...")
        rebuild_epub(book2, chapters, map2, output_path2)


def run_fb2(input_path, output_path, model_name, only_sections=None):
    """
    only_sections — список индексов секций верхнего уровня (0-based).
    Если None — переводятся все.
    СЕКЦИИ НЕ ПЕРЕКЛЮЧАЮТСЯ, ПОКА ТЕКУЩАЯ НЕ ПЕРЕВЕДЕНА ПОЛНОСТЬЮ.
    """
    print(f"\nЧитаем FB2: {input_path}")
    try:
        from lxml import etree
    except ImportError:
        try:
            import xml.etree.ElementTree as etree
        except:
            print("[!] lxml или xml.etree недоступны")
            return

    sections, tree, ns = read_fb2(input_path)
    flat = flatten_fb2_sections(sections)

    if only_sections is not None:
        # Фильтруем flat по первому элементу пути (индекс секции верхнего уровня)
        filtered_indices = [(i, item) for i, item in enumerate(flat) if item["path"][0] in only_sections]
        print(f"Секции {[s+1 for s in only_sections]}: {len(filtered_indices)} текстовых блоков из {len(flat)}")
        
        # Загружаем прогресс
        last_block = 0
        if os.path.exists(PROGRESS_FILE_FB2):
            try:
                with open(PROGRESS_FILE_FB2, 'r') as f:
                    last_block = int(f.read().strip())
            except:
                pass
        
        orig_texts = [item["text"] for item in flat]
        translated_texts = list(orig_texts)
        
        start_pos = max(last_block, 0)
        pos = start_pos
        current_key_idx = 0
        
        while pos < len(filtered_indices):
            orig_idx, item = filtered_indices[pos]
            print(f"\n--- Блок {pos+1}/{len(filtered_indices)} (секция {item['path'][0]+1}, {item['type']}) ---")
            
            translated = translate_single_text(item["text"], model_name, current_key_idx)
            
            if translated and translated != item["text"]:
                translated_texts[orig_idx] = translated
                with open(PROGRESS_FILE_FB2, 'w') as f:
                    f.write(str(pos + 1))
                pos += 1
            else:
                print(f"  Блок {pos+1} не переведён. Повторяем попытку...")
                time.sleep(5)
        
        if pos >= len(filtered_indices):
            print("\nСобираем FB2...")
            rebuild_fb2(input_path, output_path, translated_texts)
            if os.path.exists(PROGRESS_FILE_FB2):
                os.remove(PROGRESS_FILE_FB2)
        else:
            print(f"Прогресс сохранён. Запустите скрипт снова для продолжения.")
            
    else:
        # Для всей книги
        texts = [item["text"] for item in flat]
        print(f"Текстовых блоков: {len(texts)}")
        
        print("\nПереводим...")
        translated_texts = translate_paragraphs(texts, model_name, 0)
        rebuild_fb2(input_path, output_path, translated_texts)


def run_fb2_parallel(input_path, output_path1, output_path2, model_name1, model_name2, only_sections=None):
    """Параллельный перевод FB2 двумя моделями → два файла.
    СЕКЦИИ НЕ ПЕРЕКЛЮЧАЮТСЯ.
    """
    print(f"\nЧитаем FB2: {input_path}")
    sections, tree, ns = read_fb2(input_path)
    flat = flatten_fb2_sections(sections)

    if only_sections is not None:
        filtered_indices = [(i, item) for i, item in enumerate(flat) if item["path"][0] in only_sections]
        print(f"Секции {[s+1 for s in only_sections]}: {len(filtered_indices)} блоков")
        
        orig_texts = [item["text"] for item in flat]
        translated1 = list(orig_texts)
        translated2 = list(orig_texts)
        
        start_pos = 0
        if os.path.exists(PROGRESS_FILE_PARALLEL):
            try:
                with open(PROGRESS_FILE_PARALLEL, 'r') as f:
                    start_pos = int(f.read().strip())
            except:
                pass
        
        pos = start_pos
        while pos < len(filtered_indices):
            orig_idx, item = filtered_indices[pos]
            print(f"\n=== Блок {pos+1}/{len(filtered_indices)} (секция {item['path'][0]+1}) ===")
            
            print(f"[{model_name1}] переводит...")
            t1 = translate_single_text(item["text"], model_name1, 0)
            print(f"[{model_name2}] переводит...")
            t2 = translate_single_text(item["text"], model_name2, 1)
            
            if t1 and t1 != item["text"]:
                translated1[orig_idx] = t1
            if t2 and t2 != item["text"]:
                translated2[orig_idx] = t2
            
            with open(PROGRESS_FILE_PARALLEL, 'w') as f:
                f.write(str(pos + 1))
            pos += 1
        
        if pos >= len(filtered_indices):
            rebuild_fb2(input_path, output_path1, translated1)
            rebuild_fb2(input_path, output_path2, translated2)
            if os.path.exists(PROGRESS_FILE_PARALLEL):
                os.remove(PROGRESS_FILE_PARALLEL)
    else:
        texts = [item["text"] for item in flat]
        print(f"Текстовых блоков: {len(texts)}")
        
        print(f"\n[{model_name1}] переводит...")
        translated1 = translate_paragraphs(texts, model_name1, 0)
        print(f"\n[{model_name2}] переводит...")
        translated2 = translate_paragraphs(texts, model_name2, 1)
        
        print("\nСобираем FB2 #1...")
        rebuild_fb2(input_path, output_path1, translated1)
        print("Собираем FB2 #2...")
        rebuild_fb2(input_path, output_path2, translated2)


def run_parallel(chunks, output1, output2, model_name1, model_name2):
    """Параллельный режим — две модели, два файла (для TXT)"""
    total = len(chunks)
    current_key1 = 0
    current_key2 = 1

    with open(output1, 'w', encoding='utf-8') as f1, \
         open(output2, 'w', encoding='utf-8') as f2:
        for i in range(total):
            print(f"\n--- Часть {i+1}/{total} ---")
            
            print(f"[{model_name1}] переводит...")
            t1, success1, current_key1 = translate_chunk_with_retry(
                chunks[i], i+1, total, current_key1, model_name1
            )
            if t1:
                f1.write(t1 + "\n")
                f1.flush()
            
            time.sleep(15)
            
            print(f"[{model_name2}] переводит...")
            t2, success2, current_key2 = translate_chunk_with_retry(
                chunks[i], i+1, total, current_key2, model_name2
            )
            if t2:
                f2.write(t2 + "\n")
                f2.flush()
            
            time.sleep(15)

    print(f"\nГотово!\n  {model_name1}: {output1}\n  {model_name2}: {output2}")


# ══════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ВЫБОРА
# ══════════════════════════════════════════════

def parse_range_input(raw, total):
    """Разбирает строку вида '3', '2,5', '3-7' → список индексов 0-based."""
    indices = set()
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                a, b = int(bounds[0]), int(bounds[1])
                indices.update(range(a - 1, b))
        elif part.isdigit():
            indices.add(int(part) - 1)
    valid = sorted(i for i in indices if 0 <= i < total)
    if not valid:
        print("[!] Не удалось распознать номера, отмена.")
        return None
    return valid


def ask_chapter_range_epub(chapters):
    """Запрашивает у пользователя диапазон или конкретные номера глав EPUB."""
    total = len(chapters)
    print(f"\nДоступные главы ({total} шт.):")
    for i, ch in enumerate(chapters):
        para_count = len(ch["paragraphs"])
        title = ch.get("title", f"Глава {i+1}")
        if len(title) > 40:
            title = title[:37] + "..."
        print(f"  {i+1:3}. {title}  ({para_count} абз.)")
    print("\nВведите номера глав через запятую или диапазон (например: 3  или  2,5  или  3-7):")
    raw = input("Главы: ").strip()
    return parse_range_input(raw, total)


def ask_section_range_fb2(sections):
    """Запрашивает у пользователя диапазон секций FB2."""
    total = len(sections)
    print(f"\nДоступные секции верхнего уровня ({total} шт.):")
    for i, sec in enumerate(sections):
        title = sec.get("title") or f"(без названия)"
        n_par = len(sec.get("paragraphs", []))
        n_sub = len(sec.get("subsections", []))
        print(f"  {i+1:3}. {title[:40]}  ({n_par} абз., {n_sub} подсекций)")
    print("\nВведите номера секций через запятую или диапазон (например: 3  или  2,5  или  3-7):")
    raw = input("Секции: ").strip()
    return parse_range_input(raw, total)


# ══════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ
# ══════════════════════════════════════════════

print("=" * 50)
print("  Переводчик книг (TXT / EPUB / FB2)")
print("=" * 50)

input_file = input("\nПуть к файлу (Enter = book_full.txt): ").strip()
if not input_file:
    input_file = "book_full.txt"

if not os.path.exists(input_file):
    print(f"Файл не найден: {input_file}")
    sys.exit(1)

fmt = detect_format(input_file)
print(f"Определён формат: {fmt.upper()}")

# Имя выходного файла
base_name = os.path.splitext(input_file)[0]

if fmt == "epub":
    if not check_ebooklib():
        sys.exit(1)

    # Читаем главы заранее
    print(f"\nЧитаем список глав EPUB...")
    _book_preview, _chapters_preview = read_epub(input_file)
    total_chapters = len(_chapters_preview)
    print(f"Глав: {total_chapters}")

    print("\nРежим работы:")
    print("  1. Обычный перевод — вся книга (одна модель)")
    print("  2. Параллельный — вся книга (две модели → два файла)")
    print("  3. Перевод конкретных глав (одна модель)")
    print("  4. Параллельный — конкретные главы (две модели → два файла)")
    epub_mode = input("\nВаш выбор (1-4): ").strip()

    if epub_mode == "2":
        model1 = choose_model("модель 1")
        model2 = choose_model("модель 2")
        out1 = f"{base_name}_ru_{model1.replace('-','_')}.epub"
        out2 = f"{base_name}_ru_{model2.replace('-','_')}.epub"
        print(f"\nФайлы: {out1}  /  {out2}\n")
        run_epub_parallel(input_file, out1, out2, model1, model2)

    elif epub_mode == "3":
        sel = ask_chapter_range_epub(_chapters_preview)
        if sel:
            model_name = choose_model()
            suffix = f"_ch{'_'.join(str(i+1) for i in sel)}"
            output_path = f"{base_name}_ru{suffix}.epub"
            print(f"\nВыходной файл: {output_path}")
            run_epub(input_file, output_path, model_name, only_chapters=sel)

    elif epub_mode == "4":
        sel = ask_chapter_range_epub(_chapters_preview)
        if sel:
            model1 = choose_model("модель 1")
            model2 = choose_model("модель 2")
            suffix = f"_ch{'_'.join(str(i+1) for i in sel)}"
            out1 = f"{base_name}_ru{suffix}_{model1.replace('-','_')}.epub"
            out2 = f"{base_name}_ru{suffix}_{model2.replace('-','_')}.epub"
            print(f"\nФайлы: {out1}  /  {out2}\n")
            run_epub_parallel(input_file, out1, out2, model1, model2, only_chapters=sel)

    else:  # режим 1 по умолчанию
        model_name = choose_model()
        output_path = f"{base_name}_ru.epub"
        print(f"\nВыходной файл: {output_path}")
        print(f"Модель: {model_name}\n")
        run_epub(input_file, output_path, model_name)

elif fmt == "fb2":
    # Читаем секции заранее
    print(f"\nЧитаем структуру FB2...")
    _sections_preview, _, _ = read_fb2(input_file)
    total_sections = len(_sections_preview)
    print(f"Секций верхнего уровня: {total_sections}")

    print("\nРежим работы:")
    print("  1. Обычный перевод — вся книга (одна модель)")
    print("  2. Параллельный — вся книга (две модели → два файла)")
    print("  3. Перевод конкретных секций/глав (одна модель)")
    print("  4. Параллельный — конкретные секции/главы (две модели → два файла)")
    fb2_mode = input("\nВаш выбор (1-4): ").strip()

    if fb2_mode == "2":
        model1 = choose_model("модель 1")
        model2 = choose_model("модель 2")
        out1 = f"{base_name}_ru_{model1.replace('-','_')}.fb2"
        out2 = f"{base_name}_ru_{model2.replace('-','_')}.fb2"
        print(f"\nФайлы: {out1}  /  {out2}\n")
        run_fb2_parallel(input_file, out1, out2, model1, model2)

    elif fb2_mode == "3":
        sel = ask_section_range_fb2(_sections_preview)
        if sel:
            model_name = choose_model()
            suffix = f"_sec{'_'.join(str(i+1) for i in sel)}"
            output_path = f"{base_name}_ru{suffix}.fb2"
            print(f"\nВыходной файл: {output_path}")
            run_fb2(input_file, output_path, model_name, only_sections=sel)

    elif fb2_mode == "4":
        sel = ask_section_range_fb2(_sections_preview)
        if sel:
            model1 = choose_model("модель 1")
            model2 = choose_model("модель 2")
            suffix = f"_sec{'_'.join(str(i+1) for i in sel)}"
            out1 = f"{base_name}_ru{suffix}_{model1.replace('-','_')}.fb2"
            out2 = f"{base_name}_ru{suffix}_{model2.replace('-','_')}.fb2"
            print(f"\nФайлы: {out1}  /  {out2}\n")
            run_fb2_parallel(input_file, out1, out2, model1, model2, only_sections=sel)

    else:  # режим 1 по умолчанию
        model_name = choose_model()
        output_path = f"{base_name}_ru.fb2"
        print(f"\nВыходной файл: {output_path}")
        print(f"Модель: {model_name}\n")
        run_fb2(input_file, output_path, model_name)

elif fmt == "txt":
    # Функционал TXT
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    chunks = split_text(text, CHUNK_SIZE)
    total = len(chunks)
    print(f"Символов: {len(text)}, частей: {total}")

    OUTPUT_FILE = f"{base_name}_ru.txt"

    print("\nРежим работы:")
    print("  1. Обычный перевод (одна модель)")
    print("  2. Параллельный — вся книга (две модели)")
    print("  3. Параллельный — конкретная часть/глава")
    mode_choice = input("\nВаш выбор (1-3): ").strip()

    if mode_choice == "1":
        start_from = load_progress()
        if start_from > 0:
            print(f"\nПродолжаем с части {start_from + 1}/{total}")
        model_name = choose_model()
        print(f"\nКлюч #1, модель: {model_name}\n")
        run_normal_txt(chunks, start_from, OUTPUT_FILE, 0, model_name)

    elif mode_choice == "2":
        model1 = choose_model("модель 1")
        model2 = choose_model("модель 2")
        out1 = f"{base_name}_ru_{model1.replace('-','_')}.txt"
        out2 = f"{base_name}_ru_{model2.replace('-','_')}.txt"
        run_parallel(chunks, out1, out2, model1, model2)

    elif mode_choice == "3":
        print(f"\nВыберите единицу:")
        print("  1. По номеру части")
        print("  2. По номеру главы")
        unit_choice = input("\nВаш выбор (1-2): ").strip()

        if unit_choice == "1":
            part_num = int(input(f"Номер части (1–{total}): ").strip())
            if 1 <= part_num <= total:
                model1 = choose_model("модель 1")
                model2 = choose_model("модель 2")
                out1 = f"compare_part{part_num}_{model1.replace('-','_')}.txt"
                out2 = f"compare_part{part_num}_{model2.replace('-','_')}.txt"
                run_parallel([chunks[part_num-1]], out1, out2, model1, model2)

        elif unit_choice == "2":
            # Универсальный поиск глав на разных языках
            chapter_pattern = re.compile(
                r'^(?:KAPITEL|CHAPTER|CHAPITRE|CAPÍTULO|CAPITOLO|ГЛАВА)\s+\d+',
                re.MULTILINE | re.IGNORECASE
            )
            matches = list(chapter_pattern.finditer(text))
            if not matches:
                print("Не найдено глав в тексте. Попробуйте режим 'По номеру части'")
            else:
                print(f"Найдено глав: {len(matches)}")
                chap_num = int(input(f"Номер главы (1–{len(matches)}): ").strip())
                if 1 <= chap_num <= len(matches):
                    start = matches[chap_num-1].start()
                    end = matches[chap_num].start() if chap_num < len(matches) else len(text)
                    chap_text = text[start:end].strip()
                    chap_chunks = split_text(chap_text, CHUNK_SIZE)
                    model1 = choose_model("модель 1")
                    model2 = choose_model("модель 2")
                    out1 = f"compare_glava{chap_num}_{model1.replace('-','_')}.txt"
                    out2 = f"compare_glava{chap_num}_{model2.replace('-','_')}.txt"
                    run_parallel(chap_chunks, out1, out2, model1, model2)
else:
    print(f"Формат '{fmt}' не поддерживается. Используйте .txt, .epub или .fb2")
    sys.exit(1)