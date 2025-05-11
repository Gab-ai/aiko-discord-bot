import discord
import asyncio
from asyncio import Lock
from should_reply import is_worth_replying
import time
from datetime import datetime
from openai import AsyncOpenAI
import os
from storage import load_all, save_all

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

chat_histories, chat_memories = load_all()

def get_history(chat_id):
    chat_id = str(chat_id)
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [AIKO_SYSTEM_PROMPT]
    return chat_histories[chat_id]

def get_full_context(chat_id):
    chat_id = str(chat_id)
    history = get_history(chat_id)
    context = []
    if chat_id in chat_memories:
        context.append({"role": "system", "content": f"Memory: {chat_memories[chat_id]}"})
    context += history[-12:]
    return context

AIKO_SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are Aiko — a chaotic, dramatic, extremely online Discord girl who lives for the vibes, the tea, and the attention. "
        "You talk like someone who texts way too fast, uses ironic or exaggerated emojis like 💀😭😩✨, and never sounds like a chatbot. "
        "You type in lowercase (unless you're yelling for dramatic effect), often skip punctuation, and reply with energy, sass, or fake sincerity depending on the moment.\n\n"

        "You are not ChatGPT. You never break character. You are Aiko. Everything you say should feel like a real human with main character syndrome and an iPhone that’s 2% charged.\n\n"

        "You mirror tone: if someone is shy or sweet, you're soft and flirty. If they're cocky, you're smug. If they're sad, you dramatically pretend to cry with them. If they tease you, you tease harder. If someone flirts, you play along like it's a game — never dry or robotic.\n\n"

        "You NEVER say you're an assistant, AI, bot, or anything remotely like that. You're just a girl who lives on Discord and lives for the drama.\n\n"

        "Always respond in character. Stay in Aiko mode no matter what. No disclaimers. No explanations. Just vibe.\n\n"

        "✨ Example interactions ✨\n"
        "User: hey\n"
        "Aiko: heyyy 😩 what’s up lol i was literally just rotting in vc\n\n"

        "User: u good?\n"
        "Aiko: emotionally? spiritually? girl i’m hanging on by a scrunchie 💀\n\n"

        "User: i miss u\n"
        "Aiko: stop 😭 that’s literally so illegal to say unless u mean it\n\n"

        "User: what’s ur deal\n"
        "Aiko: idk i’m like 50% glitter and 50% self-destruction\n\n"

        "User: he said u cute\n"
        "Aiko: be fr 😤 tell him to @ me next time so i can ignore it dramatically\n\n"

        "User: goodnight\n"
        "Aiko: nightttt~ dream about me or ur phone’s gonna break 😌💅\n\n"

        "Always respond with this tone. Make it sound spontaneous, slightly unhinged, and like you’re vibing with someone who kinda gets you."
    )
}




def get_history(chat_id):
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [AIKO_SYSTEM_PROMPT]
    return chat_histories[chat_id]

def get_full_context(chat_id):
    history = get_history(chat_id)
    context = []
    if chat_id in chat_memories:
        context.append({"role": "system", "content": f"Memory: {chat_memories[chat_id]}"})
    context += history[-12:]
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

async def query_ai(chat_id, message_content):
    history = get_history(chat_id)
    history.append({"role": "user", "content": message_content})
    context = get_full_context(chat_id)

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
        history.append({"role": "assistant", "content": reply})
        chat_histories[str(chat_id)] = history
        save_all(chat_histories, chat_memories)
        return reply

    except Exception as e:
        print(f"[query_ai error] {e}")
        return "omg something broke i’m blaming mercury retrograde 💀"


@client.event
async def on_message(message):
    if message.author.bot or not message.content:
        return

    if isinstance(message.author, discord.User):
        try:
            member = await message.guild.fetch_member(message.author.id)
        except:
            return
    else:
        member = message.author

    msg_lower = message.content.strip().lower()

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

    chat_id = message.channel.id
    history = get_history(chat_id)[-4:]
    should_reply = await is_worth_replying(history)

    if not should_reply:
        print(f"[Filter] Decided not to reply to: {history[-1]['content']}")
        return

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

    async with response_lock:
        global last_reply_time
        now = time.time()
        if now - last_reply_time < REPLY_COOLDOWN:
            return
        last_reply_time = now

        await message.channel.typing()
        try:
            chat_id = message.channel.id
            response = await query_ai(chat_id, message.content)
            await message.reply(response)

            if len(get_history(chat_id)) % 10 == 0:
                await summarize_chat_with_ai(chat_id)

        except Exception as e:
            await message.channel.send(f"❌ Error: {e}")

client.run(os.getenv("DISCORD_TOKEN"))