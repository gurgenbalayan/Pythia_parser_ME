import re
from typing import List, Optional, Dict

from selenium.webdriver import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from utils.logger import setup_logger
import os
from bs4 import BeautifulSoup
from selenium import webdriver


SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL")
STATE = os.getenv("STATE")
logger = setup_logger("scraper")
async def fetch_company_details(url: str) -> dict:
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get("https://apps3.web.maine.gov/nei-sos-icrs/ICRS")
        driver.execute_script(
            f"window.location.href='{url}'")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "body > center > table > tbody > tr:nth-child(3) > td > table")))
        html = driver.page_source
        return await parse_html_details(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{url}': {e}")
        return {}
    finally:
        if driver:
            driver.quit()

async def fetch_company_data(query: str) -> list[dict]:
    driver = None
    url = f"https://apps3.web.maine.gov/nei-sos-icrs/ICRS?MainPage=x"
    try:

        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        first_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "WAISqueryString"))
        )
        first_input.send_keys(query)
        first_input.send_keys(Keys.RETURN)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,
                                                   "body > form > center > table > tbody > tr:nth-child(3) > td > table:nth-child(1) > tbody")))

        html = driver.page_source
        return await parse_html_search(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{query}': {e}")
        return []
    finally:
        if driver:
            driver.quit()

async def parse_html_search(html: str) -> List[Dict]:
    results = []

    try:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("tbody")
        if not table:
            logger.warning("Не найден <tbody> в HTML.")
            return results
        rows = table.find_all("tr")
        for idx, row in enumerate(rows):
            try:
                cols = row.find_all("td")
                if len(cols) != 4:
                    logger.debug(f"Строка {idx} пропущена: ожидается 4 столбца, найдено {len(cols)}.")
                    continue
                name_tag = cols[1].find("font")
                registry_link = cols[3].find("a")
                name = name_tag.text.strip() if name_tag else ""
                reg_id = ""
                url = (
                    f"https://apps3.web.maine.gov{registry_link['href']}"
                    if registry_link and "href" in registry_link.attrs else ""
                )
                match = re.search(r"CorpSumm=([0-9A-Za-z\+]+)", registry_link['href'])

                if match:
                    reg_id = match.group(1).replace("+", "")
                result = {
                    "state": STATE,
                    "name": name,
                    "id": reg_id,
                    "url": url,
                }
                results.append(result)
            except Exception as e:
                logger.error(f"Ошибка при обработке строки {idx}: {e}")
                continue
    except Exception as e:
        logger.error(f"Ошибка при парсинге HTML: {e}")

    return results


async def parse_html_details(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    def extract_registration_number():
        for row in rows:
            cells = row.find_all("td")
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                if "Mark Number" in text or "Charter Number" in text:
                    if i + 1 < len(cells):
                        registration_number = cells[i + 1].get_text(strip=True)
                        return registration_number
        return None

    data = {
        "state": STATE,
        "name": None,
        "principal_address": None,
        "mailing_address": None,
        "agent_name": None,
        "agent_address": None,
        "owner_name": None,
        "owner_address": None,
        "registration_number": extract_registration_number(),
        "date_registered": None,
        "expiration_date": None,
        "entity_type": None,
        "status": None,
    }

    for i, row in enumerate(rows):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not cells:
            continue

        if "Filing Date" in row.text and i + 1 < len(rows):
            next_cells = [td.get_text(strip=True) for td in rows[i + 1].find_all("td")]
            if len(next_cells) >= 2:
                data["date_registered"] = next_cells[0] if next_cells[0] else None
                data["expiration_date"] = None if next_cells[1].upper() == "N/A" else next_cells[1]

        if "Mark Text" in row.text and i + 1 < len(rows):
            next_cells = [td.get_text(strip=True) for td in rows[i + 1].find_all("td")]
            if len(next_cells) >= 2:
                data["name"] = next_cells[0]
                data["status"] = next_cells[1]

        if "Mark Number" in row.text and i + 1 < len(rows):
            next_cells = [td.get_text(strip=True) for td in rows[i + 1].find_all("td")]
            if len(next_cells) >= 4:
                data["registration_number"] = next_cells[0]
                data["date_registered"] = next_cells[1]
                data["expiration_date"] = next_cells[2]
                data["entity_type"] = next_cells[3]

        if "Legal Name" in row.text and i + 1 < len(rows):
            next_cells = [td.get_text(strip=True) for td in rows[i + 1].find_all("td")]
            if len(next_cells) >= 4:
                data["name"] = next_cells[0]
                data["registration_number"] = next_cells[1].replace(" ", "")
                data["entity_type"] = next_cells[2]
                data["status"] = next_cells[3]

        if "Principal Home Office Address" in row.text and i + 2 < len(rows):
            address_row = rows[i + 2].find_all("td")
            if len(address_row) == 2:
                principal_text = list(address_row[0].stripped_strings)
                mailing_text = list(address_row[1].stripped_strings)
                data["principal_address"] = "\n".join(principal_text) if principal_text else None
                data["mailing_address"] = "\n".join(mailing_text) if mailing_text else None

        if "Owner Name" in row.text and i + 1 < len(rows):
            owner_row = rows[i + 1].find_all("td")
            if len(owner_row) >= 1:
                owner_text = list(owner_row[0].stripped_strings)
                if owner_text:
                    owner_full = "\n".join(owner_text).split("\n")
                    data["owner_name"] = owner_full[0] if len(owner_full) > 0 else None
                    data["owner_address"] = "\n".join(owner_full[1:]) if len(owner_full) > 1 else None

        if "Clerk/Registered Agent" in row.text and i + 2 < len(rows):
            agent_row = rows[i + 2].find_all("td")
            if len(agent_row) >= 2:
                agent_text = list(agent_row[0].stripped_strings)
                if agent_text:
                    data["agent_name"] = agent_text[0]
                    data["agent_address"] = "\n".join(agent_text[1:]) if len(agent_text) > 1 else None

    return data