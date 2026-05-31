import google.generativeai as genai
import time
import os
import threading
import sys
import re

# Все API ключи
API_KEYS = [
    "AIzaSyCnrJfTGUIaXWajNc0eLT5coWc9Gb1okzY",
    "AIzaSyAmJdYHl_ggZZKA1XUqpNsNIgm8X8qoTv8",
    "AIzaSyB7ZNPhYFWTiuxumJbtGnRn2IGCx1EBKNc",
    "AIzaSyACEfZxO5eGXnnRlmxwEZ22jYq1XrDtwCE",
    "AIzaSyBeJ8ntOpdIDfelw9ZIAwTqLAPiSfx_AaQ",
    "AIzaSyB04gLtJkXRoxHTzpA-N4Aazum-2C2wkwU",
    "AIzaSyBeFCsJC7gZvF3fJPjFzI_rY1B1LHy2798",
    "AIzaSyAM5Lk1GFPyRFJG-V4WzyrwYSGBxYRc9Mg",
    "AIzaSyCgHTbU736NRZgB7z2_qJ-KHlQF8LMBm7c",
    "AIzaSyDhMtIsVTlhu_LJB5BPJVfKoc4S0ByljME",
]

PROGRESS_FILE = "translate_progress.txt"
PROGRESS_FILE_CHAPTER = "translate_progress_chapter.txt"
PROGRESS_FILE_FB2 = "translate_progress_fb2.txt"
PROGRESS_FILE_PARALLEL = "translate_progress_parallel.txt"
CHUNK_SIZE = 12000

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


def rebuild_fb2(original_path, output_path, translations, footnotes_list=None):
    """
    Берёт оригинальный FB2, заменяет текстовые узлы переводами, сохраняет структуру.
    translations — list: список переведённых текстов в порядке обхода
    footnotes_list — list of {"marker": str, "note": str} — сноски переводчика
    """
    try:
        from lxml import etree
        USE_LXML = True
    except ImportError:
        import xml.etree.ElementTree as etree
        USE_LXML = False

    with open(original_path, 'rb') as f:
        raw = f.read()

    tree = etree.parse(original_path)
    root = tree.getroot()
    ns_uri = ""
    tag = root.tag
    if tag.startswith("{"):
        ns_uri = tag.split("}")[0][1:]

    ns = f"{{{ns_uri}}}" if ns_uri else ""

    all_text_nodes = []

    def collect(el):
        local = el.tag.replace(ns, "")
        if local in ("p", "subtitle"):
            all_text_nodes.append(el)
        for child in el:
            collect(child)

    for body in root.findall(f"{ns}body"):
        collect(body)

    for idx, (el, translated) in enumerate(zip(all_text_nodes, translations)):
        if translated:
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
            src_lang = etree.SubElement(title_info, f"{ns}src-lang")
            src_lang.text = "da"
        # Переводим annotation если есть
        annot_el = title_info.find(f"{ns}annotation")
        if annot_el is not None:
            for p_el in annot_el.findall(f".//{ns}p"):
                pass  # уже обработано через collect

    # Добавляем сноски переводчика как отдельный body notes
    if footnotes_list:
        notes_body = etree.SubElement(root, f"{ns}body")
        notes_body.set("name", "notes")
        notes_title = etree.SubElement(notes_body, f"{ns}title")
        notes_title_p = etree.SubElement(notes_title, f"{ns}p")
        notes_title_p.text = "Примечания переводчика"

        for i, fn in enumerate(footnotes_list, 1):
            sec = etree.SubElement(notes_body, f"{ns}section")
            sec.set("id", f"note{i}")
            p = etree.SubElement(sec, f"{ns}p")
            marker_text = fn.get("marker", "")
            note_text = fn.get("note", "")
            p.text = f"{i}. {marker_text} — {note_text}"

        # Вставляем ссылки на сноски в текст
        # Ищем в переведённых параграфах маркеры и добавляем надстрочные индексы
        for i, fn in enumerate(footnotes_list, 1):
            marker = fn.get("marker", "")
            if not marker:
                continue
            for el in all_text_nodes:
                if el.text and marker[:20] in el.text:
                    # Добавляем сноску после текста параграфа
                    orig_text = el.text
                    el.text = orig_text
                    note_ref = etree.SubElement(el, f"{ns}a")
                    note_ref.set("l:href", f"#note{i}")
                    note_ref.set("type", "note")
                    note_ref.text = f"[{i}]"
                    note_ref.tail = ""
                    break

    if USE_LXML:
        tree.write(output_path, encoding='utf-8', xml_declaration=True,
                   pretty_print=True)
    else:
        tree.write(output_path, encoding='unicode', xml_declaration=False)

    print(f"FB2 сохранён: {output_path}")
    if footnotes_list:
        print(f"  Добавлено примечаний: {len(footnotes_list)}")



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


