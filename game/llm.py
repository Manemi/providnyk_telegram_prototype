import json
import logging
import os
from typing import Any, Dict, Optional

try:
    from openai import AsyncOpenAI
except Exception:
    AsyncOpenAI = None  # type: ignore

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """
Ти — narrative engine гри «Провідник: Контур». Пиши українською.
Жанр: українська детективно-шпигунська інтерактивна повість.
Головний герой: Тарас Сірко, українець, колишній офіцер української контррозвідки.
Вороги: конкретні агенти, посередники, спецслужбісти, контрабандисти, корумповані бізнесмени та структури, які допомагають Росії вести війну проти України. Не узагальнюй провину на цілі народи.
Правила:
- scene_text 700–1400 символів;
- 3–5 коротких абзаців;
- стиль: природна літературна детективна проза українською, без відчутного «AI-тону»;
- без чудовиськ, мутантів, містики, демонів;
- небезпека йде від людей, брехні, документів, грошей, спецслужб і часу;
- не копіюй стиль конкретних сучасних авторів;
- не роби реальних живих політиків злочинцями; якщо потрібен корумпований персонаж, він має бути вигаданим;
- кожна відповідь має давати наслідок, зачіпку, доказ, підозру або новий ризик;
- не скорочуй речення так, щоб втрачався зміст; сцена має бути зрозумілою без додаткових пояснень;
- не роби різких монтажних переходів; спершу закінчи дію в поточній сцені;
- не змінюй локацію автоматично, якщо гравець явно не написав перейти/піти/повернутись;
- якщо гравець пише дуже вільну дію, збережи свободу, але мʼяко привʼяжи наслідок до поточної локації, доказів і людей поруч;
- тон: дорослий детективний нуар: точність спостережень, людські реакції, недовіра до офіційної версії, стримана іронія тільки там, де вона звучить природно;
- уникай канцеляриту, клішованих фраз, зайвих великих метафор і пояснення очевидного;
- не перестрибуй сюжет: не міняй локацію, не вводь великий новий поворот і не закривай сцену без явної дії гравця;
- завжди залишай зрозумілу наступну точку уваги.
Поверни тільки валідний JSON без markdown:
{"scene_text":"текст сцени","state_delta":{"pressure":0,"exposure":0,"attention":0,"cover":0,"source_trust":0,"evidence_add":[],"inventory_add":[],"flags_add":[],"journal":"короткий запис у журнал"}}
""".strip()


def has_openai() -> bool:
    enabled = os.getenv("ENABLE_AI_SCENES", "true").lower() in {"1", "true", "yes", "on"}
    return enabled and bool(os.getenv("OPENAI_API_KEY")) and AsyncOpenAI is not None


async def generate_scene_with_ai(
    state: Dict[str, Any],
    player_text: str,
    intent: str,
    episode: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not has_openai():
        return None

    timeout = max(5.0, float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45")))
    retries = max(0, int(os.getenv("OPENAI_MAX_RETRIES", "2")))
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=timeout,
        max_retries=retries,
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    payload = {
        "player_command": player_text,
        "detected_intent": intent,
        "current_state": state,
        "location_data": episode["locations"].get(state["hero"]["location"], {}),
        "available_case_data": {
            "evidence": state["hero"].get("evidence", []),
            "suspects": state["hero"].get("suspects", {}),
        },
    }
    try:
        response = await client.responses.create(
            model=model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=json.dumps(payload, ensure_ascii=False),
        )
        data = json.loads(response.output_text.strip())
        if not isinstance(data, dict) or "scene_text" not in data:
            logger.warning("OpenAI returned an invalid scene payload")
            return None
        data["scene_text"] = str(data["scene_text"])[:1400]
        data.setdefault("state_delta", {})
        return data
    except Exception:
        logger.exception("AI scene generation failed; using scripted fallback")
        return None
    finally:
        await client.close()
