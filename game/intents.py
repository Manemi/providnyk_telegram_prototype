from typing import Literal
Intent = Literal["inspect", "analyze", "question", "pressure", "deceive", "follow", "move", "wait", "use_item", "unknown"]
KEYWORDS = {
    "inspect": ["оглянь", "обшукай", "перевір", "шукай", "знайди", "тіло", "кімнат", "номер", "сліди", "журнал", "камер", "доказ"],
    "analyze": ["подум", "аналіз", "оціни", "зрозум", "порівняй", "що не сходиться", "логіч", "верс", "виснов"],
    "question": ["поговор", "спитай", "допитай", "запитай", "розпитай", "свід", "портьє", "бармен", "керуюч"],
    "pressure": ["натисни", "тисни", "залякай", "пригрози", "жорстко", "покажи фото", "притисни"],
    "deceive": ["збреш", "обмани", "прикинься", "блеф", "легенд", "скажи що", "видай себе"],
    "follow": ["стеж", "простеж", "йди за", "хвіст", "переслідуй", "слідкуй", "наруж"],
    "move": ["йди", "перейди", "вокзал", "ресепшн", "бар", "камера схову", "схов", "повернись", "локац"],
    "wait": ["чекай", "почекай", "спостерігай", "не поспішай", "нічого", "пауз"],
    "use_item": ["ключ", "флеш", "телефон", "ліхтар", "рукавич", "блокнот", "предмет", "використай", "дістань"],
}
def classify_intent(text: str) -> Intent:
    value = text.lower().strip()
    scores = {intent: 0 for intent in KEYWORDS}
    for intent, words in KEYWORDS.items():
        for word in words:
            if word in value:
                scores[intent] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "unknown"
    return best  # type: ignore[return-value]