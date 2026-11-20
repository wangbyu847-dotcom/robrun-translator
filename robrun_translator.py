# -*- coding: utf-8 -*-
"""
ROB RUN 实时屏幕翻译工具（免费版）
================================================
这是什么？
    一个 Windows 上的实时屏幕翻译小工具，专门给没有中文的 Steam 游戏
    ROB RUN 用的。游戏画面上的英文会被实时认出来、翻成中文，
    再用悬浮窗盖在原文的位置上，看起来就像游戏自带中文一样。

原理（和 LagoFast 翻译工具完全一样）：
    截屏 -> OCR 认字 -> 机器翻译 -> 悬浮窗显示
    全程只"看"屏幕像素，不改游戏文件、不注入 DLL、不读游戏内存，
    所以内核级反作弊（Easy Anti-Cheat）不会拦它，也不会封号。

全部依赖都是免费公开库，不需要任何 API key，不需要付费：
    mss                  截屏
    rapidocr-onnxruntime OCR 认字（离线，不用联网）
    deep-translator      翻译（MyMemory 免费接口主用，Google 备用，都不要 key）
    pillow               图片处理
    pynput               全局快捷键
    tkinter              悬浮窗（Python 自带）

用法：
    双击 start.bat 即可。进游戏后按 F9 开关翻译。
    游戏请开"无边框窗口"模式，全屏独占模式下悬浮窗可能盖不上去。

作者：Liuli（Muse）为王不语制作，2026-11-16

v2 自适应翻译（2026-11-16）：机翻优先、整段带上下文翻译，
只保留最小专有名词修正表；另有 user_corrections.txt 供用户纠错。

v3 离线版（2026-11-17）：在 v2 基础上新增离线引擎（Argos Translate
本地 en→zh 模型），在线/离线可切换：
    --offline 启动参数 / 运行中按 F10 切换 / 在线接口报错时自动回落离线。
离线只做翻译，不碰 OCR 和悬浮窗逻辑；截屏前先隐藏悬浮窗，
截完再恢复，绝不让 OCR 读到自己刚显示的译文。
"""

import argparse
import os
import sys
import threading
import time

# ---------------------------------------------------------------- 配置区
# 不懂代码也没关系，只改这里就够了。改完保存，双击 start.bat 重新运行。

# 翻译目标语言（zh-CN = 简体中文）
TARGET_LANG = "zh-CN"

# 每隔多少秒刷新一次翻译（1.0 秒够用了，太快会吃 CPU）
REFRESH_INTERVAL = 1.0

# 开关翻译的快捷键（默认 F9）
TOGGLE_KEY = "F9"

# 切换在线/离线引擎的快捷键（默认 F10）
TOGGLE_ENGINE_KEY = "F10"

# 翻译区域：None = 全屏；想只翻一块区域就改成 (x, y, 宽, 高)，单位是像素
# 比如只翻屏幕左上角一块：REGION = (0, 0, 960, 540)
REGION = None

# OCR 置信度：低于这个分数的识别结果直接丢掉（0.5 比较合适）
OCR_MIN_SCORE = 0.5

# 悬浮窗中文的字体和大小（Windows 上"微软雅黑"一般都有）
OVERLAY_FONT = "微软雅黑"
OVERLAY_FONT_SIZE = 16

# ---------------------------------------------------------------- 平台判断
IS_WINDOWS = sys.platform.startswith("win")

# 翻译缓存：同一句英文只翻一次，省时间也省流量
_translate_cache = {}

# 翻译开关（默认开着）
_enabled = True
_enabled_lock = threading.Lock()


def is_enabled():
    with _enabled_lock:
        return _enabled


def set_enabled(value):
    global _enabled
    with _enabled_lock:
        _enabled = value

# ---------------------------------------------------------------- 翻译
_translators = None


def _build_translators():
    """造两个免费翻译器：MyMemory 主用（实测稳定），Google 备用（都不要 key）。

    注意：deep-translator 1.11.4 里 Google 要用 source="en"，
    MyMemory 要用 source="en-GB"，写错会直接报"不支持该语言"。
    """
    global _translators
    if _translators is not None:
        return _translators
    from deep_translator import GoogleTranslator, MyMemoryTranslator
    _translators = [
        ("MyMemory", MyMemoryTranslator(source="en-GB", target=TARGET_LANG)),
        ("Google", GoogleTranslator(source="en", target=TARGET_LANG)),
    ]
    return _translators


