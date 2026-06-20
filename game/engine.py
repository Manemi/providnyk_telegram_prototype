from typing import Any, Dict, List, Optional, Tuple

from . import db
from .episode import default_state, load_episode
from .intents import classify_intent
from .llm import generate_scene_with_ai
from .rules import (
    apply_ai_delta,
    apply_intent_delta,
    apply_personality,
    apply_scene_delta,
    skill_level,
    update_npc_memory,
)


INTENT_LABELS = {
    "inspect": "оглянути предмети, сліди або деталі сцени",
    "analyze": "зіставити факти і сформулювати внутрішню версію",
    "question": "поговорити з людиною поруч",
    "pressure": "обережно або жорстко натиснути в розмові",
    "deceive": "зіграти легенду, напівправду або перевірочну брехню",
    "follow": "простежити, перевірити хвіст або чужий маршрут",
    "move": "змінити локацію",
    "wait": "почекати, послухати місце, дати людям проявитись",
    "use_item": "використати предмет, зафіксувати або перевірити доказ",
}


def start_or_get(telegram_id: int) -> Dict[str, Any]:
    state = db.get_state(telegram_id)
    if state:
        return state
    state = default_state()
    db.save_state(telegram_id, state)
    db.add_journal(telegram_id, "Тарас Сірко прибув у готель «Континенталь».")
    return state


def new_game(telegram_id: int) -> Dict[str, Any]:
    db.delete_state(telegram_id)
    return start_or_get(telegram_id)


def _paragraphs(text: str) -> str:
    text = (text or "").strip()
    if "\n\n" in text:
        return text
    parts = [p.strip() for p in text.split(". ") if p.strip()]
    if len(parts) <= 2:
        return text
    first = ". ".join(parts[:2]).strip()
    rest = ". ".join(parts[2:]).strip()
    if first and not first.endswith((".", "!", "?", "»")):
        first += "."
    return f"{first}\n\n{rest}"


def current_location(state: Dict[str, Any]) -> Dict[str, Any]:
    return load_episode()["locations"][state["hero"]["location"]]


def difficulty_complete(state: Dict[str, Any]) -> bool:
    return bool(state.get("hero", {}).get("difficulty"))


def setup_complete(state: Dict[str, Any]) -> bool:
    return bool(state.get("hero", {}).get("setup_complete"))


def render_difficulty_selection() -> str:
    ep = load_episode()
    lines = [
        "🎚️ Обери режим складності",
        "",
        "Це впливає не на силу ворогів, а на те, скільки орієнтирів отримує гравець.",
        "",
    ]
    for key, opt in ep.get("difficulty_options", {}).items():
        lines.append(f"{key}. {opt['title']}")
        lines.append(f"   {opt['description']}")
        lines.append("")
    lines.append("Напиши 1, 2 або 3.")
    return "\n".join(lines)


def choose_difficulty(telegram_id: int, text: str) -> Tuple[str, Dict[str, Any]]:
    state = start_or_get(telegram_id)
    ep = load_episode()
    value = (text or "").lower().strip()
    chosen = None
    for key, opt in ep.get("difficulty_options", {}).items():
        aliases = [key, opt["key"].lower(), opt["title"].lower()]
        if value in aliases or opt["key"].lower() in value or opt["title"].lower() in value:
            chosen = opt
            break
    if not chosen:
        return "Не впізнав режим. Напиши 1, 2 або 3.\n\n" + render_difficulty_selection(), state

    hero = state["hero"]
    hero["difficulty"] = chosen["key"]
    hero["difficulty_title"] = chosen["title"]
    hero["hint_tokens"] = int(chosen.get("hint_tokens", 0))
    hero["hint_tokens_max"] = int(chosen.get("hint_tokens", 0))
    hero.setdefault("hint_bonus_flags", [])
    state["case_status"] = "difficulty_selected"
    db.save_state(telegram_id, state)
    db.add_journal(telegram_id, f"Обрано режим складності: {chosen['title']}.")

    return (
        f"✅ Обрано: {chosen['title']}\n\n"
        f"{chosen['description']}\n\n"
        f"Тепер обери характер Тараса.\n\n"
        f"{render_character_selection()}"
    ), state