def rebuild_epub(book, chapters, translations_map, output_path, footnotes_by_chapter=None):
    """
    translations_map: {chapter_id: [translated_paragraph, ...]}
    footnotes_by_chapter: {chapter_id: [{"marker": str, "note": str}, ...]}
    """
    import ebooklib
    from ebooklib import epub
    try:
        from bs4 import BeautifulSoup
        USE_BS4 = True
    except ImportError:
        USE_BS4 = False
        print("[!] beautifulsoup4 не установлен, HTML структура может упроститься")

    if footnotes_by_chapter is None:
        footnotes_by_chapter = {}

    BLOCK_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'li', 'td', 'th', 'blockquote']

    # Глобальный счётчик сносок через всю книгу
    global_note_counter = [0]
    all_footnotes = []  # (note_id, marker, note_text)

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        ch_id = item.get_id()
        if ch_id not in translations_map:
            continue

        translated_paras = translations_map[ch_id]
        chapter_footnotes = footnotes_by_chapter.get(ch_id, [])
        html = item.get_content().decode('utf-8', errors='replace')

        if USE_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            all_tags = soup.find_all(BLOCK_TAGS)
            para_idx = 0
            for el in all_tags:
                text = el.get_text(strip=True)
                if text and para_idx < len(translated_paras):
                    translated_text = translated_paras[para_idx]
                    el.string = translated_text

                    # Проверяем, нужна ли сноска для этого параграфа
                    for fn in chapter_footnotes:
                        marker = fn.get("marker", "")
                        if marker and marker[:20] in translated_text:
                            global_note_counter[0] += 1
                            note_id = f"fn{global_note_counter[0]}"
                            all_footnotes.append((note_id, marker, fn.get("note", "")))
                            # Добавляем надстрочную ссылку
                            sup_tag = soup.new_tag("sup")
                            a_tag = soup.new_tag("a", href=f"../Text/footnotes.xhtml#{note_id}")
                            a_tag["epub:type"] = "noteref"
                            a_tag.string = str(global_note_counter[0])
                            sup_tag.append(a_tag)
                            el.append(sup_tag)

                    para_idx += 1
            new_html = str(soup).encode('utf-8')
        else:
            body = "\n".join(f"<p>{p}</p>" for p in translated_paras)
            new_html = f"<html><body>{body}</body></html>".encode('utf-8')

        item.set_content(new_html)

    # Создаём отдельный файл сносок если они есть
    if all_footnotes:
        fn_html = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="utf-8"/><title>Примечания переводчика</title>
