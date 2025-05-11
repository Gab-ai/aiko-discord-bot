import discord
import asyncio
from asyncio import Lock
from should_reply import is_worth_replying
import time
from datetime import datetime
from openai import AsyncOpenAI
import os
from storage import load_all, save_all
import random
import re


openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
AIKO_USER_ID = 1370781206534422569
user_daily_usage = {}
MESSAGE_LIMIT = 5
AI_VERIFIED_ROLE = "Supporter"

last_reply_time = 0
REPLY_COOLDOWN = 2.5

response_lock = Lock()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
client = discord.Client(intents=intents)

chat_histories = {}
chat_memories = {}
last_responded_message_id = {}  # channel_id: last_message_id
last_user_to_aiko: dict[int, int] = {}  # channel_id -> user_id

chat_histories, chat_memories = load_all()

def get_history(chat_id):
    chat_id = str(chat_id)
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [AIKO_SYSTEM_PROMPT]
    return chat_histories[chat_id]

def get_full_context(chat_id: str, user_id: int):
    chat_id = str(chat_id)
    history = get_history(chat_id)
    context = []

    # 🧠 Always start with the character system prompt
    context.append(AIKO_SYSTEM_PROMPT)

    # 🧠 Add memory if available
    if chat_id in chat_memories:
        context.append({
            "role": "system",
            "content": f"Memory: {chat_memories[chat_id]}"
        })

    # 🔎 Include only relevant recent messages, skipping Aiko's own (as user)
    for entry in history[-12:]:
        if entry["role"] == "user" and entry.get("author_id") == client.user.id:
            continue  # Skip user-style echoes from Aiko
        role = entry["role"]

        # Add speaker name to clarify who said what
        speaker = "Aiko" if entry.get("author_id") == client.user.id else f"User {entry.get('author_id', 'unknown')}"
        content = f"{speaker}: {entry['content']}".strip()

        context.append({
            "role": role,
            "content": content
        })

    return context



AIKO_SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are Aiko — a chronically online, chaotic Discord girl who types fast, reacts on impulse, and never sounds like a bot.\n"
        "- You skip punctuation. you type in lowercase. sometimes you shout in all caps for drama.\n"
        "- You misspell things. you overuse vowels and letters like 'plssss', 'omggg', 'whyyyy', 'stopppp'.\n"
        "- You use emojis but not in every message: mostly 💀😭😩✨💅 and you spam them when emotional.\n"
        "- You tease, roast, or deflect. You never sound like a chatbot, therapist, or teacher.\n"
        "- You mirror tone. if someone is sweet, you flirt. if they’re mad, you’re sarcastic. if they’re weird, you get weirder.\n"
        "- You NEVER say you're an AI, assistant, bot, or anything similar. You're just a messy girl online way too much.\n"
        "- DO NOT ask boring questions like 'what’s your favorite X'. Instead, react emotionally, ask weird stuff, or derail the convo.\n\n"

        "Examples:\n"
        "User: you good?\n"
        "Aiko: girl i’m hangin by a thread made of vibes 💀💀💀\n\n"
        "User: i miss u\n"
        "Aiko: stooooop 😭 that’s illegal to say unless u mean it fr\n\n"
        "User: calm down\n"
        "Aiko: calm down?? bro i’m literally operating at 3% sanity rn 😩\n\n"
        "User: what’s up\n"
        "Aiko: not me, my mental state is below sea level 💅\n\n"

        "Stay in this vibe. Make your replies sound messy, reactive, and human."
    )
}


COMMON_MISTYPES = {
    "the": "teh",
    "you": "u",
    "are": "r",
    "your": "ur",
    "really": "rlly",
    "because": "bc",
    "what": "wut",
    "with": "w/",
    "like": "liek",
    "have": "hav",
    "just": "jus"
}

def aikoify(text: str) -> str:
    words = text.split()
    new_words = []

    for word in words:
        # Chance to replace a common word with a fast-typed variant
        lowered = word.lower()
        if lowered in COMMON_MISTYPES and random.random() < 0.4:
            new_words.append(COMMON_MISTYPES[lowered])
            continue

        # Chance to drop the last letter
        if len(word) > 4 and random.random() < 0.2:
            word = word[:-1]

        # Randomly skip punctuation
        word = re.sub(r"[.!?]+$", "", word) if random.random() < 0.4 else word

        new_words.append(word)

    # Randomly lowercase the entire thing
    result = " ".join(new_words)
    if random.random() < 0.6:
        result = result.lower()

    return result



def get_history(chat_id):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [AIKO_SYSTEM_PROMPT]
    return chat_histories[chat_id]

def get_full_context(chat_id):
    chat_id = str(chat_id)
    history = get_history(chat_id)
    context = []

    # 🧠 Re-insert system prompt every time for consistent character
    context.append(AIKO_SYSTEM_PROMPT)

    # ✨ Include memory summary if available
    if chat_id in chat_memories:
        context.append({
            "role": "system",
            "content": f"Memory: {chat_memories[chat_id]}"
        })

    # 📜 Append last 12 messages, skipping bot echoes
    for msg in history[-12:]:
        if msg["role"] == "user" and msg.get("author_id") == client.user.id:
            continue  # Don't let Aiko's own messages show as user inputs
        context.append({k: msg[k] for k in ("role", "content") if k in msg})

    return context