# ---------------------------------------------------------------- 自适应翻译（v2）
# v1 是"先查 35 词字典，查不到再机翻"——已废弃。
# v2 的逻辑（按优先级）：
#   1. 用户纠错优先：user_corrections.txt 里的"英文 = 中文"直接覆盖一切。
#      这就是自适应学习——玩的时候发现翻错了，自己加一行就能纠正，
#      不用改代码；文件改了不用重启，工具会自动重新读取。
#   2. 整段带上下文机翻：同一屏上相邻的几行拼成一段一起发给翻译接口，
#      引擎按上下文选词（抢劫语境下的 Rob 翻"抢劫"而不是"机器人"，
#      而单独一个 PLAY 机翻只会翻成"玩耍"）。
#   3. 专有名词修正：机翻之后，只修正那些实测一定会翻错的专有名词
#      （地名、货币、固定玩法名词），不再用大字典当翻译主力。
#      修正表是拿真机翻结果一条一条测出来的，不是凭空编的。

# 专有名词正名表：整行就是这个词时（比如地图上的地名）直接用这个译法。
PROPER_NOUN_CANONICAL = {
    "Looty Bay": "卢蒂湾",
    "B-Coins": "B币",
    "B-Coin": "B币",
    "BCoin": "B币",
    "Federal Raid": "联邦突袭",
    "Shadow Governor": "影子州长",
    "Lenny's Motel": "伦尼汽车旅馆",
    "Highlands": "高地",
}

# 机翻错译修正表：key 是机翻实际会输出的错误译法，value 是正确译法。
# （2026-11-16 用 MyMemory 实测出来的。Google 在这台机器上被限流，
#  在用户家里的住宅 IP 上可能能用，仍保留为备用接口。）
CORRECTIONS = {
    "影子总督": "影子州长",
    "干净的钱": "干净钱",
    "地块名称": "地块地契",
    "结算标题": "定居点地契",
    "银行保险库身份证": "银行金库身份卡",
    "漏洞解码器": "破门解码器",
    "洗衣台": "洗钱桌",
    "可疑的门": "可疑之门",
    "定居居民": "定居点居民",
    "区域负责人": "地区掌控者",
    "脏钱": "黑钱",
}


def apply_proper_noun_fixes(text):
    """机翻后修正专有名词的错译。"""
    for wrong, right in CORRECTIONS.items():
        if wrong in text:
            text = text.replace(wrong, right)
    return text


# ---------------------------------------------------------------- 用户纠错文件
# user_corrections.txt 和脚本放同一个文件夹，格式：英文原文 = 中文翻译
# 每行一条，# 开头是注释。工具启动时读取，文件改了会自动重新读取，
# 不用重启。里面的条目优先级最高，会覆盖机翻和缓存。
USER_CORRECTIONS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "user_corrections.txt")
_user_corrections = {}
_user_corrections_lower = {}
_user_corrections_nospace = {}  # 去掉空格再大写：OCR 经常把空格吃掉
_user_corrections_mtime = None


