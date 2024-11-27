import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

def scrape_headlines(ticker, country) -> pd.DataFrame:
    """
    Scrape headlines from Marketwatch and return dataframe of headlines and dates.

    Args:
        ticker (str): the ticker to scrape.
        country (str): the country of the ticker to scrape.

    Returns:
        pd.DataFrame with 3 columns:
            Date (datetime64): date of the headline
            Headline (object): headline of the news
            Link (object): Link to the headline news
    """

    # check if the country is US, HK or China
    if country.upper() in ['US', 'U.S.', 'UNITED STATES', 'USA', 'U.S.A.', 'UNITED STATES OF AMERICA']:
        country_code = 'US'
    elif country.upper() in ['CN', 'CHINA', 'PRC']:
        country_code = 'CN'
    elif country.upper() in ['HK', 'HONG KONG', 'HKG']:
        country_code = 'HK'
    else:
        print('Country is not supported, only stocks in US, CN and HK are supported.')
        return -1

    url = f'https://www.marketwatch.com/investing/Stock/{ticker}?countryCode={country_code}'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
               'Accept-Language': 'en-US,en;q=0.5'
               }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")

    headlines = []
    dates = []
    links = []
    unsupported_label = ["opinion", "market", "watchlist", "investor", "premium"]

    for headline_element in soup.find_all("h3", class_="article__headline"):
        headline = None
        date = None
        link = None
        label = headline_element.find('span')

        if (label == None or not (label.text.strip().lower() in unsupported_label)):
            headline = headline_element.text.strip().replace('\n', '')
            headline = ' '.join(headline.split())
            if headline != '':
                link_element = headline_element.find('a')
                if link_element is not None:
                    link = link_element['href']
                date_element = headline_element.find_next("span", class_="article__timestamp")
                if date_element is not None:
                    date_text = date_element["data-est"]
                    parsed_date = re.search(r"\d{4}-\d{2}-\d{2}", date_text).group(0)
                    date = datetime.datetime.strptime(parsed_date, "%Y-%m-%d").date()

                headlines.append(headline)
                dates.append(date)
                links.append(link)

    temp_dict = {'Date': dates, 'Headline': headlines, 'Link': links}
    headline_df = pd.DataFrame(temp_dict)
    headline_df['Date'] = pd.to_datetime(headline_df['Date'])
    headline_df = headline_df.sort_values(by='Date', ascending=False).reset_index(drop=True)

    return headline_df

if __name__ == "__main__":
    headline_table = scrape_headlines('9988', 'HK')
    print(headline_table)
