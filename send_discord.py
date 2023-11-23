import os
import requests

discord_webhook = os.environ.get('DISCORD_WEBHOOK_URL')


def send_discord_message(message):
    payload = {'content': message}
    requests.post(discord_webhook, json=payload)