def load_user_corrections(force=False):
    """读取 user_corrections.txt（文件没改过就跳过，省磁盘 IO）。"""
    global _user_corrections, _user_corrections_lower, _user_corrections_nospace
    global _user_corrections_mtime
    global _translate_cache
    try:
        mtime = os.path.getmtime(USER_CORRECTIONS_FILE)
    except OSError:
        return _user_corrections
    if not force and _user_corrections_mtime == mtime:
        return _user_corrections
    # 文件变了就把翻译缓存也清掉：缓存只认英文原文，不知道纠错文件
    # 变了，不清掉的话已经翻过的行还留着旧结果，纠错改了也看不到效果。
    _translate_cache.clear()
    corrections = {}
    corrections_lower = {}
    corrections_nospace = {}
    try:
        with open(USER_CORRECTIONS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                en, zh = line.split("=", 1)
                en, zh = en.strip(), zh.strip()
                if en and zh:
                    corrections[en] = zh
                    corrections_lower[en.upper()] = zh
                    corrections_nospace[en.upper().replace(" ", "")] = zh
    except OSError as e:
        print(f"【提示】读不到 user_corrections.txt：{e}")
    _user_corrections = corrections
    _user_corrections_lower = corrections_lower
    _user_corrections_nospace = corrections_nospace
    _user_corrections_mtime = mtime
    return _user_corrections


def _user_correction_lookup(text):
    """查用户纠错：先精确匹配，再忽略大小写匹配，最后去掉空格匹配
    （OCR 经常把词中间的空格吃掉，比如把 "Looty Bay" 认成 "LootyBay"）。"""
    load_user_corrections()
    if text in _user_corrections:
        return _user_corrections[text]
    hit = _user_corrections_lower.get(text.upper())
    if hit:
        return hit
    return _user_corrections_nospace.get(text.upper().replace(" ", ""))


def _proper_noun_lookup(text):
    """整行就是专有名词时直接给正名（比如地图上的 Looty Bay）。
    比对时去掉空格：OCR 认出来的词中间可能没空格。"""
    norm = text.upper().replace(" ", "")
    for en, zh in PROPER_NOUN_CANONICAL.items():
        if norm == en.upper().replace(" ", ""):
            return zh
    return None


# ---------------------------------------------------------------- 翻译引擎（v3）
# 两种引擎，默认在线，可切换：
#   在线  = MyMemory 主用 + Google 备用（免费接口，不要 key，要联网）
#   离线  = Argos Translate 本地 en→zh 模型（首次运行联网下载约 70MB，
#           之后断网也能用；翻译是亚秒级，不是"0 毫秒"）
# 切换方式：启动参数 --offline / 运行中按 F10 / 在线接口报错时自动回落。
# 自动回落是"粘性"的：切到离线后会一直待在离线，直到按 F10 切回去或重启。
_engine_mode = "online"
_engine_lock = threading.Lock()
_engine_auto_switched = False


def get_engine_mode():
    """当前引擎："online" 或 "offline"。"""
    with _engine_lock:
        return _engine_mode


def engine_label():
    """给悬浮窗和控制台看的引擎名字。"""
    mode = get_engine_mode()
    if mode == "offline":
        return "离线·Argos"
    return "在线·MyMemory/Google"


def set_engine_mode(mode, auto=False):
    """切换引擎（只改状态 + 打印提示，不碰任何界面控件，线程安全）。"""
    global _engine_mode, _engine_auto_switched
    if mode not in ("online", "offline"):
        return
    with _engine_lock:
        _engine_mode = mode
        if auto:
            _engine_auto_switched = True
    print(f"【提示】翻译引擎已切换为：{engine_label()}")


def toggle_engine_mode():
    """在线 <-> 离线切换（F10 热键调这个）。"""
    set_engine_mode("offline" if get_engine_mode() == "online" else "online")


_offline_translation = None  # Argos 翻译对象，第一次用离线时才加载
_offline_unavailable_warned = False  # 离线库没装的提示只打一次，别每秒刷屏


def _argos_packages_dir():
    """Argos 模型包的标准存放目录（和 argostranslate 库用的是同一个位置，
    这样两种加载方式装的模型能互相认到）。"""
    import pathlib
    env = os.environ.get("ARGOS_PACKAGES_DIR")
    if env:
        return pathlib.Path(env)
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return pathlib.Path(base) / "argos-translate" / "packages"
    return pathlib.Path.home() / ".local" / "share" / "argos-translate" / "packages"


_ARGOS_MODEL_CODE = "translate-en_zh-1_9"
_ARGOS_MODEL_URL_FALLBACK = "https://argos-net.com/v1/translate-en_zh-1_9.argosmodel"


def _safe_extract(zip_file, target_dir):
    """解压 zip，但跳过那些想写到目标文件夹外面的成员（zip slip），
    只解压落在目标文件夹里面的文件。模型包是官方下的，正常情况下
    用不上这道检查，防的是万一哪天包被人掉包。"""
    target = os.path.realpath(target_dir)
    for member in zip_file.infolist():
        dest = os.path.realpath(os.path.join(target, member.filename))
        try:
            inside = os.path.commonpath([target, dest]) == target
        except ValueError:
            inside = False
        if not inside:
            continue
        zip_file.extract(member, target)


def _ensure_argos_model_package():
    """确保 Argos 英中模型包已下载并解压到标准位置。返回包目录或 None。

    已装好就直接返回，不联网。没装才联网：先去官方索引拿下载地址，
    拿不到就用已知的直链。模型约 70MB，只需要下载这一次。
    """
    pkg_dir = _argos_packages_dir() / _ARGOS_MODEL_CODE
    if (pkg_dir / "model" / "model.bin").is_file() and \
            (pkg_dir / "sentencepiece.model").is_file():
        return pkg_dir
    url = None
    try:
        import json
        import urllib.request
        with urllib.request.urlopen(
                "https://raw.githubusercontent.com/argosopentech/"
                "argospm-index/main/index.json", timeout=20) as resp:
            index = json.load(resp)
        for entry in index:
            if entry.get("code") == _ARGOS_MODEL_CODE and entry.get("links"):
                url = entry["links"][0]
                break
    except Exception:
        url = None
    if not url:
        url = _ARGOS_MODEL_URL_FALLBACK
    print("【提示】正在下载 Argos 英中离线模型（约 70MB，只需要这一次）……")
    try:
        import tempfile
        import urllib.request
        import zipfile
        pkg_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".argosmodel",
                                        delete=False) as tmp:
            tmp_path = tmp.name
        try:
            urllib.request.urlretrieve(url, tmp_path)
            with zipfile.ZipFile(tmp_path) as zf:
                _safe_extract(zf, pkg_dir.parent)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if (pkg_dir / "model" / "model.bin").is_file():
            print("【提示】离线模型下载完成。")
            return pkg_dir
        print("【提示】离线模型解压后没找到模型文件。")
        return None
    except Exception as e:
        print(f"【提示】离线模型下载失败：{str(e)[:150]}")
        return None