def render_character_selection() -> str:
    ep = load_episode()
    lines = [
        "🧬 Обери характер Тараса Сірка",
        "",
        "Це не косметика. Характер змінить стартові сильні сторони, реакції людей і те, як герой природно поводиться в сценах.",
        "",
    ]
    for key, opt in ep["character_options"].items():
        lines.append(f"{key}. {opt['title']}")
        lines.append(f"   {opt['description']}")
        lines.append("")
    lines.append("Напиши цифру 1–5 або назву характеру.")
    return "\n".join(lines)


def choose_character(telegram_id: int, text: str) -> Tuple[str, Dict[str, Any]]:
    state = start_or_get(telegram_id)
    ep = load_episode()
    value = (text or "").lower().strip()
    chosen = None
    for key, opt in ep["character_options"].items():
        if value == key or opt["title"].lower() in value or opt["key"].lower() in value:
            chosen = opt
            break
    if not chosen:
        return "Не впізнав вибір. Напиши цифру від 1 до 5.\n\n" + render_character_selection(), state
    state = apply_personality(state, chosen)
    db.save_state(telegram_id, state)
    db.add_journal(telegram_id, f"Обрано характер: {chosen['title']}.")
    return (
        f"✅ Обрано характер: {chosen['title']}\n\n"
        f"{chosen['description']}\n\n"
        f"Тон героя: {chosen.get('tone', 'стриманий')}.\n\n"
        f"Тепер справа починається по-справжньому.\n\n"
        f"{render_intro(state)}"
    ), state


def render_intro(state: Dict[str, Any]) -> str:
    if not difficulty_complete(state):
        return render_difficulty_selection()
    if not setup_complete(state):
        return render_character_selection()
    ep = load_episode()
    h = state["hero"]
    loc = current_location(state)
    return (
        f"📖 {state['season']}\n"
        f"🕯️ {state['episode']}\n\n"
        f"🧭 ПЕРЕДІСТОРІЯ\n{ep.get('backstory','')}\n\n"
        f"🎬 ПОЧАТОК\n{_paragraphs(state['last_scene'])}\n\n"
        f"🎚️ Режим: {h.get('difficulty_title', 'не обрано')}\n"
        f"🧍 Характер: {h.get('personality_title', 'не обрано')}\n"
        f"📍 Локація: {loc['title']}\n"
        f"⏳ Дій у сцені: {h.get('scene_turn',0)}/{loc.get('limit',4)}\n\n"
        f"{render_action_options(state)}\n\n"
        f"✍️ Напиши, що має зробити Тарас."
    )


def render_profile(state: Dict[str, Any]) -> str:
    h = state["hero"]
    inv = ", ".join(h.get("inventory", [])) or "порожньо"
    return (
        f"🧍 Герой: {h['name']}\n"
        f"🎭 Роль: {h['archetype']}\n"
        f"🧬 Характер: {h.get('personality_title') or 'ще не обрано'}\n"
        f"🎚️ Режим: {h.get('difficulty_title') or 'ще не обрано'}\n"
        f"📍 Локація: {current_location(state)['title']}\n\n"
        f"👁️ Увага: {h['attention']}/100\n"
        f"🔥 Тиск: {h['pressure']}/100\n"
        f"🎭 Легенда: {h['cover']}/100\n"
        f"🤝 Довіра джерел: {h['source_trust']}/100\n"
        f"🚨 Рівень викриття: {h['exposure']}/100\n\n"
        f"💡 Підказки: {_hint_status(h)}\n"
        f"🎒 Інвентар: {inv}"
    )


def render_skills(state: Dict[str, Any]) -> str:
    skills = state["hero"].get("skills", {})
    if not skills:
        return "🧠 Навички ще не сформовані."
    lines = ["🧠 Реальні навички Тараса\n"]
    for name, value in sorted(skills.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"• {name}: {value}/100 — {skill_level(value)}")
    log = state["hero"].get("skill_log", [])[-5:]
    if log:
        lines.append("\nОстанній розвиток:")
        lines.extend([f"• {x}" for x in log])
    lines.append("\nНавички ростуть тільки від повторюваної поведінки: допитів, аналізу, стеження, фіксації доказів, витримки, руху під тиском.")
    return "\n".join(lines)


def render_npc_memory(state: Dict[str, Any]) -> str:
    return (
        "🧠 Памʼять персонажів працює приховано.\n\n"
        "Люди запамʼятовують, як Тарас поводився: спокійно, грубо, чесно, маніпулятивно, професійно або необережно. "
        "Це впливає на майбутні зустрічі, чутки, довіру, страх і готовність говорити.\n\n"
        "Гравець не бачить цю таблицю напряму — репутацію доведеться відчувати за реакціями."
    )


