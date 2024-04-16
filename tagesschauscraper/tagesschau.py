import sqlite3
from datetime import date
from typing import Literal, Dict
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from socket import gaierror

from tagesschauscraper import constants, helper, retrieve

from icecream import ic

def create_url_for_news_archive(
    date_: date,
    category: Literal["wirtschaft", "inland", "ausland", "all"] = "all",
) -> str:
    """
    Creating a url leading to the articles published on the specified date.
    Additionally, the articles can be filtered by the category.

    Parameters
    ----------
    date_ : date
        Filter articles on date.
    category : str, optional
        Filter articles on category. Could be "wirtschaft", "inland",
        "ausland" or "all".
        By default, "all" is selected.

    Returns
    -------
    str
        Url for the news archive.

    Raises
    ------
    ValueError
        When category is not defined.
    """
    categories = ["wirtschaft", "inland", "ausland"]
    date_pattern = "%Y-%m-%d"
    date_str = date_.strftime(date_pattern)
    if category in categories:
        return f"https://www.tagesschau.de/archiv/?datum={date_str}&ressort={category}"
    elif category == "all":
        return f"https://www.tagesschau.de/archiv/?datum={date_str}"
    else:
        raise ValueError(
            f"category {category} not defined. category must be in"
            f" {categories}"
        )


class TagesschauScraper:
    """
    A web scraper specified for scraping the news archive of Tagesschau.de.
    """

    def __init__(self) -> None:
        self.validation_element = {"class": "archive__headline"}

    def scrape_teaser(self, url: str, wait=200) -> dict:
        """
        Scrape all teaser on the archive <url>.

        Parameters
        ----------
        url : str
            Archive website.

        Returns
        -------
        dict
            Scraped teaser.
        """
        websiteTest = retrieve.WebsiteTest(url)
        if websiteTest.is_element(self.validation_element):
            return self._extract_info_for_all_teaser(websiteTest.soup)
        else:
            raise ValueError(
                f"HTML element with specifications {self.validation_element}  "
                f"              cannot be found in URL {url}"
            )

    def _extract_info_for_all_teaser(self, soup: BeautifulSoup) -> dict:
        self.teaser_element = {
            "class": "teaser-right twelve"
        }
        extracted_teaser_list = []
        for teaser in soup.find_all(
            class_=self.teaser_element["class"]
        ):
            teaserObj = Teaser(soup=teaser)
            # ic(teaserObj)
            teaser_info = teaserObj.extract_info_from_teaser()
            # ic(teaser_info)
            teaser_info_enriched = (
                teaserObj.enrich_teaser_info_with_article_tags(teaser_info)
            )
            # ic(teaser_info_enriched)
            teaser_info_processed = teaserObj.process_info(
                teaser_info_enriched
            )
            if teaserObj.is_teaser_info_valid(teaser_info_processed):
                extracted_teaser_list.append(teaserObj.teaser_info)
        return {"teaser": extracted_teaser_list}


class Archive:
    """
    A class for extracting information from news archive.
    """

    def __init__(self, soup: BeautifulSoup) -> None:
        """
        Initializes the Teaser with the provided BeautifulSoup element.

        Parameters
        ----------
        soup : BeautifulSoup
            BeautifulSoup object representing an element for a news teaser.
        """
        self.archive_soup = soup
        self.archive_info: Dict[str, str] = dict()

    def transform_date_to_date_in_headline(self, date_: date) -> str:
        year = date_.year
        month = date_.month
        day = date_.day
        return f"{day}. {constants.german_month_names[month]} {year}"

    def transform_date_in_headline_to_date(
        self, date_in_headline: str
    ) -> date:
        day_raw, month_raw, year_raw = date_in_headline.split()
        day = int(day_raw[:-1])
        month = constants.german_month_names.index(month_raw)
        year = int(year_raw)
        return date(year, month, day)

    def extract_info_from_archive(self) -> dict:
        name_html_mapping_text = {
            "headline": "archive__headline",
            "num_teaser": "ergebnisse__anzahl",
        }
        self.archive_info = {
            name: retrieve.get_text_from_html(
                self.archive_soup, {"class_": html_tag}
            )
            for name, html_tag in name_html_mapping_text.items()
        }
        return self.archive_info


