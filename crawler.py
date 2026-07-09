#!/usr/bin/env python3
"""Crawler Agent Plugin for recursively scraping and exploring domain websites."""

import time
import json
from urllib.parse import urlparse, urljoin
from pathlib import Path
from plugin_interface import BrowserPlugin

class CrawlerPlugin(BrowserPlugin):
    """Plugin to recursively navigate, discover, and crawl internal domain links."""

    def __init__(self, agent):
        self.agent = agent

    def execute(self, action: str, **kwargs):
        if action == "crawl":
            base_url = kwargs.get("base_url")
            max_pages = int(kwargs.get("max_pages", 10))
            max_depth = int(kwargs.get("max_depth", 2))
            if not base_url:
                return {"error": "base_url is required"}
            return self.crawl(base_url, max_pages, max_depth)
        else:
            return {"error": f"Unknown action: {action}"}

    def crawl(self, base_url: str, max_pages: int = 10, max_depth: int = 2):
        """Crawls starting from base_url, staying inside the same domain."""
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc.lower()
        if not base_domain:
            return {"error": f"Invalid base URL: {base_url}"}

        queue = [(base_url, 0)]  # (url, depth)
        visited = set()
        results = []
        
        print(f"[CrawlerAgent] Starting crawl at {base_url} (domain: {base_domain}, max pages: {max_pages}, max depth: {max_depth})")

        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            
            if url in visited:
                continue
            if depth > max_depth:
                continue
                
            visited.add(url)
            print(f"\n[CrawlerAgent] Crawling ({len(visited)}/{max_pages}) at depth {depth}: {url}")
            
            # Navigate to URL
            nav_res = self.agent.navigate(url)
            if "error" in nav_res:
                print(f"[CrawlerAgent] Failed to navigate to {url}: {nav_res['error']}")
                results.append({"url": url, "depth": depth, "status": "failed", "error": nav_res["error"]})
                continue
                
            # Wait for page to settle
            time.sleep(1.5)
            
            # Extract content and links
            js_code = """
            (() => {
                const links = Array.from(document.querySelectorAll('a')).map(a => a.href);
                const title = document.title;
                const text = document.body ? document.body.innerText.substring(0, 1000) : "";
                return { links, title, text };
            })()
            """
            extract_res = self.agent.bridge.execute("evaluate", code=js_code)
            
            if "error" in extract_res or not extract_res.get("result"):
                results.append({"url": url, "depth": depth, "status": "navigation_success", "extraction": "failed"})
                continue
                
            data = extract_res["result"]
            results.append({
                "url": url,
                "depth": depth,
                "status": "success",
                "title": data.get("title", ""),
                "snippet": data.get("text", "")[:300].strip()
            })
            
            # Queue discovered links
            for link in data.get("links", []):
                absolute_link = urljoin(url, link)
                parsed_link = urlparse(absolute_link)
                
                # Check domain match and HTTP/HTTPS protocol
                if parsed_link.netloc.lower() == base_domain and parsed_link.scheme in ("http", "https"):
                    # Strip fragment identifier
                    clean_url = absolute_link.split("#")[0]
                    if clean_url not in visited and clean_url not in [q[0] for q in queue]:
                        queue.append((clean_url, depth + 1))

        # Save output
        output_dir = Path("data/crawls")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"crawl_{int(time.time())}.json"
        
        report = {
            "base_url": base_url,
            "domain": base_domain,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "total_visited": len(visited),
            "pages": results
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            
        print(f"\n[CrawlerAgent] Completed. Scraped {len(visited)} pages. Saved to {output_file}")
        return {"success": True, "file": str(output_file), "total_visited": len(visited)}
