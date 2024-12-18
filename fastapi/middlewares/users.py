import fastapi

from helpers.fastapi.models.users import AbstractBaseUser, AnonymousUser


async def RequestUserMiddleware(request: fastapi.Request, call_next):
    """
    Middleware to add the request user to the request state.

    request.state.user will be an AbstractBaseUser instance,
    or AnonymousUser if no user can be associated with the request.

    :param request: FastAPI request object
    :param call_next: Next middleware in the chain
    """
    request_user = getattr(request.state, "user", None)
    if not isinstance(request_user, AbstractBaseUser):
        request.state.user = AnonymousUser()
    
    response = await call_next(request)
    return response
