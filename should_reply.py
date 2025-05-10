import os
from openai import OpenAI

client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def is_worth_replying(history):
    """
    history: List of dicts like [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey~"}]
    Only the last 4 messages are needed.
    """

    # Keep only the last 4 exchanges
    context = history[-4:]

    messages = [
        {
            "role": "system",
            "content": (
                "You are a filter that decides if a new Discord message is clearly addressing a user named Aiko in an ongoing conversation.\n\n"
                "Only return 'yes' or 'no'.\n\n"
                "Say 'yes' if the most recent message:\n"
                "- mentions 'aiko'\n"
                "- uses 'you', 'u', or 'your' referring to Aiko\n"
                "- replies directly to something Aiko just said\n"
                "- is playful or flirty in a back-and-forth way\n\n"
                "Say 'no' if:\n"
                "- it’s general banter not aimed at Aiko\n"
                "- it talks to someone else\n"
                "- there’s no clear continuation or reference to Aiko"
            )
        },
        *context,
        {
            "role": "user",
            "content": "Should Aiko respond to that last message? Yes or no?"
        }
    ]

    try:
        response = client_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.2
        )
        decision = response.choices[0].message.content.strip().lower()
        return decision.startswith("y")
    except Exception as e:
        print(f"[AI filter error] {e}")
        return False
