import re, urllib.request, time
from urllib.parse import urljoin, urlparse
from queue import Queue
import threading

# Improved email regex pattern
emailRegex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Track visited URLs and emails to avoid duplicates
visited_urls = set()
found_emails = set()
url_queue = Queue()
max_depth = 3  # How deep to crawl
max_urls_per_domain = 50  # Limit URLs per domain

def is_valid_url(url, base_domain):
    """Check if URL is valid and belongs to base domain"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.endswith(base_domain)
    except:
        return False

def extract_urls(html_content, base_url):
    """Extract all URLs from HTML content"""
    urls = re.findall(r'href=[\'"]?([^\'" >]+)', html_content)
    return [urljoin(base_url, url) for url in urls]

def is_valid_email_domain(email, base_domain):
    """Check if email domain matches the base domain"""
    try:
        email_domain = email.split('@')[1]
        return email_domain == base_domain
    except:
        return False

def extractEmailsFromUrlText(urlText, emailFile, url, base_domain):
    emails = emailRegex.findall(urlText)
    if emails:
        # Filter emails to only include those matching the base domain
        valid_emails = [email for email in emails if is_valid_email_domain(email, base_domain)]
        new_emails = set(valid_emails) - found_emails
        
        if new_emails:
            print(f"\tFound {len(new_emails)} new valid emails on {url}")
            with threading.Lock():
                for email in new_emails:
                    emailFile.write(email + "\n")
                    found_emails.add(email)
        else:
            print(f"\tNo new valid emails found on {url}")

def htmlPageRead(url, emailFile, base_domain):
    max_retries = 3
    base_delay = 2  # Base delay in seconds
    
    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            request = urllib.request.Request(url, None, headers)
            response = urllib.request.urlopen(request, timeout=10)
            html_content = response.read().decode('utf-8', errors='ignore')
            
            # Add delay between requests
            time.sleep(1)
            
            # Extract emails with base_domain check
            extractEmailsFromUrlText(html_content, emailFile, url, base_domain)
            
            return html_content
            
        except urllib.error.HTTPError as e:
            if e.code == 429:  # Too Many Requests
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"Rate limited, waiting {delay} seconds before retry...")
                    time.sleep(delay)
                    continue
            print(f"Error processing {url}: {str(e)}")
            return None
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            return None

def process_url(url, base_domain, emailFile, depth=0):
    if depth >= max_depth or url in visited_urls:
        return
    
    visited_urls.add(url)
    html_content = htmlPageRead(url, emailFile, base_domain)
    
    if html_content:
        urls = extract_urls(html_content, url)
        for new_url in urls:
            if is_valid_url(new_url, base_domain) and len(visited_urls) < max_urls_per_domain:
                url_queue.put((new_url, depth + 1))

def worker(base_domain, emailFile):
    while True:
        try:
            url, depth = url_queue.get(timeout=5)
            process_url(url, base_domain, emailFile, depth)
            url_queue.task_done()
        except:
            break

def main():
    with open("urls.txt", 'r') as urlFile, open("emails.txt", 'a') as emailFile:
        start_time = time.time()
        
        for base_url in urlFile:
            base_url = base_url.strip()
            if not base_url:
                continue
                
            base_domain = urlparse(base_url).netloc
            print(f"\nProcessing domain: {base_domain}")
            
            # Clear sets before processing new domain
            visited_urls.clear()
            found_emails.clear()
            
            # Initialize crawl with base URL
            url_queue.put((base_url, 0))
            
            # Start worker threads
            threads = []
            for _ in range(5):  # 5 concurrent threads
                t = threading.Thread(target=worker, args=(base_domain, emailFile))
                t.start()
                threads.append(t)
            
            # Wait for all URLs to be processed
            url_queue.join()
            
            # Stop threads
            for t in threads:
                t.join()
                
        print(f"\nTotal Elapsed Time: {time.time() - start_time:.2f} seconds")
        print(f"Total URLs processed: {len(visited_urls)}")

if __name__ == "__main__":
    main()