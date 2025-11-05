from typing import TYPE_CHECKING

from githubkit import GitHub, Response, UnauthAuthStrategy

if TYPE_CHECKING:
    from githubkit.rest import Release


class CustomGitHub(GitHub[UnauthAuthStrategy]):
    async def get_latest_release(self, owner: str, repo: str) -> Release:
        response = await self.rest.repos.async_get_latest_release(owner, repo)
        return response.parsed_data

    async def download_latest_release(self, owner: str, repo: str) -> Response[object, object]:
        release = await self.get_latest_release(owner, repo)
        return await self.arequest("GET", release.assets[0].browser_download_url)  # pyright: ignore[reportUnknownMemberType]
