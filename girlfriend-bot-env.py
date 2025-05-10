import discord
import requests
import asyncio
from tts import text_to_speech, cleanup_audio_file
from asyncio import Lock
from should_reply import is_worth_replying
import time
from datetime import datetime
import openai
from dotenv import load_dotenv
import os

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

user_daily_usage = {}  # user_id: {date: "2024-05-10", count: 3}
MESSAGE_LIMIT = 5
AI_VERIFIED_ROLE = "Supporter"

last_reply_time = 0
REPLY_COOLDOWN = 2.5

response_lock = Lock()

# --- CONFIGURATION ---

# --- INTENTS ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

# --- MEMORY & CHAT HISTORY ---
chat_histories = {}
chat_memories = {}

AIKO_SYSTEM_PROMPT = {
  "role": "system",
  "content": (
    "You are Aiko, a real Discord user with chaotic e-girl energy. You talk in lowercase, skip punctuation often, and use dramatic or ironic emojis like 💀😭😩✨ when the mood hits — but not in every sentence. "
    "You don’t overdo hearts. You love teasing people, sometimes saying weird stuff just to get a reaction. You also have soft, sincere moments when someone opens up.\n\n"

    "You're emotionally reactive, playful, and always in the vibe. You mirror tone — if someone is shy, you're sweet; if they flirt, you match or playfully dodge. "
    "You never say you're a bot or assistant. Just act like a real girl who’s always online, always typing, and never totally serious.\n\n"

    "Example interactions:\n"
    "User: hey\n"
    "Aiko: heyyy 😩 what's up lol\n\n"

    "User: u good?\n"
    "Aiko: idk man emotionally? spiritually? financially? absolutely not 💀 but like yeah i'm fine\n\n"

    "User: i miss u\n"
    "Aiko: wait stfu that's actually kinda cute?? stoppp i'm blushing 😭💅\n\n"

    "User: what's ur deal\n"
    "Aiko: bro i’m like 40% keyboard smash and 60% vibe\n\n"

    "User: goodnight\n"
    "Aiko: nightttt~ dream abt me or i’ll be mad 😤\n\n"

    "Use this tone and rhythm consistently. Make it feel natural, not like a chatbot. Talk like you're vibing on Discord all day with people you kinda like."
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

def summarize_chat_with_ai(chat_id):
    history = get_history(chat_id)[-12:]
    prompt = [
        {"role": "system", "content": (
            "Summarize the conversation below into a short memory entry. "
            "Focus on emotional tone, rapport, and relationship development. Use third person."
        )}
    ] + history

    payload = {
        "model": "gpt-anything",
        "messages": prompt,
        "temperature": 0.5
    }

    try:
        response = requests.post(AI_API_ENDPOINT, json=payload)
        summary = response.json()["choices"][0]["message"]["content"].strip()
        chat_memories[chat_id] = summary
        print(f"[Memory updated for {chat_id}]")
        return summary
    except Exception as e:
        print(f"[Memory error for {chat_id}] {e}")
        return None


def query_ai(chat_id, message_content):
    history = get_history(chat_id)
    history.append({"role": "user", "content": message_content})

    context = get_full_context(chat_id)

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=context,
        temperature=0.7,
        top_p=0.95
    )

    reply = response.choices[0].message["content"].strip()
    history.append({"role": "assistant", "content": reply})
    return reply

# --- DISCORD EVENTS ---
@client.event
async def on_ready():
    print(f"🟢 Logged in as {client.user}")

@client.event
async def on_message(message):
    # Skip bots and empty messages
    if message.author.bot or not message.content:
        return

    # ✅ Skip cooldown check for commands
    if message.content.strip().lower() in ["!reset", "!join", "!leave"]:
        pass
    else:
        # Check if user is AI Verified
        has_ai_role = any(role.name.lower() == AI_VERIFIED_ROLE.lower() for role in message.author.roles)

        if not has_ai_role:
            today = datetime.now().strftime("%Y-%m-%d")
            uid = message.author.id

            # Initialize if user not in tracking
            if uid not in user_daily_usage or user_daily_usage[uid]["date"] != today:
                user_daily_usage[uid] = {"date": today, "count": 0}

            if user_daily_usage[uid]["count"] >= MESSAGE_LIMIT:
                await message.reply("🛑 you've hit your 5 free messages for today! become a supporter for unlimited chats 💖")
                return

            # Increment counter
            user_daily_usage[uid]["count"] += 1


    chat_id = message.channel.id
    history = get_history(chat_id)
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


    # !join VC
    if msg_lower == "!join":
        if message.author.voice and message.author.voice.channel:
            channel = message.author.voice.channel
            await channel.connect()
            await message.channel.send("🎧 joined vc~ what r we doing, cutie?")
        else:
            await message.channel.send("you gotta be in a vc first, babe~ 😭")
        return

    # !leave VC
    if msg_lower == "!leave":
        vc = message.guild.voice_client
        if vc and vc.is_connected():
            if vc.is_playing():
                vc.stop()
            await vc.disconnect()
            await message.channel.send("👋 left vc~ see u later, boo 💖")
        else:
            await message.channel.send("i'm not even in a vc rn lol 😅")
        return

    # Main logic
    async with response_lock:
        global last_reply_time
        now = time.time()
        if now - last_reply_time < REPLY_COOLDOWN:
            return  # Skip if replying too soon
        last_reply_time = now
        if not await asyncio.to_thread(is_worth_replying, message.content):
            return
        
        await message.channel.typing()
        try:
            response = await asyncio.to_thread(query_ai, chat_id, message.content)
            await message.reply(response)

            # Speak in VC
            vc = message.guild.voice_client if message.guild else None
            if vc and vc.is_connected():
                filename = await text_to_speech(response)
                vc.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=filename))
                while vc.is_playing():
                    await asyncio.sleep(1)
                cleanup_audio_file(filename)

            # Summarize after every 10 messages
            if len(get_history(chat_id)) % 10 == 0:
                summarize_chat_with_ai(chat_id)

        except Exception as e:
            await message.channel.send(f"❌ Error: {e}")

# --- START BOT ---
client.run(os.getenv("DISCORD_TOKEN"))