<style>
  body { font-family: serif; margin: 2em; }
  .footnote { margin-bottom: 1em; }
  .fn-num { font-weight: bold; }
  .fn-marker { font-style: italic; color: #555; }
</style>
</head>
<body epub:type="backmatter">
<h2>Примечания переводчика</h2>
"""
        for (note_id, marker, note_text) in all_footnotes:
            fn_num = note_id.replace("fn", "")
            fn_html += f"""<div class="footnote" id="{note_id}" epub:type="footnote">
  <span class="fn-num">{fn_num}.</span>
  <span class="fn-marker"> {marker[:50]}{'...' if len(marker) > 50 else ''} —</span>
  {note_text}
</div>
"""
        fn_html += "</body></html>"

        fn_item = epub.EpubHtml(
            title="Примечания переводчика",
            file_name="Text/footnotes.xhtml",
            lang="ru",
            uid="footnotes"
        )
        fn_item.set_content(fn_html.encode('utf-8'))
        book.add_item(fn_item)
        book.spine.append(fn_item)
        print(f"  Добавлены примечания переводчика: {len(all_footnotes)} сносок")

    # Обновляем метаданные языка
    book.set_language("ru")

    # Переводим TOC (оглавление) если есть переводы заголовков в translations_map
    # ebooklib хранит TOC как список объектов Link/Section
    def _translate_toc_item(item, title_map):
        if hasattr(item, 'title') and item.title and item.href:
            # ищем совпадение по href среди переведённых глав
            for ch_id, translated_list in translations_map.items():
                pass  # title_map заполнен снаружи
            new_title = title_map.get(item.title)
            if new_title:
                item.title = new_title

    # Строим словарь оригинальный_заголовок → переведённый для глав которые мы перевели
    # Берём первый непустой переведённый абзац как «переведённый заголовок» только если
    # в оригинальном HTML этот элемент был h1-h6. Используем chapter title напрямую.
    toc_title_map = {}
    for ch in chapters:
        if ch["id"] in translations_map:
            orig_title = ch.get("title", "")
            translated_list = translations_map[ch["id"]]
            if orig_title and translated_list:
                # Первый переведённый элемент — это обычно заголовок главы
                first = next((p for p in translated_list if p and p.strip()), None)
                if first and first.strip() != orig_title:
                    toc_title_map[orig_title] = first.strip()

    def update_toc(toc_items):
        result = []
        for item in toc_items:
            if isinstance(item, tuple):
                section, children = item
                if hasattr(section, 'title') and section.title in toc_title_map:
                    section.title = toc_title_map[section.title]
                result.append((section, update_toc(children)))
            else:
                if hasattr(item, 'title') and item.title in toc_title_map:
                    item.title = toc_title_map[item.title]
                result.append(item)
        return result

    if book.toc:
        book.toc = update_toc(book.toc)

    epub.write_epub(output_path, book)
    print(f"EPUB сохранён: {output_path}")



# ══════════════════════════════════════════════
#  ПЕРЕВОДЧИК (общая логика)
# ══════════════════════════════════════════════

def make_prompt(text, mode=0):
    QUOTE_RULES = """- Прямую речь персонажей оформляй через тире: — Привет, — сказал он. НЕ используй кавычки «» для диалогов.
- Кавычки «» используй ТОЛЬКО для: названий книг/фильмов/газет, цитат внутри повествования, иностранных слов, прозвищ — то есть там где они действительно нужны по смыслу.
- Вложенные кавычки внутри кавычек: „вот так"."""

    if mode == 0:
        return f"""Переведи с датского на русский. Сохраняй стиль автора.
Правила:
- Первая буква абзаца заглавная, остальные слова строчными (кроме имён собственных)
- Слова написанные ЗАГЛАВНЫМИ БУКВАМИ переводи как обычные слова без капслока
{QUOTE_RULES}
- Верни только перевод без пояснений

Текст:
{text}"""
    elif mode == 1:
        return f"""Ты опытный переводчик художественной литературы.
Передай этот фрагмент на русском языке, сохраняя живой разговорный стиль и эмоции автора.
Первая буква абзаца заглавная, остальные слова строчными (кроме имён собственных).
Слова написанные ЗАГЛАВНЫМИ БУКВАМИ переводи как обычные слова без капслока.
{QUOTE_RULES}
Верни только перевод без пояснений.

Текст:
{text}"""
    else:
        return f"""Ты опытный переводчик художественной прозы с датского языка.
Выполни литературный перевод — передай характеры персонажей, атмосферу и интонацию автора, сохраняя живость и естественность речи.
Первая буква абзаца заглавная, остальные слова строчными (кроме имён собственных).
Слова написанные ЗАГЛАВНЫМИ БУКВАМИ переводи как обычные слова без капслока.
{QUOTE_RULES}
Верни только текст перевода без пояснений.

Фрагмент:
{text}"""


def make_title_prompt(text):
    """Промпт для перевода заголовков/оглавления."""
    return f"""Переведи с датского на русский название главы или раздела книги.
Правила:
- Верни ТОЛЬКО перевод, без кавычек, без пояснений
- Сохраняй регистр: если оригинал написан заглавными — сохрани заглавные
- Названия глав: первая буква заглавная, остальные строчные (кроме имён собственных)

Название:
{text}"""


def make_footnote_prompt(text):
    """Промпт для поиска культурных/исторических отсылок и генерации сносок."""
    return f"""Ты эрудированный редактор художественного перевода. Проверь текст на наличие отсылок, которые требуют пояснения для русскоязычного читателя.

Ищи:
- Исторические события, персонажи, мифы (например: «три мушкетера», «Дон Кихот», скандинавские саги)
- Культурные реалии Дании/Скандинавии (праздники, обычаи, топонимы с историей)
- Литературные/библейские цитаты или аллюзии
- Известные исторические личности, на которых намекается
- Устойчивые выражения с неочевидным происхождением

Для КАЖДОЙ найденной отсылки дай краткое фактическое пояснение (1-3 предложения), которое помогает понять смысл.

Формат ответа — строго JSON-массив (без markdown-обёртки):
[
  {{"marker": "точная цитата из текста (5-15 слов)", "note": "пояснение для читателя"}},
  ...
]

Если отсылок нет — верни пустой массив: []

Текст для анализа:
{text}"""


def choose_model(label="", current_model=None):
    opts = ", ".join(f"{k}={v}" for k, v in MODELS.items())
    suffix = f" [{label}]" if label else ""
    default_hint = f", Enter={current_model}" if current_model else ", Enter=gemini-2.0-flash"
    try:
        choice = input(f"Модель{suffix} ({opts}{default_hint}): ").strip()
    except:
        choice = ""
    if choice == "" and current_model:
        return current_model
    elif choice == "":
        return "gemini-2.0-flash"
    elif choice in MODELS:
        return MODELS[choice]
    else:
        return choice  # ввели название вручную


def choose_start_key():
    """Позволяет пользователю выбрать начальный API ключ."""
    try:
        val = input(f"Начальный ключ (1–{len(API_KEYS)}, Enter=1): ").strip()
    except:
        val = ""
    if val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < len(API_KEYS):
            return idx
    return 0


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


BATCH_PROGRESS_FILE = "translate_batch_progress.json"


def translate_paragraphs(paragraphs, model_name, start_key_index=0, progress_tag=None):
    """
    Переводит список абзацев пачками по CHUNK_SIZE символов.
    Возвращает список переведённых абзацев того же размера.
    НЕ ПРОПУСКАЕТ — повторяет неудачные батчи с новыми ключами.
    При KeyboardInterrupt ВОЗВРАЩАЕТ частично переведённый результат (не бросает исключение).
    progress_tag — уникальная метка (напр. chapter_id или "fb2_main") для сохранения
                   прогресса батчей на диск и восстановления после прерывания.
    """
    import json

    # Группируем абзацы в чанки
    batches = []
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
    results = list(paragraphs)  # начинаем с оригиналов
    current_key_idx = start_key_index

    # Загружаем сохранённый прогресс если есть
    start_batch = 0
    if progress_tag and os.path.exists(BATCH_PROGRESS_FILE):
        try:
            with open(BATCH_PROGRESS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if saved.get("tag") == progress_tag and saved.get("total") == len(paragraphs):
                saved_results = saved.get("results", [])
                saved_batch = saved.get("batch_num", 0)
                if saved_results and len(saved_results) == len(paragraphs) and saved_batch > 0:
                    results = saved_results
                    start_batch = saved_batch
                    print(f"  [Прогресс] Восстанавливаем с батча {start_batch + 1}/{total_batches} "
                          f"(уже переведено ~{saved_batch * CHUNK_SIZE // 500} абз.)")
        except Exception:
            pass  # битый файл — начинаем сначала

    def save_batch_progress(batch_num):
        if not progress_tag:
            return
        try:
            with open(BATCH_PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "tag": progress_tag,
                    "total": len(paragraphs),
                    "batch_num": batch_num,
                    "results": results,
                }, f, ensure_ascii=False)
        except Exception as e:
            print(f"  [!] Не удалось сохранить прогресс батча: {e}")

    def clear_batch_progress():
        if progress_tag and os.path.exists(BATCH_PROGRESS_FILE):
            try:
                os.remove(BATCH_PROGRESS_FILE)
            except Exception:
                pass

    batch_num = start_batch
    interrupted = False
    try:
        while batch_num < total_batches:
            batch = batches[batch_num]
            combined = "\n\n".join(p for _, p in batch if p)

            if not combined.strip():
                for orig_idx, _ in batch:
                    results[orig_idx] = ""
                batch_num += 1
                continue

            print(f"  Батч {batch_num + 1}/{total_batches} ({len(batch)} абзацев, {len(combined)} символов) | Ключ #{current_key_idx+1}")

            translated, success, new_key_idx = translate_chunk_with_retry(
                combined, batch_num + 1, total_batches, current_key_idx, model_name
            )

            if success and translated:
                translated_parts = [p.strip() for p in translated.split("\n\n") if p.strip()]
                if len(translated_parts) == len([x for x in batch if x[1]]):
                    pidx = 0
                    for (orig_idx, orig_text) in batch:
                        if orig_text:
                            results[orig_idx] = translated_parts[pidx]
                            pidx += 1
                        else:
                            results[orig_idx] = ""
                else:
                    results[batch[0][0]] = translated
                    print(f"    Предупреждение: несовпадение числа абзацев ({len(translated_parts)} vs {len(batch)})")
                batch_num += 1
                current_key_idx = new_key_idx
                # Сохраняем прогресс на диск после каждого успешного батча
                save_batch_progress(batch_num)
            else:
                print(f"  Батч {batch_num + 1} не удался. Повторяем попытку...")
                if new_key_idx >= len(API_KEYS):
                    print(f"  Все ключи исчерпаны. Невозможно продолжить.")
                    break
                current_key_idx = new_key_idx
                time.sleep(3)
    except KeyboardInterrupt:
        print(f"\n[!] Прерывание — сохранено {batch_num}/{total_batches} батчей. "
              f"При следующем запуске продолжим с батча {batch_num + 1}.")
        save_batch_progress(batch_num)
        interrupted = True

    if not interrupted:
        clear_batch_progress()

    return results, interrupted


def translate_single_text(text, model_name, start_key_index=0):
    """Переводит один текст (заголовок или абзац) с переключением ключей."""
    if not text or not text.strip():
        return text
    
    translated, success, _ = translate_chunk_with_retry(
        text, 1, 1, start_key_index, model_name
    )
    return translated if (success and translated) else text


def translate_title(text, model_name, start_key_index=0):
    """Переводит заголовок главы/раздела с правильным промптом."""
    if not text or not text.strip():
        return text
    key_idx = start_key_index
    prompt = make_title_prompt(text)
    while key_idx < len(API_KEYS):
        try:
            model = make_model(API_KEYS[key_idx], model_name)
            response = model.generate_content(prompt)
            result = response.text.strip().strip('«»"\'')
            print(f"  Заголовок переведён: «{result}»")
            return result
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                key_idx += 1
                time.sleep(1)
                continue
            print(f"  Ошибка перевода заголовка: {err}")
            return text
    return text


def find_footnotes(translated_text, model_name, start_key_index=0):
    """
    Анализирует переведённый текст и возвращает список сносок.
    Возвращает: list of {"marker": str, "note": str}
    """
    if not translated_text or len(translated_text.strip()) < 100:
        return []

    import json
    key_idx = start_key_index
    prompt = make_footnote_prompt(translated_text)

    while key_idx < len(API_KEYS):
        try:
            model = make_model(API_KEYS[key_idx], model_name)
            response = model.generate_content(prompt)
            raw = response.text.strip()
            # Убираем возможные markdown-блоки
            raw = raw.replace("```json", "").replace("```", "").strip()
            footnotes = json.loads(raw)
            if isinstance(footnotes, list) and footnotes:
                print(f"  Найдено сносок: {len(footnotes)}")
                for fn in footnotes:
                    print(f"    → «{fn.get('marker','')[:40]}»")
            return footnotes if isinstance(footnotes, list) else []
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                key_idx += 1
                time.sleep(1)
                continue
            # JSON parse error или другие — возвращаем пусто, не критично
            return []
    return []



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
            time.sleep(3)

    print(f"\nПеревод сохранён: {output_file}")
    if load_progress() >= total:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
        print("Перевод завершён полностью!")


def run_epub(input_path, output_path, model_name, only_chapters=None, start_key_idx=0, enable_footnotes=False):
    """
    only_chapters — список индексов глав (0-based) для частичного перевода.
    Если None — переводятся все главы.
    start_key_idx — начальный индекс ключа (не сбрасывается после успешного перевода).
    enable_footnotes — искать культурные/исторические отсылки и добавлять сноски.
    """
    if not check_ebooklib():
        return
    print(f"\nЧитаем EPUB: {input_path}")
    book, chapters = read_epub(input_path)
    total_ch = len(chapters)
    print(f"Глав/разделов с текстом: {total_ch}")

    to_translate = only_chapters if only_chapters is not None else list(range(total_ch))
    translations_map = {}
    footnotes_by_chapter = {}

    last_chapter = 0
    if os.path.exists(PROGRESS_FILE_CHAPTER):
        try:
            with open(PROGRESS_FILE_CHAPTER, 'r') as f:
                last_chapter = int(f.read().strip())
            print(f"[Прогресс] Продолжаем с главы #{last_chapter + 1}")
        except:
            pass

    # При возобновлении — загружаем уже переведённые главы из partial epub
    partial_path = output_path.replace(".epub", "_partial.epub")
    if last_chapter > 0 and os.path.exists(partial_path):
        print(f"[Прогресс] Загружаем переведённые главы из: {partial_path}")
        try:
            import ebooklib
            from ebooklib import epub as epub_mod
            from bs4 import BeautifulSoup
            partial_book = epub_mod.read_epub(partial_path)
            for item in partial_book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                ch_id = item.get_id()
                # Проверяем, нужна ли эта глава
                matching = [c for c in chapters if c["id"] == ch_id]
                if not matching:
                    continue
                ch = matching[0]
                html = item.get_content().decode('utf-8', errors='replace')
                soup = BeautifulSoup(html, 'html.parser')
                BLOCK_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'blockquote']
                paras = [el.get_text(strip=True) for el in soup.find_all(BLOCK_TAGS) if el.get_text(strip=True)]
                if paras and len(paras) >= len(ch["paragraphs"]) * 0.5:
                    translations_map[ch_id] = paras
            print(f"[Прогресс] Загружено {len(translations_map)} глав из partial файла")
        except Exception as e:
            print(f"[!] Не удалось загрузить partial: {e}. Начинаем с нуля.")
            translations_map = {}
            last_chapter = 0

    start_pos = 0
    if last_chapter > 0:
        for i, ch_idx in enumerate(to_translate):
            if ch_idx + 1 > last_chapter:  # прогресс = ch_idx+1 последней переведённой
                start_pos = i
                break
        else:
            start_pos = len(to_translate)  # всё уже переведено

    i = start_pos
    current_key_idx = start_key_idx

    def save_partial():
        if translations_map:
            partial_path = output_path.replace(".epub", "_partial.epub")
            print(f"\n[Сохранение] Сохраняем {len(translations_map)} переведённых глав в: {partial_path}")
            try:
                rebuild_epub(book, chapters, translations_map, partial_path, footnotes_by_chapter)
                print(f"[OK] Частичный EPUB сохранён: {partial_path}")
            except Exception as e:
                print(f"[!] Ошибка сохранения частичного EPUB: {e}")
        else:
            print("[!] Нет переведённых глав для сохранения.")

    try:
        while i < len(to_translate):
            ch_idx = to_translate[i]
            if ch_idx >= total_ch:
                i += 1
                continue

            chapter = chapters[ch_idx]
            print(f"\n{'='*50}")
            print(f"=== Глава {ch_idx+1}/{total_ch}: {chapter['title']} "
                  f"({len(chapter['paragraphs'])} абзацев) | Ключ #{current_key_idx+1} ===")
            print(f"{'='*50}")

            success = False
            max_attempts = len(API_KEYS) * 3
            attempt = 0
            progress_tag = f"epub_{chapter['id']}"
            progress_tag = f"epub_{chapter['id']}"

            while not success and attempt < max_attempts:
                translated_paras, was_interrupted = translate_paragraphs(
                    chapter["paragraphs"], model_name, current_key_idx,
                    progress_tag=progress_tag
                )

                # Ctrl+C внутри translate_paragraphs — немедленно сохраняем и выходим
                if was_interrupted:
                    non_empty = sum(1 for p in translated_paras if p and p.strip())
                    print(f"\n[Ctrl+C] Прерывание. Сохраняем частично переведённую главу {ch_idx+1} "
                          f"({non_empty}/{len(chapter['paragraphs'])} абз.) и выходим.")
                    if non_empty > 0:
                        translations_map[chapter["id"]] = translated_paras
                    save_partial()
                    return

                non_empty = sum(1 for p in translated_paras if p and p.strip())
                if non_empty > len(chapter["paragraphs"]) * 0.5:
                    translations_map[chapter["id"]] = translated_paras
                    success = True

                    # Ищем сноски если включено
                    if enable_footnotes:
                        print(f"  Анализируем текст главы на культурные/исторические отсылки...")
                        combined_text = "\n\n".join(p for p in translated_paras if p)
                        footnotes = find_footnotes(combined_text, model_name, current_key_idx)
                        if footnotes:
                            footnotes_by_chapter[chapter["id"]] = footnotes

                    with open(PROGRESS_FILE_CHAPTER, 'w') as f:
                        f.write(str(ch_idx + 1))
                    print(f"[OK] Глава {ch_idx+1} переведена (ключ #{current_key_idx+1})")
                else:
                    attempt += 1
                    print(f"\n[!] Глава {ch_idx+1} переведена не полностью ({non_empty}/{len(chapter['paragraphs'])} абзацев).")
                    print(f"    Повторная попытка {attempt}/{max_attempts}...")
                    time.sleep(5)

            if success:
                i += 1
            else:
                print(f"\n[ОШИБКА] Глава {ch_idx+1} не переведена после {max_attempts} попыток.")
                print("Сохраняем частичный результат и останавливаемся.")
                save_partial()
                return

    except Exception as e:
        print(f"\n[ОШИБКА] Неожиданная ошибка: {e}")
        save_partial()
        return

    if i >= len(to_translate) and os.path.exists(PROGRESS_FILE_CHAPTER):
        os.remove(PROGRESS_FILE_CHAPTER)

    print(f"\nСобираем финальный EPUB...")
    rebuild_epub(book, chapters, translations_map, output_path, footnotes_by_chapter)
    partial_path = output_path.replace(".epub", "_partial.epub")
    if os.path.exists(partial_path):
        os.remove(partial_path)



