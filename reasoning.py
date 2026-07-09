#!/usr/bin/env python3
"""Reasoning Engine planning and routing high-level browser goals."""

import re
import json
import time

class ReasoningEngine:
    """Decomposes tasks using Observe-Think-Decide-Act-Verify-Repeat loop."""

    def __init__(self, router):
        self.router = router

    def observe(self) -> dict:
        """Step 1: Observe - Capture DOM snapshot and current active tab details."""
        print("[ReasoningEngine] [Observe] Fetching page DOM snapshot...")
        snapshot_res = self.router.route("snapshot")
        
        snapshot_preview = ""
        if isinstance(snapshot_res, dict) and "tree" in snapshot_res:
            def format_tree(node, max_lines=45):
                lines = []
                def traverse(n, depth=0):
                    if len(lines) >= max_lines: return
                    tag = n.get("tag", "")
                    text = (n.get("text") or n.get("name") or "")[:40].strip()
                    ref = n.get("ref", "")
                    if tag and (text or ref):
                        ref_str = f" @{ref}" if ref else ""
                        lines.append(f"{'  '*depth}<{tag}{ref_str}>{text}</{tag}>")
                    for child in n.get("children", []):
                        traverse(child, depth+1)
                traverse(node)
                return "\n".join(lines)
            snapshot_preview = format_tree(snapshot_res["tree"])

        return {
            "snapshot_raw": snapshot_res,
            "dom_preview": snapshot_preview
        }

    def think(self, observation: dict, goal: str, history: list) -> str:
        """Step 2: Think - Formulate analysis about goal progress and any failures."""
        print("[ReasoningEngine] [Think] Evaluating goal progress and past action history...")
        prompt = (
            f"Goal: '{goal}'. Action History: {history}\n"
            f"Current DOM State:\n{observation['dom_preview']}\n\n"
            "Analyze if we are making progress or if a previous action failed and we need to replan. "
            "Write a brief thought on what is missing or what needs to be solved next."
        )
        res = self.router.route("understand", prompt=prompt)
        thought = ""
        if isinstance(res, dict) and "result" in res:
            thought = res["result"].strip()
        elif isinstance(res, str):
            thought = res.strip()
        return thought

    def decide(self, thought: str, goal: str, history: list, observation: dict) -> str:
        """Step 3: Decide - Determine the next specific action command to invoke."""
        print("[ReasoningEngine] [Decide] Formulating the next target action...")
        prompt = (
            f"Goal: '{goal}'. Analysis Thought: {thought}. Action History: {history}\n"
            f"Current page DOM:\n{observation['dom_preview']}\n\n"
            "Determine the next single immediate action. Choose from one of the following exact formats:\n"
            "- click <selector> (e.g. 'click @e12' or 'click button.submit')\n"
            "- fill <selector> <text> (e.g. 'fill @e15 Bob')\n"
            "- scroll <y> (e.g. 'scroll 400' or 'scroll -300')\n"
            "- wait\n"
            "- finish\n\n"
            "Provide ONLY the chosen action string."
        )
        res = self.router.route("understand", prompt=prompt)
        action_text = ""
        if isinstance(res, dict) and "result" in res:
            action_text = res["result"].strip()
        elif isinstance(res, str):
            action_text = res.strip()
            
        if not action_text:
            action_text = "wait"
        return action_text

    def act(self, action_text: str) -> dict:
        """Step 4: Act - Execute the chosen action via the plugin router."""
        print(f"[ReasoningEngine] [Act] Executing action command: '{action_text}'")
        parts = action_text.split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "click":
            return self.router.route("click", selector=args)
        elif cmd == "fill":
            sub_parts = args.split(" ", 1)
            sel = sub_parts[0] if len(sub_parts) > 0 else ""
            val = sub_parts[1] if len(sub_parts) > 1 else ""
            return self.router.route("fill", selector=sel, value=val)
        elif cmd == "scroll":
            try: y_val = int(args)
            except: y_val = 400
            return self.router.route("scroll", y=y_val)
        elif cmd == "wait":
            time.sleep(2)
            return {"success": True, "action": "wait"}
        elif cmd == "finish":
            return {"success": True, "action": "finish"}
        else:
            return self.router.route("execute", instruction=action_text)

    def verify(self, action_text: str, result: dict, goal: str) -> bool:
        """Step 5: Verify - Check if the last action succeeded and if the final goal is met."""
        print(f"[ReasoningEngine] [Verify] Evaluating action result: {result}")
        if "error" in result:
            print(f"[ReasoningEngine] Action '{action_text}' failed: {result['error']}. Re-evaluating plan.")
            return False
            
        if action_text.startswith("finish"):
            return True
            
        # Call Page-Agent to check if the main goal is now complete
        prompt = (
            f"Has the goal '{goal}' been successfully and fully achieved? "
            "Answer with exactly 'YES' or 'NO' followed by a short explanation."
        )
        check_res = self.router.route("understand", prompt=prompt)
        is_completed = False
        ans = ""
        if isinstance(check_res, dict) and "result" in check_res:
            ans = str(check_res["result"]).strip().upper()
        elif isinstance(check_res, str):
            ans = check_res.strip().upper()
            
        if ans.startswith("YES"):
            is_completed = True
        return is_completed

    def run_goal(self, goal: str, **kwargs):
        """Orchestrator driving the cognitive loop and repeating steps dynamically."""
        print(f"[ReasoningEngine] Analyzing goal: '{goal}'")
        
        # Detect navigation intent (e.g., "open facebook")
        nav_match = re.search(r'(?i)(?:open|goto|go to|navigate to)\s+([a-zA-Z0-9.\-_]+)', goal)
        remaining_goal = goal
        if nav_match:
            target = nav_match.group(1).strip()
            url = target
            if not url.startswith("http"):
                if "." not in url:
                    url = f"https://www.{url}.com"
                else:
                    url = f"https://{url}"
            
            print(f"[ReasoningEngine] Navigation intent detected to: {url}")
            nav_res = self.router.route("navigate", url=url)
            
            remaining = goal.replace(nav_match.group(0), "").strip()
            if not remaining or remaining.lower() in [target.lower(), "website", "page"]:
                return nav_res
            remaining_goal = remaining
            time.sleep(2)

        max_steps = kwargs.get("max_steps", 5)
        print(f"[ReasoningEngine] Starting Observe-Think-Decide-Act-Verify cognitive loop (max steps: {max_steps})")
        
        action_history = []
        last_result = None
        
        for step in range(1, max_steps + 1):
            print(f"\n--- [ReasoningEngine] Cognitive Loop Cycle {step}/{max_steps} ---")
            
            # 1. Observe
            obs = self.observe()
            
            # 2. Think
            thought = self.think(obs, remaining_goal, action_history)
            print(f"[ReasoningEngine] Thought: {thought}")
            
            # 3. Decide
            action = self.decide(thought, remaining_goal, action_history, obs)
            print(f"[ReasoningEngine] Decided Action: {action}")
            
            # 4. Act
            last_result = self.act(action)
            action_history.append(action)
            
            # 5. Verify & Repeat
            goal_achieved = self.verify(action, last_result, remaining_goal)
            if goal_achieved:
                print(f"[ReasoningEngine] Goal achieved successfully in cycle {step}!")
                return {"status": "success", "step": step, "message": "Goal achieved"}
                
            time.sleep(2)
            
        print("[ReasoningEngine] Reached maximum cognitive steps without confirming goal completion.")
        return {"status": "max_steps_reached", "last_result": last_result}