class _DirectArgosTranslator:
    """直接用 ctranslate2 + sentencepiece 加载 Argos 模型文件。

    和 argostranslate 库翻的是同一个 .argosmodel、同一个权重，
    只是跳过了库里硬依赖的 stanza/torch（stanza 要拉 500MB+ 的 torch，
    弱网环境下根本装不上；但翻译本身从来用不到 stanza——
    这个模型包自带 MiniSBD 分句，argostranslate 库内部也是调
    ctranslate2 在翻）。translate(text) 的行为和库里的一致：
    按换行分段，每行单独翻，拼回换行。
    """

    def __init__(self, package_dir):
        import ctranslate2
        import sentencepiece as spm
        self._sp = spm.SentencePieceProcessor(
            model_file=str(package_dir / "sentencepiece.model"))
        self._tr = ctranslate2.Translator(str(package_dir / "model"),
                                          device="cpu")

    def translate(self, text):
        lines = (text or "").split("\n")
        out = []
        for line in lines:
            if not line.strip():
                out.append(line)
                continue
            tokens = self._sp.encode(line, out_type=str)
            result = self._tr.translate_batch(
                [tokens], beam_size=4, num_hypotheses=1,
                length_penalty=0.2, replace_unknowns=True)
            zh = self._sp.decode_pieces(
                result[0].hypotheses[0]).replace("▁", " ").replace("_", " ")
            out.append(zh.strip())
        return "\n".join(out)


def _get_offline_translation():
    """拿到离线翻译对象（两种加载方式，翻的是同一个 Argos 模型）。

    Tier 1（标准）：argostranslate 库——装了完整依赖就能用。
    Tier 2（轻量）：库装不上时（比如 stanza 拖着 500MB+ 的 torch
    在弱网下下载失败），直接用 ctranslate2 + sentencepiece 加载
    同一个 .argosmodel 模型文件，不需要 torch/stanza/spacy。

    关键顺序（修掉 Gemini 版的断网启动 bug）：
      1. 先查本地已安装的模型包——不联网。en→zh 已装好就直接加载，
         绝不调 update_package_index() 去联网拉索引。
      2. 只有没装时才联网下载一次模型（约 70MB）。
    断网时只要模型已装好，第 1 步就能加载，照常翻译。
    """
    global _offline_translation, _offline_unavailable_warned
    if _offline_translation is not None:
        return _offline_translation
    # Tier 1：argostranslate 库（如果装了完整依赖）
    try:
        import argostranslate.package
        import argostranslate.translate
        try:
            installed = argostranslate.package.get_installed_packages()
        except Exception:
            installed = []
        has_package = any(p.from_code == "en" and p.to_code == "zh"
                          for p in installed)
        if not has_package:
            print("【提示】离线模型还没装，正在联网下载英中模型"
                  "（约 70MB，只需要这一次，之后断网也能用）……")
            try:
                argostranslate.package.update_package_index()
                available = argostranslate.package.get_available_packages()
                pkg = next((p for p in available
                            if p.from_code == "en" and p.to_code == "zh"),
                           None)
                if pkg is None:
                    print("【提示】在官方包列表里没找到英中模型，"
                          "改走轻量加载方式。")
                else:
                    argostranslate.package.install_from_path(pkg.download())
                    print("【提示】离线模型下载完成。")
            except Exception as e:
                print(f"【提示】离线模型下载失败：{str(e)[:150]}，"
                      "改走轻量加载方式。")
        try:
            print("【提示】正在加载离线翻译模型到内存"
                  "（约 200–500MB，第一次要几秒）……")
            langs = argostranslate.translate.get_installed_languages()
            from_lang = next((l for l in langs if l.code == "en"), None)
            to_lang = next((l for l in langs if l.code == "zh"), None)
            if from_lang and to_lang:
                _offline_translation = from_lang.get_translation(to_lang)
                print("【提示】离线翻译模型已就绪"
                      "（Argos 本地，断网可用）。")
                return _offline_translation
            print("【提示】离线模型装好了，但没找到英中语言对，"
                  "改走轻量加载方式。")
        except Exception as e:
            print(f"【提示】离线模型加载失败：{str(e)[:150]}，"
                  "改走轻量加载方式。")
    except ImportError:
        pass  # 库本身没装全，走 Tier 2
    # Tier 2：直接用 ctranslate2 + sentencepiece 加载同一个模型文件
    try:
        pkg_dir = _ensure_argos_model_package()
        if pkg_dir is None:
            if not _offline_unavailable_warned:
                _offline_unavailable_warned = True
                print("【提示】离线引擎没装好：模型下载失败，"
                      "请检查网络后重试，或运行："
                      "pip install -r requirements-offline.txt")
            return None
        print("【提示】正在加载离线翻译模型到内存"
              "（约 120MB，第一次要几秒）……")
        _offline_translation = _DirectArgosTranslator(pkg_dir)
        print("【提示】离线翻译模型已就绪"
              "（Argos 本地，断网可用；轻量加载，不依赖 torch）。")
        return _offline_translation
    except ImportError:
        if not _offline_unavailable_warned:
            _offline_unavailable_warned = True
            print("【提示】离线引擎没装（缺少 ctranslate2 / sentencepiece 库），"
                  "请先运行：pip install -r requirements-offline.txt")
        return None
    except Exception as e:
        print(f"【提示】离线模型加载失败：{str(e)[:150]}")
        return None


