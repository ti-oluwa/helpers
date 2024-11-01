from helpers.dependencies import deps_required

deps_required(
    {
        "django": "https://www.djangoproject.com/",
        "channels": "https://channels.readthedocs.io/en/stable/",
    }
)

from helpers.config import settings


channels_settings = settings.WEBSOCKETS.CHANNELS