class Teaser:
    """
    A class for extracting information from news teaser elements.
    """

    def __init__(self, soup: BeautifulSoup) -> None:
        """
        Initializes the Teaser with the provided BeautifulSoup element.

        Parameters
        ----------
        soup : BeautifulSoup
            BeautifulSoup object representing an element for a news teaser.
        """
        self.teaser_soup = soup
        self.teaser_info: Dict[str, str] = dict()
        self.required_attributes = {
            "date",
            # "topline",
            "headline",
            "shorttext",
            "link",
        }

    def extract_info_from_teaser(self) -> dict:
        """
        Extracts structured information from a teaser element.
        The extracted elements are: date, topline, headline, shorttext and
        link to the corresponding article.

        Returns
        -------
        dict
            A dictionary containing all the information of the news teaser
        """
        field_names_text = ["date", "topline", "headline", "shorttext"]
        field_names_link = ["link"]
        name_html_mapping = {
            key: f"teaser-right__{key}"
            for key in field_names_text + field_names_link
        }

        for field_name, html_class_name in name_html_mapping.items():
            tag = self.teaser_soup.find(class_=html_class_name)
            if isinstance(tag, Tag):
                if field_name in field_names_text:
                    self.teaser_info[field_name] = tag.get_text(
                        strip=True, separator=" "
                    )
                elif field_name in field_names_link:
                    href = tag.get("href")
                    if isinstance(href, str):
                        if not "www." in href:
                            self.teaser_info[field_name] = f'https://www.tagesschau.de{href}'  # type: ignore
                        else:
                            self.teaser_info[field_name] = href  # type: ignore
                            
                    else:
                        raise ValueError

        return self.teaser_info

    def enrich_teaser_info_with_article_tags(self, teaser_info: dict) -> dict:
        """
        Enrich the teaser information with the article tags.

        Parameters
        ----------
        teaser_info : dict
            All information extracted from the news teaser.

        Returns
        -------
        dict
            Dictionary containing news teaser information enriched by article
            tags.
        """
        article_link = teaser_info["link"]
        try:
            article_soup = retrieve.get_soup_from_url(article_link)
            articleObj = Article(article_soup)
            article_tags = articleObj.extract_article_tags()
            teaser_info.update(article_tags)
            self.teaser_info.update(teaser_info)

        except requests.exceptions.TooManyRedirects:
            print(f"Article not found for link: {article_link}.")
        except gaierror as e:
            print(f"gaierror: {e}")
        except ConnectionError as e:
            print(f"ConnectionError: {e}")
        except BaseException as e:
            print(f"Error: {e}")

        return teaser_info

    def process_info(self, teaser_info: dict) -> dict:
        """
        Process the extracted teaser information.

        Parameters
        ----------
        teaser_info : dict
            Dictionary containing news teaser information.

        Returns
        -------
        dict
            Dictionary containing processed teaser information.
        """
        teaser_info["id"] = helper.get_hash_from_string(teaser_info["link"])
        teaser_info["date"] = helper.transform_datetime_str(
            teaser_info["date"]
        )
        self.teaser_info.update(teaser_info)
        return teaser_info

    def is_teaser_info_valid(self, teaser_info: Dict[str, str]) -> bool:
        """
        Check if scraped information exists for all required attributes.

        Parameters
        ----------
        teaser_info : dict
            Dictionary containing news teaser information.

        Returns
        -------
        bool
            News teaser information is valid, when the function returns True.
        """
        if not self.required_attributes.difference(teaser_info.keys()):
            return True
        else:
            ic("False")
            ic("teaser_info.keys()")
            return False


