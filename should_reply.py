from openai import AsyncOpenAI
import os

client_ai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def is_worth_replying(channel_history: list[dict], aiko_user_id: int) -> bool:
    # Exclude Aiko’s own messages
    recent = [msg for msg in channel_history if msg.get("author_id") != aiko_user_id][-3:]
    transcript = "\n".join(f"{msg['role']}: {msg['content']}" for msg in recent)

    try:
        response = await client_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a filter that determines whether the last few messages in a Discord chat are directed at Aiko, a chaotic e-girl user.\n"
                        "Aiko replies impulsively, like a real person — she doesn't interrupt unrelated convos.\n\n"
                        "You will answer with **only 'yes' or 'no'**.\n\n"
                        "Say 'yes' if:\n"
                        "- The latest message is clearly addressed to Aiko (by name or tone)\n"
                        "- Aiko was the last one to speak and the user is replying\n"
                        "- A joke, reaction, or retort is clearly meant for Aiko\n"
                        "- The user is continuing a thread where Aiko is involved\n\n"
                        "Say 'no' if:\n"
                        "- The user is talking to someone else\n"
                        "- The conversation has moved on from Aiko\n"
                        "- The messages are too vague to confidently say they’re directed at Aiko\n"
                        "- It's general commentary, news, or chatter not involving her\n\n"
                        "Be cautious. When in doubt, answer 'no'."
                    )
                },
                {"role": "user", "content": f"{transcript}\n\nIs the last message directed at Aiko?"}
            ],
            temperature=0.1
        )

        if not response.choices:
            print("[AI filter warning] No choices returned.")
            return False

        decision = response.choices[0].message.content.strip().lower()
        return decision.startswith("y")

    except Exception as e:
        print(f"[AI filter error] {e}")
        return False