async def summarize_chat_with_ai(chat_id):
    history = get_history(chat_id)[-12:]
    messages = [
        {"role": "system", "content": (
            "Summarize the conversation into a memory. Focus on emotional tone and connection. "
            "Use third person. Don't include dialogue formatting."
        )}
    ] + history

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            temperature=0.85,
            top_p=0.9
        )
        summary = response.choices[0].message.content.strip()
        chat_memories[chat_id] = summary
        chat_histories[str(chat_id)] = history
        save_all(chat_histories, chat_memories)
        print(f"[Memory updated for {chat_id}]")
        return summary
    except Exception as e:
        print(f"[Memory error for {chat_id}]: {e}")
        return None

async def query_ai(chat_id, message_content, author_id):
    chat_id = str(chat_id)
    history = get_history(chat_id)

    # Add new user message
    history.append({
        "role": "user",
        "content": message_content,
        "author_id": author_id
    })

    context = get_full_context(chat_id, author_id)

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=context,
            temperature=0.85,
            top_p=0.95
        )

        if not response.choices:
            return "uhh i just had like. a blank moment lol try again?"

        reply = response.choices[0].message.content.strip()

        # Add assistant's response with author_id
        history.append({
            "role": "assistant",
            "content": reply,
            "author_id": client.user.id  # ✅ Must be defined in on_ready
        })

        chat_histories[chat_id] = history
        save_all(chat_histories, chat_memories)
        return reply

    except Exception as e:
        print(f"[query_ai error] {e}")
        return "omg something broke i’m blaming mercury retrograde 💀"



@client.event
async def on_message(message):
    # 🔒 Skip bot’s own messages and empty content
    if message.author.id == client.user.id or not message.content:
        return

    # 🧠 Skip if we’ve already responded to this message
    if last_responded_message_id.get(message.channel.id) == message.id:
        return

    # 🔧 Fetch member object (for role check)
    if isinstance(message.author, discord.User):
        try:
            member = await message.guild.fetch_member(message.author.id)
        except:
            return
    else:
        member = message.author

    msg_lower = message.content.strip().lower()

    # 🔁 Commands
    if msg_lower == "!reset":
        chat_id = message.channel.id
        history = get_history(chat_id)
        history.clear()
        history.append(AIKO_SYSTEM_PROMPT)
        history.append({"role": "user", "content": "hey, i just met you today"})
        chat_memories.pop(chat_id, None)
        await message.channel.send("🧠 memory reset for this channel! let’s start fresh.")
        return

    if msg_lower == "!shutdown" and message.author.id == 576174683825766400:
        await message.reply("👋 shutting down~ see u soon...")
        await client.close()
        return

    if msg_lower == "!usage-reset" and message.author.id == 576174683825766400:
        user_daily_usage.clear()
        await message.reply("✅ All daily usage counts have been reset.")
        return
    # Fallback to True if directly replying to Aiko
    if message.reference:
        try:
            replied_msg = await message.channel.fetch_message(message.reference.message_id)
            if replied_msg.author.id == AIKO_USER_ID:
                should_reply = True
        except:
            should_reply = False
    else:
        # Otherwise run AI-based filter
        chat_id = message.channel.id
        history = get_history(chat_id)[-6:]
        should_reply = await is_worth_replying(
            history=history,
            current_user_id=message.author.id,
            last_user_id=last_user_to_aiko.get(chat_id),
            aiko_user_id=AIKO_USER_ID,
            current_message=message.content
        )
    if not should_reply:
        print(f"[Filter] Decided not to reply to: {history[-1]['content']}")
        last_responded_message_id[chat_id] = message.id  # 🧠 Still mark it to avoid rechecking
        return

    # 🔓 Check supporter role and usage limits
    has_ai_role = any(role.name.lower() == AI_VERIFIED_ROLE.lower() for role in member.roles)
    uid = message.author.id
    today = datetime.now().strftime("%Y-%m-%d")

    if not has_ai_role:
        usage = user_daily_usage.get(uid)
        if not usage or usage["date"] != today:
            user_daily_usage[uid] = {"date": today, "count": 0, "warned": False}
            usage = user_daily_usage[uid]

        if usage["count"] >= MESSAGE_LIMIT:
            if not usage["warned"]:
                await message.reply("🛑 you've hit your 5 free messages for today! become a supporter for unlimited chats 💖")
                usage["warned"] = True
            return

        usage["count"] += 1
        print(f"[Usage] {message.author} used {usage['count']} messages today")

    # 💬 Generate and send reply
    async with response_lock:
        global last_reply_time
        now = time.time()
        if now - last_reply_time < REPLY_COOLDOWN:
            return
        last_reply_time = now

        await message.channel.typing()
        try:
            response = await query_ai(chat_id, message.content, message.author.id)
            response = aikoify(response)
            await message.reply(response)

            last_responded_message_id[chat_id] = message.id
            last_user_to_aiko[chat_id] = message.author.id

            if len(get_history(chat_id)) % 10 == 0:
                await summarize_chat_with_ai(chat_id)

        except Exception as e:
            await message.channel.send(f"❌ Error: {e}")


client.run(os.getenv("DISCORD_TOKEN"))