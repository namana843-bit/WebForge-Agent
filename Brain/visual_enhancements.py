#!/usr/bin/env python3
"""Enhanced Visual capabilities: Full-page, Element crop, Visual diffing, and Annotations."""

import time
import os
import json
import base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageFont
from plugin_interface import BrowserPlugin

class VisualEnhancementsPlugin(BrowserPlugin):
    """Plugin implementing enhanced screenshot capturing, comparison, and annotations."""

    def __init__(self, agent):
        self.agent = agent

    def execute(self, action: str, **kwargs):
        try:
            if action == "full_page_screenshot":
                filename = kwargs.get("filename") or f"fullpage_{int(time.time())}.png"
                return self.full_page_screenshot(filename)
                
            elif action == "element_screenshot":
                selector = kwargs.get("selector")
                filename = kwargs.get("filename") or f"element_{int(time.time())}.png"
                if not selector:
                    return {"error": "Selector is required"}
                return self.element_screenshot(selector, filename)
                
            elif action == "visual_diff":
                img1 = kwargs.get("baseline")
                img2 = kwargs.get("current")
                out = kwargs.get("output") or "diff.png"
                if not img1 or not img2:
                    return {"error": "baseline and current image paths required"}
                return self.visual_diff(img1, img2, out)
                
            elif action == "annotate_image":
                img = kwargs.get("image")
                ann_str = kwargs.get("annotations")
                out = kwargs.get("output") or "annotated.png"
                if not img or not ann_str:
                    return {"error": "image and annotations required"}
                annotations = ann_str
                if isinstance(ann_str, str):
                    annotations = json.loads(ann_str)
                return self.annotate_image(img, annotations, out)
                
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": str(e)}

    def full_page_screenshot(self, filename: str):
        """Scrolls step-by-step and stitches screenshots vertically to capture the whole page."""
        if not filename.endswith(".png"):
            filename += ".png"
            
        output_dir = Path("Memory/data/screenshots")
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename

        # Get page scroll metrics
        metrics = self.agent.bridge.execute("evaluate", code="""
        (() => {
            return {
                scrollHeight: document.documentElement.scrollHeight,
                clientHeight: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio || 1
            };
        })()
        """)
        
        if "error" in metrics or "result" in metrics and not metrics["result"]:
            return {"error": f"Failed to get viewport metrics: {metrics.get('error')}"}
            
        res = metrics["result"]
        scroll_height = res["scrollHeight"]
        viewport_height = res["clientHeight"]
        
        # Scroll to top first
        self.agent.bridge.execute("evaluate", code="window.scrollTo(0, 0)")
        time.sleep(0.5)
        
        current_scroll = 0
        images = []
        
        while current_scroll < scroll_height:
            # Capture visible viewport
            temp_name = f"temp_fullpage_{current_scroll}.png"
            snap = self.agent.bridge.screenshot(temp_name)
            if "path" in snap:
                img_path = Path(snap["path"])
                images.append((current_scroll, Image.open(img_path)))
                # Delete temp file
                try: os.remove(img_path)
                except: pass
            else:
                return {"error": f"Failed capturing viewport at scroll: {current_scroll}"}
                
            current_scroll += viewport_height
            if current_scroll < scroll_height:
                self.agent.bridge.execute("evaluate", code=f"window.scrollTo(0, {current_scroll})")
                time.sleep(0.4)
                
        if not images:
            return {"error": "No images captured"}
            
        # Stitch all together
        total_width = images[0][1].width
        # Total stitched height is scroll_height * scale (represented by ratio of captured image to viewport height)
        ratio = images[0][1].height / viewport_height
        total_height = int(scroll_height * ratio)
        
        stitched = Image.new("RGB", (total_width, total_height))
        for scroll_y, img in images:
            y_offset = int(scroll_y * ratio)
            stitched.paste(img, (0, y_offset))
            
        stitched.save(filepath)
        return {"success": True, "path": str(filepath)}

    def element_screenshot(self, selector: str, filename: str):
        """Locates an element, takes a screenshot of the visible screen, and crops it to the element."""
        if not filename.endswith(".png"):
            filename += ".png"
            
        output_dir = Path("Memory/data/screenshots")
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename
        
        # Get bounding box of the element
        escaped_selector = json.dumps(selector)
        js_code = f"""
        (() => {{
            const el = document.querySelector({escaped_selector});
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {{
                x: r.left,
                y: r.top,
                w: r.width,
                h: r.height,
                dpr: window.devicePixelRatio || 1
            }};
        }})()
        """
        rect_res = self.agent.bridge.execute("evaluate", code=js_code)
        if "error" in rect_res or not rect_res.get("result"):
            return {"error": f"Element '{selector}' not found or inaccessible."}
            
        rect = rect_res["result"]
        
        # Take page screenshot
        temp_name = f"temp_el_{int(time.time())}.png"
        snap = self.agent.bridge.screenshot(temp_name)
        if "error" in snap:
            return {"error": f"Page screenshot failed: {snap['error']}"}
            
        page_img = Image.open(snap["path"])
        
        # Crop to element
        dpr = rect["dpr"]
        box = (
            int(rect["x"] * dpr),
            int(rect["y"] * dpr),
            int((rect["x"] + rect["w"]) * dpr),
            int((rect["y"] + rect["h"]) * dpr)
        )
        cropped = page_img.crop(box)
        cropped.save(filepath)
        
        # Cleanup page screenshot
        try: os.remove(snap["path"])
        except: pass
        
        return {"success": True, "path": str(filepath)}

    def visual_diff(self, baseline_path: str, current_path: str, diff_output_path: str):
        """Compares two images and highlights differences."""
        img1 = Image.open(baseline_path).convert("RGB")
        img2 = Image.open(current_path).convert("RGB")
        
        # Resize if different
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
            
        diff = ImageChops.difference(img1, img2)
        
        # Calculate percentage difference
        stat = diff.getbbox()
        diff_pixels = 0
        if stat:
            # Count non-zero pixels
            gray = diff.convert("L")
            non_zero = gray.point(lambda p: 255 if p > 15 else 0).getdata()
            diff_pixels = sum(1 for p in non_zero if p > 0)
            
        total_pixels = img1.width * img1.height
        pct_diff = (diff_pixels / total_pixels) * 100.0
        
        # Generate diff image (overlay red highlight where changed)
        diff_visual = Image.new("RGB", img1.size)
        draw = ImageDraw.Draw(diff_visual)
        
        # Blend baseline and diff
        blended = Image.blend(img1, img2, alpha=0.5)
        # Highlight changes with red overlay
        mask = diff.convert("L").point(lambda p: 255 if p > 15 else 0)
        red_overlay = Image.new("RGB", img1.size, (255, 0, 0))
        blended.paste(red_overlay, (0, 0), mask=mask)
        
        blended.save(diff_output_path)
        return {
            "success": True,
            "percentage_difference": pct_diff,
            "diff_path": diff_output_path
        }

    def annotate_image(self, img_path: str, annotations: list, output_path: str):
        """Draws bounding boxes and text labels on top of an image."""
        img = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        for ann in annotations:
            # bbox should be list [x1, y1, x2, y2]
            bbox = ann.get("bbox")
            label = ann.get("label", "")
            color = ann.get("color", "red")
            
            if bbox and len(bbox) == 4:
                # Draw box
                draw.rectangle(bbox, outline=color, width=3)
                if label:
                    # Draw label background and text
                    draw.rectangle([bbox[0], bbox[1] - 15, bbox[0] + len(label) * 8, bbox[1]], fill=color)
                    draw.text((bbox[0] + 2, bbox[1] - 14), label, fill="white")
                    
        img.save(output_path)
        return {"success": True, "path": output_path}