def render_evidence(state: Dict[str, Any]) -> str:
    evidence = state["hero"].get("evidence", [])
    if not evidence:
        return "📌 Доказів поки немає. Є лише кімната, труп і відчуття, що хтось дуже поспішає закрити справу."
    return "📌 Докази:\n\n" + "\n".join([f"{i+1}. {ev}" for i, ev in enumerate(evidence)])


def render_suspects(state: Dict[str, Any]) -> str:
    lines = ["🕵️ Підозрювані / фігуранти:\n"]
    for name, data in state["hero"].get("suspects", {}).items():
        lines.append(
            f"• {name}\n"
            f"  Роль: {data.get('role','невідомо')}\n"
            f"  Статус: {data.get('status','невідомо')}\n"
            f"  Мотив: {data.get('motive','невідомо')}\n"
            f"  Ризик: {data.get('risk','невідомо')}"
        )
    return "\n\n".join(lines)


def _hint_status(h: Dict[str, Any]) -> str:
    diff = h.get("difficulty")
    if diff == "easy":
        return "автоматичні"
    if diff == "normal":
        return f"{h.get('hint_tokens', 0)} доступно"
    if diff == "hardcore":
        return "вимкнені"
    return "режим не обрано"


def render_mission(state: Dict[str, Any]) -> str:
    h = state["hero"]
    loc = current_location(state)
    evidence_count = len(h.get("evidence", []))
    suspects_count = len(h.get("suspects", {}))
    return (
        "🎯 Картка місії\n\n"
        f"📖 {state['season']}\n"
        f"🕯️ {state['episode']}\n"
        f"🎚️ Режим: {h.get('difficulty_title','не обрано')} · 💡 {_hint_status(h)}\n\n"
        "Головне завдання:\n"
        "• встановити, хто вбив людину з порожнім паспортом;\n"
        "• знайти, що було в камері схову №46;\n"
        "• вийти на людей мережі «Контур»;\n"
        "• не дати справу закрити як самогубство.\n\n"
        f"📍 Поточна точка: {loc['title']}\n"
        f"💡 Оперативний орієнтир: {loc.get('hint', '')}\n\n"
        f"📌 Доказів зібрано: {evidence_count}\n"
        f"🕵️ Фігурантів у справі: {suspects_count}\n"
        f"🔥 Тиск: {h['pressure']} · 🚨 Викриття: {h['exposure']}\n\n"
        f"{render_action_options(state)}"
    )


def render_notebook(state: Dict[str, Any]) -> str:
    h = state["hero"]
    evidence = h.get("evidence", [])
    theories = h.get("theories", [])
    flags = h.get("flags", [])
    location = current_location(state)
    blocks = [
        "📒 Блокнот Тараса",
        "",
        f"📍 Де зараз: {location['title']}",
        f"💡 Що важливо тут: {location.get('hint', '')}",
    ]
    if evidence:
        blocks.append("\n📌 Важливі докази:")
        blocks.extend([f"• {ev}" for ev in evidence[-8:]])
    else:
        blocks.append("\n📌 Докази: поки немає твердих фактів.")
    if theories:
        blocks.append("\n🧩 Останні версії:")
        blocks.extend([f"• {th}" for th in theories[-5:]])
    else:
        blocks.append("\n🧩 Версії: ще не висунуті. Можна написати /theory і свою гіпотезу.")
    useful_flags = [f for f in flags if not str(f).endswith("_started")]
    if useful_flags:
        blocks.append("\n🗂️ Позначки справи:")
        blocks.extend([f"• {fl}" for fl in useful_flags[-8:]])
    return "\n".join(blocks)


def render_locations(state: Dict[str, Any]) -> str:
    return render_map(state)


def render_map(state: Dict[str, Any]) -> str:
    ep = load_episode()
    loc_key = state["hero"]["location"]
    loc = ep["locations"][loc_key]
    lines = [
        f"🗺️ Карта справи",
        "",
        f"📍 Тарас зараз: {loc['title']}",
        f"🎯 Сенс точки: {loc.get('objective') or loc.get('hint','')}",
        "",
        "🧭 Куди можна піти:",
    ]
    dirs = loc.get("directions", [])
    if dirs:
        for key in dirs:
            target = ep["locations"][key]
            lines.append(f"• {target['title']} — напиши: йди до {target['title']}")
    else:
        lines.append("• Немає відкритих переходів.")
    lines.append("")
    lines.append(render_action_options(state))
    return "\n".join(lines)


