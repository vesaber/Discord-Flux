import discord
import fluxer
import aiohttp
import asyncio
import json
import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

dtoken = os.getenv("discordtoken")
ftoken = os.getenv("fluxertoken")
mapfile = "mappings.json"
msgfile = "messages.json"

def loadjson(path):
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                content = f.read()
                return json.loads(content) if content else {}
    except: pass
    return {}

def savejson(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def trackmsg(did, fid, discordauthorid, fluxerauthorid, text):
    msgs = loadjson(msgfile)
    entry = {
        "did": str(did),
        "fid": str(fid),
        "dauth": str(discordauthorid),
        "fauth": str(fluxerauthorid),
        "text": text[:50]
    }
    msgs[str(did)] = entry
    msgs[str(fid)] = entry
    
    if len(msgs) > 3000:
        msgs = dict(list(msgs.items())[-3000:])
    savejson(msgfile, msgs)

intents = discord.Intents.all()
dbot = commands.Bot(command_prefix=os.getenv("commandprefix"), intents=intents)
fbot = fluxer.Client(intents=fluxer.Intents.all())

session = None

async def getsession():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session

@dbot.event
async def on_ready():
    print(f"Logged into Discord {dbot.user}")

@fbot.event
async def on_ready():
    print(f"Logged into Fluxer {fbot.user}")

@dbot.event
async def on_message(message):
    await dbot.process_commands(message)
    if message.author.bot or message.webhook_id:
        return

    mappings = loadjson(mapfile)
    config = mappings.get(str(message.channel.id))
    if not config:
        return

    origcontnent = message.clean_content
    content = origcontnent
    
    if message.attachments:
        links = "\n".join([a.url for a in message.attachments])
        content = f"{content}\n{links}".strip()

    if message.reference and message.reference.message_id:
        msgs = loadjson(msgfile)
        ref = msgs.get(str(message.reference.message_id))
        if ref:
            url = f"https://fluxer.app/channels/{config['fid']}/{config['fid']}/{ref['fid']}"
            content = f"> <{url}> <@{ref['fauth']}>\n{content}"

    if not content.strip():
        return

    s = await getsession()
    payload = {
        "content": content,
        "username": f"{message.author.display_name}",
        "avatar_url": str(message.author.display_avatar.url)
    }
    
    async with s.post(config["fwebhook"], json=payload) as resp:
        if resp.status in [200, 201, 204]:
            await asyncio.sleep(0.5)
            
            headers = {"Authorization": f"Bot {ftoken}"}
            apiurl = f"https://api.fluxer.app/v1/channels/{config['fid']}/messages?limit=5"
            
            try:
                async with s.get(apiurl, headers=headers) as fetchresp:
                    if fetchresp.status == 200:
                        msglist = await fetchresp.json()
                        
                        for msg in msglist:
                            msg_content = msg.get('content', '')
                            if msg.get('webhook_id') and origcontnent in msg_content:
                                fluxer_msg_id = msg.get('id')
                                trackmsg(message.id, fluxer_msg_id, message.author.id, "0", origcontnent)
                                break
            except Exception as e:
                pass

@fbot.event
async def on_message(message):
    iswebhook = hasattr(message, "webhook_id") and message.webhook_id is not None
    if message.author.bot or iswebhook:
        return

    mappings = loadjson(mapfile)
    config = next((v for k, v in mappings.items() if str(v["fid"]) == str(message.channel.id)), None)
    if not config:
        return

    refid = None
    
    s = await getsession()
    headers = {"Authorization": f"Bot {ftoken}"}
    apiurl = f"https://api.fluxer.app/v1/channels/{message.channel_id}/messages/{message.id}"
    
    try:
        async with s.get(apiurl, headers=headers) as resp:
            if resp.status == 200:
                rawdata = await resp.json()
                if 'message_reference' in rawdata:
                    refid = rawdata['message_reference'].get('message_id')
    except Exception as e:
        pass

    replyheader = ""
    if refid:
        msgs = loadjson(msgfile)
        ref_data = msgs.get(str(refid))
        if ref_data:
            jumpurl = f"https://discord.com/channels/{config['gid']}/{config['did']}/{ref_data['did']}"
            replyheader = f"> {jumpurl} <@{ref_data['dauth']}>\n"

    content = message.content
    atts = getattr(message, 'attachments', [])
    if atts:
        links = [a.get('url') if isinstance(a, dict) else getattr(a, 'url', '') for a in atts]
        content = f"{content}\n" + "\n".join(links)

    fincontent = f"{replyheader}{content}".strip()
    if not fincontent:
        return

    webhook = discord.Webhook.from_url(config["dwebhook"], session=s)
    
    sent = await webhook.send(
        content=fincontent,
        username=f"{message.author.username}",
        avatar_url=getattr(message.author, "avatar_url", None),
        wait=True
    )
    trackmsg(sent.id, message.id, "0", message.author.id, message.content)

@dbot.command()
@commands.has_permissions(manage_webhooks=True)
async def bridge(ctx, fid: str):
    await ctx.send(f"Bridging to Fluxer `{fid}`...")
    try:
        hook = await ctx.channel.create_webhook(name="Fluxer Bridge")
        s = await getsession()
        headers = {"Authorization": f"Bot {ftoken}"}
        url = f"https://api.fluxer.app/v1/channels/{fid}/webhooks"
        
        async with s.post(url, json={"name": "Discord Bridge"}, headers=headers) as resp:
            data = await resp.json()
            fhook = data.get("url") or f"https://api.fluxer.app/webhooks/{data['id']}/{data['token']}"

        maps = loadjson(mapfile)
        maps[str(ctx.channel.id)] = {
            "fid": str(fid),
            "did": str(ctx.channel.id),
            "gid": str(ctx.guild.id),
            "dwebhook": hook.url,
            "fwebhook": fhook
        }
        savejson(mapfile, maps)
        await ctx.send("Successfully bridged")
    except Exception as e:
        await ctx.send(f"Error: {e}")

async def main():
    await asyncio.gather(dbot.start(dtoken), fbot.start(ftoken))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass