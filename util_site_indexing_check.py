import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys
import time

def check_page_status(url):
    """
    Check if a page exists and returns its status code and any redirects.
    
    Args:
        url: Full URL to check
        
    Returns:
        Dictionary with status code, redirect info, and response time
    """
    result = {
        'url': url,
        'status_code': None,
        'redirect': False,
        'redirect_url': None,
        'response_time': None,
        'error': None
    }
    
    try:
        # First request with no redirects to check initial status
        start_time = time.time()
        no_redirect_response = requests.head(url, allow_redirects=False, timeout=10)
        result['status_code'] = no_redirect_response.status_code
        
        # Check if there's a redirect
        if 300 <= no_redirect_response.status_code < 400:
            result['redirect'] = True
            if 'Location' in no_redirect_response.headers:
                result['redirect_url'] = no_redirect_response.headers['Location']
                
                # Follow redirect to get final destination
                full_response = requests.head(url, allow_redirects=True, timeout=10)
                result['final_url'] = full_response.url
        
        result['response_time'] = round(time.time() - start_time, 2)
        
    except requests.exceptions.RequestException as e:
        result['error'] = str(e)
        
    return result

def check_robots_txt(domain):
    """
    Analyze robots.txt for disallow directives.
    
    Args:
        domain: Website domain (e.g., 'example.com')
        
    Returns:
        Dictionary with robots.txt content and analysis
    """
    result = {
        'exists': False,
        'content': None,
        'disallow_directives': [],
        'error': None
    }
    
    robots_url = f"https://{domain}/robots.txt"
    
    try:
        response = requests.get(robots_url, timeout=10)
        
        if response.status_code == 200:
            result['exists'] = True
            result['content'] = response.text
            
            # Parse disallow directives
            lines = response.text.split('\n')
            current_agent = "*"  # Default user agent
            
            for line in lines:
                line = line.strip()
                
                if line.lower().startswith('user-agent:'):
                    current_agent = line.split(':', 1)[1].strip()
                
                elif line.lower().startswith('disallow:'):
                    path = line.split(':', 1)[1].strip()
                    if path:  # Only add non-empty disallow directives
                        result['disallow_directives'].append({
                            'user_agent': current_agent,
                            'path': path
                        })
                        
        else:
            result['error'] = f"No robots.txt found (status code: {response.status_code})"
            
    except requests.exceptions.RequestException as e:
        result['error'] = str(e)
        
    return result