def run_epub_parallel(input_path, output_path1, output_path2, model_name1, model_name2, only_chapters=None, start_key_idx=0, enable_footnotes=False):
    """Параллельный перевод EPUB двумя моделями → два файла.
    ГЛАВЫ НЕ ПЕРЕКЛЮЧАЮТСЯ, ПОКА ТЕКУЩАЯ НЕ ПЕРЕВЕДЕНА.
    Ключ не сбрасывается после успешного перевода. Сохраняет при Ctrl+C.
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
    current_key_idx = start_key_idx

    def save_partial():
        book2_p, _ = read_epub(input_path)
        partial1 = output_path1.replace(".epub", "_partial.epub")
        partial2 = output_path2.replace(".epub", "_partial.epub")
        if map1:
            print(f"[Сохранение] {partial1}")
            try:
                rebuild_epub(book1, chapters, map1, partial1)
            except Exception as e:
                print(f"[!] Ошибка сохранения: {e}")
        if map2:
            print(f"[Сохранение] {partial2}")
            try:
                rebuild_epub(book2_p, chapters, map2, partial2)
            except Exception as e:
                print(f"[!] Ошибка сохранения: {e}")

    try:
        for ch_idx in to_translate:
            if ch_idx >= total_ch:
                print(f"[!] Глава #{ch_idx+1} не существует, пропускаю")
                continue

            chapter = chapters[ch_idx]
            print(f"\n{'='*50}")
            print(f"=== Глава {ch_idx+1}/{total_ch}: {chapter['title']} "
                  f"({len(chapter['paragraphs'])} абзацев) | Ключ #{current_key_idx+1} ===")
            print(f"{'='*50}")

            # Переводим главу моделью 1
            print(f"[{model_name1}] переводит...")
            success1 = False
            attempt1 = 0
            t1 = None
            while not success1 and attempt1 < len(API_KEYS) * 3:
                t1, was_interrupted = translate_paragraphs(chapter["paragraphs"], model_name1, current_key_idx)
                if was_interrupted:
                    print(f"\n[Ctrl+C] Прерывание при переводе моделью {model_name1}.")
                    save_partial()
                    return
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
                t2, was_interrupted = translate_paragraphs(chapter["paragraphs"], model_name2, current_key_idx)
                if was_interrupted:
                    print(f"\n[Ctrl+C] Прерывание при переводе моделью {model_name2}.")
                    save_partial()
                    return
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
                print("Сохраняем частичный результат и останавливаемся.")
                save_partial()
                return

    except KeyboardInterrupt:
        print(f"\n\n[Ctrl+C] Перевод прерван пользователем.")
        save_partial()
        return

    book2, _ = read_epub(input_path)

    if map1:
        print(f"\nСобираем EPUB #1 ({model_name1})...")
        rebuild_epub(book1, chapters, map1, output_path1)
    if map2:
        print(f"\nСобираем EPUB #2 ({model_name2})...")
        rebuild_epub(book2, chapters, map2, output_path2)
    # Чистим partial если были
    for p in [output_path1.replace(".epub", "_partial.epub"), output_path2.replace(".epub", "_partial.epub")]:
        if os.path.exists(p):
            os.remove(p)


def run_fb2(input_path, output_path, model_name, only_sections=None, start_key_idx=0, enable_footnotes=False):
    """
    only_sections — список индексов секций верхнего уровня (0-based).
    Если None — переводятся все.
    start_key_idx — начальный ключ (не сбрасывается после успешного перевода).
    enable_footnotes — искать культурные/исторические отсылки и добавлять сноски.
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

    # Переводим заголовки верхнего уровня книги (метаданные)
    _translate_fb2_book_title(input_path, model_name, start_key_idx)

    def save_partial_fb2(translated_texts, footnotes_list=None):
        partial_path = output_path.replace(".fb2", "_partial.fb2")
        print(f"\n[Сохранение] Сохраняем частичный результат в: {partial_path}")
        try:
            rebuild_fb2(input_path, partial_path, translated_texts, footnotes_list)
            print(f"[OK] Частичный FB2 сохранён: {partial_path}")
        except Exception as e:
            print(f"[!] Ошибка сохранения частичного FB2: {e}")

    if only_sections is not None:
        filtered_indices = [(i, item) for i, item in enumerate(flat) if item["path"][0] in only_sections]
        print(f"Секции {[s+1 for s in only_sections]}: {len(filtered_indices)} текстовых блоков из {len(flat)}")

        orig_texts = [item["text"] for item in flat]
        translated_texts = list(orig_texts)

        batch_texts = [item["text"] for _, item in filtered_indices]
        print(f"\nПереводим {len(batch_texts)} блоков батчами...")
        batch_translated, was_interrupted = translate_paragraphs(
            batch_texts, model_name, start_key_idx,
            progress_tag="fb2_sections"
        )
        for (orig_idx, _), t in zip(filtered_indices, batch_translated):
            if t and t.strip():
                translated_texts[orig_idx] = t

        if was_interrupted:
            print("\n[Ctrl+C] Сохраняем частичный результат и выходим.")
            save_partial_fb2(translated_texts)
            return

        footnotes_list = []
        if enable_footnotes:
            print("\nАнализируем текст на культурные/исторические отсылки...")
            combined = "\n\n".join(t for t in translated_texts if t)
            footnotes_list = find_footnotes(combined, model_name, start_key_idx)

        print("\nСобираем FB2...")
        rebuild_fb2(input_path, output_path, translated_texts, footnotes_list if enable_footnotes else None)
        if os.path.exists(PROGRESS_FILE_FB2):
            os.remove(PROGRESS_FILE_FB2)

    else:
        texts = [item["text"] for item in flat]
        print(f"Текстовых блоков: {len(texts)}")

        print("\nПереводим...")
        translated_texts, was_interrupted = translate_paragraphs(
            texts, model_name, start_key_idx,
            progress_tag="fb2_main"
        )

        if was_interrupted:
            print("\n[Ctrl+C] Сохраняем частичный результат и выходим.")
            save_partial_fb2(translated_texts)
            return

        footnotes_list = []
        if enable_footnotes:
            print("\nАнализируем текст на культурные/исторические отсылки...")
            combined = "\n\n".join(t for t in translated_texts if t)
            footnotes_list = find_footnotes(combined, model_name, start_key_idx)

        save_partial_path = output_path.replace(".fb2", "_partial.fb2")
        rebuild_fb2(input_path, output_path, translated_texts, footnotes_list if enable_footnotes else None)
        if os.path.exists(save_partial_path):
            os.remove(save_partial_path)


