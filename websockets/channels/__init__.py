from helpers.dependencies import required_deps

required_deps(
    {
        "django": "https://www.djangoproject.com/",
        "channels": "https://channels.readthedocs.io/en/stable/",
    }
)

from helpers.config import settings


channels_settings = settings.WEBSOCKETS.CHANNELS
