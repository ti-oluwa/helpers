from helpers.dependencies import deps_required

deps_required(
    {
        "channels": "https://channels.readthedocs.io/en/stable/",
    }
)

from helpers.django.config import settings


channels_settings = settings.CHANNELS
