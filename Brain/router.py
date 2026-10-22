#!/usr/bin/env python3
"""Plugin Router coordinating action dispatching between browser plugins."""

import inspect

# action -> plugin name
ACTION_PLUGINS = {
    "navigate": "bridge",
    "click": "bridge",
    "fill": "bridge",
    "snapshot": "bridge",
    "screenshot": "bridge",
    "scroll": "bridge",
    "understand": "page_agent",
    "desktop_click": "desktop",
    "desktop_write": "desktop",
    "desktop_press": "desktop",
    "desktop_screenshot": "desktop",
    "desktop_move": "desktop",
    "desktop_scroll": "desktop",
    "smart_fill": "form",
    "smart_fill_nl": "form",
    "full_page_screenshot": "visual",
    "element_screenshot": "visual",
    "visual_diff": "visual",
    "annotate_image": "visual",
    "export_data": "exporter",
    "schedule_export": "exporter",
    "crawl": "crawler",
    "start_voice_control": "accessibility",
    "swarm_spawn": "swarm",
    "create_api": "web_to_api",
}


class PluginRouter:
    """Routes execution commands to the appropriate registered browser plugin."""

    def __init__(self):
        self.plugins = {}

    def register_plugin(self, name: str, plugin):
        """Register a browser plugin under a given name."""
        self.plugins[name] = plugin

    def route(self, action: str, **kwargs):
        """Routes the action to the corresponding plugin based on type."""
        plugin = self.plugins.get(ACTION_PLUGINS.get(action))
        if plugin is None:
            return {"error": f"Unknown action: {action}"}

        # Snapshot distinguishes itself from the standard Plugin.execute() call.
        if action == "snapshot":
            return plugin.get_snapshot()

        # Screenshot and understand are called directly on the plugin instance.
        if action in ("screenshot", "understand"):
            method = getattr(plugin, action)
            sig = inspect.signature(method)
            pass_args = {k: v for k, v in kwargs.items() if k in sig.parameters}
            return method(**pass_args)

        # Low-level bridge actions: invoke the dedicated method.
        if ACTION_PLUGINS[action] == "bridge":
            method = getattr(plugin, action)
            sig = inspect.signature(method)
            pass_args = {k: v for k, v in kwargs.items() if k in sig.parameters}
            return method(**pass_args)

        # Everything else routes through the generic Plugin.execute() interface.
        return plugin.execute(action, **kwargs)
