"""Organization context middleware"""

from collections.abc import Awaitable, Callable
from typing import Any, cast

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.http import HttpRequest, HttpResponse

from agentproof_backend.apps.organizations.constants import ACTIVE_ORGANIZATION_SESSION_KEY
from agentproof_backend.apps.organizations.models import Membership
from agentproof_backend.apps.organizations.selectors import memberships_for_user

SyncGetResponse = Callable[[HttpRequest], HttpResponse]
AsyncGetResponse = Callable[[HttpRequest], Awaitable[HttpResponse]]
GetResponse = SyncGetResponse | AsyncGetResponse


class CurrentOrganizationMiddleware:
    """Resolve the authenticated user's active organization."""

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response
        self.is_async = iscoroutinefunction(get_response)

        if self.is_async:
            markcoroutinefunction(self)

    def __call__(
        self,
        request: HttpRequest,
    ) -> HttpResponse | Awaitable[HttpResponse]:
        if self.is_async:
            return self._async_call(request)

        return self._sync_call(request)

    def _sync_call(
        self,
        request: HttpRequest,
    ) -> HttpResponse:
        self._bind_organization_context(request)

        get_response = cast(
            SyncGetResponse,
            self.get_response,
        )
        return get_response(request)

    async def _async_call(
        self,
        request: HttpRequest,
    ) -> HttpResponse:
        await sync_to_async(
            self._bind_organization_context,
            thread_sensitive=True,
        )(request)

        get_response = cast(AsyncGetResponse, self.get_response)

        return await get_response(request)

    @staticmethod
    def _bind_organization_context(request: HttpRequest) -> None:
        typed_request = cast(Any, request)
        typed_request.organization = None
        typed_request.organization_membership = None

        if not request.user.is_authenticated:
            return

        memberships = memberships_for_user(user=request.user)

        requested_organization_id = request.session.get(ACTIVE_ORGANIZATION_SESSION_KEY)

        membership: Membership | None = None

        if requested_organization_id:
            membership = memberships.filter(organization_id=requested_organization_id).first()

        if membership is None:
            request.session.pop(ACTIVE_ORGANIZATION_SESSION_KEY, None)
            membership = memberships.first()

        if membership is None:
            return

        request.session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(membership.organization_id)

        typed_request.organization = membership.organization
        typed_request.organization_membership = membership