class Article:
    """
    A class for extracting information from news article HTML elements.
    """

    def __init__(self, soup: BeautifulSoup) -> None:
        self.article_soup = soup
        self.tags_element = {"class": "taglist"}

    def extract_article_tags(self) -> dict:
        tags_group = self.article_soup.find(class_="taglist")
        if isinstance(tags_group, Tag):
            tags = [
                tag.get_text(strip=True)
                for tag in tags_group.find_all(
                    class_="tag-btn tag-btn--light-grey"
                )
                if hasattr(tag, "get_text")
            ]
        else:
            tags = []
        return {"tags": ",".join(sorted(tags))}


class TagesschauDB:
    _DB_NAME = "news.db"
    _TABLE_NAME = "Tagesschau"

    def __init__(self) -> None:
        self.connect()

    def connect(self) -> None:
        self.conn = sqlite3.connect(TagesschauDB._DB_NAME)
        self.c = self.conn.cursor()
        print(f"Connected to {TagesschauDB._DB_NAME}")

    def create_table(self) -> None:
        query = f"""
            CREATE TABLE IF NOT EXISTS  {TagesschauDB._TABLE_NAME} (
            id text UNIQUE,
            timestamp datetime,
            topline text,
            headline text,
            shorttext text,
            link text,
            tags text)
            """
        self.c.execute(query)

    def drop_table(self) -> None:
        query = f"""
            DROP TABLE IF EXISTS {TagesschauDB._TABLE_NAME}
            """
        self.c.execute(query)

    def insert(self, content: dict) -> None:
        query = f"""
            INSERT OR IGNORE INTO {TagesschauDB._TABLE_NAME}
            VALUES (:id, :date, :topline, :headline, :shorttext, :link, :tags)
            """
        with self.conn:
            self.c.execute(query, content)


class TagesschauArticle:
    def __init__(self, url, tags_to_remove=['header', 'footer', 'aside']) -> None:
        self.url = url
        self.check_url()
        self.soup = self.scrape_article()
        self.tags_to_remove = tags_to_remove
        self.markdown_content = self.get_markdown_content()
        
    def scrape_article(self) -> str:
        return retrieve.get_soup_from_url(self.url)

    def get_markdown_content(self):
        markdown_content = """"""
        self.remove_elements()
        # Find all elements with class "textabsatz" or "h2"
        elements = self.soup.find_all()
        
        # Convert each element to Markdown
        for element in elements:
            markdown_content += self.convert_to_markdown(element)

        return markdown_content

    def convert_to_markdown(self, element):
        markdown = ""

        # If element is a string, simply append it to the markdown content
        if isinstance(element, NavigableString):
            markdown += f"{element}"
        elif 'textabsatz' in element.get('class', []):
            # Check if the element contains a <strong> tag
            strong_text = element.find('strong')
            if strong_text:
                # If <strong> tag is present, make the text bold
                markdown += f" **{strong_text.get_text()}** "
            else:
                # If <strong> tag is not present, keep the text as is
                markdown += f"{element.get_text()}"
                
        elif element.name == 'h1':
            span_elements = element.find_all('span')
            if len(span_elements):
                topline_text = span_elements[0].get_text(strip=True)
                headline_text = span_elements[1].get_text(strip=True)
                markdown += f"# {topline_text.replace("\n", " ")} - {headline_text.replace("\n", " ")}"
            else:
                markdown += f"# {element.get_text().replace("\n", " ")}\n\n"
        elif element.name == 'h2':
            markdown += f"\n\n## {element.get_text().replace("\n", " ")}\n\n"

        return markdown
 
    def remove_elements(self):
        for tag in self.tags_to_remove:
            elements = self.soup.find_all(tag)
            for element in elements:
                element.decompose()

    def check_url(self):
        try:
            if not "www.tagesschau.de" in self.url:
                raise NameError
        except NameError:
            print("URL must be cotain: 'www.tagesschau.de'")