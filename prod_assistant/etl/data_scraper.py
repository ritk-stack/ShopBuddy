import csv
import time
import re
import os
import subprocess
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from bs4 import BeautifulSoup
from httpx import options
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchWindowException, WebDriverException

class FlipkartScraper:
    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        if not hasattr(uc.ChromeOptions, "headless"):
            uc.ChromeOptions.headless = False

    def _get_chrome_version_main(self, binary_location: str | None):
        if not binary_location:
            return None
        try:
            output = subprocess.check_output([binary_location, "--version"], text=True).strip()
            match = re.search(r"(\d+)\.", output)
            return int(match.group(1)) if match else None
        except Exception:
            return None

    def _build_driver(self):
        options = uc.ChromeOptions()
        options.binary_location = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--disable-blink-features=AutomationControlled")

        version_main = 149

        try:
            return uc.Chrome(
                options=options,
                use_subprocess=False,
                headless=False,
                version_main=version_main
            )
        except Exception:
            # Recreate options since undetected_chromedriver does not allow reusing ChromeOptions
            options_fallback = uc.ChromeOptions()
            options_fallback.binary_location = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
            options_fallback.add_argument("--no-sandbox")
            options_fallback.add_argument("--disable-dev-shm-usage")
            options_fallback.add_argument("--disable-gpu")
            options_fallback.add_argument("--disable-software-rasterizer")
            options_fallback.add_argument("--no-first-run")
            options_fallback.add_argument("--no-default-browser-check")
            options_fallback.add_argument("--remote-debugging-port=0")
            options_fallback.add_argument("--disable-blink-features=AutomationControlled")
            
            return uc.Chrome(
                options=options_fallback,
                use_subprocess=False,
                headless=False
            )

    def _normalize_reviews_url(self, url: str) -> str:
        """Ensure reviews URL points to Overall tab (not a specific aspect like Camera)."""
        try:
            parts = urlparse(url)
            if "product-reviews" not in parts.path:
                return url
            q = parse_qs(parts.query)
            q.pop("an", None)  # remove aspect filter like an=Camera
            # If a tab param exists in some layouts, default to Overall.
            if "tab" in q:
                q["tab"] = ["Overall"]
            new_query = urlencode(q, doseq=True)
            return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))
        except Exception:
            return url

    def get_top_reviews(self,product_url,count=2):
        """Get the top reviews for a product.
        """
        driver = self._build_driver()

        if not product_url.startswith("http"):
            driver.quit()
            return "No reviews found"

        try:
            driver.get(product_url)
            time.sleep(2)
            current_url = driver.current_url
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
                time.sleep(1)
            except Exception as e:
                print(f"Error occurred while closing popup: {e}")

            # Scroll to ratings section to trigger lazy-load.
            try:
                ratings_header = driver.find_element(By.XPATH, "//*[contains(text(),'Ratings and reviews')]")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ratings_header)
                time.sleep(1)
            except Exception:
                pass

            # Try to open full reviews if a link/button exists.
            try:
                show_all = driver.find_element(
                    By.XPATH,
                    "//a[contains(text(),'Show all reviews') or contains(text(),'All reviews') or contains(text(),'See all reviews')]",
                )
                href = show_all.get_attribute("href")
                if href:
                    driver.get(href)
                else:
                    show_all.click()
                time.sleep(2)
            except Exception:
                # Fallback: use the actual product-reviews link if present in DOM,
                # otherwise try to build it from the item id.
                try:
                    soup_link = BeautifulSoup(driver.page_source, "html.parser")
                    link = soup_link.select_one("a[href*='product-reviews']")
                    if link and link.get("href"):
                        href = link.get("href")
                        if href.startswith("/"):
                            href = "https://www.flipkart.com" + href
                        href = self._normalize_reviews_url(href)
                        driver.get(href)
                        time.sleep(2)
                    else:
                        match = re.search(r"/p/(itm[0-9A-Za-z]+)", product_url)
                        if match:
                            reviews_url = f"https://www.flipkart.com/product-reviews/{match.group(1)}"
                            reviews_url = self._normalize_reviews_url(reviews_url)
                            driver.get(reviews_url)
                            time.sleep(2)
                except Exception:
                    pass

            for _ in range(4):
                ActionChains(driver).send_keys(Keys.END).perform()
                time.sleep(1.5)

            # Wait for any review content to appear.
            wait = WebDriverWait(driver, 10)
            review_selectors = [
                "div[data-review-id]",
                "div._27M-vq",  # common body class in some Flipkart layouts
                "div.t-ZTKy",
                "div._6K-7Co",
                "div.G4PxIA",
            ]
            try:
                wait.until(
                    lambda d: any(d.find_elements(By.CSS_SELECTOR, sel) for sel in review_selectors)
                )
            except Exception:
                pass

            soup = BeautifulSoup(driver.page_source, "html.parser")
            if "Unfortunately the page you are looking for has been moved or deleted" in soup.get_text():
                # Reviews URL invalid; fall back to product page DOM.
                driver.get(product_url)
                time.sleep(2)
                soup = BeautifulSoup(driver.page_source, "html.parser")
            if os.getenv("DEBUG_REVIEW_DUMP") == "1":
                dump_path = os.path.join(self.output_dir, "review_page_dump.html")
                with open(dump_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"[debug] review page dumped to: {dump_path}")
                print(f"[debug] review page url: {driver.current_url} (from {current_url})")
            # More flexible selectors: grab headings + bodies from common review card containers.
            review_cards = (
                soup.select("div[data-review-id]") or
                soup.select("div._27M-vq, div.t-ZTKy, div._6K-7Co, div.G4PxIA, div.col.EPCmJX")
            )
            headlines = soup.select("p.qW2QI1, p._2-N8zT, p._2xg6Ul, div._2-N8zT, div._1mfR1Z")
            bodies = soup.select("div.G4PxIA, div._6K-7Co, div._27M-vq, div.t-ZTKy, div._3LWZlK, div.col.EPCmJX")

            seen = set()
            reviews = []

            if review_cards:
                for card in review_cards:
                    title_el = card.select_one("p.qW2QI1, p._2-N8zT, p._2xg6Ul, div._2-N8zT, div._1mfR1Z")
                    body_el = card.select_one("div.G4PxIA, div._6K-7Co, div._27M-vq, div.t-ZTKy, div._3LWZlK, div.col.EPCmJX")
                    if body_el is None:
                        # Some layouts render review text in links within the card.
                        for a in card.select("a"):
                            text = a.get_text(" ", strip=True)
                            if len(text) >= 20:
                                body_el = a
                                break
                    title = title_el.get_text(strip=True) if title_el else ""
                    body = body_el.get_text(" ", strip=True) if body_el else ""
                    text = " — ".join([t for t in [title, body] if t])
                    if text and text not in seen:
                        reviews.append(text)
                        seen.add(text)
                    if len(reviews) >= count:
                        break
            else:
                for h, b in zip(headlines, bodies):
                    text = f"{h.get_text(strip=True)} — {b.get_text(' ', strip=True)}"
                    if text and text not in seen:
                        reviews.append(text)
                        seen.add(text)
                    if len(reviews) >= count:
                        break

            # Last-resort fallback: parse reviews from page text (works on some review pages
            # where content is rendered as large text blocks without stable selectors).
            if not reviews:
                # Try structured extraction from the new reviews DOM (batman-returns).
                review_nodes = []
                for cb in soup.find_all(string=lambda s: isinstance(s, str) and "Certified Buyer" in s):
                    node = cb
                    for _ in range(6):
                        if not node:
                            break
                        if getattr(node, "name", None) == "div" and node.get("class") and "r-nsbfu8" in node.get("class", []):
                            review_nodes.append(node)
                            break
                        node = node.parent

                if review_nodes:
                    for node in review_nodes:
                        spans = node.select("span.r-1vgyyaa.r-1b43r93.r-1rsjblm")
                        text = " ".join(s.get_text(" ", strip=True) for s in spans)
                        text = re.sub(r"\s+", " ", text).replace("...", "").strip()
                        if len(text) < 20:
                            continue
                        if text not in seen:
                            reviews.append(text)
                            seen.add(text)
                        if len(reviews) >= count:
                            break

            if not reviews:
                page_text = soup.get_text(" ", strip=True)
                page_text = page_text.replace("\xa0", " ")
                page_text = re.sub(r"\s+", " ", page_text)
                # Capture review snippets that appear before "READ MORE"
                candidates = re.findall(r"(.{20,800}?)\\s+READ MORE", page_text, flags=re.IGNORECASE)
                if os.getenv("DEBUG_REVIEW_DUMP") == "1":
                    print(f"[debug] review candidates found: {len(candidates)}")
                for c in candidates:
                    # Keep only the tail to avoid header/nav text
                    snippet = c[-350:]
                    cleaned = re.sub(r"\\s+", " ", snippet).strip()
                    cleaned = cleaned.replace("...", "").strip()
                    if "Reviews Most Helpful" in cleaned:
                        cleaned = cleaned.split("Reviews Most Helpful")[-1].strip()
                    if "feedback" in cleaned:
                        cleaned = cleaned.split("feedback")[-1].strip()
                    # If "Certified Buyer" is present, keep only the review text before it.
                    if "Certified Buyer" in cleaned:
                        cleaned = cleaned.split("Certified Buyer")[0].strip()
                    if os.getenv("DEBUG_REVIEW_DUMP") == "1":
                        print(f"[debug] candidate: {cleaned[:120]}")
                    # Avoid pulling page chrome/nav text.
                    if len(cleaned) < 30:
                        continue
                    if any(skip in cleaned for skip in ["Explore Plus", "Become a Seller", "ABOUT Contact Us", "Help Center"]):
                        continue
                    if cleaned not in seen:
                        reviews.append(cleaned)
                        seen.add(cleaned)
                    if len(reviews) >= count:
                        break

        except Exception:
            reviews = []

        driver.quit()
        return " || ".join(reviews) if reviews else "No reviews found"
    
    def scrape_flipkart_products(self, query, max_products=1, review_count=2):
        """Scrape Flipkart products based on a search query.
        """
        driver = self._build_driver()
        time.sleep(2)

        try:
            search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
            try:
                driver.get(search_url)
            except (NoSuchWindowException, WebDriverException):
                # Rebuild driver if the window/session died.
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = self._build_driver()
                driver.get(search_url)
            time.sleep(5)

            try:
                driver.find_element(By.XPATH, "//button[contains(text(), '✕')]").click()
            except Exception as e:
                print(f"Error occurred while closing popup: {e}")

            time.sleep(2)
            products = []

            items = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")[:max_products]
            print("FOUND ITEMS:", len(items))
            # if items:
            #     print(items[0].get_attribute("outerHTML"))


            for item in items:
                def safe_text(el, selector):
                    try:
                        return el.find_element(By.CSS_SELECTOR, selector).text.strip()
                    except Exception:
                        return "N/A"

                title = safe_text(item, "div.RG5Slk")
                price = safe_text(item, "div.hZ3P6w")
                rating = safe_text(item, "div.MKiFS6")
                reviews_text = safe_text(item, "span.PvbNMB")


                match = re.search(r"([\d,]+)\s+Reviews", reviews_text)
                total_reviews = match.group(1) if match else "N/A"


                try:
                    link_el = item.find_element(By.CSS_SELECTOR, "a.k7wcnx")
                    href = link_el.get_attribute("href")
                    product_link = href if href.startswith("http") else "https://www.flipkart.com" + href
                    match = re.findall(r"/p/(itm[0-9A-Za-z]+)", href)
                    product_id = match[0] if match else "N/A"
                except Exception as e:
                    print(f"Error occurred while extracting product link: {e}")
                    continue

                top_reviews = self.get_top_reviews(product_link, count=review_count) if "flipkart.com" in product_link else "Invalid product URL"
                products.append([product_id, title, rating, total_reviews, price, top_reviews])
        finally:
            driver.quit()
        return products
    
    def save_to_csv(self, data, filename="product_reviews.csv"):
        """Save the scraped product reviews to a CSV file."""
        if os.path.isabs(filename):
            path = filename
        elif os.path.dirname(filename):  # filename includes subfolder like 'data/product_reviews.csv'
            path = filename
            os.makedirs(os.path.dirname(path), exist_ok=True)
        else:
            # plain filename like 'output.csv'
            path = os.path.join(self.output_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["product_id", "product_title", "rating", "total_reviews", "price", "top_reviews"])
            writer.writerows(data)
        