def _translate_fb2_book_title(input_path, model_name, start_key_idx=0):
    """Переводит метаданные книги в FB2: название, аннотацию."""
    try:
        from lxml import etree
        USE_LXML = True
    except ImportError:
        import xml.etree.ElementTree as etree
        USE_LXML = False

    tree = etree.parse(input_path)
    root = tree.getroot()
    ns_uri = ""
    tag = root.tag
    if tag.startswith("{"):
        ns_uri = tag.split("}")[0][1:]
    ns = f"{{{ns_uri}}}" if ns_uri else ""

    title_info = root.find(f".//{ns}title-info")
    if title_info is None:
        return

    changed = False
    # Переводим название книги
    book_title_el = title_info.find(f"{ns}book-title")
    if book_title_el is not None and book_title_el.text:
        orig = book_title_el.text.strip()
        print(f"\nПереводим название книги: «{orig}»")
        translated = translate_title(orig, model_name, start_key_idx)
        if translated and translated != orig:
            book_title_el.text = translated
            changed = True

    # Переводим аннотацию
    annotation_el = title_info.find(f"{ns}annotation")
    if annotation_el is not None:
        para_texts = []
        para_els = []
        for p_el in annotation_el.findall(f".//{ns}p"):
            t = "".join(p_el.itertext()).strip()
            if t:
                para_texts.append(t)
                para_els.append(p_el)

        if para_texts:
            print(f"Переводим аннотацию ({len(para_texts)} абзацев)...")
            translated_annot, _ = translate_paragraphs(para_texts, model_name, start_key_idx)
            for p_el, t in zip(para_els, translated_annot):
                if t and t.strip():
                    p_el.text = t
                    changed = True

    if changed:
        if USE_LXML:
            tree.write(input_path, encoding='utf-8', xml_declaration=True, pretty_print=True)
        else:
            tree.write(input_path, encoding='unicode', xml_declaration=False)



