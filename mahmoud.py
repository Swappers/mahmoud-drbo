# client Mahmoud

import discord
from urllib.request import 	urlopen as uReq
from bs4 import BeautifulSoup as soup
import requests
from discord.ext import commands
from discord.ext.commands import Bot
import asyncio
import itertools
import csv
import random
from config_bot import *
import datetime

# TODO &help
# TODO &m help 
# TODO Que se passe t il quand on lance plusieurs &p à la fois ?
# TODO clear @user number
# TODO search yt


PREFIX = Config.PREFIX
TOKEN = Config.TOKEN
DELETE_AFTER = Config.DELETE_AFTER


#memes 
file = open("content/memes.txt")
memes_array = []
for line in file.readlines():
    y = [value for value in line.strip().split('\t')]
    memes_array.append(y)
file.close()

client = commands.Bot(command_prefix=PREFIX)


#category
file = open("content/category.txt")
category_array = []
for line in file.readlines():
    y = [value for value in line.strip().split('\t')]
    category_array.append(y)
file.close()


class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '*{0.title}* [{1.display_name}]'
        duration = self.player.duration
        if duration:
            fmt = fmt + ' [Longueur: {0[0]}m {0[1]}s]'.format(divmod(duration, 60))
            
        return fmt.format(self.player, self.requester)


class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False

        player = self.current.player
        return not player.is_done()
    
    @property
    def player(self):
        return self.current.player

    def skip(self):
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await self.bot.send_message(self.current.channel, 'Lecture de ' + str(self.current))
            self.current.player.start()
            await self.play_next_song.wait()

