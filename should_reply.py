from openai import AsyncOpenAI
import os

client_ai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def is_worth_replying(
    history: list[dict],
    current_user_id: int,
    last_user_id: int | None,
    aiko_user_id: int,
    current_message: str
) -> bool:
    # Filter out Aiko’s messages
    recent = [msg for msg in history if msg.get("author_id") != aiko_user_id][-3:]
    transcript = "\n".join(f"{msg['role']}: {msg['content']}" for msg in recent)

    system_prompt = (
        "You are an assistant helping a Discord bot named Aiko decide if someone is talking to her.\n\n"
        "- Say 'yes' if the user is replying to Aiko’s previous message or continuing a conversation with her.\n"
        "- Say 'yes' if Aiko was last addressed and the tone implies follow-up (sarcasm, flirty, annoyed, etc).\n"
        "- Say 'no' if it’s general chatter or unrelated to her messages.\n"
        "- Do NOT be overly cautious — Aiko thrives on messy attention.\n\n"
        "ONLY reply with 'yes' or 'no'."
    )

    user_prompt = (
        f"Previous messages:\n{transcript}\n\n"
        f"Last user Aiko replied to: {last_user_id}\n"
        f"Current message: {current_message}\n"
        f"Current user ID: {current_user_id}\n\n"
        "Is this message directed at Aiko?"
    )

    try:
        response = await client_ai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            top_p=0.9,
        )
        decision = response.choices[0].message.content.strip().lower()
        return decision.startswith("y")

    except Exception as e:
        print(f"[AI filter error] {e}")
        return False

