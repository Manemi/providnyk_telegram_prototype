from typing import Any, Dict, List, Tuple


def clamp(value: int, min_value: int = 0, max_value: int = 100) -> int:
    return max(min_value, min(max_value, int(value)))


def _add_unique(items: List[str], value: str) -> bool:
    value = str(value).strip()
    if not value:
        return False
    if value not in items:
        items.append(value[:160])
        return True
    return False


def skill_level(value: int) -> str:
    if value < 10:
        return "початковий"
    if value < 22:
        return "робочий"
    if value < 40:
        return "сильний"
    if value < 65:
        return "дуже сильний"
    return "майстерний"


def _raise_skill(hero: Dict[str, Any], skill: str, amount: int, reason: str) -> str | None:
    skills = hero.setdefault("skills", {})
    before = clamp(skills.get(skill, 0))
    after = clamp(before + amount)
    skills[skill] = after
    if after > before:
        note = f"{skill}: {before}→{after} — {reason}"
        hero.setdefault("skill_log", []).append(note)
        hero["skill_log"] = hero["skill_log"][-12:]
        return note
    return None


def apply_personality(state: Dict[str, Any], option: Dict[str, Any]) -> Dict[str, Any]:
    hero = state["hero"]
    effects = option.get("effects", {})
    for key in ["attention", "pressure", "source_trust", "cover", "exposure"]:
        if key in effects:
            hero[key] = clamp(hero.get(key, 0) + int(effects[key]))
    for skill, amount in effects.get("skills", {}).items():
        _raise_skill(hero, skill, int(amount), "стартовий характер героя")
    hero["setup_complete"] = True
    hero["personality"] = option.get("key")
    hero["personality_title"] = option.get("title")
    hero["personality_tone"] = option.get("tone")
    state["case_status"] = "open"
    return state


def apply_intent_delta(state: Dict[str, Any], intent: str) -> Tuple[Dict[str, Any], List[str]]:
    hero = state["hero"]
    style = state["moral_style"]
    skill_notes: List[str] = []

    if intent == "inspect":
        hero["pressure"] = clamp(hero["pressure"] + 1)
        style["careful"] += 1
        note = _raise_skill(hero, "Спостережливість", 1, "уважний огляд сцени")
        if note: skill_notes.append(note)
    elif intent == "analyze":
        hero["attention"] = clamp(hero["attention"] + 1)
        hero["pressure"] = clamp(hero["pressure"] - 1)
        style["analytical"] += 1
        for sk, why in [("Аналітичне мислення", "побудова логічного висновку"), ("Самоконтроль", "пауза замість поспіху")]:
            note = _raise_skill(hero, sk, 1, why)
            if note: skill_notes.append(note)
    elif intent == "question":
        hero["source_trust"] = clamp(hero["source_trust"] + 1)
        style["diplomatic"] += 1
        for sk, why in [("Переговори", "розмова зі свідком"), ("Читання людей", "оцінка реакції співрозмовника")]:
            note = _raise_skill(hero, sk, 1, why)
            if note: skill_notes.append(note)
    elif intent == "pressure":
        hero["pressure"] = clamp(hero["pressure"] + 5)
        hero["exposure"] = clamp(hero["exposure"] + 3)
        style["aggressive"] += 1
        for sk, why in [("Психологічний тиск", "жорсткий допит"), ("Ораторське мистецтво", "контроль темпу розмови")]:
            note = _raise_skill(hero, sk, 1, why)
            if note: skill_notes.append(note)
    elif intent == "deceive":
        hero["cover"] = clamp(hero["cover"] - 2)
        hero["pressure"] = clamp(hero["pressure"] + 2)
        style["deceptive"] += 1
        note = _raise_skill(hero, "Легенда під прикриттям", 1, "робота з напівправдою і легендою")
        if note: skill_notes.append(note)
    elif intent == "follow":
        hero["exposure"] = clamp(hero["exposure"] + 4)
        hero["pressure"] = clamp(hero["pressure"] + 3)
        for sk, why in [("Контрспостереження", "робота з хвостом"), ("Фізична витривалість", "рух під напругою")]:
            note = _raise_skill(hero, sk, 1, why)
            if note: skill_notes.append(note)
    elif intent == "move":
        note = _raise_skill(hero, "Польова тактика", 1, "зміна точки розслідування без застою")
        if note: skill_notes.append(note)
    elif intent == "wait":
        hero["pressure"] = clamp(hero["pressure"] - 2)
        hero["exposure"] = clamp(hero["exposure"] + 1)
        note = _raise_skill(hero, "Самоконтроль", 1, "витримка замість поспіху")
        if note: skill_notes.append(note)
    elif intent == "use_item":
        hero["attention"] = clamp(hero["attention"] + 1)
        note = _raise_skill(hero, "Письмова фіксація доказів", 1, "акуратна робота з предметами і доказами")
        if note: skill_notes.append(note)

    hero["scene_turn"] = int(hero.get("scene_turn", 0)) + 1
    hero["chapter_turn"] = int(hero.get("chapter_turn", 0)) + 1
    state["turn"] += 1
    return state, skill_notes


