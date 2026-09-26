import requests

WEBHOOK_URL = "https://discordapp.com/api/webhooks/1514011996553740388/Xj5aK-q5e3AhCnL1WL0SYHRT5tbaITijbKqF-bsxtWuerOTrBjrixT86gAL2OQkp0JPi"

response = requests.post(
    WEBHOOK_URL,
    json={"content": "Ya ando tranquilito, pido perdones D:"}
)

print(response.status_code)