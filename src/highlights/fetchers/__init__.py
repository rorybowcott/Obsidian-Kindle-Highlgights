"""HTTP fetchers for retrieving Kindle highlights from remote services."""
from .kindle_cloud import KindleCloudFetcher, KindleCloudFetchError

__all__ = ["KindleCloudFetcher", "KindleCloudFetchError"]
