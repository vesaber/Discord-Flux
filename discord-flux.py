import discord
from discord.ext import commands
import fluxer
import os
from dotenv import load_dotenv
import json
import asyncio
import sqlite3
import aiohttp
import io

load_dotenv()

confloc = "bridges.json"
dbfile = "messages.db"
api_base = "https://api.fluxer.app"

def loadconf():
    if not os.path.exists(confloc): return {}
    try:
        with open(confloc, "r") as f: return json.load(f)
    except: return {}

def saveconf(config):
    with open(confloc, "w") as f:
        json.dump(config, f, indent=4)

db = sqlite3.connect(dbfile)
db.execute("CREATE TABLE IF NOT EXISTS msgmap (discord_id TEXT, fluxer_id TEXT, channel_id TEXT, fluxer_author_id TEXT, server_id TEXT)")
db.commit()

class FluxerBridge:
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.prefix = os.getenv("commandprefix", "!")
        self.discord = commands.Bot(command_prefix=self.prefix, intents=intents)
        self.fluxer = fluxer.Bot()
        self.bridges = loadconf()
        self.dwebhooks = {}
        self.fwebhooks = {}
        self.session = None

    async def getsesh(self):
        if self.session is None or self.session.closed:
            token = os.getenv("fluxertoken")
            auth = f"Bot {token}" if not token.startswith("Bot ") else token
            self.session = aiohttp.ClientSession(headers={"Authorization": auth})
        return self.session

    async def download(self, url):
        session = await self.getsesh()
        try:
            async with session.get(url) as r:
                if r.status == 200:
                    data = await r.read()
                    filename = url.split("?")[0].split("/")[-1] or "file"
                    return data, filename
        except Exception as e:
            print(f"Download failed {url}: {e}")
        return None, None

    async def getdiswebhook(self, channel):
        if channel.id in self.dwebhooks:
            return self.dwebhooks[channel.id]
        try:
            webhooks = await channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Flux Bridge")
            if not webhook:
                webhook = await channel.create_webhook(name="Flux Bridge")
            self.dwebhooks[channel.id] = webhook
            return webhook
        except: return None

    async def getfluxwebhook(self, fchannelid):
        if fchannelid in self.fwebhooks:
            return self.fwebhooks[fchannelid]
        session = await self.getsesh()
        try:
            async with session.get(f"{api_base}/channels/{fchannelid}/webhooks") as r:
                if r.status == 200:
                    data = await r.json()
                    webhook = next((w for w in data if w['name'] == "Discord Bridge"), None)
                    if webhook:
                        self.fwebhooks[fchannelid] = webhook
                        return webhook
            async with session.post(f"{api_base}/channels/{fchannelid}/webhooks", json={"name": "Discord Bridge"}) as r:
                if r.status in [200, 201]:
                    webhook = await r.json()
                    self.fwebhooks[fchannelid] = webhook
                    return webhook
        except: return None

    def iswebhookd(self, message):
        if not message.webhook_id:
            return False
        cached = self.dwebhooks.get(message.channel_id)
        return cached is not None and message.webhook_id == cached.id

    def iswebhookf(self, message):
        webhookid = getattr(message, 'webhook_id', None)
        if not webhookid:
            return False
        channelid = str(message.channel_id)
        cached = self.fwebhooks.get(channel_id)
        return cached is not None and str(webhook_id) == str(cached['id'])

    def setupevents(self):
        @self.discord.event
        async def on_ready():
            print(f"Discord Ready: {self.discord.user}")

        @self.discord.event
        async def on_message(message):
            await self.discord.process_commands(message)
            if self.iswebhookd(message): return
            if message.author.bot: return
            if message.content.startswith(self.prefix): return

            cid = str(message.channel.id)
            if cid not in self.bridges: return
            if not message.content and not message.attachments: return

            fid = self.bridges[cid]
            replyhead = ""

            if message.reference and message.reference.message_id:
                res = db.execute("SELECT fluxer_id, fluxer_author_id, server_id FROM msgmap WHERE discord_id = ?", (str(message.reference.message_id),)).fetchone()
                if res:
                    replyhead = f"-# → <https://fluxer.app/channels/{res[2]}/{fid}/{res[0]}> <@{res[1]}>\n"

            webhook = await self.getfluxwebhook(fid)
            if not webhook: return

            session = await self.getsesh()
            url = f"{api_base}/webhooks/{webhook['id']}/{webhook['token']}?wait=true"

            lastfmsg = None

            form = aiohttp.FormData()
            form_payload = {
                "username": message.author.display_name,
                "avatar_url": str(message.author.display_avatar.url),
                "attachments": [],
            }

            text = f"{replyhead}{message.clean_content}".strip()
            if text: form_payload["content"] = text

            for i, attachment in enumerate(message.attachments):
                data, filename = await self.download(attachment.url)
                if data:
                    form_payload["attachments"].append({"id": i, "filename": filename})
                    form.add_field(f"files[{i}]", data, filename=filename, content_type="application/octet-stream")

            form.add_field("payload_json", json.dumps(form_payload), content_type="application/json")

            async with session.post(url, data=form) as r:
                if r.status in [200, 201]: lastfmsg = await r.json()
                else: print(f"[D->F] Message post failed: {r.status} {await r.text()}")

            if lastfmsg:
                fchan = await self.fluxer.fetch_channel(fid)
                sid = getattr(fchan, "guild_id", "0")
                db.execute(
                    "INSERT INTO msgmap VALUES (?, ?, ?, ?, ?)",
                    (
                        str(message.id),
                        str(lastfmsg["id"]),
                        cid,
                        str(lastfmsg["author"]["id"]),
                        str(sid),
                    ),
                )
                db.commit()

        @self.fluxer.event
        async def on_message(message):
            if self.iswebhookf(message): return
            if message.author.id == self.fluxer.user.id or getattr(message.author, 'bot', False): return

            did = next((k for k, v in self.bridges.items() if v == str(message.channel_id)), None)
            if not did: return

            channel = self.discord.get_channel(int(did))
            if not channel: return

            replyhead = ""
            try:
                session = await self.getsesh()
                refid = None
                async with session.get(f"{api_base}/channels/{message.channel_id}/messages/{message.id}") as r:
                    if r.status == 200:
                        raw = await r.json()
                        ref = raw.get('referenced_message') or raw.get('reply_to')
                        if isinstance(ref, dict):
                            refid = ref.get('id')
                        elif isinstance(ref, str):
                            refid = ref

                if refid:
                    res = db.execute("SELECT discord_id FROM msgmap WHERE fluxer_id = ?", (str(refid),)).fetchone()
                    if res:
                        msgurl = f"https://discord.com/channels/{channel.guild.id}/{did}/{res[0]}"
                        try:
                            origmsg = await channel.fetch_message(int(res[0]))
                            mention = origmsg.author.mention
                        except:
                            mention = ""
                        replyhead = f"-# → {msgurl} {mention}\n"
            except Exception as e:
                print(f"[F->D] Reply lookup error: {e}")

            webhook = await self.getdiswebhook(channel)
            if not webhook: return

            files = []
            for a in (message.attachments or []):
                if isinstance(a, dict): atturl = a.get("url") or a.get("proxy_url")
                else: atturl = getattr(a, "url", None) or getattr(a, "proxy_url", None)

                if atturl:
                    data, filename = await self.download(atturl)
                    if data: files.append(discord.File(io.BytesIO(data), filename=filename))

            try:
                username = message.author.username
                avatar_url = str(message.author.avatar_url)
                content = f"{replyhead}{message.content}".strip() or None

                if content or files:
                    if files:
                        dismsg = await webhook.send(
                            content=content,
                            username=username,
                            avatar_url=avatar_url,
                            files=files,
                            wait=True,
                        )
                    else:
                        dismsg = await webhook.send(
                            content=content,
                            username=username,
                            avatar_url=avatar_url,
                            wait=True,
                        )

                    if dismsg:
                        fchan = await self.fluxer.fetch_channel(str(message.channel_id))
                        sid = getattr(fchan, "guild_id", "0")
                        db.execute(
                            "INSERT INTO msgmap VALUES (?, ?, ?, ?, ?)",
                            (
                                str(dismsg.id),
                                str(message.id),
                                did,
                                str(message.author.id),
                                str(sid),
                            ),
                        )
                        db.commit()

            except Exception as e:
                print(f"[F->D] Webhook send error: {e}")

        @self.discord.command()
        @commands.has_permissions(manage_channels=True)
        async def bridge(ctx, fid: str):
            self.bridges[str(ctx.channel.id)] = fid
            saveconf(self.bridges)
            await ctx.send(f"Bridged to Fluxer channel: `{fid}`")

        @self.discord.command()
        @commands.has_permissions(manage_channels=True)
        async def unbridge(ctx):
            cid = str(ctx.channel.id)
            if cid in self.bridges:
                del self.bridges[cid]
                saveconf(self.bridges)
                await ctx.send("Bridge removed")
            else:
                await ctx.send("This channel is not bridged")

    async def run(self):
        self.setupevents()
        await asyncio.gather(
            self.discord.start(os.getenv("discordtoken")),
            self.fluxer.start(os.getenv("fluxertoken"))
        )

if __name__ == "__main__":
    bot = FluxerBridge()
    try: asyncio.run(bot.run())
    except KeyboardInterrupt: pass
