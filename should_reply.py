import openai 
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def is_worth_replying(message_content):
    prompt = [
        {
            "role": "system",
            "content": (
                "You are an assistant that decides whether a Discord message is clearly directed at a user named Aiko.\n\n"
                "Reply with only 'yes' or 'no'.\n\n"
                "Say 'yes' if the message:\n"
                "- mentions 'aiko' by name\n"
                "- uses 'you', 'u', or 'your' to refer to Aiko\n"
                "- contains a greeting or question that would naturally be directed at her\n\n"
                "Say 'no' if the message:\n"
                "- is general chatter\n"
                "- is just emojis, memes, or unrelated reactions\n"
                "- is aimed at another user or group"
            )
        },
        {"role": "user", "content": message_content.strip()}
    ]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=prompt,
            temperature=0.2,
            top_p=0.9
        )
        decision = response.choices[0].message["content"].strip().lower()
        return decision.startswith("y")
    except Exception as e:
        print(f"[AI filter error] {e}")
        return False