def render_action_options(state: Dict[str, Any]) -> str:
    ep = load_episode()
    loc_key = state["hero"]["location"]
    loc = ep["locations"][loc_key]
    scripted = ep.get("scripted_scenes", {}).get(loc_key, {})
    intent_order = ["inspect", "analyze", "question", "pressure", "deceive", "follow", "use_item", "wait"]

    lines = [
        "🧭 Оперативна рамка",
        "Це не вибір замість тебе. Це карта можливостей, щоб не загубити сцену.",
        "",
        "Можна залишитись тут і:"
    ]

    actions = [i for i in intent_order if i in scripted]
    if not actions:
        actions = ["inspect", "analyze", "question"]

    for intent in actions[:5]:
        lines.append(f"• {INTENT_LABELS.get(intent, intent)}")

    dirs = loc.get("directions", [])
    if dirs:
        lines.append("")
        lines.append("Можна перейти:")
        for key in dirs[:4]:
            lines.append(f"• {ep['locations'][key]['title']}")

    lines.append("")
    lines.append("Або напиши власну дію своїми словами — Тарас спробує зрозуміти намір.")
    return "\n".join(lines)

def _strategic_hint(state: Dict[str, Any]) -> str:
    h = state["hero"]
    loc_key = h["location"]
    evidence = " | ".join(h.get("evidence", [])).lower()
    if loc_key == "hotel_room":
        if "сірий пил" not in evidence:
            return "Почни з того, що фізично не сходиться з самогубством: тіло, склянка, пил, квиток, ключ."
        return "У номері вже є сліди. Тепер корисно перевірити, хто першим знайшов тіло або куди веде ключ."
    if loc_key == "reception":
        if "портьє" not in evidence and "журнал" not in evidence:
            return "Ресепшн — це люди й записи. Перевір час дзвінка, журнал гостей і реакцію портьє на ключ."
        return "Якщо людина бреше про час, шукай, що вона захищає: камери, службовий коридор або зовнішнього гостя."
    if loc_key == "station_locker":
        if "флеш" not in evidence:
            return "Камера схову — точка передачі. Перевір замок, ручку, вміст і тих, хто спостерігає."
        return "Флешка й контейнер — вже не готельна справа. Потрібен звʼязок між вантажем, готелем і людьми, які стежили."
    if loc_key == "hotel_bar":
        return "Бар — місце памʼяті. Розмовляй не тільки з тим, хто знає, а й з тим, хто боїться згадати."
    return "Звір карту, докази й останню версію. Наступний крок має або дати доказ, або перевірити підозрюваного."


def use_hint(telegram_id: int) -> Tuple[str, Dict[str, Any]]:
    state = start_or_get(telegram_id)
    h = state["hero"]
    if not difficulty_complete(state):
        return render_difficulty_selection(), state
    if not setup_complete(state):
        return render_character_selection(), state
    diff = h.get("difficulty")
    if diff == "hardcore":
        return "💡 У режимі Хардкор підказки вимкнені. У тебе є карта, блокнот, докази й власна голова. Цього достатньо, якщо не поспішати.", state
    if diff == "normal":
        tokens = int(h.get("hint_tokens", 0))
        if tokens <= 0:
            return (
                "💡 Підказки закінчились.\n\n"
                "Нову підказку можна здобути, знайшовши важливу зачіпку: ключовий доказ, сильну суперечність або звʼязок між фігурантами.",
                state,
            )
        h["hint_tokens"] = tokens - 1
        db.save_state(telegram_id, state)
        return f"💡 Підказка\n\n{_strategic_hint(state)}\n\nЗалишилось підказок: {h['hint_tokens']}", state
    return f"💡 Підказка\n\n{_strategic_hint(state)}", state


