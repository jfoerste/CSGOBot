import discord
import os

client = discord.Client()


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')


if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if token is None:
        print('The environment variable TOKEN is missing!')
        exit()
    client.run(token)