def _offline_translate(text):
    """用 Argos 本地模型翻一段英文。失败返回 None（不抛错）。"""
    text = (text or "").strip()
    if not text:
        return None
    tr = _get_offline_translation()
    if tr is None:
        return None
    try:
        result = tr.translate(text)
        return result.strip() if result and result.strip() else None
    except Exception as e:
        print(f"【提示】离线翻译失败：{str(e)[:150]}")
        return None


def _online_translate(text):
    """调免费接口翻一段英文（MyMemory 主用，Google 备用）。失败返回 None。"""
    text = (text or "").strip()
    if not text:
        return None
    result = None
    try:
        for name, translator in _build_translators():
            try:
                result = translator.translate(text)
                if result and result.strip():
                    break
                result = None
            except Exception as e:
                # 报错只打印前 150 字，避免某些接口把几万字的语言列表全吐出来
                print(f"【提示】{name} 翻译失败，换备用接口：{str(e)[:150]}")
                result = None
    except Exception as e:
        print(f"【提示】翻译器初始化失败：{str(e)[:150]}")
        result = None
    return result.strip() if result else None


def translate_with_engine(text):
    """按当前引擎翻一段英文（在线失败自动回落离线，并切过去）。

    在线模式：先走 MyMemory/Google；两个都失败（429 限流、断网等），
    自动切换到离线引擎再翻一次，并打印提示。切过去之后就一直待在
    离线模式，直到按 F10 手动切回在线（或重启）。
    离线模式：直接走 Argos 本地模型。
    """
    text = (text or "").strip()
    if not text:
        return None
    if get_engine_mode() == "offline":
        return _offline_translate(text)
    result = _online_translate(text)
    if result:
        return result
    print("【提示】在线翻译接口都失败了（可能被限流或断网），"
          "已自动切换到离线引擎（Argos 本地），按 "
          f"{TOGGLE_ENGINE_KEY} 可切回在线。")
    set_engine_mode("offline", auto=True)
    return _offline_translate(text)


def _mt_translate(text):
    """兼容老接口：内部走当前引擎（含自动回落）。"""
    return translate_with_engine(text)


def translate_lines(lines):
    """把同一屏上的一组英文行翻成中文（带上下文整段翻译）。

    lines: 英文列表（一般是同一屏上相邻的几行，从上到下）。
    返回：和 lines 一一对应的中文列表，翻不出来的那行是 None。
    """
    results = [None] * len(lines)
    pending = []  # (下标, 英文) —— 需要调接口的
    for i, raw in enumerate(lines):
        text = (raw or "").strip()
        if not text:
            continue
        # 1. 用户纠错优先（自适应学习）——先查纠错再查缓存，
        #    纠错文件随时能改，缓存可不知道文件变了。
        hit = _user_correction_lookup(text)
        if hit:
            results[i] = hit
            _translate_cache[text] = hit
            continue
        if text in _translate_cache:
            results[i] = _translate_cache[text]
            continue
        # 2. 整行就是专有名词，直接给正名
        canon = _proper_noun_lookup(text)
        if canon:
            results[i] = canon
            _translate_cache[text] = canon
            continue
        pending.append((i, text))

    if pending:
        # 3. 剩下的拼成一段一起翻，让引擎按上下文选词
        joined = chr(10).join(t for _, t in pending)
        translated = _mt_translate(joined)
        parts = translated.split(chr(10)) if translated else []
        if len(parts) == len(pending):
            for (i, text), part in zip(pending, parts):
                fixed = apply_proper_noun_fixes(part.strip())
                # 翻出来是空的就别进缓存，留着 None 下次刷新再试一次
                if fixed:
                    results[i] = fixed
                    _translate_cache[text] = fixed
        else:
            # 行数对不上（接口吞了换行），退回逐行翻
            for i, text in pending:
                one = _mt_translate(text)
                if one:
                    fixed = apply_proper_noun_fixes(one.strip())
                    results[i] = fixed
                    _translate_cache[text] = fixed
    return results


def translate_text(text):
    """把一句英文翻成中文（兼容老接口，内部走整段翻译）。"""
    text = (text or "").strip()
    if not text:
        return None
    return translate_lines([text])[0]


# ---------------------------------------------------------------- OCR
_ocr_engine = None


