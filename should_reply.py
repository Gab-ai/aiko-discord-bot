from openai import AsyncOpenAI
import os

client_ai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def is_worth_replying(channel_history: list[dict]) -> bool:
    recent = channel_history[-3:]  # last 3 exchanges (dicts with "role" + "content")
    transcript = "\n".join(f"{msg['role']}: {msg['content']}" for msg in recent)

    try:
        response = await client_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You're an assistant that determines if the last few messages in a Discord chat are directed at Aiko, a user with chaotic e-girl energy.\n\n"
                        "Reply only with 'yes' or 'no'.\n\n"
                        "Say 'yes' if:\n"
                        "- Someone is replying to Aiko's last message\n"
                        "- Aiko is implied (e.g. sarcastic response, continued thread)\n"
                        "- The conversation feels like it’s part of an exchange with her\n\n"
                        "Say 'no' if:\n"
                        "- The messages are aimed at other users\n"
                        "- Aiko is not part of the conversation anymore\n"
                        "- It's general chatter not involving her"
                    )
                },
                {"role": "user", "content": f"{transcript}\n\nIs this directed at Aiko?"}
            ],
            temperature=0.2
        )

        decision = response.choices[0].message.content.strip().lower()
        return decision.startswith("y")

    except Exception as e:
        print(f"[AI filter error] {e}")
        return False
