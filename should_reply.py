import requests

AI_API_ENDPOINT = "http://127.0.0.1:5000/v1/chat/completions"

def is_worth_replying(message_content):
    prompt = [
        {
            "role": "system",
            "content": (
                "You decide if a Discord message is clearly addressing Aiko directly. "
                "Reply only with 'yes' or 'no'.\n\n"
                "Say 'yes' if the message:\n"
                "- mentions 'aiko' by name (anywhere)\n"
                "- uses 'you', 'u', or 'your' in a way that addresses Aiko\n"
                "- asks a question or includes a greeting toward Aiko\n\n"
                "Say 'no' if:\n"
                "- it's just conversation not aimed at her\n"
                "- it's emojis, reactions, or inside jokes not involving her\n"
                "- it talks to another person or is unrelated banter"
            )
        },
        {"role": "user", "content": f"\"{message_content.strip()}\"\n\nAnswer:"}
    ]

    payload = {
        "model": "gpt-anything",
        "messages": prompt,
        "temperature": 0.2,
        "top_p": 0.9
    }

    try:
        response = requests.post(AI_API_ENDPOINT, json=payload)
        decision = response.json()["choices"][0]["message"]["content"].strip().lower()
        return decision.startswith("y")
    except Exception as e:
        print(f"[AI filter error] {e}")
        return False
