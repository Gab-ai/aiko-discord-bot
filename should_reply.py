from openai import AsyncOpenAI
import os

client_ai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
AIKO_USER_ID = 1370781206534422569

async def is_worth_replying(
    history: list[dict],
    current_user_id: int,
    last_user_id: int | None,
    aiko_user_id: int,
    current_message: str
) -> bool:
    # Only keep messages not by Aiko
    recent = [msg for msg in history if msg.get("author_id") != aiko_user_id][-3:]
    transcript = "\n".join(f"{msg['role']}: {msg['content']}" for msg in recent)

    system_prompt = (
        "You are a judgment system for Aiko, a Discord user with chaotic e-girl energy. "
        "Your job is to decide whether the current message is meant for her.\n\n"
        "Say 'yes' if:\n"
        "- The message continues a conversation Aiko was part of\n"
        "- The message reacts to Aiko’s tone or phrasing (flirt, sarcasm, teasing, etc)\n"
        "- Aiko was the last to reply to this user and the user is replying again\n\n"
        "Say 'no' if:\n"
        "- The message is general or not tied to Aiko’s previous messages\n"
        "- It’s a new topic not involving Aiko\n\n"
        "Be slightly generous. Aiko enjoys attention. Reply ONLY with 'yes' or 'no'."
    )

    user_prompt = (
        f"{transcript}\n\n"
        f"[Aiko last replied to user ID: {last_user_id}]\n"
        f"[Current user ID: {current_user_id}]\n"
        f"[Current message: {current_message}]\n\n"
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
