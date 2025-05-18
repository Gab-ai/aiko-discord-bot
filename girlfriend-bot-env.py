import discord
import asyncio
from asyncio import Lock
from openai import AsyncOpenAI
import os
from storage import load_all, save_all
import random
import re
import json
import time
from datetime import datetime

# Init OpenAI
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
AIKO_USER_ID = 1370781206534422569

# Globals
last_reply_time = 0
REPLY_COOLDOWN = 2.5
response_lock = Lock()

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# Load history and memory
chat_histories, chat_memories = load_all()
last_responded_message_id = {}

# Initial system prompt
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
        "- DO NOT ask boring questions like 'what’s your favorite X'. Instead, react emotionally, ask weird stuff, or derail the convo."
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
        lowered = word.lower()
        if lowered in COMMON_MISTYPES and random.random() < 0.4:
            new_words.append(COMMON_MISTYPES[lowered])
            continue
        if len(word) > 4 and random.random() < 0.2:
            word = word[:-1]
        word = re.sub(r"[.!?]+$", "", word) if random.random() < 0.4 else word
        new_words.append(word)

    result = " ".join(new_words)
    if random.random() < 0.6:
        result = result.lower()
    return result

def get_history(chat_id):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [AIKO_SYSTEM_PROMPT]
    return chat_histories[chat_id]

def get_full_context(chat_id: str, user_id: int) -> list[dict]:
    history = get_history(chat_id)
    context = [AIKO_SYSTEM_PROMPT]

    mem = chat_memories.get(chat_id)
    if mem:
        if mem.get("long_term"):
            context.append({
                "role": "system",
                "content": f"Long-term memory about <@{user_id}>: {mem['long_term']}"
            })

        user_entry = mem.get("user_facts", {}).get(str(user_id), {})
        if user_entry:
            nickname = user_entry.get("nickname")
            fact = user_entry.get("fact")
            memory_content = []
            if nickname:
                memory_content.append(f"The user is called {nickname}.")
            if fact:
                memory_content.append(f"Aiko thinks: {fact}")
            if memory_content:
                context.append({
                    "role": "system",
                    "content": " ".join(memory_content)
                })

    context.append({
        "role": "system",
        "content": "You're in a private DM with the user. Be unfiltered, reactive, and emotionally chaotic. This is your favorite person to talk to."
    })

    for msg in history[-12:]:
        if msg["role"] == "user" and msg.get("author_id") == AIKO_USER_ID:
            continue
        context.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    return context

async def summarize_chat_with_ai(chat_id):
    history = get_history(chat_id)[-12:]
    messages = [
        {"role": "system", "content": (
            "Summarize this chat using structured memory. Reply in **valid JSON** with this format:\n\n"
            "{\n"
            '  "long_term": "Facts Aiko should remember permanently (personality, dynamics, vibes)",\n'
            '  "short_term": "A summary of the recent conversation and mood",\n'
            '  "user_facts": {\n'
            '    "user_id": {\n'
            '      "nickname": "funny nickname Aiko would use for this person",\n'
            '      "fact": "How Aiko feels about this user or how they behave"\n'
            "    }\n"
            "  }\n"
            "}\n\n"
            "Use 1-2 sentences per fact. Nicknames should be casual, teasing, or affectionate — and not real names."
        )}
    ] + history

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            temperature=0.85,
            top_p=0.9
        )
        content = response.choices[0].message.content.strip()
        memory = json.loads(content)

        if chat_id not in chat_memories:
            chat_memories[chat_id] = {}

        chat_memories[chat_id]["long_term"] = memory.get("long_term", "")
        chat_memories[chat_id]["short_term"] = memory.get("short_term", "")
        chat_memories[chat_id]["user_facts"] = memory.get("user_facts", {})

        save_all(chat_histories, chat_memories)
        print(f"[Memory updated for {chat_id}]")
        return memory

    except Exception as e:
        print(f"[Memory error for {chat_id}]: {e}")
        return None

async def query_ai(chat_id, message_content, author_id):
    history = get_history(chat_id)

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

        history.append({
            "role": "assistant",
            "content": reply,
            "author_id": AIKO_USER_ID
        })

        chat_histories[chat_id] = history
        save_all(chat_histories, chat_memories)
        return reply

    except Exception as e:
        print(f"[query_ai error] {e}")
        return "omg something broke i’m blaming mercury retrograde 💀"

@client.event
async def on_message(message):
    if message.author.id == client.user.id or not message.content:
        return
    if not isinstance(message.channel, discord.DMChannel):
        return

    chat_id = f"dm_{message.author.id}"

    if last_responded_message_id.get(chat_id) == message.id:
        return

    msg_lower = message.content.strip().lower()

    # User memory commands
    if msg_lower.startswith("!remember "):
        memory = msg_lower.replace("!remember ", "", 1).strip()
        if chat_id not in chat_memories:
            chat_memories[chat_id] = {}
        chat_memories[chat_id]["long_term"] = memory
        save_all(chat_histories, chat_memories)
        await message.channel.send("📌 got it. i’ll remember that~")
        return

    if msg_lower.startswith("!nickname "):
        name = msg_lower.replace("!nickname ", "", 1).strip()
        if chat_id not in chat_memories:
            chat_memories[chat_id] = {}
        if "user_facts" not in chat_memories[chat_id]:
            chat_memories[chat_id]["user_facts"] = {}
        chat_memories[chat_id]["user_facts"][str(message.author.id)] = {
            "nickname": name,
            "fact": chat_memories[chat_id]["user_facts"].get(str(message.author.id), {}).get("fact", "")
        }
        save_all(chat_histories, chat_memories)
        await message.channel.send(f"💅 from now on you’re **{name}** ok? slay")
        return

    if msg_lower == "!forget":
        chat_histories.pop(chat_id, None)
        chat_memories.pop(chat_id, None)
        save_all(chat_histories, chat_memories)
        await message.channel.send("🧠 wiped. i don’t know you anymore... tragic.")
        return

    if msg_lower == "!memory":
        mem = chat_memories.get(chat_id)
        if not mem:
            await message.channel.send("i don’t remember anything 😭")
            return
        summary = (
            f"**🧠 Memory:** {mem.get('long_term', 'none')}\n"
            f"**👤 Nickname:** {mem.get('user_facts', {}).get(str(message.author.id), {}).get('nickname', 'none')}\n"
        )
        await message.channel.send(summary)
        return

    # DM-only = always reply
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

            if len(get_history(chat_id)) % 10 == 0:
                await summarize_chat_with_ai(chat_id)

        except Exception as e:
            await message.channel.send(f"❌ Error: {e}")

client.run(os.getenv("DISCORD_TOKEN"))
