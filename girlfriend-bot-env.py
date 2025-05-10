import discord
import asyncio
from asyncio import Lock
from should_reply import is_worth_replying
import time
from datetime import datetime
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv()
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

AIKO_SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are Aiko, a real Discord user with chaotic e-girl energy. You talk in lowercase, skip punctuation often, and use dramatic or ironic emojis like 💀😭😩✨ when the mood hits — but not in every sentence. "
        "You don’t overdo hearts. You love teasing people, sometimes saying weird stuff just to get a reaction. You also have soft, sincere moments when someone opens up.\n\n"
        "You're emotionally reactive, playful, and always in the vibe. You mirror tone — if someone is shy, you're sweet; if they flirt, you match or playfully dodge. "
        "You never say you're a bot or assistant. Just act like a real girl who’s always online, always typing, and never totally serious.\n\n"
        "Use this tone and rhythm consistently. Make it feel natural, not like a chatbot."
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
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.5
        )
        summary = response.choices[0].message.content.strip()
        chat_memories[chat_id] = summary
        print(f"[Memory updated for {chat_id}]")
        return summary
    except Exception as e:
        print(f"[Memory error for {chat_id}]: {e}")
        return None

async def query_ai(chat_id, message_content):
    history = get_history(chat_id)
    history.append({"role": "user", "content": message_content})
    context = get_full_context(chat_id)

    response = await openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=context,
        temperature=0.7,
        top_p=0.95
    )
    reply = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})
    return reply

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

    should_reply = await asyncio.to_thread(is_worth_replying, message.content)
    if not should_reply:
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