def apply_scene_delta(state: Dict[str, Any], scene: Dict[str, Any]) -> List[str]:
    hero = state["hero"]
    added = []
    for key in ["pressure", "exposure", "attention", "cover", "source_trust"]:
        if key in scene and isinstance(scene[key], int):
            hero[key] = clamp(hero.get(key, 0) + scene[key])
    for ev in scene.get("evidence_add", []) or []:
        if _add_unique(hero["evidence"], ev):
            added.append(ev)
    for item in scene.get("inventory_add", []) or []:
        _add_unique(hero["inventory"], item)
    for flag in scene.get("flags_add", []) or []:
        _add_unique(hero["flags"], flag)
    updates = scene.get("suspect_update", {}) or {}
    for name, status in updates.items():
        if name in hero["suspects"]:
            hero["suspects"][name]["status"] = str(status)[:160]
    return added


def _safe_delta(value: int, low: int = -6, high: int = 6) -> int:
    """AI can influence the state, but cannot spike global tension too hard in one move."""
    return max(low, min(high, int(value)))


def apply_ai_delta(state: Dict[str, Any], delta: Dict[str, Any]) -> List[str]:
    hero = state["hero"]
    added = []
    for key in ["pressure", "exposure", "attention", "cover", "source_trust"]:
        if key in delta and isinstance(delta[key], int):
            hero[key] = clamp(hero.get(key, 0) + _safe_delta(delta[key]))
    for ev in delta.get("evidence_add", []) or []:
        if _add_unique(hero["evidence"], ev):
            added.append(ev)
    for item in delta.get("inventory_add", []) or []:
        _add_unique(hero["inventory"], item)
    for flag in delta.get("flags_add", []) or []:
        _add_unique(hero["flags"], flag)
    return added


def update_npc_memory(state: Dict[str, Any], location: Dict[str, Any], intent: str, player_text: str, public: bool = True) -> List[str]:
    if not public:
        return []
    hero = state["hero"]
    memory = hero.setdefault("npc_memory", {})
    npcs = location.get("npcs", []) or []
    if not npcs:
        return []

    phrase_by_intent = {
        "inspect": "бачив, що Тарас працює уважно й не чіпає зайвого",
        "analyze": "запамʼятав, що Тарас робить висновки без показного шуму",
        "question": "памʼятає, що Тарас ставив точні питання без крику",
        "pressure": "памʼятає, що Тарас тиснув жорстко і не відступав",
        "deceive": "відчуває, що Тарас говорив не всю правду",
        "follow": "помітив, що Тарас працює як оперативник, а не турист",
        "move": "бачив, що Тарас швидко змінив точку й не застряг",
        "wait": "запамʼятав його витримку й небажання метушитись",
        "use_item": "бачив, що Тарас акуратно фіксує речі й докази",
        "unknown": "памʼятає неясну, але помітну дію Тараса"
    }
    line = phrase_by_intent.get(intent, phrase_by_intent["unknown"])
    changed: List[str] = []
    for npc in npcs:
        rec = memory.setdefault(npc, {"trust": 0, "fear": 0, "respect": 0, "suspicion": 0, "memories": []})
        if intent in ["question", "inspect", "analyze", "use_item", "wait"]:
            rec["respect"] = clamp(rec.get("respect", 0) + 1, -100, 100)
            rec["trust"] = clamp(rec.get("trust", 0) + 1, -100, 100)
        elif intent == "pressure":
            rec["fear"] = clamp(rec.get("fear", 0) + 2, -100, 100)
            rec["suspicion"] = clamp(rec.get("suspicion", 0) + 1, -100, 100)
            rec["trust"] = clamp(rec.get("trust", 0) - 1, -100, 100)
        elif intent == "deceive":
            rec["suspicion"] = clamp(rec.get("suspicion", 0) + 2, -100, 100)
            rec["trust"] = clamp(rec.get("trust", 0) - 2, -100, 100)
        elif intent == "follow":
            rec["suspicion"] = clamp(rec.get("suspicion", 0) + 1, -100, 100)
            rec["respect"] = clamp(rec.get("respect", 0) + 1, -100, 100)
        rec["memories"].append(line + f"; команда гравця: {player_text[:90]}")
        rec["memories"] = rec["memories"][-5:]
        changed.append(npc)
    return changed