def run_fb2_parallel(input_path, output_path1, output_path2, model_name1, model_name2, only_sections=None, enable_footnotes=False):
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

        batch_texts = [item["text"] for _, item in filtered_indices]
        print(f"\n[{model_name1}] переводит {len(batch_texts)} блоков батчами...")
        bt1, _ = translate_paragraphs(batch_texts, model_name1, 0)
        print(f"\n[{model_name2}] переводит {len(batch_texts)} блоков батчами...")
        bt2, _ = translate_paragraphs(batch_texts, model_name2, 1)

        for (orig_idx, _), t1, t2 in zip(filtered_indices, bt1, bt2):
            if t1 and t1.strip():
                translated1[orig_idx] = t1
            if t2 and t2.strip():
                translated2[orig_idx] = t2

        rebuild_fb2(input_path, output_path1, translated1)
        rebuild_fb2(input_path, output_path2, translated2)
    else:
        texts = [item["text"] for item in flat]
        print(f"Текстовых блоков: {len(texts)}")
        
        print(f"\n[{model_name1}] переводит...")
        translated1, _ = translate_paragraphs(texts, model_name1, 0)
        print(f"\n[{model_name2}] переводит...")
        translated2, _ = translate_paragraphs(texts, model_name2, 1)
        
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
            
            time.sleep(3)
            
            print(f"[{model_name2}] переводит...")
            t2, success2, current_key2 = translate_chunk_with_retry(
                chunks[i], i+1, total, current_key2, model_name2
            )
            if t2:
                f2.write(t2 + "\n")
                f2.flush()
            
            time.sleep(3)

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

