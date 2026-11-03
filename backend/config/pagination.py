from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """25 per page by default. Clients may ask for ?page_size=N (at most 100)."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