def _move_if_requested(state: Dict[str, Any], player_text: str) -> Optional[str]:
    ep = load_episode()
    text = player_text.lower()
    current = state["hero"]["location"]
    dirs = ep["locations"][current].get("directions", [])
    candidates = {
        "reception": ["ресепшн", "портьє", "стійк"],
        "station_locker": ["вокзал", "камера схову", "схов", "ключ", "46"],
        "hotel_bar": ["бар"],
        "hotel_room": ["номер", "312", "кімнат"],
    }
    for loc, words in candidates.items():
        title = ep["locations"].get(loc, {}).get("title", "").lower()
        if loc in dirs and (any(w in text for w in words) or title in text):
            state["hero"]["location"] = loc
            state["hero"]["scene_turn"] = 0
            target = ep["locations"][loc]
            return f"Тарас залишає попередню точку без зайвого шуму. Тепер він тут: {target['title']}.\n\n{target.get('hint','')}"
    return None


def _scene_exhaustion_note(state: Dict[str, Any]) -> Optional[str]:
    loc = current_location(state)
    if int(state["hero"].get("scene_turn", 0)) < int(loc.get("limit", 4)):
        return None
    return (
        "У цій точці Тарас уже взяв майже все, що лежить на поверхні. "
        "Можна залишитись і копати глибше, але ризик тупцювання росте. Краще звірити карту й обрати наступний напрямок."
    )


def _scripted_scene(state: Dict[str, Any], intent: str) -> Tuple[str, List[str], bool]:
    ep = load_episode()
    loc_key = state["hero"]["location"]
    scene = ep["scripted_scenes"].get(loc_key, {}).get(intent)
    if not scene:
        scene = {
            "text": "Тарас не робить різкого руху. Команда звучить широко, і він бере з неї те, що можна виконати без дурного ризику.\n\nВін ще раз звіряє місце, людей поруч і те, що вже має в голові. У цій справі необережність не створює драму — вона створює свідків проти нього.\n\nМожна залишитись і уточнити дію, поговорити з кимось поруч, перевірити докази або перейти до іншої точки.",
            "pressure": 1,
            "public": True,
        }
    added = apply_scene_delta(state, scene)
    return scene["text"], added, bool(scene.get("public", True))


def _grant_hint_tokens(state: Dict[str, Any], added: List[str]) -> List[str]:
    h = state["hero"]
    if h.get("difficulty") != "normal" or not added:
        return []
    important_markers = ["Флешка", "контейнера", "Портьє збрехав", "дипломатичними", "Порохівський", "камера схову", "ключ"]
    flags = h.setdefault("hint_bonus_flags", [])
    notes: List[str] = []
    for ev in added:
        if any(m.lower() in ev.lower() for m in important_markers):
            flag = "hint_bonus_" + ev[:40]
            if flag not in flags:
                flags.append(flag)
                h["hint_tokens"] = int(h.get("hint_tokens", 0)) + 1
                notes.append(f"+1 підказка за важливу зачіпку: {ev}")
    return notes


def _risk_word(value: int) -> str:
    value = int(value)
    if value < 25:
        return "низько"
    if value < 50:
        return "помірно"
    if value < 75:
        return "високо"
    return "критично"


def _scene_pace_text(state: Dict[str, Any]) -> str:
    loc = current_location(state)
    current = int(state["hero"].get("scene_turn", 0))
    limit = int(loc.get("limit", 4))
    if current < max(1, limit - 1):
        comment = "сцена ще має простір"
    elif current < limit:
        comment = "сцена наближається до вичерпання"
    else:
        comment = "сцена майже вичерпана, але ти можеш залишитись"
    return f"{current} із {limit} дій у цій локації — {comment}"


def _format_scene(text: str, state: Dict[str, Any], added: List[str], skill_notes: List[str], bonus_notes: List[str]) -> str:
    loc = current_location(state)
    h = state["hero"]
    blocks = [f"🎬 ХІД {state['turn']}", _paragraphs(text)]
    if added:
        blocks.append("📌 Нові докази:\n" + "\n".join([f"• {x}" for x in added]))
    if skill_notes:
        blocks.append("🧠 Навички розвиваються:\n" + "\n".join([f"• {x}" for x in skill_notes[-3:]]))
    if bonus_notes:
        blocks.append("💡 Ресурс підказок:\n" + "\n".join([f"• {x}" for x in bonus_notes]))
    exhaustion = _scene_exhaustion_note(state)
    if exhaustion:
        blocks.append("🕰️ Ритм сцени:\n" + exhaustion)
    blocks.append(
        f"📍 {loc['title']}\n"
        f"⏳ Темп сцени: {_scene_pace_text(state)}\n"
        f"🔥 Напруга справи: {_risk_word(h['pressure'])} ({h['pressure']}/100)\n"
        f"🚨 Ризик викриття: {_risk_word(h['exposure'])} ({h['exposure']}/100)\n"
        f"💡 Підказки: {_hint_status(h)}"
    )
    if h.get("difficulty") == "easy":
        blocks.append("💡 Мʼяка підказка:\n" + _strategic_hint(state))
    blocks.append(render_action_options(state))
    blocks.append("✍️ Напиши наступну дію Тараса. Можна коротко, можна як сцену.")
    return "\n\n".join(blocks)