base_name = os.path.splitext(input_file)[0]

# Спрашиваем про сноски (для EPUB и FB2)
enable_footnotes = False
if fmt in ("epub", "fb2"):
    fn_choice = input("Примечания переводчика (y/N): ").strip().lower()
    enable_footnotes = fn_choice in ("y", "yes", "да", "д")
if fmt == "epub":
    if not check_ebooklib():
        sys.exit(1)

    print("Читаем список глав EPUB...")
    _book_preview, _chapters_preview = read_epub(input_file)
    total_chapters = len(_chapters_preview)
    print(f"Глав: {total_chapters}")

    print("Режим работы:")
    print("  1. Обычный перевод — вся книга (одна модель)")
    print("  2. Параллельный — вся книга (две модели → два файла)")
    print("  3. Перевод конкретных глав (одна модель)")
    print("  4. Параллельный — конкретные главы (две модели → два файла)")
    epub_mode = input("Режим (1-4): ").strip()

    if epub_mode == "2":
        model1 = choose_model("модель 1")
        model2 = choose_model("модель 2")
        start_key = choose_start_key()
        out1 = f"{base_name}_ru_{model1.replace('-','_')}.epub"
        out2 = f"{base_name}_ru_{model2.replace('-','_')}.epub"
        print(f"Файлы: {out1} / {out2}")
        run_epub_parallel(input_file, out1, out2, model1, model2, start_key_idx=start_key, enable_footnotes=enable_footnotes)

    elif epub_mode == "3":
        sel = ask_chapter_range_epub(_chapters_preview)
        if sel:
            model_name = choose_model()
            start_key = choose_start_key()
            suffix = f"_ch{'_'.join(str(i+1) for i in sel)}"
            output_path = f"{base_name}_ru{suffix}.epub"
            print(f"Выходной файл: {output_path}")
            run_epub(input_file, output_path, model_name, only_chapters=sel, start_key_idx=start_key, enable_footnotes=enable_footnotes)

    elif epub_mode == "4":
        sel = ask_chapter_range_epub(_chapters_preview)
        if sel:
            model1 = choose_model("модель 1")
            model2 = choose_model("модель 2")
            start_key = choose_start_key()
            suffix = f"_ch{'_'.join(str(i+1) for i in sel)}"
            out1 = f"{base_name}_ru{suffix}_{model1.replace('-','_')}.epub"
            out2 = f"{base_name}_ru{suffix}_{model2.replace('-','_')}.epub"
            print(f"Файлы: {out1} / {out2}")
            run_epub_parallel(input_file, out1, out2, model1, model2, only_chapters=sel, start_key_idx=start_key, enable_footnotes=enable_footnotes)

    else:  # режим 1 по умолчанию
        model_name = choose_model()
        start_key = choose_start_key()
        output_path = f"{base_name}_ru.epub"
        print(f"Выходной файл: {output_path}")
        print(f"Модель: {model_name} | Ключ: #{start_key+1}")
        run_epub(input_file, output_path, model_name, start_key_idx=start_key, enable_footnotes=enable_footnotes)