class Music:
    """Voice related commands.
    Works in multiple servers at once.
    """
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def create_voice_client(self, channel):
        voice = await self.bot.join_voice_channel(channel)
        state = self.get_voice_state(channel.server)
        state.voice = voice

    def __unload(self):
        for state in self.voice_states.values():
            try:
                state.audio_player.cancel()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnect())
            except:
                pass

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """Summons the bot to join your voice channel."""
        summoned_channel = ctx.message.author.voice_channel
        if summoned_channel is None:
            await self.bot.say("T'es dans aucun channel connard.", delete_after = DELETE_AFTER)
            return False

        state = self.get_voice_state(ctx.message.server)
        if state.voice is None:
            state.voice = await self.bot.join_voice_channel(summoned_channel)
        else:
            await state.voice.move_to(summoned_channel)

        return True

    @commands.command(pass_context=True, no_pm=True, aliases=['p', 'pl', 'pla'])
    async def play(self, ctx, *, song : str):

        state = self.get_voice_state(ctx.message.server)
        opts = {
            'default_search': 'auto',
            'quiet': True,
            'format': 'bestaudio[ext=m4a]/best',
            'restrictfilenames': True,
            'noplaylist': True,
            'prefer_ffmpeg': True
        }

        if state.voice is None:
            success = await ctx.invoke(self.summon)
            if not success:
                return

        try:
            player = await state.voice.create_ytdl_player(song, ytdl_options=opts, after=state.toggle_next)
        except Exception as e:
            fmt = 'Erreur lors de la requête : ```py\n{}: {}\n```'
            await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))
        else:
            player.volume = 0.2
            entry = VoiceEntry(ctx.message, player)
            await state.songs.put(entry)

    @commands.command(pass_context=True, no_pm=True, aliases = ['volume','volum'])
    async def vol(self, ctx, value : int):
        """Sets the volume of the currently playing song."""

        state = self.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.volume = value / 100
            await self.bot.say('Volume : {:.0%}'.format(player.volume), delete_after = DELETE_AFTER)
            await self.bot.delete_message(ctx.message)

    @commands.command(pass_context=True, no_pm=True)
    async def pause(self, ctx):
        """Pauses the currently played song."""
        state = self.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.pause()

    @commands.command(pass_context=True, no_pm=True)
    async def resume(self, ctx):
        """Resumes the currently played song."""
        state = self.get_voice_state(ctx.message.server)
        if state.is_playing():
            player = state.player
            player.resume()

    @commands.command(pass_context=True, no_pm=True, aliases=['degag', 'dega', 'deg', 'd'])
    async def stop(self, ctx):
        """Stops playing audio and leaves the voice channel.
        This also clears the queue.
        """
        server = ctx.message.server
        state = self.get_voice_state(server)

        if state.is_playing():
            player = state.player
            player.stop()

        try:
            state.audio_player.cancel()
            del self.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass
        
        await client.delete_message(ctx.message)   
    

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):

        state = self.get_voice_state(ctx.message.server)
        if not state.is_playing():
            await self.bot.say('Tu veux que je skip quoi fdp ?', delete_after = DELETE_AFTER)
            return

        await self.bot.say('Allez on skip...', delete_after = DELETE_AFTER)
        state.skip()

    @commands.command(pass_context=True, no_pm=True)
    async def playing(self, ctx):
        """Currently played song."""

        state = self.get_voice_state(ctx.message.server)
        if state.current is None:
            await self.bot.say('Y a R frère...', delete_after = DELETE_AFTER)
        else:
            await self.bot.say('Lecture en cours de {}'.format(state.current), delete_after = DELETE_AFTER)

    @commands.command(pass_context=True, no_pm= True, aliases=['m', 'mem', 'me'])
    async def meme(self, ctx, *, song : str):

        url=''
        m_commands=[]
        output =[]

        for meme in memes_array:
            m_commands.append(meme[1])
            if(meme[1] == song):
                meme_r = meme[1]
                url = meme[0]
        
        if (song == 'help'):
            embed = discord.Embed(title = "Commandes memes help :", description = "Aide sur les commandes de memes",color =0x00ff00)
            for m_command in m_commands:
                output.append(PREFIX + "m " + str(m_command))

            com_str = '\n'.join(str(e) for e in output)
            embed.add_field(name= PREFIX + "m help", value=com_str, inline = True)
            await client.say(embed=embed)

        elif not url=='':

            state = self.get_voice_state(ctx.message.server)
            if state.voice is None:
                success = await ctx.invoke(self.summon)
                if not success:
                    return

            try:
                if (url.startswith('http')):
                    player = await state.voice.create_ytdl_player(url, after=state.toggle_next)
                    entry = VoiceEntry(ctx.message, player)
                else:
                    if state.is_playing():
                        player_prev = state.player
                        player_prev.pause()
                    local_link = url+ str(meme_r)+'.mp3'
                    player = state.voice.create_ffmpeg_player(local_link)
                    entry = '*'+ meme_r + '* ['+ ctx.message.author.name+'] [Longueur: 5s]'

            except Exception as e:
                fmt = 'Erreur lors de la requête : ```py\n{}: {}\n```'
                await self.bot.send_message(ctx.message.channel, fmt.format(type(e).__name__, e))

            else:
                player.volume = 0.2
                print(entry)
                if (url.startswith('http')):
                    await state.songs.put(entry)
                else:
                    player.start()
                    await asyncio.sleep(10)
                    if state.is_playing():                    
                        player_prev.resume()
                        await self.bot.delete_message(ctx.message)



        else:
            await self.bot.say("Commande inconnue.", delete_after = DELETE_AFTER)

        await self.bot.delete_message(ctx.message)


@client.event
async def on_ready():
    print ("I am running on " + client.user.name)
    print ("With the ID: " + client.user.id)
    await client.change_presence(game=discord.Game(name=' la dinette'))


@client.command(pass_context=True)
async def hello(ctx):
    await client.say("Va bien niquer ta mère fdp !")

@client.event
async def on_message(message):
    if "ass to mouth" in message.content:
        await client.send_message(message.channel, "Ok ok tbarkellah 3lik a si "+str(message.author.name)+" ...")
    elif "viens de chier" in message.content:
        today = datetime.date.today()
        await client.send_message(message.channel, today.strftime('%d %B % %Y') + "Libération de Nelson Mandela en Afrique du Sud. Quelques heures après que le président de l'Afrique du Sud, Frederik de Klerk, en eut fait l'annonce, le militant de la lutte anti-apartheid Nelson Mandela est libéré après 27 ans d'incarcération...")
    elif "boutef" in message.content:
        await client.send_message(message.channel, "T'inquiètes, j'enregistre tout :incoming_envelope: :innocent: ")

    await client.process_commands(message)