def _get_ocr_engine():
    """第一次用时才加载 OCR 模型（首次运行会下载十几 MB 的模型，请稍等）。"""
    global _ocr_engine
    if _ocr_engine is None:
        print("【提示】正在加载 OCR 识别模型（首次运行需要下载，请稍等）……")
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        print("【提示】OCR 模型加载完成。")
    return _ocr_engine


def ocr_image(pil_image):
    """识别一张图里的英文，返回 [(x, y, 宽, 高), 英文, 置信度] 的列表。

    坐标是相对于这张图左上角的像素坐标。
    只有"带字母、置信度够高"的行会被留下来，纯数字和乱码会被过滤掉。
    """
    import numpy as np
    engine = _get_ocr_engine()
    result, _ = engine(np.array(pil_image))
    items = []
    if not result:
        return items
    for box, text, score in result:
        if score is None or score < OCR_MIN_SCORE:
            continue
        text = (text or "").strip()
        if len(text) < 2:
            continue
        # 至少要含一个英文字母，不然多半是数字或符号乱码
        if not any("a" <= ch <= "z" or "A" <= ch <= "Z" for ch in text):
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x, y = int(min(xs)), int(min(ys))
        w, h = int(max(xs) - x), int(max(ys) - y)
        items.append(((x, y, w, h), text, float(score)))
    return items


# ---------------------------------------------------------------- 截屏
_sct = None
_sct_failed = False


def capture_screen(region=None):
    """截取屏幕（或指定区域），返回 PIL 图片。失败返回 None（不抛错）。"""
    global _sct, _sct_failed
    try:
        import mss
        from PIL import Image
        if _sct is None:
            _sct = mss.MSS()
        monitor = _sct.monitors[0] if region is None else {
            "left": int(region[0]), "top": int(region[1]),
            "width": int(region[2]), "height": int(region[3]),
        }
        shot = _sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        _sct_failed = False
        return img
    except Exception as e:
        if not _sct_failed:
            print(f"【提示】截屏失败：{e}")
            _sct_failed = True
        _sct = None
        return None

# ---------------------------------------------------------------- 悬浮窗（仅 Windows）
class Overlay:
    """透明置顶、鼠标点透的悬浮窗。

    实现方式：tkinter 做一个全屏无边框窗口，背景设成纯黑并设为透明色，
    再用 Win32 API 加上 WS_EX_TRANSPARENT 让鼠标点透。
    中文以"深色小卡片 + 亮字"的形式画在原文位置上。
    """

    def __init__(self):
        import tkinter as tk
        self._tk = tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        # 纯黑变透明：窗口背景是黑色的地方会透出游戏画面
        self.win.attributes("-transparentcolor", "black")
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{sw}x{sh}+0+0")
        self.win.configure(bg="black")
        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._make_click_through()
        self._last_signature = None
        # 让窗口先显示出来（内容是空的，全透明）
        self.win.deiconify()
        self.win.update_idletasks()

    def _make_click_through(self):
        """调用 Win32 API，让鼠标点击穿过悬浮窗落到游戏上。"""
        try:
            import ctypes
            hwnd = self.win.winfo_id()
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                  style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        except Exception as e:
            print(f"【提示】设置鼠标穿透失败（不影响翻译显示）：{e}")

    def hide(self):
        """截屏前隐藏悬浮窗（防自拍回环：绝不让 OCR 读到自己刚显示的译文）。

        只在主线程里调。隐藏后调 update_idletasks() 让窗口真的先消失，
        再等 0.05 秒给系统合成器留出时间。
        """
        try:
            self.win.withdraw()
            self.root.update_idletasks()
            time.sleep(0.05)
        except Exception:
            pass

    def show(self):
        """截完屏恢复悬浮窗。只在主线程里调。"""
        try:
            self.win.deiconify()
            self.root.update_idletasks()
        except Exception:
            pass

    def update(self, items, offset=(0, 0), engine_text=""):
        """刷新悬浮窗内容。

        items: [((x, y, 宽, 高), 中文), ...]，坐标是屏幕坐标。
        内容没变就不重画，避免闪烁。
        engine_text: 左上角显示的当前引擎（比如"在线·MyMemory/Google"），
        引擎切换时跟着变。只在主线程里调。
        """
        signature = (tuple((box, text) for box, text in items), engine_text)
        if signature == self._last_signature:
            return
        self._last_signature = signature
        self.canvas.delete("all")
        ox, oy = offset
        if engine_text:
            # 左上角小灰字：当前用的哪个引擎
            self.canvas.create_text(
                10, 8, text=engine_text, anchor="nw", fill="#9a9a9a",
                font=(OVERLAY_FONT, 11))
        for (x, y, w, h), text in items:
            cx, cy = x + ox, y + oy
            # 深色卡片垫底，亮黄色文字，游戏画面上看得清楚
            self.canvas.create_rectangle(
                cx - 2, cy - 2, cx + w + 4, cy + h + 4,
                fill="#101010", outline="")
            self.canvas.create_text(
                cx, cy, text=text, anchor="nw", fill="#ffe14d",
                font=(OVERLAY_FONT, OVERLAY_FONT_SIZE, "bold"))

    def pump(self):
        """让 tkinter 处理一下窗口消息（主循环里每轮调一次）。"""
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass


# ---------------------------------------------------------------- 快捷键
def start_hotkey_listener():
    """启动全局快捷键监听（F9 开关翻译，F10 切换在线/离线引擎）。

    注意：回调跑在 pynput 自己的线程里，只能改状态、打印提示，
    绝不能直接碰 tkinter 控件（线程不安全）。悬浮窗的刷新只在主循环
    （主线程）里做。失败也不影响主流程。
    """
    if not IS_WINDOWS:
        print("【提示】当前不是 Windows，快捷键监听不可用，翻译将一直开着，"
              f"引擎固定为 {engine_label()}。")
        return
    try:
        from pynput import keyboard

        def on_press(key):
            try:
                name = getattr(key, "name", "") or ""
                name = name.lower()
                if name == TOGGLE_KEY.lower():
                    new_state = not is_enabled()
                    set_enabled(new_state)
                    print(f"【提示】翻译已{'开启' if new_state else '暂停'}"
                          f"（按 {TOGGLE_KEY} 切换）。")
                elif name == TOGGLE_ENGINE_KEY.lower():
                    toggle_engine_mode()
                    print(f"【提示】按 {TOGGLE_ENGINE_KEY} 切换引擎，"
                          f"当前：{engine_label()}。")
            except Exception:
                pass

        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()
        print(f"【提示】快捷键已就绪：按 {TOGGLE_KEY} 开关翻译，"
              f"按 {TOGGLE_ENGINE_KEY} 切换在线/离线引擎。")
    except Exception as e:
        print(f"【提示】快捷键监听启动失败（翻译会一直开着，不影响使用）：{e}")


# ---------------------------------------------------------------- 主流程
# 同一屏上相邻两行的纵向间距（像素）。小于这个值就当成一段一起翻。
BLOCK_LINE_GAP = 50


def _group_lines(ocr_results):
    """把一屏的 OCR 结果按纵向位置分段：相邻的行拼成一段。

    ocr_results: [((x, y, 宽, 高), 英文, 置信度), ...]
    返回：[[...], [...]]，每组是从上到下的相邻行。
    """
    ordered = sorted(ocr_results, key=lambda r: (r[0][1], r[0][0]))
    groups = []
    current = []
    prev_bottom = None
    for item in ordered:
        (x, y, w, h), _text, _score = item
        if prev_bottom is not None and y - prev_bottom > BLOCK_LINE_GAP:
            groups.append(current)
            current = []
        current.append(item)
        prev_bottom = max(prev_bottom or 0, y + h)
    if current:
        groups.append(current)
    return groups


def build_overlay_items(ocr_results, offset=(0, 0)):
    """把 OCR 结果翻成中文，返回 [((x, y, 宽, 高), 中文)]。

    同一段里的行会拼在一起翻（带上下文），翻失败的那一行会跳过
    （不显示），下次刷新再试。
    """
    items = []
    for group in _group_lines(ocr_results):
        texts = [text for (_box, text, _score) in group]
        translated = translate_lines(texts)
        for ((x, y, w, h), _text, _score), chinese in zip(group, translated):
            if chinese:
                items.append(((x + offset[0], y + offset[1], w, h), chinese))
    return items


# 主循环里同一个报错别每秒刷屏：截屏、OCR 一直失败时，
# 同一条提示 30 秒内只打一次。
_error_last_shown = {}


def _throttled_print(key, message, interval=30.0):
    now = time.monotonic()
    last = _error_last_shown.get(key)
    if last is not None and now - last < interval:
        return
    _error_last_shown[key] = now
    print(message)