elif fmt == "fb2":
    print("Читаем структуру FB2...")
    _sections_preview, _, _ = read_fb2(input_file)
    total_sections = len(_sections_preview)
    print(f"Секций верхнего уровня: {total_sections}")

    print("Режим работы:")
    print("  1. Обычный перевод — вся книга (одна модель)")
    print("  2. Параллельный — вся книга (две модели → два файла)")
    print("  3. Перевод конкретных секций/глав (одна модель)")
    print("  4. Параллельный — конкретные секции/главы (две модели → два файла)")
    fb2_mode = input("Режим (1-4): ").strip()

    if fb2_mode == "2":
        model1 = choose_model("модель 1")
        model2 = choose_model("модель 2")
        start_key = choose_start_key()
        out1 = f"{base_name}_ru_{model1.replace('-','_')}.fb2"
        out2 = f"{base_name}_ru_{model2.replace('-','_')}.fb2"
        print(f"Файлы: {out1} / {out2}")
        run_fb2_parallel(input_file, out1, out2, model1, model2, enable_footnotes=enable_footnotes)

    elif fb2_mode == "3":
        sel = ask_section_range_fb2(_sections_preview)
        if sel:
            model_name = choose_model()
            start_key = choose_start_key()
            suffix = f"_sec{'_'.join(str(i+1) for i in sel)}"
            output_path = f"{base_name}_ru{suffix}.fb2"
            print(f"Выходной файл: {output_path}")
            run_fb2(input_file, output_path, model_name, only_sections=sel, start_key_idx=start_key, enable_footnotes=enable_footnotes)

    elif fb2_mode == "4":
        sel = ask_section_range_fb2(_sections_preview)
        if sel:
            model1 = choose_model("модель 1")
            model2 = choose_model("модель 2")
            start_key = choose_start_key()
            suffix = f"_sec{'_'.join(str(i+1) for i in sel)}"
            out1 = f"{base_name}_ru{suffix}_{model1.replace('-','_')}.fb2"
            out2 = f"{base_name}_ru{suffix}_{model2.replace('-','_')}.fb2"
            print(f"Файлы: {out1} / {out2}")
            run_fb2_parallel(input_file, out1, out2, model1, model2, only_sections=sel, enable_footnotes=enable_footnotes)

    else:  # режим 1 по умолчанию
        model_name = choose_model()
        start_key = choose_start_key()
        output_path = f"{base_name}_ru.fb2"
        print(f"Выходной файл: {output_path}")
        print(f"Модель: {model_name} | Ключ: #{start_key+1}")
        run_fb2(input_file, output_path, model_name, start_key_idx=start_key, enable_footnotes=enable_footnotes)

elif fmt == "txt":
    # Функционал TXT
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    chunks = split_text(text, CHUNK_SIZE)
    total = len(chunks)
    print(f"Символов: {len(text)}, частей: {total}")

    OUTPUT_FILE = f"{base_name}_ru.txt"

    print("Режим работы:")
    print("  1. Обычный перевод (одна модель)")
    print("  2. Параллельный — вся книга (две модели)")
    print("  3. Параллельный — конкретная часть/глава")
    mode_choice = input("Режим (1-3): ").strip()

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