def get_location_image(state: Dict[str, Any]) -> Optional[str]:
    return current_location(state).get("image")


async def handle_player_text(
    telegram_id: int,
    player_text: str,
) -> Tuple[str, Dict[str, Any], Optional[str]]:
    state = start_or_get(telegram_id)
    if not difficulty_complete(state):
        answer, state = choose_difficulty(telegram_id, player_text)
        return answer, state, "cover.png"
    if not setup_complete(state):
        answer, state = choose_character(telegram_id, player_text)
        return answer, state, "cover.png"

    intent = classify_intent(player_text)
    moved_text = None
    if intent == "move":
        moved_text = _move_if_requested(state, player_text)

    state, skill_notes = apply_intent_delta(state, intent)
    added: List[str] = []
    public_action = True

    if moved_text:
        scene_text = moved_text
    else:
        ep = load_episode()
        ai = await generate_scene_with_ai(state, player_text, intent, ep)
        if ai:
            scene_text = ai["scene_text"]
            added = apply_ai_delta(state, ai.get("state_delta", {}) or {})
            public_action = bool((ai.get("state_delta", {}) or {}).get("public", True))
            journal = (ai.get("state_delta", {}) or {}).get("journal") or f"Дія: {player_text[:160]}"
            db.add_journal(telegram_id, journal)
        else:
            scene_text, added, public_action = _scripted_scene(state, intent)

    update_npc_memory(state, current_location(state), intent, player_text, public_action)
    bonus_notes = _grant_hint_tokens(state, added)
    state["last_scene"] = scene_text
    db.save_state(telegram_id, state)
    if not moved_text:
        db.add_journal(telegram_id, f"Хід {state['turn']}: {player_text[:160]}")

    return _format_scene(scene_text, state, added, skill_notes, bonus_notes), state, get_location_image(state)


def evaluate_theory(telegram_id: int, theory: str) -> Tuple[str, Dict[str, Any]]:
    state = start_or_get(telegram_id)
    h = state["hero"]
    text = theory.lower()
    evidence_text = " ".join(h.get("evidence", [])).lower()
    score = 0
    notes = []
    if "флеш" in text or "контур" in text:
        if "флеш" in evidence_text or "контейнер" in evidence_text:
            score += 2
        else:
            notes.append("Флешка й «Контур» звучать логічно, але доказів ще замало.")
    if "портьє" in text or "клим" in text:
        if "портьє" in evidence_text or "журнал" in evidence_text:
            score += 2
        else:
            notes.append("Клим підозрілий, але поки це радше поведінка, ніж доказ.")
    if "порох" in text:
        if "порохівський" in evidence_text:
            score += 2
        else:
            notes.append("Порохівський може бути великим гравцем, але його ще треба привʼязати до сцени.")
    if "астахов" in text or "рос" in text or "дипломат" in text:
        if "дипломат" in evidence_text:
            score += 2
        else:
            notes.append("Російський слід імовірний, але потрібен конкретний канал звʼязку.")
    h.setdefault("theories", []).append(theory[:500])
    db.save_state(telegram_id, state)
    db.add_journal(telegram_id, f"Версія гравця: {theory[:500]}")
    if score >= 4:
        verdict = "Версія сильна. Вона ще не доведена, але вже небезпечна для тих, хто будував сцену."
    elif score >= 2:
        verdict = "Версія частково тримається. Є правильний напрямок, але бракує одного-двох твердих звʼязків."
    else:
        verdict = "Версія поки слабка. Вона може бути інтуїтивно правильною, але справа не прийме її без фактів."
    if not notes:
        notes.append("Наступний крок — знайти звʼязок між доказами, людьми й маршрутом грошей.")
    return "🧩 Аналіз версії\n\n" + verdict + "\n\n" + "\n".join([f"• {n}" for n in notes]), state