@client.command(pass_context=True)
async def info(ctx, user : discord.Member):
    embed = discord.Embed(title = "Informations sur {}".format(user.name), description = "Voilà ce que j'ai pu trouver.",color =0x00ff00)
    embed.add_field(name="Pseudo", value=user.name, inline = True)
    embed.add_field(name="ID", value=user.id,inline=True)
    embed.add_field(name="Rôle", value=user.top_role)
    embed.add_field(name="Date d'arrivée",value=user.joined_at)
    embed.set_thumbnail(url=user.avatar_url)
    await client.say(embed=embed)

@client.command(pass_context=True, aliases=['serverinfo', 'server', 'serveri'])
@commands.has_role("Con de service" or "Chieuse de service" or "Macaque")
async def sinfo(ctx):
    embed = discord.Embed(name="Informations sur le serveur {}".format(ctx.message.server.name), description = "Voilà ce que j'ai pu trouver.", color = 0x00ff00)
    embed.set_author(name="")
    embed.add_field(name="Pseudo", value=ctx.message.server.name, inline = True)
    embed.add_field(name="ID", value=ctx.message.server.id,inline=True)
    embed.add_field(name="Rôles", value="Il y a {} rôles".format(len(ctx.message.server.roles)))
    embed.add_field(name="Membres",value="Il y a {} utilisateurs".format(len(ctx.message.server.members)))
    embed.set_thumbnail(url=ctx.message.server.icon_url)

    await client.say(embed=embed, delete_after = DELETE_AFTER)

@client.command(pass_context = True, aliases=['clea', 'cle', 'cl', 'c'])
async def clear(ctx, number = 1, author : discord.Member = None):
    messages = []
    number = int(number)
    async for message in client.logs_from(ctx.message.channel, limit = number + 1):
        if (author is None):
            messages.append(message)
        else:
            if str(message.author).startswith(str(author)):
                messages.append(message)
    await client.delete_messages(messages)

@client.command(pass_context=True, aliases=['cat'])
async def category(ctx,arg = None):

    category_matching = []
    if arg is None:
        cat_chosen = random.choice(category_array)
    
    else:        
        for category in category_array:
            if str(arg) in category[0]:
                category_matching.append(category)
        if not category_matching:
            await client.say("J'ai rien trouvé avec tes mots clés de merde.", delete_after = DELETE_AFTER)
            await asyncio.sleep(10)
            await client.delete_message(ctx.message)
        
    
        cat_chosen = random.choice(category_matching)
    
    cat_chosen_str = '\n'.join(str(e) for e in cat_chosen)

    url_p = Config.URL_P
    url_f = url_p + '/search/' + cat_chosen_str

    r = requests.get(url_f)

    page_soup = soup(r.content, "html.parser")
    elements = page_soup.findAll("ul",{"class":"thumbs container"})[0]
    element = elements.findAll("li",{"class":"thumb sub"})[0]
    sub_link = element.div.find("a",{"class":"item-link"})['href']
    link = url_p + sub_link
    title = element.div.find("a",{"class":"item-link"})['title']
    site_p = element.div.findAll("span",{"class":"source"})[0].a.findAll(text=True)[0]
    
    embed = discord.Embed(name="Résultats : ", color = 0x00ff00)
    embed.add_field(name="Catégorie",value="["+str(cat_chosen_str)+"]"+"("+str(link)+")")
    embed.add_field(name='Site',value=str(site_p))
    embed.add_field(name='Titre',value=str(title))
    embed.set_thumbnail(url='https://ih1.redbubble.net/image.113815690.9530/flat,550x550,075,f.u4.jpg')

    await client.say(embed=embed, delete_after= DELETE_AFTER)
    await asyncio.sleep(10)
    await client.delete_message(ctx.message)    

    
client.add_cog(Music(client))
client.run(TOKEN)