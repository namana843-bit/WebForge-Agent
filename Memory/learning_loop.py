import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

class LearningLoop:
    """
    Self-Learning Loop and Auto-Healing module.
    Maintains a database of past failure events, attempts automatic corrective actions 
    (such as selector healing or coordinate fallback), and updates its memory for future tasks.
    """

    def __init__(self, memory_path: str = "Memory/data/learning_memory.json"):
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory = self._load_memory()

    def _load_memory(self) -> Dict[str, Any]:
        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_memory(self):
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LearningLoop] Failed to save memory: {e}")

    def get_learned_solution(self, url: str, action_text: str) -> Optional[str]:
        """Looks up a previously successful healed action for a given context."""
        cleaned_url = self._clean_url(url)
        key = f"{cleaned_url}::{action_text}"
        solution = self.memory.get(key)
        if solution:
            print(f"[LearningLoop] Found learned solution in memory: '{action_text}' -> '{solution}'")
            return solution
        return None

    def record_success(self, url: str, original_action: str, healed_action: str):
        """Records a successful healing outcome to memory."""
        cleaned_url = self._clean_url(url)
        key = f"{cleaned_url}::{original_action}"
        self.memory[key] = healed_action
        self._save_memory()
        print(f"[LearningLoop] Successfully learned and saved: '{original_action}' -> '{healed_action}'")

    def attempt_auto_heal(self, router, page_url: str, action_text: str, error_msg: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to automatically solve the action failure by analyzing the error, 
        running page diagnostics, and executing alternative fallback strategies.
        """
        print(f"[LearningLoop] Initiating self-healing loop for action '{action_text}' (Error: {error_msg})")
        parts = action_text.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Strategy 1: Element Selector Healing
        if cmd == "click" and args:
            # Check if there is an alternative selector based on text fallback
            healed_selector = self._find_healed_selector(router, args)
            if healed_selector and healed_selector != args:
                new_action = f"click {healed_selector}"
                print(f"[LearningLoop] Healed selector found! Retrying action with alternative selector: '{new_action}'")
                res = router.route("click", selector=healed_selector)
                if res and "error" not in res:
                    self.record_success(page_url, action_text, new_action)
                    return res

            # Strategy 2: Fallback to coordinate-click if selector click fails
            coords = self._get_selector_coordinates(router, args)
            if coords:
                x, y = coords.get("x"), coords.get("y")
                print(f"[LearningLoop] Selector click failed but found element coordinates ({x}, {y}). Retrying via coordinate click...")
                # Dispatch coordinate click via evaluation
                js_code = f"""
                (() => {{
                    const el = document.elementFromPoint({x}, {y});
                    if (!el) return {{ error: "No element at coordinates" }};
                    el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
                    return {{ success: true }};
                }})()
                """
                res = router.plugins["bridge"].execute("evaluate", code=js_code)
                if res and "error" not in res:
                    new_action = f"click_coordinates {x} {y}"
                    self.record_success(page_url, action_text, new_action)
                    return res

        # Strategy 3: Input Field Healing
        elif cmd == "fill" and args:
            sub_parts = args.split(" ", 1)
            sel = sub_parts[0] if len(sub_parts) > 0 else ""
            val = sub_parts[1] if len(sub_parts) > 1 else ""
            if sel:
                healed_selector = self._find_healed_selector(router, sel)
                if healed_selector and healed_selector != sel:
                    new_action = f"fill {healed_selector} {val}"
                    print(f"[LearningLoop] Healed input selector found! Retrying fill action: '{new_action}'")
                    res = router.route("fill", selector=healed_selector, value=val)
                    if res and "error" not in res:
                        self.record_success(page_url, action_text, new_action)
                        return res

        # Strategy 4: DOM State Wait Recovery
        print("[LearningLoop] Strategy fallback: Waiting for DOM updates or potential overlays to clear...")
        time.sleep(3.0)
        res = router.route("click", selector=args) if cmd == "click" else None
        if res and "error" not in res:
            self.record_success(page_url, action_text, action_text)
            return res

        print("[LearningLoop] Self-healing attempts completed. Unable to automatically resolve.")
        return None

    def _clean_url(self, url: str) -> str:
        """Helper to normalize URLs so memory matches domain/route structures."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.netloc}{parsed.path}"
        except Exception:
            return url

    def _find_healed_selector(self, router, failed_selector: str) -> Optional[str]:
        """Tries to find matching interactive elements when the original selector fails."""
        # Grab DOM snapshot
        snapshot_res = router.route("snapshot")
        if not isinstance(snapshot_res, dict) or "tree" not in snapshot_res:
            return None

        # Simple text or class name heuristic to locate alternatives
        clean_target = failed_selector.replace("#", "").replace(".", "").lower()
        
        found_ref = None
        def traverse(node):
            nonlocal found_ref
            if found_ref:
                return
            tag = node.get("tag", "")
            text = (node.get("text") or node.get("name") or "").lower()
            ref = node.get("ref", "")
            
            # If the tag matches class/id keyword, or inner text is similar
            if ref and (clean_target in text or clean_target in tag or text in clean_target):
                if node.get("interactive") or tag in ["button", "a", "input"]:
                    found_ref = ref
                    return
            
            for child in node.get("children", []):
                traverse(child)

        traverse(snapshot_res["tree"])
        return found_ref

    def _get_selector_coordinates(self, router, selector: str) -> Optional[Dict[str, int]]:
        """Retrieves pixel coordinates of a selector element for coordinate fallback clicking."""
        snapshot_res = router.route("snapshot")
        if not isinstance(snapshot_res, dict) or "tree" not in snapshot_res:
            return None

        coords = None
        def traverse(node):
            nonlocal coords
            if coords:
                return
            ref = node.get("ref", "")
            if ref == selector or node.get("tag", "") == selector:
                rect = node.get("rect")
                if rect:
                    coords = {
                        "x": rect.get("x", 0) + rect.get("w", 0) // 2,
                        "y": rect.get("y", 0) + rect.get("h", 0) // 2
                    }
                    return
            for child in node.get("children", []):
                traverse(child)

        traverse(snapshot_res["tree"])
        return coords
