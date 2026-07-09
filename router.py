#!/usr/bin/env python3
"""Plugin Router coordinating action dispatching between browser plugins."""

import inspect

class PluginRouter:
    """Routes execution commands to the appropriate registered browser plugin."""

    def __init__(self):
        self.plugins = {}

    def register_plugin(self, name: str, plugin):
        """Register a browser plugin under a given name."""
        self.plugins[name] = plugin

    def route(self, action: str, **kwargs):
        """Routes the action to the corresponding plugin based on type."""
        low_level_actions = ["navigate", "click", "fill", "snapshot", "screenshot", "scroll"]
        desktop_actions = ["desktop_click", "desktop_write", "desktop_press", "desktop_screenshot", "desktop_move", "desktop_scroll"]
        visual_actions = ["full_page_screenshot", "element_screenshot", "visual_diff", "annotate_image"]
        
        if action in low_level_actions:
            if "bridge" in self.plugins:
                plugin = self.plugins["bridge"]
                if action == "snapshot":
                    return plugin.get_snapshot()
                elif action == "screenshot":
                    return plugin.screenshot(kwargs.get("filename"))
                else:
                    method = getattr(plugin, action)
                    sig = inspect.signature(method)
                    pass_args = {k: v for k, v in kwargs.items() if k in sig.parameters}
                    return method(**pass_args)
            else:
                return {"error": "Bridge plugin not registered for low-level actions"}

        elif action in desktop_actions:
            if "desktop" in self.plugins:
                plugin = self.plugins["desktop"]
                method = getattr(plugin, "execute")
                return method(action, **kwargs)
            else:
                return {"error": "Desktop plugin not registered"}

        elif action in ["smart_fill", "smart_fill_nl"]:
            if "form" in self.plugins:
                plugin = self.plugins["form"]
                return plugin.execute(action, **kwargs)
            else:
                return {"error": "Form plugin not registered"}

        elif action in visual_actions:
            if "visual" in self.plugins:
                plugin = self.plugins["visual"]
                return plugin.execute(action, **kwargs)
            else:
                return {"error": "Visual plugin not registered"}

        elif action in ["export_data", "schedule_export"]:
            if "exporter" in self.plugins:
                plugin = self.plugins["exporter"]
                return plugin.execute(action, **kwargs)
            else:
                return {"error": "Exporter plugin not registered"}

        elif action == "crawl":
            if "crawler" in self.plugins:
                plugin = self.plugins["crawler"]
                return plugin.execute(action, **kwargs)
            else:
                return {"error": "Crawler plugin not registered"}

        elif action == "start_voice_control":
            if "accessibility" in self.plugins:
                plugin = self.plugins["accessibility"]
                return plugin.execute(action, **kwargs)
            else:
                return {"error": "Accessibility plugin not registered"}

        elif action in ["execute", "understand"]:
            if "page_agent" in self.plugins:
                plugin = self.plugins["page_agent"]
                method = getattr(plugin, action)
                sig = inspect.signature(method)
                pass_args = {k: v for k, v in kwargs.items() if k in sig.parameters}
                return method(**pass_args)
            else:
                return {"error": "Page-Agent plugin not registered for high-level intelligent actions"}

        return {"error": f"Unknown action: {action}"}
