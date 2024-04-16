import requests
from bs4 import BeautifulSoup
from requests.models import Response


def get_soup_from_url(url: str) -> BeautifulSoup:
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError
    return BeautifulSoup(response.text, "html.parser")


def get_soup(response: Response) -> BeautifulSoup:
    if response.status_code != 200:
        raise ValueError
    return BeautifulSoup(response.text, "html.parser")


def get_text_from_html(soup, element, separator="\n"):
    return soup.find(**element).get_text(strip=True, separator=separator)


def get_link_from_html(soup, element):
    return soup.find(**element).get("href")


class WebsiteTest:
    """
    Testing if a website works as expected.
    """

    def __init__(self, url):
        self.url = url
        response = requests.get(url=self.url)
        self.soup = get_soup(response)

    def is_element(
        self, name=None, attrs={}, recursive=True, string=None, **kwargs
    ):
        """
        Check if html element exists on website.
        """
        if self.soup.find(
            name=None, attrs={}, recursive=True, string=None, **kwargs
        ):
            return True
        else:
            return False

    def is_text_in_element(
        self,
        target_text: str,
        name=None,
        attrs={},
        recursive=True,
        string=None,
        **kwargs,
    ):
        f"""
        Check if text is in html element.

        Docstring for bs4 function find:
        {self.soup.find.__doc__}
        """
        result = self.soup.find(name, attrs, recursive, string, **kwargs)
        if result:
            return target_text in result.get_text()
        else:
            return False