def run_live():
    """正式运行：截屏 -> OCR -> 翻译 -> 悬浮窗，约每秒一轮。

    这个函数就是"工作线程"——它在主线程里跑，每轮都真实执行
    截屏、OCR、翻译、刷新悬浮窗（v3 已验证它在跑，见 harvest/test_v3.py）。
    """
    print("=" * 56)
    print("ROB RUN 实时屏幕翻译工具（免费版）v3 离线版")
    print("原理：截屏 -> OCR 认字 -> 机器翻译 -> 悬浮窗显示")
    print("不改游戏文件、不注入、不读内存，反作弊不会拦。")
    print("=" * 56)
    print(f"【提示】当前翻译引擎：{engine_label()}")
    if get_engine_mode() == "offline":
        print("【提示】离线模式：用 Argos 本地模型翻译，断网也能用；"
              "首次运行会联网下载一次模型（约 70MB）。")
    else:
        print("【提示】在线模式：MyMemory 主用、Google 备用；"
              "接口报错时自动回落到离线引擎。")
    print("【提示】请先把游戏设成【无边框窗口】模式再进游戏。")
    print(f"【提示】按 {TOGGLE_KEY} 开关翻译，按 {TOGGLE_ENGINE_KEY} "
          f"切换在线/离线引擎，关控制台或按 Ctrl+C 退出。")
    print()

    overlay = None
    if IS_WINDOWS:
        try:
            overlay = Overlay()
            print("【提示】悬浮窗已创建。")
        except Exception as e:
            print(f"【提示】悬浮窗创建失败（翻译仍会在控制台打印）：{e}")
            overlay = None
    else:
        print("【提示】当前不是 Windows，没有悬浮窗，翻译结果只打印在控制台。")

    start_hotkey_listener()
    offset = (REGION[0], REGION[1]) if REGION else (0, 0)

    while True:
        try:
            if not is_enabled():
                if overlay is not None:
                    # 暂停了就把悬浮窗上的旧译文清掉，别一直糊在游戏画面上
                    overlay.update([], engine_text=engine_label())
                    overlay.pump()
                time.sleep(0.3)
                continue

            # 防自拍回环：截屏前先隐藏悬浮窗，截完再恢复，
            # 绝不让 OCR 读到自己刚显示出来的译文。
            if overlay is not None:
                overlay.hide()
            try:
                img = capture_screen(REGION)
            finally:
                if overlay is not None:
                    overlay.show()

            if img is None:
                _throttled_print("capture",
                                 "【提示】截屏失败，1 秒后重试……")
                time.sleep(REFRESH_INTERVAL)
                continue

            try:
                results = ocr_image(img)
            except Exception as e:
                _throttled_print("ocr", f"【提示】OCR 识别出错：{e}")
                time.sleep(REFRESH_INTERVAL)
                continue

            items = build_overlay_items(results, offset)
            if overlay is not None:
                overlay.update(items, engine_text=engine_label())
                overlay.pump()
            elif items:
                for (_box, text) in items:
                    print(f"  {text}")

            time.sleep(REFRESH_INTERVAL)
        except KeyboardInterrupt:
            print("\n【提示】正在退出，感谢使用。")
            break
        except Exception as e:
            # 主循环永不闪退：报错打印出来，继续跑
            print(f"【出错】{str(e)[:200]}，继续运行……")
            time.sleep(REFRESH_INTERVAL)


# ---------------------------------------------------------------- 自测模式
def run_test_image(path):
    """自测：对一张图片跑一遍 OCR -> 翻译，打印结果后退出。

    用来验证"认字 + 翻译"这条链路通不通，不用进游戏。
    """
    from PIL import Image
    print(f"【自测】正在处理图片：{path}")
    print(f"【自测】当前引擎：{engine_label()}")
    img = Image.open(path).convert("RGB")
    print(f"【自测】图片尺寸：{img.size[0]} x {img.size[1]}")
    results = ocr_image(img)
    if not results:
        print("【自测】没有识别到英文文字（图片可能太暗、字太小或不是英文）。")
        return
    print(f"【自测】识别到 {len(results)} 行文字：")
    # 整屏一起翻，带上下文（和正式运行时同一个逻辑）
    translated = translate_lines([t for (_b, t, _s) in results])
    ok = 0
    for (_box, text, score), chinese in zip(results, translated):
        if chinese:
            ok += 1
            print(f"  [{score:.2f}] {text}  ->  {chinese}")
        else:
            print(f"  [{score:.2f}] {text}  ->  （翻译失败，请检查网络）")
    print(f"【自测】完成：{ok}/{len(results)} 行翻译成功。")


def main():
    parser = argparse.ArgumentParser(description="ROB RUN 实时屏幕翻译工具（免费版）")
    parser.add_argument("--test-image", metavar="图片路径",
                        help="自测模式：对一张图片做 OCR+翻译并打印结果，不启动悬浮窗")
    parser.add_argument("--region", nargs=4, type=int, metavar=("x", "y", "宽", "高"),
                        help="只翻译指定屏幕区域，例如 --region 0 0 960 540")
    parser.add_argument("--offline", action="store_true",
                        help="离线模式启动：用 Argos 本地模型翻译，断网也能用；"
                             "首次运行会联网下载一次模型（约 70MB）")
    args = parser.parse_args()

    global REGION
    if args.region:
        REGION = tuple(args.region)
        print(f"【提示】只翻译屏幕区域：{REGION}")

    if args.offline:
        set_engine_mode("offline")
        print("【提示】已用 --offline 启动，离线引擎（Argos 本地）。")

    if args.test_image:
        run_test_image(args.test_image)
    else:
        run_live()


if __name__ == "__main__":
    main()