def check_page_indexability(url):
    """
    Check a page for noindex tags and canonical tag issues.
    
    Args:
        url: Full URL to check
        
    Returns:
        Dictionary with indexability information
    """
    result = {
        'url': url,
        'indexable': True,
        'noindex_tag': False,
        'noindex_header': False,
        'canonical_tag': None,
        'canonical_matches_url': None,
        'meta_robots': None,
        'error': None
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        
        # Check for X-Robots-Tag header
        if 'X-Robots-Tag' in response.headers:
            result['meta_robots'] = response.headers['X-Robots-Tag']
            if 'noindex' in response.headers['X-Robots-Tag'].lower():
                result['noindex_header'] = True
                result['indexable'] = False
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check meta robots tag
        meta_robots = soup.find('meta', attrs={'name': 'robots'})
        if meta_robots:
            content = meta_robots.get('content', '').lower()
            result['meta_robots'] = content
            if 'noindex' in content:
                result['noindex_tag'] = True
                result['indexable'] = False
        
        # Check canonical tag
        canonical_link = soup.find('link', attrs={'rel': 'canonical'})
        if canonical_link:
            canonical_url = canonical_link.get('href')
            result['canonical_tag'] = canonical_url
            
            # Remove trailing slashes and protocol for comparison
            normalized_url = url.rstrip('/')
            if '://' in normalized_url:
                normalized_url = normalized_url.split('://', 1)[1]
                
            normalized_canonical = canonical_url.rstrip('/')
            if '://' in normalized_canonical:
                normalized_canonical = normalized_canonical.split('://', 1)[1]
            
            result['canonical_matches_url'] = (normalized_url == normalized_canonical)
            
            # If canonical points elsewhere, it affects indexability
            if not result['canonical_matches_url']:
                result['indexable'] = False
        
        # Count total links on the page
        all_links = soup.find_all('a', href=True)
        result['total_links'] = len(all_links)
        
        # Count internal links
        internal_links = [link for link in all_links if link['href'].startswith('/') or domain in link['href']]
        result['internal_links'] = len(internal_links)
        
    except requests.exceptions.RequestException as e:
        result['error'] = str(e)
        result['indexable'] = False
        
    return result

def run_indexability_audit(domain, paths_to_check):
    """
    Run a complete indexability audit on a list of URLs.
    
    Args:
        domain: Website domain (e.g., 'example.com')
        paths_to_check: List of URL paths to check
        
    Returns:
        Comprehensive audit results
    """
    print(f"\n{'='*80}")
    print(f"INDEXABILITY AUDIT FOR {domain}")
    print(f"{'='*80}\n")
    
    # First check robots.txt
    print("CHECKING ROBOTS.TXT...")
    robots_result = check_robots_txt(domain)
    
    if robots_result['error']:
        print(f"Error: {robots_result['error']}")
    else:
        print(f"Found robots.txt with {len(robots_result['disallow_directives'])} disallow directives")
        
        for directive in robots_result['disallow_directives']:
            print(f"  User-agent: {directive['user_agent']} | Disallow: {directive['path']}")
    
    # Then check each individual page
    print("\nCHECKING INDIVIDUAL PAGES...")
    
    results = []
    for path in paths_to_check:
        full_url = f"https://{domain}{path}"
        print(f"\nAnalyzing: {full_url}")
        
        # Check redirects first
        status_result = check_page_status(full_url)
        
        if status_result['error']:
            print(f"  Error accessing page: {status_result['error']}")
            continue
            
        print(f"  Status Code: {status_result['status_code']}")
        
        if status_result['redirect']:
            print(f"  REDIRECT FOUND: {full_url} → {status_result['redirect_url']}")
            
            # If it redirects, check the destination
            full_url = status_result['final_url']
            print(f"  Checking final destination: {full_url}")
        
        # Check indexability
        index_result = check_page_indexability(full_url)
        
        if index_result['error']:
            print(f"  Error checking indexability: {index_result['error']}")
            continue
            
        print(f"  Indexable: {'Yes' if index_result['indexable'] else 'NO'}")
        
        if index_result['noindex_tag']:
            print(f"  WARNING: Page has noindex in meta tag")
            
        if index_result['noindex_header']:
            print(f"  WARNING: Page has noindex in HTTP header")
            
        if index_result['canonical_tag']:
            print(f"  Canonical tag: {index_result['canonical_tag']}")
            
            if not index_result['canonical_matches_url']:
                print(f"  WARNING: Canonical tag points to different URL")
        
        results.append({**status_result, **index_result})
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY OF ISSUES")
    print("="*80)
    
    not_indexable = [r for r in results if not r.get('indexable', True)]
    redirects = [r for r in results if r.get('redirect', False)]
    canonical_issues = [r for r in results if r.get('canonical_tag') and not r.get('canonical_matches_url')]
    
    if not_indexable:
        print(f"\n{len(not_indexable)} pages not indexable:")
        for r in not_indexable:
            print(f"  {r['url']}")
    
    if redirects:
        print(f"\n{len(redirects)} pages with redirects:")
        for r in redirects:
            print(f"  {r['url']} → {r.get('redirect_url', 'unknown')}")
    
    if canonical_issues:
        print(f"\n{len(canonical_issues)} pages with canonical issues:")
        for r in canonical_issues:
            print(f"  {r['url']} (canonical points to: {r['canonical_tag']})")
            
    return results

if __name__ == "__main__":
    # Default domain to check
    domain = "cryptotoolshq.com"
    
    # List of important paths to check
    paths_to_check = [
        "/",  # Homepage
        "/dynex-large-transactions-monitor/",
        "/how-to-install-wsl2-on-windows-10-11-step-by-step-guide/",
        "/how-to-backup-your-wsl2-instance/",
        "/wsl-file-transfer-guide/",
        "/petoshi-complete-pump-trading-analysis-on-mexc-689-gain/",
        "/blade-complete-pump-trading-analysis-on-mexc-984-gain/",
        "/user/27/",  # Test a user page to verify our canonical fix
    ]
    
    # Run the audit
    results = run_indexability_audit(domain, paths_to_check)
    
    print("\nAudit complete. Check the output above for issues that need fixing.")